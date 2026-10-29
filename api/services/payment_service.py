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
from services import notifications
from services.db import Jsonb, connection, execute, fetch_all, fetch_one

log = logging.getLogger(__name__)

PAYABLE = ("accepted", "in_progress", "completed")
CHECKOUT_REUSE_MINUTES = 30


class PaymentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


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

    def initialize(self, *, tx_ref: str, **_) -> str:
        return f"{settings.web_base_url}/pay/test/{tx_ref}"

    def verify(self, tx_ref: str) -> dict:
        row = fetch_one("select raw, amount, currency from payments where tx_ref = %s", (tx_ref,)) or {}
        outcome = (row.get("raw") or {}).get("simulated_outcome")
        return {"status": outcome or "pending", "amount": row.get("amount"), "currency": row.get("currency"),
                "reference": f"SIM-{tx_ref[-8:].upper()}", "method": "test", "fee": None, "raw": {"simulated": True}}


class ChapaGateway:
    name = "chapa"

    def __init__(self) -> None:
        if not settings.chapa_secret_key:
            raise PaymentError("Payments are not set up yet (CHAPA_SECRET_KEY is missing)", 503)
        self.base = settings.chapa_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings.chapa_secret_key}", "Content-Type": "application/json"}

    def _call(self, method: str, path: str, json: dict | None = None) -> dict:
        try:
            r = httpx.request(method, f"{self.base}{path}", headers=self.headers, json=json, timeout=20)
        except httpx.HTTPError as exc:
            log.warning("Chapa unreachable: %s", exc)
            raise PaymentError("The payment service is not reachable right now. Please try again.", 502) from exc
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code >= 400 or str(body.get("status", "")).lower() == "failed":
            message = body.get("message")
            if isinstance(message, dict):
                message = "; ".join(f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in message.items())
            log.warning("Chapa %s %s -> %s %s", method, path, r.status_code, message)
            raise PaymentError(f"Payment service: {message or 'request failed'}", 502)
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
        try:
            data = self._call("GET", f"/transfers/verify/{reference}").get("data") or {}
        except PaymentError:
            return "approved"
        status = str(data.get("status", "")).lower()
        return "paid" if status == "success" else "failed" if status in ("failed", "cancelled", "reversed") else "approved"

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


