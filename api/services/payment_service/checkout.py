"""Client payments: the price breakdown, starting a checkout and confirming it."""

from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from config.config import settings
from services import payment_service, platform_settings
from services.db import Jsonb, connection, execute, fetch_all, fetch_one

from .earnings import _test_money
from .gateways import PaymentError, _money, mode

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- client payments

PAYMENT_COLUMNS = """
  id::text, engagement_id::text, tx_ref, gateway, amount::float, currency, price::float, vat_rate::float,
  provider_vat::float, commission_percent::float, commission_amount::float, commission_vat::float,
  provider_amount::float, provider_vat_number, status, checkout_url, gateway_reference, payment_method,
  gateway_fee::float, created_at, updated_at, verified_at, is_test, unapplied_reason, refunded_amount::float
"""


def breakdown(price, provider_vat_registered: bool) -> dict:
    """Every amount in a payment, from the provider's agreed price (VAT Proclamation 1341/2024):
      client pays    price + provider VAT (only if the provider is VAT-registered)
      our commission price x commission %, plus VAT on it when we are VAT-registered
      provider gets  price - commission - VAT on commission + the provider VAT they collected (they file it)
    """
    price = _money(price)
    rate = Decimal(str(platform_settings.get("vat_rate_percent")))
    pct = Decimal(str(platform_settings.get("commission_percent")))
    provider_vat = _money(price * rate / 100) if provider_vat_registered else Decimal("0.00")
    commission = _money(price * pct / 100)
    commission_vat = _money(commission * rate / 100) if platform_settings.get("platform_vat_registered") else Decimal("0.00")
    return {
        "price": price, "vat_rate": rate, "provider_vat": provider_vat, "total": price + provider_vat,
        "commission_percent": pct, "commission": commission, "commission_vat": commission_vat,
        "provider_amount": price - commission - commission_vat + provider_vat,
    }


def latest_for(engagement_id: str) -> dict | None:
    return fetch_one(f"select {PAYMENT_COLUMNS} from payments where engagement_id = %s order by created_at desc limit 1",
                     (engagement_id,))


def get(tx_ref: str) -> dict | None:
    return fetch_one(f"select {PAYMENT_COLUMNS}, payer_user_id::text from payments where tx_ref = %s", (tx_ref,))


