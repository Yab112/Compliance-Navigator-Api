"""Clients pay the platform; providers withdraw their earnings.

Flow: the provider delivers and that requests payment -> the client pays the agreed price to our
account -> the job closes and the provider's share (price minus commission) is credited to their
earnings balance (provider_ledger) -> the provider requests a payout -> staff approve -> we send it
to the provider's own bank account (Chapa transfer; simulated in test mode) -> payout history.

Gateways sit behind one small interface, so another provider (YaGout, Telebirr) can be added:
  banks()                 banks a provider can be paid into
  initialize(...)         start a checkout, returns the URL to send the client to
  verify(tx_ref)          ask the gateway what really happened (never trust the redirect)
  transfer(...)           send a payout to a bank account
  verify_transfer(ref)    ask whether a payout arrived
  refund(...)             give a client money back (all or part of a payment)
  verify_refund(ref_id)   ask whether a refund reached the client

Money safety rules (see tests/test_money_safety.py):
  - a payout is claimed with a conditional update, so only one approval ever sends it
  - a payout goes to the account it was requested with, stored encrypted on the payout row
  - a transfer or refund error that does not prove the money stayed is marked "needs checking",
    and nothing is released until the gateway confirms it failed
  - money from test checkouts never counts as withdrawable once payments are live
  - a second successful payment for the same job is never credited; it is flagged for a refund

PAYMENTS_MODE: off | simulated (a local test checkout, no money moves) | chapa
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from decimal import ROUND_HALF_UP, Decimal

import httpx

from config.config import settings
from services import notifications, platform_settings
from services.db import Jsonb, connection, execute, fetch_all, fetch_one

log = logging.getLogger(__name__)

PAYABLE = ("accepted", "in_progress", "completed")


class PaymentError(Exception):
    """
    uncertain: the gateway may have done it anyway (timeout, network error, server error), so the
    caller must not assume the money stayed where it was.
    """

    def __init__(self, message: str, status_code: int = 400, *, uncertain: bool = False,
                 gateway_status: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.uncertain = uncertain
        self.gateway_status = gateway_status  # the HTTP status the gateway itself answered with


def mode() -> str:
    return (settings.payments_mode or "off").lower()


def enabled() -> bool:
    return mode() in ("simulated", "chapa")


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- gateways


class SimulatedGateway:
    """Behaves like a gateway without moving money: the checkout is a local test page."""

    name = "simulated"
    BANKS = [
        {"code": "sim-cbe", "name": "Commercial Bank of Ethiopia"},
        {"code": "sim-awash", "name": "Awash Bank"},
        {"code": "sim-dashen", "name": "Dashen Bank"},
        {"code": "sim-abyssinia", "name": "Bank of Abyssinia"},
        {"code": "sim-telebirr", "name": "telebirr"},
    ]

    def banks(self) -> list[dict]:
        return self.BANKS

    def transfer(self, *, account_name: str, account_number: str, bank_code: str, amount: Decimal, reference: str) -> dict:
        return {"status": "paid", "reference": f"SIMTR-{reference[-8:].upper()}"}

    def verify_transfer(self, reference: str) -> str:
        return "paid"

    def refund(self, *, tx_ref: str, amount: Decimal, reason: str, reference: str) -> dict:
        return {"status": "refunded", "ref_id": f"SIMRF-{reference[-8:].upper()}"}

    def verify_refund(self, ref_id: str) -> str:
        return "refunded"

    def initialize(self, *, tx_ref: str, **_) -> str:
        return f"{settings.web_base_url}/pay/test/{tx_ref}"

    def verify(self, tx_ref: str) -> dict:
        row = fetch_one("select raw, amount, currency from payments where tx_ref = %s", (tx_ref,)) or {}
        outcome = (row.get("raw") or {}).get("simulated_outcome")
        return {"status": outcome or "pending", "amount": row.get("amount"), "currency": row.get("currency"),
                "reference": f"SIM-{tx_ref[-8:].upper()}", "method": "test", "fee": None, "raw": {"simulated": True}}


def _record(data, reference: str) -> dict:
    """Chapa returns one record, or (for transfers) a list of them; pick the one for our reference."""
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
        mine = [r for r in rows if reference in (r.get("reference"), r.get("tx_ref"), r.get("ref_id"))]
        # Never fall back to another record: its status says nothing about our transfer or refund
        return mine[0] if mine else {}
    return data if isinstance(data, dict) else {}


class ChapaGateway:
    name = "chapa"

    def __init__(self) -> None:
        if not settings.chapa_secret_key:
            raise PaymentError("Payments are not set up yet (CHAPA_SECRET_KEY is missing)", 503)
        self.base = settings.chapa_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.chapa_secret_key}", "Content-Type": "application/json"}

    def _call(self, method: str, path: str, json: dict | None = None, data: dict | None = None) -> dict:
        headers = self.headers if data is None else {"Authorization": self.headers["Authorization"]}
        try:
            r = httpx.request(method, f"{self.base}{path}", headers=headers, json=json, data=data, timeout=20)
        except httpx.HTTPError as exc:
            # A timeout can come after Chapa already accepted the request
            log.warning("Chapa unreachable: %s", exc)
            raise PaymentError("The payment service is not reachable right now. Please try again.", 502,
                               uncertain=True) from exc
        try:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        except ValueError:
            body = {}
        if r.status_code >= 400 or str(body.get("status", "")).lower() == "failed":
            message = body.get("message")
            if isinstance(message, dict):
                message = "; ".join(f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in message.items())
            log.warning("Chapa %s %s -> %s %s", method, path, r.status_code, message)
            # A 5xx says nothing about whether the request was carried out; a 4xx is a clear refusal
            raise PaymentError(f"Payment service: {message or 'request failed'}", 502, uncertain=r.status_code >= 500,
                               gateway_status=r.status_code)
        return body

    def banks(self) -> list[dict]:
        data = self._call("GET", "/banks").get("data") or []
        return [{"code": str(b.get("id")), "name": b.get("name")} for b in data if b.get("id") is not None]

    def transfer(self, *, account_name: str, account_number: str, bank_code: str, amount: Decimal, reference: str) -> dict:
        body = self._call("POST", "/transfers", {
            "account_name": account_name, "account_number": account_number, "amount": str(amount),
            "currency": "ETB", "reference": reference, "bank_code": int(bank_code) if str(bank_code).isdigit() else bank_code,
        })
        # Chapa queues transfers under our reference; verify_transfer(reference) says when they land
        log.info("Chapa transfer %s queued: %s", reference, body.get("message"))
        return {"status": "approved", "reference": reference}

    def verify_transfer(self, reference: str) -> str:
        """paid | failed | approved (still on its way, or Chapa unreachable) | missing (Chapa has no such transfer)."""
        try:
            body = self._call("GET", f"/transfers/verify/{reference}")
        except PaymentError as exc:
            # Only a clear "not found" means Chapa has no such transfer; a rejected key, a bad request or a
            # rate limit says nothing about whether the money went out
            not_found = exc.gateway_status == 404 or "not found" in str(exc).lower()
            return "missing" if not_found and not exc.uncertain else "approved"
        data = _record(body.get("data"), reference)
        status = str(data.get("status", "")).lower()
        test_key = (settings.chapa_secret_key or "").startswith("CHASECK_TEST")
        if not status and test_key and "test mode" in str(body.get("message", "")).lower():
            # Chapa's test mode accepts transfers but never settles them and returns an empty record, so a
            # test payout would wait forever. Test keys can't move real money; treat it as delivered.
            log.info("Chapa test mode transfer %s has no status; recording it as paid", reference)
            return "paid"
        return "paid" if status == "success" else "failed" if status in ("failed", "cancelled", "reversed") else "approved"

    def refund(self, *, tx_ref: str, amount: Decimal, reason: str, reference: str) -> dict:
        """POST /v1/refund/{tx_ref} (form fields reason, amount, reference). Chapa's own fees are not refunded."""
        body = self._call("POST", f"/refund/{tx_ref}", data={
            "reason": reason[:200], "amount": str(amount), "reference": reference,
            "meta[source]": "compliance-navigator",
        })
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        ref_id = data.get("ref_id") or body.get("ref_id") or data.get("reference")
        status = str(data.get("status", "")).lower()
        return {"status": "refunded" if status == "refunded" else "processing", "ref_id": ref_id}

    def verify_refund(self, ref_id: str) -> str:
        """refunded | failed (reversed: the money came back to our Chapa balance) | processing."""
        try:
            data = _record(self._call("GET", f"/refund/{ref_id}/verify").get("data"), ref_id)
        except PaymentError:
            return "processing"
        status = str(data.get("status", "")).lower()
        return "refunded" if status == "refunded" else "failed" if status in ("reversed", "failed") else "processing"

    def initialize(self, *, tx_ref: str, amount: Decimal, email: str | None, first_name: str, last_name: str,
                   phone: str | None, return_url: str, callback_url: str, title: str, reason: str) -> str:
        payload = {
            "amount": str(amount), "currency": "ETB", "tx_ref": tx_ref, "first_name": first_name or "Client",
            "last_name": last_name or "", "return_url": return_url, "callback_url": callback_url,
            "customization": {"title": title[:16], "description": reason[:50]},
            "meta": {"payment_reason": reason[:100]},
        }
        if email:
            payload["email"] = email
        if phone and re.fullmatch(r"0[79]\d{8}", phone):
            payload["phone_number"] = phone
        try:
            body = self._call("POST", "/transaction/initialize", payload)
        except PaymentError as exc:
            # Chapa rejects some valid addresses (e.g. @example.com); the email is optional, so pay without it
            if "email" not in str(exc).lower() or "email" not in payload:
                raise
            payload.pop("email")
            body = self._call("POST", "/transaction/initialize", payload)
        url = (body.get("data") or {}).get("checkout_url")
        if not url:
            raise PaymentError("The payment service did not return a checkout page", 502)
        return url

    def verify(self, tx_ref: str) -> dict:
        try:
            data = self._call("GET", f"/transaction/verify/{tx_ref}").get("data") or {}
        except PaymentError:
            return {"status": "pending", "raw": None}
        status = str(data.get("status", "pending")).lower()
        return {"status": "success" if status == "success" else "failed" if status in ("failed", "cancelled") else "pending",
                "amount": data.get("amount"), "currency": data.get("currency"), "reference": data.get("reference"),
                "method": data.get("method") or data.get("payment_method"), "fee": data.get("charge"), "raw": data}