def payout_view(provider: dict) -> dict:
    return {
        "ready": bool(provider.get("payout_ready")),
        "bank_name": provider.get("payout_bank_name"),
        "account_name": provider.get("payout_account_name"),
        "account_last4": provider.get("payout_account_last4"),
        "set_at": provider.get("payout_set_at"),
        "commission_percent": settings.platform_commission_percent,
        "mode": mode(),
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
    bank = next((b for b in gateway().banks() if b["code"] == str(bank_code)), None)
    if not bank:
        raise PaymentError("Choose your bank from the list")
    execute(
        """
        update providers set payout_account_enc = %s, payout_bank_code = %s, payout_bank_name = %s,
          payout_account_name = %s, payout_account_last4 = %s, payout_set_at = now(), updated_at = now()
        where id = %s
        """,
        (encrypt(account_number), str(bank_code), bank["name"], account_name.strip(), account_number[-4:], provider["id"]),
    )
    return payout_view(provider_service.get_for_user(user_id))


# ---------------------------------------------------------------- client payments

PAYMENT_COLUMNS = """
  id::text, engagement_id::text, tx_ref, gateway, amount::float, currency, price::float, vat_rate::float,
  provider_vat::float, commission_percent::float, commission_amount::float, commission_vat::float,
  provider_amount::float, provider_vat_number, status, checkout_url, gateway_reference, payment_method,
  gateway_fee::float, created_at, updated_at, verified_at
"""


def breakdown(price, provider_vat_registered: bool) -> dict:
    """Every amount in a payment, from the provider's agreed price (VAT Proclamation 1341/2024):
      client pays    price + provider VAT (only if the provider is VAT-registered)
      our commission price x commission %, plus VAT on it when we are VAT-registered
      provider gets  price - commission - VAT on commission + the provider VAT they collected (they file it)
    """
    price = _money(price)
    rate = Decimal(str(settings.vat_rate_percent))
    pct = Decimal(str(settings.platform_commission_percent))
    provider_vat = _money(price * rate / 100) if provider_vat_registered else Decimal("0.00")
    commission = _money(price * pct / 100)
    commission_vat = _money(commission * rate / 100) if settings.platform_vat_registered else Decimal("0.00")
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

    # Reuse a fresh checkout instead of creating a second payment for the same job
    pending = fetch_one(
        "select tx_ref, checkout_url from payments where engagement_id = %s and status = 'pending' "
        "and created_at > now() - make_interval(mins => %s) order by created_at desc limit 1",
        (engagement_id, CHECKOUT_REUSE_MINUTES),
    )
    if pending and pending["checkout_url"]:
        return {"tx_ref": pending["tx_ref"], "checkout_url": pending["checkout_url"]}
    # Older unfinished checkouts may have been paid after all: settle them before opening a new one
    for old in fetch_all("select tx_ref from payments where engagement_id = %s and status = 'pending'", (engagement_id,)):
        if confirm(old["tx_ref"])["status"] == "success":
            raise PaymentError("This job is already paid", 409)

    prov = fetch_one("select vat_registered, vat_number from providers where id = %s", (eng["provider_id"],)) or {}
    b = breakdown(eng["agreed_price"], bool(prov.get("vat_registered")))
    amount = b["total"]
    tx_ref = f"cn-{engagement_id[:8]}-{secrets.token_hex(5)}"
    gw = gateway()
    with connection() as conn, conn.transaction():
        # The amounts are frozen here, so the receipt never changes if rates change later
        conn.execute(
            """
            insert into payments (engagement_id, payer_user_id, tx_ref, gateway, amount, price, vat_rate, provider_vat,
              commission_percent, commission_amount, commission_vat, provider_amount, provider_vat_number)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (engagement_id, user.id, tx_ref, gw.name, amount, b["price"], b["vat_rate"], b["provider_vat"],
             b["commission_percent"], b["commission"], b["commission_vat"], b["provider_amount"],
             prov.get("vat_number") if prov.get("vat_registered") else None),
        )
        conn.execute("update engagements set payment_status = 'pending', updated_at = now() where id = %s",
                     (engagement_id,))
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
    result = (SimulatedGateway() if payment["gateway"] == "simulated" else ChapaGateway()).verify(tx_ref)
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
    with connection() as conn, conn.transaction():
        updated = conn.execute(
            """
            update payments set status = %s, gateway_reference = %s, payment_method = %s, gateway_fee = %s,
              raw = coalesce(raw, '{}'::jsonb) || %s, verified_at = now(), updated_at = now()
            where tx_ref = %s and status = 'pending' returning id
            """,
            (status, result.get("reference"), result.get("method"),
             _money(result["fee"]) if result.get("fee") not in (None, "") else None,
             Jsonb({"verify": result.get("raw")}), tx_ref),
        ).fetchone()
        if updated and status == "success":
            # Paying is the client's confirmation: the job closes and the provider's share is credited once
            eng_row = conn.execute(
                "update engagements set payment_status = 'paid', paid_at = now(), "
                "client_confirmed_at = coalesce(client_confirmed_at, now()), updated_at = now() "
                "where id = %s returning provider_id::text",
                (payment["engagement_id"],),
            ).fetchone()
            conn.execute(
                """
                insert into provider_ledger (provider_id, kind, amount, engagement_id, payment_id, note)
                values (%s, 'earning', %s, %s, %s, %s)
                on conflict do nothing
                """,
                (eng_row["provider_id"], payment["provider_amount"], payment["engagement_id"], updated["id"],
                 f"{payment['commission_percent']:g}% platform commission and VAT on it deducted"),
            )
        elif updated:
            conn.execute("update engagements set payment_status = 'unpaid', updated_at = now() where id = %s",
                         (payment["engagement_id"],))
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


def admin_list(status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    where, params = "true", []
    if status:
        where, params = "p.status = %s", [status]
    rows = fetch_all(
        f"""
        select p.tx_ref, p.gateway, p.amount::float, p.currency, p.commission_amount::float, p.provider_amount::float,
               p.status, p.payment_method, p.gateway_reference, p.created_at, p.verified_at,
               e.id::text as engagement_id, e.title, e.client_name, pr.display_name as provider_name, pr.slug as provider_slug
        from payments p join engagements e on e.id = p.engagement_id left join providers pr on pr.id = e.provider_id
        where {where} order by p.created_at desc limit %s offset %s
        """,
        (*params, limit, offset),
    )
    total = fetch_one(f"select count(*) as c from payments p where {where}", params)["c"]
    totals = fetch_one(
        """
        select count(*) filter (where status = 'success') as paid_count,
               coalesce(sum(amount) filter (where status = 'success'), 0)::float as gross,
               coalesce(sum(commission_amount) filter (where status = 'success'), 0)::float as commission,
               coalesce(sum(provider_amount) filter (where status = 'success'), 0)::float as to_providers,
               count(*) filter (where status = 'pending') as pending,
               count(*) filter (where status = 'failed') as failed
        from payments
        """
    )
    return {"items": rows, "total": total, "totals": totals, "mode": mode(),
            "commission_percent": settings.platform_commission_percent}


# ---------------------------------------------------------------- earnings and payouts

MIN_PAYOUT = Decimal("100")
PAYOUT_COLUMNS = """
  po.id::text, po.provider_id::text, po.amount::float, po.status, po.bank_name, po.account_name, po.account_last4,
  po.reference, po.gateway, po.gateway_reference, po.note, po.decided_by, po.decided_at, po.paid_at, po.created_at
"""


def _balances(provider_id: str) -> dict:
    row = fetch_one(
        """
        select coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s), 0)::float as balance,
               coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s and kind = 'earning'), 0)::float
                 as earned_total,
               coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s and kind = 'earning'
                         and created_at >= date_trunc('month', now())), 0)::float as earned_this_month,
               coalesce((select sum(amount) from payouts where provider_id = %(p)s and status in ('requested', 'approved')), 0)::float
                 as in_payout,
               coalesce((select -sum(amount) from provider_ledger where provider_id = %(p)s and kind = 'payout'), 0)::float
                 as paid_out
        """,
        {"p": provider_id},
    )
    # Money already asked for is held until the payout is paid or rejected
    row["available"] = round(row["balance"] - row["in_payout"], 2)
    return row


def earnings(user_id: str) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    ledger = fetch_all(
        """
        select l.id, l.kind, l.amount::float, l.note, l.created_at, e.title as job_title, e.client_name,
               p.amount::float as gross, p.commission_amount::float as commission, p.commission_vat::float,
               p.provider_vat::float, p.tx_ref, po.reference as payout_reference, po.id::text as payout_id
        from provider_ledger l
        left join engagements e on e.id = l.engagement_id
        left join payments p on p.id = l.payment_id
        left join payouts po on po.id = l.payout_id
        where l.provider_id = %s order by l.created_at desc limit 100
        """,
        (provider["id"],),
    )
    payouts = fetch_all(f"select {PAYOUT_COLUMNS} from payouts po where po.provider_id = %s order by po.created_at desc limit 50",
                        (provider["id"],))
    return {**_balances(provider["id"]), "ledger": ledger, "payouts": payouts, "min_payout": float(MIN_PAYOUT),
            "payout_account": payout_view(provider), "commission_percent": settings.platform_commission_percent}


def ledger_page(user_id: str, limit: int = 20, offset: int = 0) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    items = fetch_all(
        """
        select l.id, l.kind, l.amount::float, l.note, l.created_at, e.title as job_title, e.client_name,
               p.amount::float as gross, p.commission_amount::float as commission, p.commission_vat::float,
               p.provider_vat::float, p.tx_ref, po.reference as payout_reference, po.id::text as payout_id
        from provider_ledger l
        left join engagements e on e.id = l.engagement_id
        left join payments p on p.id = l.payment_id
        left join payouts po on po.id = l.payout_id
        where l.provider_id = %s order by l.created_at desc, l.id desc limit %s offset %s
        """,
        (provider["id"], limit, offset),
    )
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
    return {"total": total, "items": items}


def request_payout(user_id: str, amount: float) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    if not provider.get("payout_ready"):
        raise PaymentError("Add the bank account to send your money to first", 409)
    amount = _money(amount)
    if amount < MIN_PAYOUT:
        raise PaymentError(f"The smallest payout is {MIN_PAYOUT:,.0f} ETB")
    with connection() as conn, conn.transaction():
        # Lock the provider row so two requests at once can't both pass the balance check
        conn.execute("select 1 from providers where id = %s for update", (provider["id"],))
        available = Decimal(str(_balances(provider["id"])["available"]))
        if amount > available:
            raise PaymentError(f"You can withdraw up to {available:,.2f} ETB", 409)
        row = conn.execute(
            """
            insert into payouts (provider_id, amount, bank_code, bank_name, account_name, account_last4, reference)
            values (%s, %s, %s, %s, %s, %s, %s) returning id::text
            """,
            (provider["id"], amount, provider["payout_bank_code"], provider["payout_bank_name"],
             provider["payout_account_name"], provider["payout_account_last4"], f"po-{secrets.token_hex(8)}"),
        ).fetchone()
    admins = [r["id"] for r in fetch_all("select id::text from users where role = 'admin' and is_active")]
    notifications.notify(admins, kind="payout_request", title=f"Payout request: {amount:,.2f} ETB",
                         body=f"{provider['display_name']} to {provider['payout_bank_name']} ••••{provider['payout_account_last4']}",
                         link="/admin/marketplace/payouts")
    return fetch_one(f"select {PAYOUT_COLUMNS} from payouts po where po.id = %s", (row["id"],))


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
    totals = fetch_one(
        """
        select count(*) filter (where status = 'requested') as requested,
               coalesce(sum(amount) filter (where status = 'requested'), 0)::float as requested_amount,
               count(*) filter (where status = 'approved') as processing,
               coalesce(sum(amount) filter (where status = 'paid'), 0)::float as paid_amount,
               coalesce((select sum(amount) from provider_ledger), 0)::float as owed_to_providers
        from payouts
        """
    )
    return {"items": items, "total": total, "totals": totals, "mode": mode()}


def _mark_paid(payout: dict, gateway_reference: str | None) -> None:
    with connection() as conn, conn.transaction():
        done = conn.execute(
            "update payouts set status = 'paid', paid_at = now(), gateway_reference = coalesce(%s, gateway_reference) "
            "where id = %s and status in ('requested', 'approved') returning id",
            (gateway_reference, payout["id"]),
        ).fetchone()
        if done:
            conn.execute(
                "insert into provider_ledger (provider_id, kind, amount, payout_id, note) values (%s, 'payout', %s, %s, %s)",
                (payout["provider_id"], -Decimal(str(payout["amount"])), payout["id"],
                 f"Paid to {payout['bank_name']} ••••{payout['account_last4']}"),
            )


def _tell_provider(payout: dict, title: str, body: str | None = None) -> None:
    owner = fetch_one("select user_id::text from providers where id = %s", (payout["provider_id"],))
    if owner and owner["user_id"]:
        notifications.notify([owner["user_id"]], kind="payout", title=title, body=body, link="/me/provider?tab=earnings")


def decide_payout(payout_id: str, *, decision: str, note: str | None, actor: str) -> dict:
    """approve: send the money (simulated: paid at once; Chapa: queued, then refresh). reject: release it."""
    from core.crypto import decrypt

    payout = fetch_one(f"select {PAYOUT_COLUMNS}, po.bank_code from payouts po where po.id = %s", (payout_id,))
    if not payout:
        raise PaymentError("Payout not found", 404)
    if decision == "reject":
        if payout["status"] not in ("requested", "approved"):
            raise PaymentError("This payout was already decided", 409)
        if not (note or "").strip():
            raise PaymentError("Tell the provider why")
        execute("update payouts set status = 'rejected', note = %s, decided_by = %s, decided_at = now() where id = %s",
                (note.strip(), actor, payout_id))
        _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB was not approved", note.strip())
    elif decision == "approve":
        if payout["status"] != "requested":
            raise PaymentError("This payout was already decided", 409)
        provider = fetch_one("select payout_account_enc from providers where id = %s", (payout["provider_id"],))
        account = decrypt(provider and provider["payout_account_enc"])
        if not account:
            raise PaymentError("The provider's bank account can't be read; ask them to add it again", 409)
        execute("update payouts set status = 'approved', decided_by = %s, decided_at = now(), note = %s, gateway = %s "
                "where id = %s", (actor, (note or "").strip() or None, mode(), payout_id))
        try:
            result = gateway().transfer(account_name=payout["account_name"], account_number=account,
                                        bank_code=payout["bank_code"], amount=_money(payout["amount"]),
                                        reference=payout["reference"])
        except PaymentError as exc:
            execute("update payouts set status = 'failed', note = %s where id = %s", (str(exc)[:300], payout_id))
            _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB failed", "Our team will contact you.")
            raise
        if result["status"] == "paid":
            _mark_paid(payout, result.get("reference"))
            _tell_provider(payout, f"{payout['amount']:,.2f} ETB sent to your bank",
                           f"{payout['bank_name']} ••••{payout['account_last4']}")
        else:
            execute("update payouts set gateway_reference = %s where id = %s", (result.get("reference"), payout_id))
            _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB approved", "It is on its way to your bank.")
    elif decision == "refresh":
        if payout["status"] == "approved":
            status = gateway().verify_transfer(payout["reference"])
            if status == "paid":
                _mark_paid(payout, None)
                _tell_provider(payout, f"{payout['amount']:,.2f} ETB arrived in your bank",
                               f"{payout['bank_name']} ••••{payout['account_last4']}")
            elif status == "failed":
                execute("update payouts set status = 'failed' where id = %s", (payout_id,))
                _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB failed", "Our team will contact you.")
    else:
        raise PaymentError("Unknown decision")
    return fetch_one(f"select {PAYOUT_COLUMNS} from payouts po where po.id = %s", (payout_id,))


# ---------------------------------------------------------------- receipts

RECEIPT_NOTICE = ("This is a payment receipt from Compliance Navigator. It is not a tax invoice registered in the "
                  "Ministry of Revenues electronic invoicing system.")


def _issuer() -> dict:
    return {"legal_name": settings.platform_legal_name, "tin": settings.platform_tin,
            "vat_number": settings.platform_vat_number, "address": settings.platform_address,
            "vat_registered": settings.platform_vat_registered}


def payment_receipt(tx_ref: str, *, user) -> dict:
    """The client's receipt; the provider (and staff) also see their statement: commission, VAT on it, their share."""
    row = fetch_one(
        """
        select p.tx_ref, p.status, p.currency, p.amount::float, p.price::float, p.vat_rate::float, p.provider_vat::float,
               p.commission_percent::float, p.commission_amount::float, p.commission_vat::float, p.provider_amount::float,
               p.provider_vat_number, p.payment_method, p.gateway, p.gateway_reference, p.verified_at, p.updated_at,
               e.title, e.service_name, e.completion_note, e.client_name, e.client_user_id::text, u.email as client_email,
               pr.display_name as provider_name, pr.registration_no as provider_registration_no,
               pr.user_id::text as provider_user_id
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
