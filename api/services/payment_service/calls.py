"""A record of every HTTP call to Chapa, for the staff Payment health page (see health.py).

What is stored: the operation, a path template, our reference, the HTTP status, how long it took and
Chapa's message. Never the secret key, the request body, account numbers, emails or phone numbers.
Recording runs in its own short transaction and swallows every error, so it can't break or hold up a payment.
"""

from __future__ import annotations

import logging
import re

from services.db import connection

log = logging.getLogger(__name__)

OPERATIONS = ("initialize", "verify", "transfer", "verify_transfer", "refund", "verify_refund", "banks", "other")

# Waiting for a free database connection or a slow insert must never hold up a payment
POOL_WAIT_SECONDS = 1.0
STATEMENT_TIMEOUT_MS = 2000
ERROR_LIMIT = 500

_REF = re.compile(r"[^A-Za-z0-9._-]")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
# A long run of digits in a message can be an account or phone number: keep only the last 4
_DIGITS = re.compile(r"(?<![A-Za-z0-9])\d{7,}(?![A-Za-z0-9])")
_LONG_SEGMENT = re.compile(r"/[^/?#]*\d[^/?#]{5,}")


def _clean_ref(value) -> str | None:
    if value is None:
        return None
    text = _REF.sub("", str(value))[:120]
    return text or None


def describe(method: str, path: str, json: dict | None = None, data: dict | None = None) -> dict:
    """Which operation a Chapa call is, a path template without the reference, and our reference."""
    path = path.split("?", 1)[0].split("#", 1)[0]
    method = method.upper()
    parts = [p for p in path.split("/") if p]
    body = json if isinstance(json, dict) else data if isinstance(data, dict) else {}
    operation, template, reference = "other", None, None
    if method == "GET" and parts == ["banks"]:
        operation, template = "banks", "/banks"
    elif method == "POST" and parts == ["transaction", "initialize"]:
        operation, template, reference = "initialize", "/transaction/initialize", body.get("tx_ref")
    elif method == "GET" and len(parts) == 3 and parts[:2] == ["transaction", "verify"]:
        operation, template, reference = "verify", "/transaction/verify/{ref}", parts[2]
    elif method == "POST" and parts == ["transfers"]:
        operation, template, reference = "transfer", "/transfers", body.get("reference")
    elif method == "GET" and len(parts) == 3 and parts[:2] == ["transfers", "verify"]:
        operation, template, reference = "verify_transfer", "/transfers/verify/{ref}", parts[2]
    elif method == "GET" and len(parts) == 3 and parts[0] == "refund" and parts[2] == "verify":
        operation, template, reference = "verify_refund", "/refund/{ref}/verify", parts[1]
    elif method == "POST" and len(parts) == 2 and parts[0] == "refund":
        # Our refund reference names the refund; the payment's tx_ref is in the path
        operation, template, reference = "refund", "/refund/{tx_ref}", body.get("reference") or parts[1]
    if template is None:
        # Anything else: drop path parts that carry numbers or ids, they could be personal
        template = _LONG_SEGMENT.sub("/{id}", path)[:200] or "/"
    return {"operation": operation, "method": method[:10], "path": template, "reference": _clean_ref(reference)}


def clean_error(message) -> str | None:
    """Chapa's message, trimmed, with emails and long digit runs (account or phone numbers) masked."""
    if message is None:
        return None
    text = str(message).strip()
    if not text:
        return None
    text = _EMAIL.sub("[email]", text)
    text = _DIGITS.sub(lambda m: "••••" + m.group(0)[-4:], text)
    return text[:ERROR_LIMIT]


def record(*, gateway: str, method: str, path: str, json: dict | None = None, data: dict | None = None,
           http_status: int | None, ok: bool, uncertain: bool = False, error=None, duration_ms: int = 0,
           is_test: bool = False) -> None:
    """Store one call. Never raises: a recording problem is logged and the payment carries on."""
    try:
        info = describe(method, path, json, data)
        with connection(timeout=POOL_WAIT_SECONDS) as conn, conn.transaction():
            conn.execute(f"set local statement_timeout = {STATEMENT_TIMEOUT_MS}")
            conn.execute(
                "insert into gateway_calls (gateway, operation, method, path, reference, http_status, ok, uncertain, "
                "error, duration_ms, is_test) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (gateway, info["operation"], info["method"], info["path"], info["reference"], http_status, ok,
                 uncertain, None if ok else clean_error(error), max(int(duration_ms), 0), is_test),
            )
    except Exception:
        log.warning("Could not record a %s call (%s %s)", gateway, method, path.split("?", 1)[0], exc_info=True)


def prune(days: int = 90) -> int:
    """Remove calls older than this many days (runs in the daily maintenance)."""
    with connection() as conn:
        return conn.execute("delete from gateway_calls where created_at < now() - make_interval(days => %s)",
                            (days,)).rowcount