def gateway():
    if mode() == "chapa":
        return ChapaGateway()
    if mode() == "simulated":
        return SimulatedGateway()
    raise PaymentError("Online payment is turned off", 503)


def gateway_named(name: str):
    """The gateway a payment was made through (a test payment stays simulated after going live)."""
    return SimulatedGateway() if name == "simulated" else ChapaGateway()


def webhook_signature_ok(raw_body: bytes, headers: dict) -> bool:
    """Chapa signs either the payload or the secret itself with HMAC SHA256; accept a valid one."""
    secret = (settings.chapa_webhook_secret or "").encode()
    if not secret:
        return False
    payload_sig = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    secret_sig = hmac.new(secret, secret, hashlib.sha256).hexdigest()
    sent = [headers.get("x-chapa-signature"), headers.get("chapa-signature")]
    return any(s and (hmac.compare_digest(s, payload_sig) or hmac.compare_digest(s, secret_sig)) for s in sent)


# ---------------------------------------------------------------- provider payout account


def banks() -> list[dict]:
    return gateway().banks()


def _waiting_payouts(provider_id: str) -> int:
    return fetch_one("select count(*) as c from payouts where provider_id = %s and status in ('requested', 'approved')",
                     (provider_id,))["c"]


def payout_view(provider: dict) -> dict:
    verified = provider.get("verified_name")
    account_name = provider.get("payout_account_name")
    return {
        "ready": bool(provider.get("payout_ready")),
        "bank_name": provider.get("payout_bank_name"),
        "account_name": account_name,
        "account_last4": provider.get("payout_account_last4"),
        "set_at": provider.get("payout_set_at"),
        "commission_percent": platform_settings.get("commission_percent"),
        "mode": mode(),
        # The holder name must match the name on the provider's verified ID (or their company's name)
        "verified_name": verified,
        "name_matches": None if not account_name else names_match(
            account_name, verified, provider.get("legal_name"), None if verified else provider.get("display_name")),
        # The account can't change while a payout is on its way to it
        "locked": bool(provider.get("id")) and _waiting_payouts(provider["id"]) > 0,
    }


def set_payout(user_id: str, *, bank_code: str, account_number: str, account_name: str) -> dict:
    """Where the provider's withdrawals are sent. Only the last 4 digits are ever shown again."""
    from core.crypto import encrypt
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    if provider["status"] != "approved":
        raise PaymentError("Your profile must be approved before you can receive payouts", 403)
    account_number = re.sub(r"\s", "", account_number)
    if not re.fullmatch(r"\d{6,20}", account_number):
        raise PaymentError("Enter the account number using digits only")
    account_name = re.sub(r"\s+", " ", account_name).strip()
    if len(account_name) < 2:
        raise PaymentError("Enter the account holder's name exactly as the bank has it")
    bank = next((b for b in gateway().banks() if b["code"] == str(bank_code)), None)
    if not bank:
        raise PaymentError("Choose your bank from the list")
    # Money already asked for goes to the account it was asked for; changing it now would confuse that
    if _waiting_payouts(provider["id"]):
        raise PaymentError("You have a payout on its way. You can change your bank account once it is paid or refused.", 409)
    execute(
        """
        update providers set payout_account_enc = %s, payout_bank_code = %s, payout_bank_name = %s,
          payout_account_name = %s, payout_account_last4 = %s, payout_set_at = now(), updated_at = now()
        where id = %s
        """,
        (encrypt(account_number), str(bank_code), bank["name"], account_name, account_number[-4:], provider["id"]),
    )
    log.info("Payout account changed for provider %s (%s ••••%s)", provider["id"], bank["name"], account_number[-4:])
    # A security notice: if someone else changed it, the owner finds out at once
    title = "Your payout bank account was changed" if provider.get("payout_account_last4") else "Payout bank account added"
    notifications.notify([user_id], kind="payout", title=title,
                         body=f"{bank['name']} ••••{account_number[-4:]} in the name of {account_name}. "
                              "If this wasn't you, change your password and contact support.",
                         link="/me/provider?tab=earnings")
    return payout_view(provider_service.get_for_user(user_id))


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
    # Older unfinished checkouts may have been paid after all: settle them before opening a new one
    for old in fetch_all("select tx_ref from payments where engagement_id = %s and status = 'pending' "
                         "and created_at <= now() - make_interval(mins => %s)", (engagement_id, reuse)):
        if confirm(old["tx_ref"])["status"] == "success":
            raise PaymentError("This job is already paid", 409)

    prov = fetch_one("select vat_registered, vat_number from providers where id = %s", (eng["provider_id"],)) or {}
    b = breakdown(eng["agreed_price"], bool(prov.get("vat_registered")))
    amount = b["total"]
    tx_ref = f"cn-{engagement_id[:8]}-{secrets.token_hex(5)}"
    gw = gateway()
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

    payment = get(tx_ref)
    if not payment:
        raise PaymentError("Payment not found", 404)
    if payment["status"] in ("success", "failed", "cancelled"):
        return payment
    result = gateway_named(payment["gateway"]).verify(tx_ref)
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
        return get(tx_ref)
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
    return get(tx_ref)


def simulate(tx_ref: str, *, user, outcome: str) -> dict:
    """The test checkout's Pay / Fail buttons. Only in simulated mode, only by the payer."""
    if mode() != "simulated":
        raise PaymentError("Test payments are off", 404)
    payment = get(tx_ref)
    if not payment or payment["payer_user_id"] != user.id or payment["gateway"] != "simulated":
        raise PaymentError("Payment not found", 404)
    if outcome not in ("success", "failed"):
        raise PaymentError("Unknown outcome")
    execute("update payments set raw = coalesce(raw, '{}'::jsonb) || %s where tx_ref = %s and status = 'pending'",
            (Jsonb({"simulated_outcome": outcome}), tx_ref))
    return confirm(tx_ref)


def checkout_view(tx_ref: str, *, user) -> dict:
    """What the test checkout page shows."""
    from services import provider_service

    payment = get(tx_ref)
    if not payment or payment["payer_user_id"] != user.id:
        raise PaymentError("Payment not found", 404)
    eng = provider_service.get_engagement(payment["engagement_id"])
    return {**{k: payment[k] for k in ("tx_ref", "amount", "currency", "status", "gateway")},
            "title": eng["title"], "provider_name": eng["provider_name"]}


# ---------------------------------------------------------------- staff

ADMIN_PAYMENT_SELECT = """
  select p.tx_ref, p.gateway, p.amount::float, p.currency, p.price::float, p.provider_vat::float,
         p.commission_amount::float, p.commission_vat::float, p.provider_amount::float, p.gateway_fee::float,
         p.status, p.payment_method, p.gateway_reference, p.created_at, p.verified_at, p.is_test, p.unapplied_reason,
         p.refunded_amount::float, (p.amount - p.refunded_amount)::float as refundable,
         e.id::text as engagement_id, e.title, e.client_name, e.refund_needed, e.payment_status as hire_payment_status,
         pr.display_name as provider_name, pr.slug as provider_slug,
         (select count(*) from refunds r where r.payment_id = p.id and r.status not in ('failed', 'refunded'))
           as refunds_open
  from payments p join engagements e on e.id = p.engagement_id left join providers pr on pr.id = e.provider_id
"""


def _admin_filters(status: str | None, q: str | None, date_from, date_to, needs_refund: bool | None,
                   engagement_id: str | None = None) -> tuple[list[str], list]:
    where, params = ["true"], []
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append("(p.tx_ref ilike %s or p.gateway_reference ilike %s or e.title ilike %s or e.client_name ilike %s "
                     "or pr.display_name ilike %s)")
        params += [like] * 5
    if date_from:
        where.append("(p.created_at at time zone 'Africa/Addis_Ababa')::date >= %s")
        params.append(date_from)
    if date_to:
        where.append("(p.created_at at time zone 'Africa/Addis_Ababa')::date <= %s")
        params.append(date_to)
    if needs_refund:
        where.append("p.status = 'success' and p.refunded_amount < p.amount and (e.refund_needed or p.unapplied_reason is not null)")
    if engagement_id:
        where.append("e.id::text = %s")
        params.append(engagement_id)
    return where, params