def start(engagement_id: str, *, user) -> dict:
    """Checkout for a delivered job. Returns {tx_ref, checkout_url}."""
    from services import provider_service

    eng = provider_service.get_engagement(engagement_id)
    if not eng or eng["client_user_id"] != user.id:
        raise PaymentError("Request not found", 404)
    if eng["payment_status"] == "paid":
        raise PaymentError("This job is already paid", 409)
    if eng["status"] != "completed" or eng.get("client_confirmed_at"):
        who = eng.get("provider_name") or "The provider"
        raise PaymentError(f"You pay once {who} has delivered the work", 409)
    if not eng.get("agreed_price"):
        raise PaymentError("This job has no price yet", 409)

    reuse = platform_settings.get_int("checkout_reuse_minutes")
    # The latest older unfinished checkout may have been paid after all: settle it before opening a new one.
    # Only that one is asked about, so a slow gateway can't make this wait once per old checkout; older ones
    # are still settled by the webhook or a staff check, and a late payment on them is flagged for a refund.
    old = fetch_one("select tx_ref from payments where engagement_id = %s and status = 'pending' "
                    "and created_at <= now() - make_interval(mins => %s) order by created_at desc limit 1",
                    (engagement_id, reuse))
    if old and payment_service.confirm(old["tx_ref"])["status"] == "success":
        raise PaymentError("This job is already paid", 409)

    prov = fetch_one("select vat_registered, vat_number from providers where id = %s", (eng["provider_id"],)) or {}
    b = breakdown(eng["agreed_price"], bool(prov.get("vat_registered")))
    amount = b["total"]
    tx_ref = f"cn-{engagement_id[:8]}-{secrets.token_hex(5)}"
    gw = payment_service.gateway()
    with connection() as conn, conn.transaction():
        # One conditional update both checks the hire and locks it: a staff cancel or a second tab running at
        # the same moment either happens before (and this refuses) or waits until this checkout is recorded
        locked = conn.execute(
            "update engagements set payment_status = 'pending', updated_at = now() "
            "where id = %s and status = 'completed' and client_confirmed_at is null "
            "and payment_status not in ('paid', 'refunded') returning id",
            (engagement_id,),
        ).fetchone()
        if not locked:
            raise PaymentError("This job can't be paid now. It may be paid already or no longer open.", 409)
        # Reuse a fresh checkout instead of creating a second payment for the same job
        pending = conn.execute(
            "select tx_ref, checkout_url from payments where engagement_id = %s and status = 'pending' "
            "and created_at > now() - make_interval(mins => %s) order by created_at desc limit 1",
            (engagement_id, reuse),
        ).fetchone()
        if pending and pending["checkout_url"]:
            return {"tx_ref": pending["tx_ref"], "checkout_url": pending["checkout_url"]}
        if pending:
            raise PaymentError("Your checkout is opening. Wait a moment and try again.", 409)
        # The amounts are frozen here, so the receipt never changes if rates change later
        conn.execute(
            """
            insert into payments (engagement_id, payer_user_id, tx_ref, gateway, amount, price, vat_rate, provider_vat,
              commission_percent, commission_amount, commission_vat, provider_amount, provider_vat_number, is_test)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (engagement_id, user.id, tx_ref, gw.name, amount, b["price"], b["vat_rate"], b["provider_vat"],
             b["commission_percent"], b["commission"], b["commission_vat"], b["provider_amount"],
             prov.get("vat_number") if prov.get("vat_registered") else None, _test_money()),
        )
    names = (eng.get("client_name") or user.fullname or "").split()
    try:
        url = gw.initialize(
            tx_ref=tx_ref, amount=amount, email=user.email, first_name=names[0] if names else "Client",
            last_name=" ".join(names[1:]), phone=eng.get("client_phone"),
            return_url=f"{settings.web_base_url}/account/requests?payment={tx_ref}",
            callback_url=f"{settings.api_public_url}/api/v1/payments/chapa/callback",
            title="Compliance Nav", reason=f"{eng['title']} by {eng['provider_name']}",
        )
    except PaymentError:
        execute("update payments set status = 'failed', updated_at = now() where tx_ref = %s", (tx_ref,))
        execute("update engagements set payment_status = 'unpaid' where id = %s and payment_status = 'pending'",
                (engagement_id,))
        raise
    execute("update payments set checkout_url = %s where tx_ref = %s", (url, tx_ref))
    return {"tx_ref": tx_ref, "checkout_url": url}


def confirm(tx_ref: str) -> dict:
    """Ask the gateway what happened and record it. Safe to call many times (redirect, webhook, polling)."""
    from services import provider_service

    payment = payment_service.get(tx_ref)
    if not payment:
        raise PaymentError("Payment not found", 404)
    if payment["status"] in ("success", "failed", "cancelled"):
        return payment
    result = payment_service.gateway_named(payment["gateway"]).verify(tx_ref)
    status = result["status"]
    if status == "success":
        # The gateway must confirm the exact amount and currency we asked for
        try:
            amount_ok = _money(result.get("amount")) == _money(payment["amount"])
        except Exception:
            amount_ok = False
        if not amount_ok or (result.get("currency") or "ETB").upper() != payment["currency"]:
            log.error("Payment %s amount/currency mismatch: %s", tx_ref, result)
            status = "failed"
    if status == "pending":
        return payment
    # Chapa says whether the payment ran with a test key; test money never becomes withdrawable when live
    raw = result.get("raw") if isinstance(result.get("raw"), dict) else {}
    test_run = payment["gateway"] == "simulated" or str(raw.get("mode", "")).lower() == "test"
    unapplied = None
    with connection() as conn, conn.transaction():
        updated = conn.execute(
            """
            update payments set status = %s, gateway_reference = %s, payment_method = %s, gateway_fee = %s,
              raw = coalesce(raw, '{}'::jsonb) || %s, verified_at = now(), updated_at = now(), is_test = is_test or %s
            where tx_ref = %s and status = 'pending' returning id, is_test
            """,
            (status, result.get("reference"), result.get("method"),
             _money(result["fee"]) if result.get("fee") not in (None, "") else None,
             Jsonb({"verify": result.get("raw")}), test_run, tx_ref),
        ).fetchone()
        if updated and status == "success":
            # Paying is the client's confirmation: the job closes and the provider's share is credited once.
            # The job row is the guard: only the first successful payment of an open job moves it to paid.
            eng_row = conn.execute(
                "update engagements set payment_status = 'paid', paid_at = now(), "
                "client_confirmed_at = coalesce(client_confirmed_at, now()), updated_at = now() "
                "where id = %s and payment_status in ('unpaid', 'pending', 'failed') and status <> 'cancelled' "
                "returning provider_id::text",
                (payment["engagement_id"],),
            ).fetchone()
            if eng_row:
                conn.execute(
                    """
                    insert into provider_ledger (provider_id, kind, amount, engagement_id, payment_id, note, is_test)
                    values (%s, 'earning', %s, %s, %s, %s, %s)
                    on conflict do nothing
                    """,
                    (eng_row["provider_id"], payment["provider_amount"], payment["engagement_id"], updated["id"],
                     f"{payment['commission_percent']:g}% platform commission and VAT on it deducted", updated["is_test"]),
                )
            else:
                # Already paid through another checkout, or the job was cancelled: keep the money aside for a refund
                state = conn.execute("select status, payment_status from engagements where id = %s",
                                     (payment["engagement_id"],)).fetchone() or {}
                unapplied = "job_closed" if state.get("status") == "cancelled" else "duplicate"
                conn.execute("update payments set unapplied_reason = %s where id = %s", (unapplied, updated["id"]))
                conn.execute("update engagements set refund_needed = true, refund_flagged_at = coalesce(refund_flagged_at, now()), "
                             "refund_flagged_by = coalesce(refund_flagged_by, 'payments') where id = %s",
                             (payment["engagement_id"],))
                provider_service._event(
                    conn, payment["engagement_id"], "refund_needed", who="system",
                    note=f"Payment {tx_ref} of {_money(payment['amount']):,.2f} ETB arrived after the job was "
                         f"{'cancelled' if unapplied == 'job_closed' else 'already paid'}. Not credited to the "
                         "provider; it must be refunded (Payments, Needs refund).")
        elif updated:
            conn.execute("update engagements set payment_status = 'unpaid', updated_at = now() "
                         "where id = %s and payment_status = 'pending'", (payment["engagement_id"],))
    if unapplied:
        log.warning("Payment %s received for a job that was %s: flagged for a refund", tx_ref,
                    "cancelled" if unapplied == "job_closed" else "already paid")
        eng = provider_service.get_engagement(payment["engagement_id"])
        if eng:
            provider_service._tell(eng, "client", f"We received an extra payment of {payment['amount']:,.2f} ETB",
                                   f"Receipt {tx_ref}. This job was already "
                                   f"{'cancelled' if unapplied == 'job_closed' else 'paid'}, so our team will refund it.")
        return payment_service.get(tx_ref)
    if updated and status == "success":
        eng = provider_service.get_engagement(payment["engagement_id"])
        provider_service.recompute(eng["provider_id"])
        amount = f"{payment['amount']:,.0f} ETB"
        first = (eng["client_name"] or "The client").split()[0]
        provider_service._tell(eng, "provider", f"{first} paid {amount} for {eng['title']}",
                               f"{payment['provider_amount']:,.2f} ETB was added to your earnings "
                               f"({payment['commission_percent']:g}% platform commission). The job is closed.")
        if not fetch_one("select payout_account_enc from providers where id = %s", (eng["provider_id"],))["payout_account_enc"]:
            provider_service._tell(eng, "provider", "Add your bank account to withdraw your earnings",
                                   "Earnings, under your provider profile.")
        provider_service._tell(eng, "client", f"Payment received: {amount}",
                               f"Receipt {tx_ref}. {eng['title']} is closed. You can now review {eng['provider_name']}.")
    return payment_service.get(tx_ref)


def check_pending_payments(min_age_minutes: int = 10, max_age_days: int = 3) -> dict:
    """
    Settle checkouts whose webhook never arrived: ask the gateway through confirm(), exactly as the webhook
    would, so a paid one closes the hire and credits the provider once (confirm only records a payment that
    is still pending, so a webhook at the same moment can't count it twice).
    A checkout still pending after max_age_days gets one last check, then is marked cancelled (abandoned).
    Runs every 15 minutes.
    """
    rows = fetch_all(
        "select tx_ref, created_at < now() - make_interval(days => %s) as too_old from payments "
        "where status = 'pending' and created_at < now() - make_interval(mins => %s) order by created_at limit 200",
        (max_age_days, min_age_minutes),
    )
    counts = {"checked": 0, "success": 0, "failed": 0, "abandoned": 0, "errors": 0}
    for row in rows:
        try:
            after = payment_service.confirm(row["tx_ref"])
        except Exception:
            counts["errors"] += 1
            log.exception("Automatic check of payment %s failed", row["tx_ref"])
            continue
        counts["checked"] += 1
        if after["status"] in ("success", "failed"):
            counts[after["status"]] += 1
        elif after["status"] == "pending" and row["too_old"]:
            with connection() as conn, conn.transaction():
                # Conditional, so a payment confirmed meanwhile is never cancelled
                gone = conn.execute(
                    "update payments set status = 'cancelled', raw = coalesce(raw, '{}'::jsonb) || %s, updated_at = now() "
                    "where tx_ref = %s and status = 'pending' returning engagement_id",
                    (Jsonb({"abandoned": True}), row["tx_ref"]),
                ).fetchone()
                if gone:
                    counts["abandoned"] += 1
                    conn.execute(
                        "update engagements set payment_status = 'unpaid', updated_at = now() where id = %s "
                        "and payment_status = 'pending' "
                        "and not exists (select 1 from payments where engagement_id = %s and status = 'pending')",
                        (gone["engagement_id"], gone["engagement_id"]),
                    )
    return counts


def simulate(tx_ref: str, *, user, outcome: str) -> dict:
    """The test checkout's Pay / Fail buttons. Only in simulated mode, only by the payer."""
    if mode() != "simulated":
        raise PaymentError("Test payments are off", 404)
    payment = payment_service.get(tx_ref)
    if not payment or payment["payer_user_id"] != user.id or payment["gateway"] != "simulated":
        raise PaymentError("Payment not found", 404)
    if outcome not in ("success", "failed"):
        raise PaymentError("Unknown outcome")
    execute("update payments set raw = coalesce(raw, '{}'::jsonb) || %s where tx_ref = %s and status = 'pending'",
            (Jsonb({"simulated_outcome": outcome}), tx_ref))
    return payment_service.confirm(tx_ref)


def checkout_view(tx_ref: str, *, user) -> dict:
    """What the test checkout page shows."""
    from services import provider_service

    payment = payment_service.get(tx_ref)
    if not payment or payment["payer_user_id"] != user.id:
        raise PaymentError("Payment not found", 404)
    if payment["gateway"] != "simulated":
        # A real payment never goes through the test page
        raise PaymentError("This is a real payment, not a test checkout. Pay it on the Chapa page instead.", 409)
    eng = provider_service.get_engagement(payment["engagement_id"])
    return {**{k: payment[k] for k in ("tx_ref", "amount", "currency", "status", "gateway")},
            "title": eng["title"], "provider_name": eng["provider_name"]}
