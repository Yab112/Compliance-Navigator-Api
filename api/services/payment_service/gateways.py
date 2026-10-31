"""Payment gateways (simulated and Chapa), the payment error and the mode switch."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import time
from decimal import ROUND_HALF_UP, Decimal

import httpx

from config.config import settings
from services.db import fetch_one

from . import calls

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


# Connect fails fast when Chapa is down; a slow answer still gets a fair wait. A timeout stays "uncertain".
CHAPA_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

# Domains Chapa refuses as an email (reserved test domains, and any it refused before in this process)
_RESERVED_EMAIL = re.compile(r"(^|\.)(example\.(com|net|org)|example|test|invalid|localhost)$")
_rejected_email_domains: set[str] = set()


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower()


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
        self.last_status: int | None = None  # the HTTP status of the last answer (the Payment health check shows it)

    def _note(self, method: str, path: str, json: dict | None, data: dict | None, started: float, **outcome) -> None:
        """Record the call for the Payment health page. A recording problem never reaches the payment."""
        try:
            calls.record(gateway=self.name, method=method, path=path, json=json, data=data,
                         duration_ms=round((time.monotonic() - started) * 1000),
                         is_test=(settings.chapa_secret_key or "").startswith("CHASECK_TEST"), **outcome)
        except Exception:
            log.warning("Could not record a Chapa call", exc_info=True)

    def _call(self, method: str, path: str, json: dict | None = None, data: dict | None = None) -> dict:
        headers = self.headers if data is None else {"Authorization": self.headers["Authorization"]}
        started = time.monotonic()
        try:
            r = httpx.request(method, f"{self.base}{path}", headers=headers, json=json, data=data,
                              timeout=CHAPA_TIMEOUT)
        except httpx.HTTPError as exc:
            # A timeout can come after Chapa already accepted the request
            log.warning("Chapa unreachable: %s", exc)
            self._note(method, path, json, data, started, http_status=None, ok=False, uncertain=True,
                       error=f"No answer from Chapa ({type(exc).__name__}){f': {exc}' if str(exc) else ''}")
            raise PaymentError("The payment service is not reachable right now. Please try again.", 502,
                               uncertain=True) from exc
        self.last_status = r.status_code
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
            self._note(method, path, json, data, started, http_status=r.status_code, ok=False,
                       uncertain=r.status_code >= 500, error=message or f"HTTP {r.status_code} without a message")
            raise PaymentError(f"Payment service: {message or 'request failed'}", 502, uncertain=r.status_code >= 500,
                               gateway_status=r.status_code)
        self._note(method, path, json, data, started, http_status=r.status_code, ok=True)
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

    @staticmethod
    def _plain(text: str, limit: int, fallback: str) -> str:
        """Chapa's customization fields take only English letters, digits, spaces, hyphens, underscores and dots.
        Anything else (punctuation, Amharic) becomes a space so a job title can never block a payment."""
        cleaned = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ._-]", " ", text or "")).strip()[:limit].strip()
        return cleaned or fallback

    def initialize(self, *, tx_ref: str, amount: Decimal, email: str | None, first_name: str, last_name: str,
                   phone: str | None, return_url: str, callback_url: str, title: str, reason: str) -> str:
        payload = {
            "amount": str(amount), "currency": "ETB", "tx_ref": tx_ref, "first_name": first_name or "Client",
            "last_name": last_name or "", "return_url": return_url, "callback_url": callback_url,
            "customization": {"title": self._plain(title, 16, "Payment"),
                              "description": self._plain(reason, 50, "Payment for a job")},
            "meta": {"payment_reason": reason[:100]},
        }
        # The email is optional: leave out one Chapa is known to refuse instead of asking twice
        if email and not (_RESERVED_EMAIL.search(_email_domain(email)) or _email_domain(email) in _rejected_email_domains):
            payload["email"] = email
        if phone and re.fullmatch(r"0[79]\d{8}", phone):
            payload["phone_number"] = phone
        try:
            body = self._call("POST", "/transaction/initialize", payload)
        except PaymentError as exc:
            # Chapa rejects some valid addresses (e.g. @example.com); the email is optional, so pay without it
            if "email" not in str(exc).lower() or "email" not in payload:
                raise
            _rejected_email_domains.add(_email_domain(payload.pop("email")))
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
    """
    Chapa sends x-chapa-signature (HMAC SHA256 of the body) and Chapa-Signature (HMAC SHA256 of the secret).
    The body signature proves this exact message, so when it is sent it must match. The secret signature is
    the same for every message, so it is only accepted when no body signature came, and only in its own header.
    Either way the payment is confirmed with Chapa before anything is recorded.
    """
    secret = (settings.chapa_webhook_secret or "").encode()
    if not secret:
        return False
    body_sent, secret_sent = headers.get("x-chapa-signature"), headers.get("chapa-signature")
    if body_sent:
        return hmac.compare_digest(body_sent, hmac.new(secret, raw_body, hashlib.sha256).hexdigest())
    return bool(secret_sent) and hmac.compare_digest(secret_sent, hmac.new(secret, secret, hashlib.sha256).hexdigest())