def admin_list(status: str | None = None, limit: int = 50, offset: int = 0, *, q: str | None = None,
               date_from=None, date_to=None, needs_refund: bool | None = None, engagement_id: str | None = None) -> dict:
    """
    Every amount in the tiles, so they add up: gross = price + provider VAT = commission + VAT on commission
    + to providers. Money from extra payments that was not credited to anyone is shown on its own.
    The tiles follow the search and dates but not the status tab. In live mode they leave out test money.
    """
    where, params = _admin_filters(None, q, date_from, date_to, needs_refund, engagement_id)
    listed = where + (["p.status = %s"] if status else [])
    list_params = params + ([status] if status else [])
    joins = "from payments p join engagements e on e.id = p.engagement_id left join providers pr on pr.id = e.provider_id"
    rows = fetch_all(f"{ADMIN_PAYMENT_SELECT} where {' and '.join(listed)} order by p.created_at desc limit %s offset %s",
                     (*list_params, limit, offset))
    total = fetch_one(f"select count(*) as c {joins} where {' and '.join(listed)}", list_params)["c"]
    live = not _test_money()
    tiles = where + (["not p.is_test"] if live else [])
    ok = "p.status = 'success' and p.unapplied_reason is null"
    totals = fetch_one(
        f"""
        select count(*) filter (where {ok}) as paid_count,
               coalesce(sum(p.amount) filter (where {ok}), 0)::float as gross,
               coalesce(sum(p.price) filter (where {ok}), 0)::float as price,
               coalesce(sum(p.provider_vat) filter (where {ok}), 0)::float as provider_vat,
               coalesce(sum(p.commission_amount) filter (where {ok}), 0)::float as commission,
               coalesce(sum(p.commission_vat) filter (where {ok}), 0)::float as commission_vat,
               coalesce(sum(p.provider_amount) filter (where {ok}), 0)::float as to_providers,
               coalesce(sum(p.gateway_fee) filter (where p.status = 'success'), 0)::float as gateway_fees,
               coalesce(sum(p.refunded_amount) filter (where p.status = 'success'), 0)::float as refunded,
               coalesce(sum(p.refunded_commission + p.refunded_commission_vat) filter (where {ok}), 0)::float
                 as commission_refunded,
               coalesce(sum(p.refunded_provider_amount) filter (where {ok}), 0)::float as provider_refunded,
               coalesce(sum(p.amount) filter (where p.status = 'success' and p.unapplied_reason is not null), 0)::float
                 as unapplied,
               count(*) filter (where p.status = 'pending') as pending,
               count(*) filter (where p.status = 'failed') as failed,
               count(*) filter (where p.status = 'success' and p.refunded_amount < p.amount
                                and (e.refund_needed or p.unapplied_reason is not null)) as needs_refund
        {joins} where {' and '.join(tiles)}
        """,
        params,
    )
    totals["net_commission"] = round(totals["commission"] + totals["commission_vat"] - totals["commission_refunded"], 2)
    test_count = fetch_one(f"select count(*) as c {joins} where {' and '.join(where)} and p.is_test", params)["c"] if live else 0
    return {"items": rows, "total": total, "totals": totals, "mode": mode(), "test_mode": _test_money(),
            "test_payments": test_count, "commission_percent": platform_settings.get("commission_percent")}


CSV_COLUMNS = ["tx_ref", "created_at", "verified_at", "status", "gateway", "is_test", "title", "client_name", "provider_name",
               "price", "provider_vat", "amount", "commission_amount", "commission_vat", "provider_amount", "gateway_fee",
               "refunded_amount", "unapplied_reason", "payment_method", "gateway_reference", "engagement_id"]


