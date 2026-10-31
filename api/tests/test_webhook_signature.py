"""Chapa webhook signatures: the body signature must match when sent; the fixed secret signature is only a fallback."""

import hashlib
import hmac

from config.config import settings
from services.payment_service.gateways import webhook_signature_ok

SECRET = "whsec-test-value"


def _sig(key: str, msg: bytes) -> str:
    return hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()


def test_body_signature_must_match_the_body(monkeypatch):
    monkeypatch.setattr(settings, "chapa_webhook_secret", SECRET)
    body = b'{"tx_ref":"cn-1","status":"success"}'
    assert webhook_signature_ok(body, {"x-chapa-signature": _sig(SECRET, body)})
    assert not webhook_signature_ok(b'{"tx_ref":"cn-2"}', {"x-chapa-signature": _sig(SECRET, body)})


def test_fixed_secret_signature_cannot_stand_in_for_the_body_signature(monkeypatch):
    monkeypatch.setattr(settings, "chapa_webhook_secret", SECRET)
    fixed = _sig(SECRET, SECRET.encode())
    body = b'{"tx_ref":"cn-3"}'
    # The fixed value in the body-signature header no longer passes
    assert not webhook_signature_ok(body, {"x-chapa-signature": fixed})
    # A wrong body signature is not rescued by a correct fixed one
    assert not webhook_signature_ok(body, {"x-chapa-signature": "bad", "chapa-signature": fixed})
    # Fallback: only the secret signature, in its own header
    assert webhook_signature_ok(body, {"chapa-signature": fixed})


def test_no_secret_configured_refuses_everything(monkeypatch):
    monkeypatch.setattr(settings, "chapa_webhook_secret", None)
    assert not webhook_signature_ok(b"{}", {"x-chapa-signature": "x", "chapa-signature": "y"})