def admin_csv(status: str | None = None, *, q: str | None = None, date_from=None, date_to=None,
              needs_refund: bool | None = None) -> str:
    import csv
    import io

    where, params = _admin_filters(status, q, date_from, date_to, needs_refund)
    if status:
        where.append("p.status = %s")
        params.append(status)
    rows = fetch_all(f"{ADMIN_PAYMENT_SELECT} where {' and '.join(where)} order by p.created_at desc limit 20000", params)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for r in rows:
        # A cell starting with = + - @ would run as a formula in a spreadsheet
        writer.writerow([("'" + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v
                         for v in (r.get(c) for c in CSV_COLUMNS)])
    return out.getvalue()


def admin_verify(tx_ref: str) -> dict:
    """Staff ask the gateway again about a payment that is still pending (the client never came back)."""
    payment = get(tx_ref)
    if not payment:
        raise PaymentError("Payment not found", 404)
    before = payment["status"]
    after = confirm(tx_ref)
    return {"payment": after, "changed": after["status"] != before}


# ---------------------------------------------------------------- earnings and payouts


def _min_payout() -> Decimal:
    return Decimal(str(platform_settings.get("min_payout_etb")))


PAYOUT_COLUMNS = """
  po.id::text, po.provider_id::text, po.amount::float, po.status, po.bank_code, po.bank_name, po.account_name,
  po.account_last4, po.reference, po.gateway, po.gateway_reference, po.note, po.decided_by, po.decided_at, po.paid_at,
  po.created_at, po.is_test, po.needs_check, po.check_note
"""


def _test_money() -> bool:
    return mode() == "simulated" or (mode() == "chapa" and (settings.chapa_secret_key or "").startswith("CHASECK_TEST"))


def _balances(provider_id: str) -> dict:
    """
    In live mode only real money counts: earnings from test checkouts (and payouts of them) are shown apart
    as test_balance and can never be withdrawn. In test mode everything counts, so the flow can be tried.
    A refund can make the balance negative; it is recovered from the next earnings before any payout.
    """
    live = not _test_money()
    only = "and not is_test" if live else ""
    row = fetch_one(
        f"""
        select coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s {only}), 0)::float as balance,
               coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s and kind = 'earning' {only}), 0)::float
                 as earned_total,
               coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s and kind = 'earning' {only}
                         and created_at >= date_trunc('month', now())), 0)::float as earned_this_month,
               coalesce((select sum(amount) from payouts where provider_id = %(p)s and status in ('requested', 'approved')
                         {only}), 0)::float as in_payout,
               coalesce((select -sum(amount) from provider_ledger where provider_id = %(p)s and kind = 'payout' {only}), 0)::float
                 as paid_out,
               coalesce((select -sum(amount) from provider_ledger where provider_id = %(p)s and kind in ('refund', 'adjustment')
                         and refund_id is not null {only}), 0)::float as refunded,
               coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s and is_test), 0)::float
                 as test_balance
        """,
        {"p": provider_id},
    )
    if not live:
        row["test_balance"] = 0.0
    # Money already asked for is held until the payout is paid or refused
    row["available"] = round(row["balance"] - row["in_payout"], 2)
    row["live"] = live
    return row


LEDGER_SELECT = """
  select l.id, l.kind, l.amount::float, l.note, l.created_at, l.is_test, e.title as job_title, e.client_name,
         p.amount::float as gross, p.commission_amount::float as commission, p.commission_vat::float,
         p.provider_vat::float, p.tx_ref, po.reference as payout_reference, po.id::text as payout_id,
         l.refund_id::text, rf.reference as refund_reference
  from provider_ledger l
  left join engagements e on e.id = l.engagement_id
  left join payments p on p.id = l.payment_id
  left join payouts po on po.id = l.payout_id
  left join refunds rf on rf.id = l.refund_id
"""


def earnings(user_id: str) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    ledger = fetch_all(f"{LEDGER_SELECT} where l.provider_id = %s order by l.created_at desc, l.id desc limit 100",
                       (provider["id"],))
    payouts = fetch_all(f"select {PAYOUT_COLUMNS} from payouts po where po.provider_id = %s order by po.created_at desc limit 50",
                        (provider["id"],))
    return {**_balances(provider["id"]), "ledger": ledger, "payouts": [_public_payout(p) for p in payouts],
            "min_payout": float(_min_payout()), "payout_account": payout_view(provider),
            "commission_percent": platform_settings.get("commission_percent")}


def _public_payout(payout: dict) -> dict:
    """What the provider sees of their payout: not the staff-only checking note."""
    return {k: v for k, v in payout.items() if k not in ("check_note", "needs_check", "bank_code")}


def ledger_page(user_id: str, limit: int = 20, offset: int = 0) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    items = fetch_all(f"{LEDGER_SELECT} where l.provider_id = %s order by l.created_at desc, l.id desc limit %s offset %s",
                      (provider["id"], limit, offset))
    total = fetch_one("select count(*) as c from provider_ledger where provider_id = %s", (provider["id"],))["c"]
    return {"total": total, "items": items}


def payouts_page(user_id: str, limit: int = 20, offset: int = 0) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    items = fetch_all(f"select {PAYOUT_COLUMNS} from payouts po where po.provider_id = %s "
                      "order by po.created_at desc limit %s offset %s", (provider["id"], limit, offset))
    total = fetch_one("select count(*) as c from payouts where provider_id = %s", (provider["id"],))["c"]
    return {"total": total, "items": [_public_payout(p) for p in items]}


def request_payout(user_id: str, amount: float) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    if not provider.get("payout_ready"):
        raise PaymentError("Add the bank account to send your money to first", 409)
    amount = _money(amount)
    if amount < _min_payout():
        raise PaymentError(f"The smallest payout is {_min_payout():,.0f} ETB")
    with connection() as conn, conn.transaction():
        # Lock the provider row so two requests at once can't both pass the balance check, and read the
        # account inside the lock so the payout keeps exactly the account it was asked for
        acct = conn.execute(
            "select payout_account_enc, payout_bank_code, payout_bank_name, payout_account_name, payout_account_last4 "
            "from providers where id = %s for update", (provider["id"],),
        ).fetchone()
        if not acct or not acct["payout_account_enc"]:
            raise PaymentError("Add the bank account to send your money to first", 409)
        available = Decimal(str(_balances(provider["id"])["available"]))
        if amount > available:
            raise PaymentError(f"You can withdraw up to {max(available, Decimal(0)):,.2f} ETB", 409)
        row = conn.execute(
            """
            insert into payouts (provider_id, amount, bank_code, bank_name, account_name, account_last4, reference,
                                 account_enc, is_test)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id::text
            """,
            (provider["id"], amount, acct["payout_bank_code"], acct["payout_bank_name"], acct["payout_account_name"],
             acct["payout_account_last4"], f"po-{secrets.token_hex(8)}", acct["payout_account_enc"], _test_money()),
        ).fetchone()
    # Staff see it in the Payouts queue (and its count); they have no notification bell
    return _public_payout(fetch_one(f"select {PAYOUT_COLUMNS} from payouts po where po.id = %s", (row["id"],)))


def admin_payouts(status: str | None = "requested", limit: int = 25, offset: int = 0) -> dict:
    where, params = ("po.status = %s", [status]) if status else ("true", [])
    # Requests waiting for approval are a queue (oldest first); everything else is history (newest first)
    order = "po.created_at" if status == "requested" else "coalesce(po.paid_at, po.decided_at, po.created_at) desc"
    items = fetch_all(
        f"""
        select {PAYOUT_COLUMNS}, pr.display_name as provider_name, pr.slug as provider_slug
        from payouts po join providers pr on pr.id = po.provider_id
        where {where} order by {order} limit %s offset %s
        """,
        (*params, limit, offset),
    )
    total = fetch_one(f"select count(*) as c from payouts po where {where}", params)["c"]
    only = "and not is_test" if not _test_money() else ""
    totals = fetch_one(
        f"""
        select count(*) filter (where status = 'requested') as requested,
               coalesce(sum(amount) filter (where status = 'requested'), 0)::float as requested_amount,
               count(*) filter (where status = 'approved') as processing,
               count(*) filter (where status = 'approved' and needs_check) as needs_check,
               coalesce(sum(amount) filter (where status = 'paid'), 0)::float as paid_amount,
               coalesce((select sum(amount) from provider_ledger where true {only}), 0)::float as owed_to_providers
        from payouts where true {only}
        """
    )
    return {"items": items, "total": total, "totals": totals, "mode": mode(), "test_mode": _test_money()}


def _mark_paid(payout: dict, gateway_reference: str | None) -> bool:
    with connection() as conn, conn.transaction():
        done = conn.execute(
            "update payouts set status = 'paid', paid_at = now(), needs_check = false, "
            "gateway_reference = coalesce(%s, gateway_reference) "
            "where id = %s and status in ('requested', 'approved') returning id, is_test",
            (gateway_reference, payout["id"]),
        ).fetchone()
        if done:
            conn.execute(
                "insert into provider_ledger (provider_id, kind, amount, payout_id, note, is_test) "
                "values (%s, 'payout', %s, %s, %s, %s)",
                (payout["provider_id"], -Decimal(str(payout["amount"])), payout["id"],
                 f"Paid to {payout['bank_name']} ••••{payout['account_last4']}", done["is_test"]),
            )
    return bool(done)


def _mark_failed(payout: dict, note: str) -> bool:
    """Releases the held money. Only for an approved payout the gateway says did not go out."""
    done = fetch_one("update payouts set status = 'failed', needs_check = false, check_note = %s "
                     "where id = %s and status = 'approved' returning id", (note[:500], payout["id"]))
    return bool(done)


def _tell_provider(payout: dict, title: str, body: str | None = None) -> None:
    owner = fetch_one("select user_id::text from providers where id = %s", (payout["provider_id"],))
    if owner and owner["user_id"]:
        notifications.notify([owner["user_id"]], kind="payout", title=title, body=body, link="/me/provider?tab=earnings")


def _name_tokens(name: str | None) -> set[str]:
    return {w for w in re.findall(r"[^\W\d_]+", (name or "").lower()) if len(w) > 1}


def names_match(holder: str | None, *candidates: str | None) -> bool:
    """The bank account holder is the provider: same name, or one name contains the other ("Meron Tadesse Alemu")."""
    h = _name_tokens(holder)
    for c in candidates:
        t = _name_tokens(c)
        if h and t and (h <= t or t <= h or len(h & t) >= 2):
            return True
    return False


def payout_review(payout_id: str) -> dict:
    """What staff check before sending money: who gets it, whether the account is theirs, and what it pays for."""
    payout = fetch_one(f"select {PAYOUT_COLUMNS}, (po.account_enc is not null) as account_stored "
                       "from payouts po where po.id = %s", (payout_id,))
    if not payout:
        raise PaymentError("Payout not found", 404)
    provider = fetch_one(
        """
        select id::text, slug, display_name, legal_name, verified_name, provider_type, status, national_id_verified,
               id_verification_method, coalesce(tin, '') <> '' as has_tin, trade_license_no, vat_registered,
               payout_set_at, payout_bank_code, payout_bank_name, payout_account_name, payout_account_last4, created_at
        from providers where id = %s
        """,
        (payout["provider_id"],),
    )
    earnings_rows = fetch_all(
        """
        select l.amount::float, l.created_at, l.is_test, e.id::text as hire_id, e.title as job_title,
               p.tx_ref, p.gateway, p.amount::float as client_paid, coalesce(u.fullname, u.email) as client
        from provider_ledger l
        left join engagements e on e.id = l.engagement_id
        left join payments p on p.id = l.payment_id
        left join users u on u.id = p.payer_user_id
        where l.provider_id = %s and l.kind = 'earning'
        order by l.created_at desc limit 50
        """,
        (payout["provider_id"],),
    )
    history = fetch_one(
        """
        select count(*) filter (where status = 'paid') as paid_count,
               coalesce(sum(amount) filter (where status = 'paid'), 0)::float as paid_total,
               count(*) filter (where status in ('rejected', 'failed')) as refused_count
        from payouts where provider_id = %s and id <> %s
        """,
        (payout["provider_id"], payout_id),
    )
    balances = _balances(payout["provider_id"])
    # The account the money goes to is the one stored on the payout, shown next to the name on the verified ID
    destination = {"bank_name": payout["bank_name"], "account_name": payout["account_name"],
                   "account_last4": payout["account_last4"], "stored": payout.pop("account_stored"),
                   "fayda_name": provider["verified_name"], "id_verified": provider["national_id_verified"]}
    return {"payout": payout, "provider": provider, "balances": balances, "destination": destination,
            "earnings": earnings_rows, "history": history,
            "checks": _payout_checks(payout, provider, history, balances, destination)}


def _payout_checks(payout: dict, provider: dict, history: dict, balances: dict, destination: dict) -> list[dict]:
    """block: approving needs a written reason (hard: can't be approved at all). warn: look first. info: worth knowing."""
    checks = []
    new_account_days = platform_settings.get_int("payout_new_account_days")
    if payout["is_test"] != _test_money():
        checks.append({"level": "hard", "code": "test_money",
                       "text": "This payout was asked for from test-mode earnings. Payments are live now, so it can't be "
                               "sent. Refuse it." if payout["is_test"] else
                               "This payout was asked for while payments were live, but they are in test mode now. "
                               "Switch back to live payments to send it."})
    if not destination["stored"]:
        checks.append({"level": "hard", "code": "no_account",
                       "text": "This request has no bank account stored with it (it was made before accounts were "
                               "kept on each request). Refuse it and ask the provider to ask again."})
    if not names_match(payout["account_name"], provider["verified_name"], provider["legal_name"], provider["display_name"]):
        checks.append({"level": "block", "code": "name_mismatch",
                       "text": f"The bank account is in the name of {payout['account_name']}, not "
                               f"{provider['verified_name'] or provider['display_name']}. Money should only go to the "
                               "provider's own account or their company's."})
    if not provider["national_id_verified"]:
        checks.append({"level": "block", "code": "id_not_verified", "text": "The provider's national ID is not verified."})
    if provider["status"] != "approved":
        checks.append({"level": "block", "code": "not_approved", "text": f"The provider is {provider['status']}, not approved."})
    if balances["balance"] < balances["in_payout"] and payout["status"] == "requested" and payout["is_test"] == _test_money():
        checks.append({"level": "block", "code": "balance_short",
                       "text": f"After refunds the provider's balance ({balances['balance']:,.2f} ETB) no longer covers "
                               f"the payouts waiting ({balances['in_payout']:,.2f} ETB)."})
    if not provider["has_tin"]:
        checks.append({"level": "warn", "code": "no_tin",
                       "text": "No TIN on file. Ethiopian income tax rules require 30% withholding on payments to "
                               "suppliers without a TIN; get it before paying."})
    if provider["payout_set_at"] and (payout["created_at"] - provider["payout_set_at"]).total_seconds() < new_account_days * 24 * 3600:
        checks.append({"level": "warn", "code": "new_account",
                       "text": f"The bank account was added or changed less than {new_account_days} days before this request."})
    if provider["payout_account_last4"] and (provider["payout_account_last4"] != payout["account_last4"]
                                              or provider["payout_bank_code"] != payout["bank_code"]):
        checks.append({"level": "warn", "code": "account_changed",
                       "text": "The provider's bank account on file is different now. The money goes to the account "
                               "shown here, the one the request was made with."})
    if payout["needs_check"]:
        checks.append({"level": "warn", "code": "needs_check",
                       "text": payout["check_note"] or "The transfer could not be confirmed. Check with Chapa."})
    if not history["paid_count"]:
        checks.append({"level": "info", "code": "first_payout", "text": "First payout to this provider."})
    if _test_money():
        checks.append({"level": "info", "code": "test_mode",
                       "text": "Payments are in test mode: no real money was collected and none will be sent."})
    return checks


def decide_payout(payout_id: str, *, decision: str, note: str | None, actor: str) -> dict:
    """
    approve:     claim the payout (only one approval wins), then send it to the account stored on it
                 (simulated: paid at once; Chapa: queued, then refresh)
    reject:      refuse a payout that is still waiting; the held money is released
    refresh:     ask the gateway about an approved payout
    mark_failed: release an approved payout, only once the gateway says it failed or never received it
    A payout with a blocking check (name mismatch, unverified ID) is only approved with a written reason.
    """
    from core.crypto import decrypt

    payout = fetch_one(f"select {PAYOUT_COLUMNS}, po.account_enc from payouts po where po.id = %s", (payout_id,))
    if not payout:
        raise PaymentError("Payout not found", 404)
    note = (note or "").strip()
    if decision == "reject":
        if not note:
            raise PaymentError("Tell the provider why")
        # Only a payout nobody has sent yet can be refused; an approved one may already be in the bank
        row = fetch_one("update payouts set status = 'rejected', note = %s, decided_by = %s, decided_at = now() "
                        "where id = %s and status = 'requested' returning id", (note, actor, payout_id))
        if not row:
            raise PaymentError("Only a payout that is still waiting can be refused. An approved one may already be on "
                               "its way: use Check with Chapa, or Mark failed once Chapa confirms it failed.", 409)
        _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB was not approved", note)
    elif decision == "approve":
        if payout["status"] != "requested":
            raise PaymentError("This payout was already decided", 409)
        checks = payout_review(payout_id)["checks"]
        hard = [c["text"] for c in checks if c["level"] == "hard"]
        if hard:
            raise PaymentError(" ".join(hard), 409)
        blocks = [c["text"] for c in checks if c["level"] == "block"]
        if blocks and len(note) < 10:
            raise PaymentError("Check before paying: " + " ".join(blocks) + " To approve anyway, write why.", 409)
        account = decrypt(payout["account_enc"])
        if not account:
            raise PaymentError("The bank account on this request can't be read. Refuse it and ask the provider to "
                               "ask again.", 409)
        gw = gateway()
        # Claim it: of two approvals at the same moment only one gets the row back, and only that one sends money
        claimed = fetch_one(
            "update payouts set status = 'approved', decided_by = %s, decided_at = now(), note = %s, gateway = %s "
            "where id = %s and status = 'requested' returning id",
            (actor, note or None, gw.name, payout_id),
        )
        if not claimed:
            raise PaymentError("This payout was already decided", 409)
        try:
            result = gw.transfer(account_name=payout["account_name"], account_number=account,
                                 bank_code=payout["bank_code"], amount=_money(payout["amount"]),
                                 reference=payout["reference"])
        except PaymentError as exc:
            # The money may have left even though we got an error (a timeout after Chapa accepted it). Keep it
            # held as approved and check with Chapa before anyone releases it.
            log.error("Payout %s transfer error (%s): %s", payout_id, "uncertain" if exc.uncertain else "refused", exc)
            execute("update payouts set needs_check = true, check_note = %s where id = %s",
                    (f"The transfer request got an error: {str(exc)[:200]}. The money stays held. Use Check "
                     f"with Chapa; release it only when Chapa says it failed."[:500], payout_id))
            raise PaymentError("The transfer could not be confirmed. The money stays held until Chapa confirms what "
                               "happened: use Check with Chapa.", 502) from exc
        if result["status"] == "paid":
            _mark_paid(payout, result.get("reference"))
            _tell_provider(payout, f"{payout['amount']:,.2f} ETB sent to your bank",
                           f"{payout['bank_name']} ••••{payout['account_last4']}")
        else:
            execute("update payouts set gateway_reference = %s where id = %s", (result.get("reference"), payout_id))
            _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB approved", "It is on its way to your bank.")
    elif decision in ("refresh", "mark_failed"):
        if payout["status"] != "approved":
            if decision == "mark_failed":
                raise PaymentError("Only an approved payout can be marked failed", 409)
            return _public_staff_payout(payout_id)
        if decision == "mark_failed" and len(note) < 10:
            raise PaymentError("Write what you checked (at least 10 characters)")
        status = gateway_named(payout["gateway"] or mode()).verify_transfer(payout["reference"])
        if status == "paid":
            if _mark_paid(payout, None):
                _tell_provider(payout, f"{payout['amount']:,.2f} ETB arrived in your bank",
                               f"{payout['bank_name']} ••••{payout['account_last4']}")
            if decision == "mark_failed":
                raise PaymentError("Chapa says this transfer was paid, so it was recorded as paid instead.", 409)
        elif status == "failed" or (status == "missing" and decision == "mark_failed"):
            why = "Chapa reports the transfer failed" if status == "failed" else \
                f"Chapa has no record of the transfer. Checked by {actor}: {note}"
            if _mark_failed(payout, why):
                _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB failed",
                               "The money is back in your balance. Our team will contact you.")
        elif status == "missing":
            execute("update payouts set check_note = %s where id = %s and status = 'approved'",
                    ("Chapa has no record of this transfer yet. If it still has none, mark it failed with a note.",
                     payout_id))
        elif decision == "mark_failed":
            raise PaymentError("Chapa still shows the transfer on its way (or can't be reached), so the money can't be "
                               "released yet. Try again later.", 409)
    else:
        raise PaymentError("Unknown decision")
    return _public_staff_payout(payout_id)


def check_processing_payouts(min_age_minutes: int = 5) -> dict:
    """Ask the gateway about every approved payout that has waited a few minutes, so a transfer that
    landed (or failed) is recorded without staff pressing "Check with Chapa". Runs every 15 minutes."""
    rows = fetch_all(
        "select id::text from payouts where status = 'approved' and decided_at < now() - make_interval(mins => %s) "
        "order by decided_at limit 100",
        (min_age_minutes,),
    )
    counts = {"checked": 0, "paid": 0, "failed": 0, "errors": 0}
    for row in rows:
        try:
            after = decide_payout(row["id"], decision="refresh", note=None, actor="automatic Chapa check")
        except Exception:
            counts["errors"] += 1
            log.exception("Automatic check of payout %s failed", row["id"])
            continue
        counts["checked"] += 1
        if after and after.get("status") in ("paid", "failed"):
            counts[after["status"]] += 1
    return counts


def _public_staff_payout(payout_id: str) -> dict:
    return fetch_one(f"select {PAYOUT_COLUMNS} from payouts po where po.id = %s", (payout_id,))


# ---------------------------------------------------------------- refunds

REFUND_COLUMNS = """
  r.id::text, r.payment_id::text, r.engagement_id::text, r.reference, r.amount::float, r.price_part::float,
  r.provider_vat::float, r.commission::float, r.commission_vat::float, r.provider_amount::float, r.reason, r.method,
  r.status, r.applied, r.gateway, r.gateway_ref, r.is_test, r.client_bank_name, r.client_account_name,
  r.client_account_last4, r.transfer_reference, r.requested_by, r.approved_by, r.confirmed_by, r.error, r.note,
  r.created_at, r.updated_at, r.completed_at
"""


def _share(total, refunded_after: Decimal, refunded_before: Decimal, amount: Decimal) -> Decimal:
    """This refund's part of one figure, so all partial refunds together add up to the whole figure exactly."""
    total = Decimal(str(total or 0))
    return _money(total * refunded_after / amount) - _money(total * refunded_before / amount)


def refund_figures(payment: dict, amount) -> dict:
    """
    How a refund of `amount` (what the client gets back) splits, in proportion to the original payment:
      amount = price part + provider VAT = commission + VAT on commission + provider's share
    Money that was never credited (a duplicate payment) is returned entirely from our side.
    Chapa's own fee on the payment is not refunded by Chapa, so the platform carries it.
    """
    amount = _money(amount)
    total = _money(payment["amount"])
    before = _money(payment.get("refunded_amount") or 0)
    after = before + amount
    if payment.get("unapplied_reason"):
        return {"amount": amount, "price_part": amount, "provider_vat": Decimal("0.00"), "commission": Decimal("0.00"),
                "commission_vat": Decimal("0.00"), "provider_amount": Decimal("0.00")}
    pvat = _share(payment["provider_vat"], after, before, total)
    commission = _share(payment["commission_amount"], after, before, total)
    cvat = _share(payment["commission_vat"], after, before, total)
    return {"amount": amount, "price_part": amount - pvat, "provider_vat": pvat, "commission": commission,
            "commission_vat": cvat, "provider_amount": amount - commission - cvat}


def _payment_for_refund(tx_ref: str, conn=None) -> dict | None:
    sql = """
      select p.id::text, p.tx_ref, p.engagement_id::text, p.gateway, p.status, p.amount, p.price, p.provider_vat,
             p.commission_amount, p.commission_vat, p.provider_amount, p.refunded_amount, p.is_test, p.unapplied_reason,
             coalesce((select sum(r.amount) from refunds r where r.payment_id = p.id and r.status = 'sending'), 0)
               as sending,
             e.title, e.client_name, e.client_user_id::text, e.provider_id::text, pr.display_name as provider_name,
             pr.user_id::text as provider_user_id
      from payments p join engagements e on e.id = p.engagement_id left join providers pr on pr.id = e.provider_id
      where p.tx_ref = %s
    """
    if conn is None:
        return fetch_one(sql, (tx_ref,))
    return conn.execute(sql + " for update of p", (tx_ref,)).fetchone()


def refund_plan(tx_ref: str, *, amount=None, reason: str, method: str = "gateway",
                client_bank: dict | None = None) -> dict:
    """
    Check a refund request and turn it into the exact payload a second staff member approves.
    The client's account number (manual refunds) is encrypted before it is stored anywhere.
    """
    from core.crypto import encrypt

    payment = _payment_for_refund(tx_ref)
    if not payment:
        raise PaymentError("Payment not found", 404)
    if payment["status"] != "success":
        raise PaymentError("Only a payment that went through can be refunded", 409)
    refundable = _money(payment["amount"]) - _money(payment["refunded_amount"]) - _money(payment["sending"])
    if refundable <= 0:
        raise PaymentError("This payment has already been refunded in full", 409)
    amount = refundable if amount in (None, "") else _money(amount)
    if amount <= 0:
        raise PaymentError("Enter an amount above zero")
    if amount > refundable:
        raise PaymentError(f"You can refund up to {refundable:,.2f} ETB of this payment", 409)
    reason = re.sub(r"\s+", " ", reason or "").strip()
    if len(reason) < 5:
        raise PaymentError("Write the reason for the refund")
    if method not in ("gateway", "manual"):
        raise PaymentError("Choose how the money goes back")
    payload = {"tx_ref": tx_ref, "amount": str(amount), "reason": reason[:500], "method": method}
    if method == "manual":
        bank = client_bank or {}
        number = re.sub(r"\s", "", str(bank.get("account_number") or ""))
        name = re.sub(r"\s+", " ", str(bank.get("account_name") or "")).strip()
        bank_name = str(bank.get("bank_name") or "").strip()
        if not bank_name or len(name) < 2 or not re.fullmatch(r"\d{6,20}", number):
            raise PaymentError("For a manual refund, enter the client's bank, account holder name and account number")
        payload["client_bank"] = {"bank_name": bank_name[:80], "account_name": name[:120],
                                  "account_enc": encrypt(number), "last4": number[-4:]}
    elif payment["gateway"] == "chapa" and payment["is_test"] and not _test_money():
        raise PaymentError("This was a test payment and payments are live now, so Chapa can't refund it. "
                           "No real money was taken.", 409)
    full = amount == _money(payment["amount"]) - _money(payment["refunded_amount"])
    figures = refund_figures(payment, amount)
    summary = (f"Refund {amount:,.2f} ETB of {_money(payment['amount']):,.2f} ETB ({'in full' if full else 'part'}) to "
               f"{payment['client_name'] or 'the client'} for \"{payment['title']}\" (payment {tx_ref}), "
               f"{'through Chapa' if method == 'gateway' and payment['gateway'] == 'chapa' else 'by bank transfer from us' if method == 'manual' else 'test refund'}. "
               f"Taken back from {payment['provider_name'] or 'the provider'}: {figures['provider_amount']:,.2f} ETB. "
               f"Reason: {reason[:200]}")
    return {"payload": payload, "summary": summary, "figures": {k: float(v) for k, v in figures.items()},
            "refundable": float(refundable)}


def _apply_refund(conn, refund: dict, payment: dict, actor: str) -> None:
    """Count a refund: payment figures, a negative ledger line for the provider, the hire's status and history."""
    conn.execute(
        """
        update payments set refunded_amount = refunded_amount + %s, refunded_commission = refunded_commission + %s,
          refunded_commission_vat = refunded_commission_vat + %s, refunded_provider_amount = refunded_provider_amount + %s,
          refunded_provider_vat = refunded_provider_vat + %s, updated_at = now()
        where id = %s
        """,
        (_money(refund["amount"]), _money(refund["commission"]), _money(refund["commission_vat"]),
         _money(refund["provider_amount"]), _money(refund["provider_vat"]), payment["id"]),
    )
    credited = conn.execute("select provider_id::text from provider_ledger where payment_id = %s and kind = 'earning'",
                            (payment["id"],)).fetchone()
    if credited and Decimal(str(refund["provider_amount"])) > 0:
        # The provider's balance may go below zero; it is recovered from their next earnings before any payout
        conn.execute(
            "insert into provider_ledger (provider_id, kind, amount, engagement_id, payment_id, refund_id, note, is_test) "
            "values (%s, 'refund', %s, %s, %s, %s, %s, %s) on conflict do nothing",
            (credited["provider_id"], -_money(refund["provider_amount"]), payment["engagement_id"], payment["id"],
             refund["id"], f"Refund {refund['reference']} to the client: {refund['reason'][:120]}", payment["is_test"]),
        )
    left = conn.execute("select (amount - refunded_amount) as left from payments where id = %s", (payment["id"],)).fetchone()
    full = left["left"] <= 0
    # A full refund of the payment that paid for the job marks the job refunded; a duplicate's refund doesn't
    if full and not payment["unapplied_reason"]:
        conn.execute("update engagements set payment_status = 'refunded', updated_at = now() "
                     "where id = %s and payment_status = 'paid'", (payment["engagement_id"],))
    conn.execute("update engagements set refund_needed = false where id = %s", (payment["engagement_id"],))
    conn.execute("update refunds set applied = true, updated_at = now() where id = %s", (refund["id"],))
    from services import provider_service

    provider_service._event(
        conn, payment["engagement_id"], "refunded" if full else "partly_refunded", who="staff", actor=actor,
        note=f"{_money(refund['amount']):,.2f} ETB refund approved ({refund['reference']}, "
             f"{'bank transfer by staff' if refund['method'] == 'manual' else 'through the payment service'}). "
             f"{refund['reason']}")


def _unapply_refund(conn, refund: dict, actor: str, why: str) -> None:
    """A refund that was counted did not reach the client: undo the figures and give the provider their share back."""
    if not refund["applied"]:
        return
    payment = conn.execute("select id::text, engagement_id::text, is_test, unapplied_reason from payments where id = %s "
                           "for update", (refund["payment_id"],)).fetchone()
    conn.execute(
        """
        update payments set refunded_amount = refunded_amount - %s, refunded_commission = refunded_commission - %s,
          refunded_commission_vat = refunded_commission_vat - %s, refunded_provider_amount = refunded_provider_amount - %s,
          refunded_provider_vat = refunded_provider_vat - %s, updated_at = now()
        where id = %s
        """,
        (_money(refund["amount"]), _money(refund["commission"]), _money(refund["commission_vat"]),
         _money(refund["provider_amount"]), _money(refund["provider_vat"]), payment["id"]),
    )
    taken = conn.execute("select provider_id::text, amount from provider_ledger where refund_id = %s and kind = 'refund'",
                         (refund["id"],)).fetchone()
    if taken:
        conn.execute(
            "insert into provider_ledger (provider_id, kind, amount, engagement_id, payment_id, refund_id, note, is_test) "
            "values (%s, 'adjustment', %s, %s, %s, %s, %s, %s)",
            (taken["provider_id"], -taken["amount"], payment["engagement_id"], payment["id"], refund["id"],
             f"Refund {refund['reference']} did not go through; your share is back", payment["is_test"]),
        )
    if not payment["unapplied_reason"]:
        conn.execute("update engagements set payment_status = 'paid', updated_at = now() "
                     "where id = %s and payment_status = 'refunded'", (payment["engagement_id"],))
    conn.execute("update engagements set refund_needed = true, refund_flagged_at = now(), refund_flagged_by = %s "
                 "where id = %s", (actor, payment["engagement_id"]))
    conn.execute("update refunds set applied = false, updated_at = now() where id = %s", (refund["id"],))
    from services import provider_service

    provider_service._event(conn, payment["engagement_id"], "refund_failed", who="staff", actor=actor,
                            note=f"Refund {refund['reference']} did not go through: {why}")


def _refund_row(refund_id: str, conn=None) -> dict | None:
    sql = f"select {REFUND_COLUMNS} from refunds r where r.id = %s"
    if conn is None:
        return fetch_one(sql, (refund_id,))
    return conn.execute(sql + " for update", (refund_id,)).fetchone()


def _tell_refund(refund: dict, payment: dict) -> None:
    from services import provider_service

    eng = provider_service.get_engagement(payment["engagement_id"])
    if not eng:
        return
    amount = f"{Decimal(str(refund['amount'])):,.2f} ETB"
    done = refund["status"] == "refunded"
    if refund["method"] == "manual":
        client_body = f"We will send it to your {refund['client_bank_name']} account ending {refund['client_account_last4']}."
    else:
        client_body = "It goes back to how you paid. Banks can take a few days." if not done else "It is on its way back to how you paid."
    provider_service._tell(eng, "client", f"Refund of {amount} for {eng['title']}", f"Reference {refund['reference']}. {client_body}")
    if Decimal(str(refund["provider_amount"])) > 0:
        provider_service._tell(eng, "provider", f"{eng['client_name'] or 'A client'} was refunded {amount}",
                               f"{Decimal(str(refund['provider_amount'])):,.2f} ETB was taken back from your earnings. "
                               f"Reason: {refund['reason'][:200]}")


def _refund_done(refund: dict, actor: str) -> None:
    """The money reached the client: the hire's refund flag is cleared and its history says so."""
    from services import provider_service

    execute("update engagements set refund_needed = false where id = %s", (refund["engagement_id"],))
    how = f"bank transfer {refund['transfer_reference']}" if refund.get("transfer_reference") else \
        f"payment service reference {refund.get('gateway_ref') or refund['reference']}"
    provider_service._event(None, refund["engagement_id"], "refund_done", who="staff", actor=actor,
                            note=f"{_money(refund['amount']):,.2f} ETB returned to the client ({refund['reference']}, {how}).")


def execute_refund(payload: dict, actor: str) -> dict:
    """
    Carry out an approved refund (called by the approval workflow, or by the route when no second person
    exists). Gateway refunds go through Chapa's refund API; manual ones wait for staff to send the money
    and confirm. A gateway error that does not prove the refund failed leaves it "needs checking".
    """
    tx_ref = payload["tx_ref"]
    amount = _money(payload["amount"])
    method = payload.get("method", "gateway")
    bank = payload.get("client_bank") or {}
    reference = f"rf-{secrets.token_hex(8)}"
    with connection() as conn, conn.transaction():
        # Lock the payment so two refunds at once can't add up to more than was paid
        payment = _payment_for_refund(tx_ref, conn)
        if not payment or payment["status"] != "success":
            raise PaymentError("Payment not found", 404)
        refundable = _money(payment["amount"]) - _money(payment["refunded_amount"]) - _money(payment["sending"])
        if amount > refundable:
            raise PaymentError(f"Only {max(refundable, Decimal(0)):,.2f} ETB of this payment is left to refund", 409)
        figures = refund_figures(payment, amount)
        refund = conn.execute(
            f"""
            insert into refunds (payment_id, engagement_id, reference, amount, price_part, provider_vat, commission,
              commission_vat, provider_amount, reason, method, status, gateway, is_test, client_bank_name,
              client_account_name, client_account_enc, client_account_last4, requested_by, approved_by)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning {REFUND_COLUMNS.replace('r.', '')}
            """,
            (payment["id"], payment["engagement_id"], reference, amount, figures["price_part"], figures["provider_vat"],
             figures["commission"], figures["commission_vat"], figures["provider_amount"], payload["reason"], method,
             "manual_pending" if method == "manual" else "sending", payment["gateway"], payment["is_test"],
             bank.get("bank_name"), bank.get("account_name"), bank.get("account_enc"), bank.get("last4"),
             actor.split(" (")[0], actor),
        ).fetchone()
        if method == "manual":
            # We owe the client this money from now on, so it is counted at once
            _apply_refund(conn, refund, payment, actor)
    if method == "gateway":
        try:
            result = gateway_named(payment["gateway"]).refund(tx_ref=tx_ref, amount=amount, reason=payload["reason"],
                                                              reference=reference)
        except PaymentError as exc:
            with connection() as conn, conn.transaction():
                refund = _refund_row(refund["id"], conn)
                if exc.uncertain:
                    # Chapa may have carried it out: count it, and let staff confirm with Chapa before undoing anything
                    conn.execute("update refunds set status = 'needs_check', error = %s, updated_at = now() where id = %s",
                                 (str(exc)[:500], refund["id"]))
                    _apply_refund(conn, refund, payment, actor)
                else:
                    conn.execute("update refunds set status = 'failed', error = %s, updated_at = now() where id = %s",
                                 (str(exc)[:500], refund["id"]))
            if not exc.uncertain:
                raise PaymentError(f"Chapa refused the refund: {exc}. Nothing was refunded. You can refund it by "
                                   "bank transfer instead.", 409) from exc
            log.error("Refund %s for %s: uncertain gateway error %s", reference, tx_ref, exc)
        else:
            with connection() as conn, conn.transaction():
                refund = _refund_row(refund["id"], conn)
                done = result["status"] == "refunded"
                conn.execute(
                    "update refunds set status = %s, gateway_ref = %s, updated_at = now(), "
                    "completed_at = case when %s then now() else completed_at end where id = %s",
                    (result["status"], result.get("ref_id"), done, refund["id"]),
                )
                _apply_refund(conn, refund, payment, actor)
    refund = _refund_row(refund["id"])
    if refund["status"] == "refunded" and refund["engagement_id"]:
        _refund_done(refund, actor)
    _tell_refund(refund, payment)
    return {"refund_id": refund["id"], "reference": refund["reference"], "status": refund["status"],
            "amount": refund["amount"]}


def refund_action(refund_id: str, *, action: str, note: str | None, transfer_reference: str | None, actor: str) -> dict:
    """
    refresh:   ask Chapa about a refund that is processing or needs checking
    confirm:   staff sent a manual refund (or saw in Chapa's dashboard that it went through)
    mark_failed: the money did not reach the client; the figures and the provider's share are restored
    """
    note = (note or "").strip()
    refund = _refund_row(refund_id)
    if not refund:
        raise PaymentError("Refund not found", 404)
    payment = fetch_one("select id::text, engagement_id::text, tx_ref from payments where id = %s", (refund["payment_id"],))
    if action == "refresh":
        if refund["status"] not in ("processing", "needs_check") or not refund["gateway_ref"]:
            if refund["status"] == "needs_check":
                raise PaymentError("Chapa gave no reference for this refund. Check the Chapa dashboard, then confirm "
                                   "or mark it failed.", 409)
            return _admin_refund(refund_id)
        status = gateway_named(refund["gateway"]).verify_refund(refund["gateway_ref"])
        if status == "refunded":
            execute("update refunds set status = 'refunded', completed_at = now(), updated_at = now() "
                    "where id = %s and status in ('processing', 'needs_check')", (refund_id,))
        elif status == "failed":
            with connection() as conn, conn.transaction():
                row = _refund_row(refund_id, conn)
                if row["status"] in ("processing", "needs_check"):
                    conn.execute("update refunds set status = 'failed', error = 'Chapa reversed the refund', "
                                 "updated_at = now() where id = %s", (refund_id,))
                    _unapply_refund(conn, row, actor, "Chapa reversed it; the money is back in our Chapa balance")
    elif action == "confirm":
        if refund["status"] not in ("manual_pending", "needs_check"):
            raise PaymentError("Only a refund waiting to be sent or checked can be confirmed", 409)
        if refund["status"] == "manual_pending" and actor == refund.get("requested_by"):
            raise PaymentError("The person who asked for this refund can't also confirm it was sent. "
                               "Ask another staff member.", 403)
        ref = (transfer_reference or "").strip()
        if refund["status"] == "manual_pending" and len(ref) < 3:
            raise PaymentError("Enter the bank transfer reference")
        if len(note) < 5 and not ref:
            raise PaymentError("Write what you checked")
        row = fetch_one(
            "update refunds set status = 'refunded', transfer_reference = coalesce(%s, transfer_reference), "
            "confirmed_by = %s, note = %s, completed_at = now(), updated_at = now() "
            "where id = %s and status in ('manual_pending', 'needs_check') returning id",
            (ref or None, actor, note or None, refund_id),
        )
        if not row:
            raise PaymentError("This refund was already decided", 409)
    elif action == "mark_failed":
        if refund["status"] not in ("manual_pending", "needs_check"):
            raise PaymentError("Only a refund waiting to be sent or checked can be marked failed", 409)
        if len(note) < 10:
            raise PaymentError("Write what you checked (at least 10 characters)")
        if refund["status"] == "needs_check" and refund["gateway"] == "chapa":
            # Chapa may already have sent this money; failing it re-opens the refund and could pay twice
            if refund["gateway_ref"]:
                if gateway_named("chapa").verify_refund(refund["gateway_ref"]) != "failed":
                    raise PaymentError("Chapa doesn't show this refund as failed, so it can't be marked failed. "
                                       "Check again later or confirm it.", 409)
            elif actor in (refund.get("requested_by"), refund.get("approved_by")):
                raise PaymentError("Chapa gave no reference for this refund. Someone other than the people who "
                                   "asked for and approved it must check the Chapa dashboard and mark it failed.", 403)
        with connection() as conn, conn.transaction():
            row = _refund_row(refund_id, conn)
            if row["status"] not in ("manual_pending", "needs_check"):
                raise PaymentError("This refund was already decided", 409)
            conn.execute("update refunds set status = 'failed', note = %s, confirmed_by = %s, updated_at = now() "
                         "where id = %s", (note, actor, refund_id))
            _unapply_refund(conn, row, actor, note)
    else:
        raise PaymentError("Unknown action")
    after = _refund_row(refund_id)
    if after["status"] != refund["status"] and after["status"] == "refunded":
        from services import provider_service

        if after["engagement_id"]:
            _refund_done(after, actor)
        eng = provider_service.get_engagement(payment["engagement_id"])
        if eng:
            provider_service._tell(eng, "client", f"Your refund of {after['amount']:,.2f} ETB was sent",
                                   f"Reference {after['reference']}. Your refund receipt is ready.")
    return _admin_refund(refund_id)


def _admin_refund(refund_id: str) -> dict:
    return fetch_one(f"select {REFUND_COLUMNS}, p.tx_ref from refunds r join payments p on p.id = r.payment_id "
                     "where r.id = %s", (refund_id,))


def admin_refunds(*, tx_ref: str | None = None, status: str | None = None, limit: int = 25, offset: int = 0,
                  show_account: bool = False) -> dict:
    """Refunds, newest first. Staff who can refund see the full client account number of a manual refund to send it."""
    from core.crypto import decrypt

    where, params = ["true"], []
    if tx_ref:
        where.append("p.tx_ref = %s")
        params.append(tx_ref)
    if status:
        where.append("r.status = %s")
        params.append(status)
    clause = " and ".join(where)
    items = fetch_all(
        f"""
        select {REFUND_COLUMNS}, r.client_account_enc, p.tx_ref, p.amount::float as payment_amount, e.title, e.client_name,
               pr.display_name as provider_name
        from refunds r join payments p on p.id = r.payment_id left join engagements e on e.id = r.engagement_id
        left join providers pr on pr.id = e.provider_id
        where {clause} order by r.created_at desc, r.id limit %s offset %s
        """,
        (*params, limit, offset),
    )
    for item in items:
        enc = item.pop("client_account_enc")
        item["client_account_number"] = decrypt(enc) if show_account and item["status"] == "manual_pending" else None
    total = fetch_one(f"select count(*) as c from refunds r join payments p on p.id = r.payment_id where {clause}",
                      params)["c"]
    return {"items": items, "total": total}


# ---------------------------------------------------------------- receipts

RECEIPT_NOTICE = ("This is a payment receipt from Compliance Navigator. It is not a tax invoice registered in the "
                  "Ministry of Revenues electronic invoicing system.")


def _issuer() -> dict:
    get = platform_settings.get
    return {"legal_name": get("legal_name"), "tin": get("tin") or None, "vat_number": get("vat_number") or None,
            "address": get("address"), "vat_registered": get("platform_vat_registered")}


def payment_receipt(tx_ref: str, *, user) -> dict:
    """The client's receipt; the provider (and staff) also see their statement: commission, VAT on it, their share."""
    row = fetch_one(
        """
        select p.tx_ref, p.status, p.currency, p.amount::float, p.price::float, p.vat_rate::float, p.provider_vat::float,
               p.commission_percent::float, p.commission_amount::float, p.commission_vat::float, p.provider_amount::float,
               p.provider_vat_number, p.payment_method, p.gateway, p.gateway_reference, p.verified_at, p.updated_at,
               e.title, e.service_name, e.completion_note, e.client_name, e.client_user_id::text, u.email as client_email,
               pr.display_name as provider_name, pr.registration_no as provider_registration_no,
               pr.user_id::text as provider_user_id, p.is_test, p.refunded_amount::float
        from payments p
        join engagements e on e.id = p.engagement_id
        left join users u on u.id = e.client_user_id
        left join providers pr on pr.id = e.provider_id
        where p.tx_ref = %s
        """,
        (tx_ref,),
    )
    if not row or row["status"] != "success":
        raise PaymentError("Receipt not found", 404)
    is_client = row["client_user_id"] == user.id
    is_provider = row["provider_user_id"] == user.id
    if not (is_client or is_provider or user.is_admin):
        raise PaymentError("Receipt not found", 404)
    receipt = {
        "receipt_no": row["tx_ref"], "kind": "payment", "paid_at": row["verified_at"] or row["updated_at"],
        "currency": row["currency"], "issued_by": _issuer(), "notice": RECEIPT_NOTICE,
        "client": {"name": row["client_name"], "email": row["client_email"]},
        "provider": {"name": row["provider_name"], "registration_no": row["provider_registration_no"],
                     "vat_number": row["provider_vat_number"]},
        "job": {"title": row["title"], "service": row["service_name"], "delivered": row["completion_note"]},
        "lines": [{"label": "Service by " + (row["provider_name"] or "provider"), "amount": row["price"]}]
                 + ([{"label": f"VAT {row['vat_rate']:g}% charged by the provider", "amount": row["provider_vat"]}]
                    if row["provider_vat"] else []),
        "total": row["amount"],
        "payment": {"method": row["payment_method"], "gateway": row["gateway"], "reference": row["gateway_reference"]},
        "is_test": row["is_test"],
        # Money given back later has its own receipts; the original receipt never changes
        "refunds": fetch_all(
            "select r.id::text, r.reference, r.amount::float, r.status, r.completed_at from refunds r "
            "join payments p on p.id = r.payment_id where p.tx_ref = %s and r.status <> 'failed' order by r.created_at",
            (tx_ref,)),
        "refunded_amount": row["refunded_amount"],
    }
    if is_provider or user.is_admin:
        receipt["statement"] = {
            "price": row["price"], "provider_vat": row["provider_vat"],
            "commission_percent": row["commission_percent"], "commission": row["commission_amount"],
            "commission_vat": row["commission_vat"], "vat_rate": row["vat_rate"],
            "provider_amount": row["provider_amount"],
        }
    return receipt


def payout_receipt(payout_id: str, *, user) -> dict:
    row = fetch_one(
        f"select {PAYOUT_COLUMNS}, pr.display_name as provider_name, pr.registration_no, pr.user_id::text as owner "
        "from payouts po join providers pr on pr.id = po.provider_id where po.id::text = %s",
        (payout_id,),
    )
    if not row or row["status"] != "paid" or not (row["owner"] == user.id or user.is_admin):
        raise PaymentError("Receipt not found", 404)
    return {
        "receipt_no": row["reference"], "kind": "payout", "paid_at": row["paid_at"], "currency": "ETB",
        "issued_by": _issuer(), "notice": "Withdrawal of earnings to the provider's own bank account.",
        "provider": {"name": row["provider_name"], "registration_no": row["registration_no"]},
        "amount": row["amount"],
        "to": {"bank": row["bank_name"], "account_name": row["account_name"], "account_last4": row["account_last4"]},
        "transfer_reference": row["gateway_reference"],
    }


def refund_receipt(refund_id: str, *, user) -> dict:
    """The client's refund receipt; the provider (and staff) also see what was taken back from each side."""
    try:
        row = fetch_one(
            f"""
            select {REFUND_COLUMNS}, p.tx_ref, p.currency, p.amount::float as payment_amount, p.vat_rate::float,
                   p.provider_vat_number, p.verified_at as paid_at,
                   e.title, e.service_name, e.client_name, e.client_user_id::text, u.email as client_email,
                   pr.display_name as provider_name, pr.registration_no as provider_registration_no,
                   pr.user_id::text as provider_user_id
            from refunds r
            join payments p on p.id = r.payment_id
            join engagements e on e.id = p.engagement_id
            left join users u on u.id = e.client_user_id
            left join providers pr on pr.id = e.provider_id
            where r.id = %s
            """,
            (refund_id,),
        )
    except Exception:  # noqa: BLE001 (a malformed id is simply not found)
        row = None
    if not row or row["status"] != "refunded":
        raise PaymentError("Receipt not found", 404)
    is_client = row["client_user_id"] == user.id
    is_provider = row["provider_user_id"] == user.id
    if not (is_client or is_provider or user.is_admin):
        raise PaymentError("Receipt not found", 404)
    receipt = {
        "receipt_no": row["reference"], "kind": "refund", "refunded_at": row["completed_at"],
        "currency": row["currency"], "issued_by": _issuer(),
        "notice": "Money given back to the client for the payment below. It is not a tax credit note registered in "
                  "the Ministry of Revenues electronic invoicing system.",
        "original": {"receipt_no": row["tx_ref"], "amount": row["payment_amount"], "paid_at": row["paid_at"]},
        "client": {"name": row["client_name"], "email": row["client_email"]},
        "provider": {"name": row["provider_name"], "registration_no": row["provider_registration_no"],
                     "vat_number": row["provider_vat_number"]},
        "job": {"title": row["title"], "service": row["service_name"]},
        "reason": row["reason"],
        "lines": [{"label": "Service by " + (row["provider_name"] or "provider"), "amount": row["price_part"]}]
                 + ([{"label": f"VAT {row['vat_rate']:g}% charged by the provider", "amount": row["provider_vat"]}]
                    if row["provider_vat"] else []),
        "total": row["amount"],
        "method": row["method"],
        "to": ({"bank": row["client_bank_name"], "account_name": row["client_account_name"],
                "account_last4": row["client_account_last4"], "transfer_reference": row["transfer_reference"]}
               if row["method"] == "manual" else None),
        "reference": row["gateway_ref"],
    }
    if is_provider or user.is_admin:
        receipt["statement"] = {
            "commission": row["commission"], "commission_vat": row["commission_vat"],
            "provider_amount": row["provider_amount"], "provider_vat": row["provider_vat"],
        }
    return receipt
