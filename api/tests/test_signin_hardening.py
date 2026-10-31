"""Email verification, no account enumeration, production config guard, rate limits, Fayda sandbox, webhook replays."""

import hashlib
import hmac
import io
import json
import logging
import uuid

import pytest

from auth import service as auth_service
from config.config import Settings
from conftest import API, LEGAL_ACCEPT
from core import ratelimit
from services import id_verification
from services.db import execute, fetch_one


@pytest.fixture
def outbox(monkeypatch):
    """Emails the API would send, captured instead of sent."""
    sent: list[auth_service.Email] = []
    monkeypatch.setattr(auth_service, "send_email", sent.append)
    return sent


@pytest.fixture
def limits_on(monkeypatch):
    monkeypatch.setattr(ratelimit, "ENABLED", True)
    yield
    execute("delete from rate_limit_counters where key = 'ip:testclient'")


def _cleanup(email: str) -> None:
    execute("delete from user_consents where user_id in (select id from users where lower(email) = lower(%s))", (email,))
    execute("delete from users where lower(email) = lower(%s)", (email,))


def _token(email_text: str) -> str:
    return email_text.split("token=")[1].split()[0]


# ---------------------------------------------------------------- sign-up and verification


def test_register_answers_the_same_for_new_and_taken_emails(client, make_user, outbox):
    existing = make_user()
    new_email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    try:
        body = {"password": "good-pass-1", "fullname": "Someone", "accept": LEGAL_ACCEPT}
        new = client.post(f"{API}/auth/register", json={**body, "email": new_email})
        taken = client.post(f"{API}/auth/register", json={**body, "email": existing["email"].upper()})
        assert new.status_code == taken.status_code == 201
        assert new.json() == taken.json() == {"message": "success", "payload": {"message": "Check your email to continue."}}
        assert "set-cookie" not in new.headers and "set-cookie" not in taken.headers
        # Nothing new for the taken address; its owner is told instead, and the new one gets a link
        assert fetch_one("select count(*) as c from users where lower(email) = lower(%s)", (existing["email"],))["c"] == 1
        to = {m.to: m for m in outbox}
        assert "already have one" in to[existing["email"]].text and "token=" not in to[existing["email"]].text
        assert "/verify-email?token=" in to[new_email].text
        # The owner's password still works and nothing about their account changed
        assert client.post(f"{API}/auth/login", json={"email": existing["email"], "password": existing["password"]}).status_code == 200
    finally:
        _cleanup(new_email)


def test_verification_link_works_once_and_unlocks_gated_actions(client, make_user, outbox):
    user = make_user(verified=False)
    me = client.get(f"{API}/auth/me", headers=user["headers"]).json()["payload"]["user"]
    assert me["emailVerified"] is False

    # Gated while unverified: becoming a provider, creating an organization, payouts
    org = {"name": f"Test Office {uuid.uuid4().hex[:6]}", "org_type": "sub_city_office", "representative_name": "A B",
           "representative_title": "Head", "official_email": "office@example.gov.et", "branches": []}
    gated = [
        client.post(f"{API}/organizations", data={"data": json.dumps(org)}, headers=user["headers"]),
        client.post(f"{API}/providers/join", data={"data": "{}"}, headers=user["headers"]),
        client.post(f"{API}/providers/me/payouts", json={"amount": 100}, headers=user["headers"]),
    ]
    for r in gated:
        assert r.status_code == 403 and "Confirm your email" in r.json()["detail"], r.text

    r = client.post(f"{API}/auth/verify-email/resend", headers=user["headers"])
    assert r.status_code == 202 and r.json()["payload"]["sent"]
    first = _token(outbox[-1].text)
    client.post(f"{API}/auth/verify-email/resend", headers=user["headers"])
    newest = _token(outbox[-1].text)
    # Only the newest link works
    assert client.post(f"{API}/auth/verify-email", json={"token": first}).status_code == 400
    r = client.post(f"{API}/auth/verify-email", json={"token": newest})
    assert r.status_code == 200 and r.json()["payload"]["user"]["emailVerified"] is True
    assert client.post(f"{API}/auth/verify-email", json={"token": newest}).status_code == 400

    assert client.get(f"{API}/auth/me", headers=user["headers"]).json()["payload"]["user"]["emailVerified"] is True
    r = client.post(f"{API}/organizations", data={"data": json.dumps(org)}, headers=user["headers"])
    assert r.status_code == 201, r.text
    # Already confirmed: nothing more to send
    assert client.post(f"{API}/auth/verify-email/resend", headers=user["headers"]).json()["payload"]["alreadyVerified"]


def test_expired_verification_link_is_refused(client, make_user, outbox):
    user = make_user(verified=False)
    client.post(f"{API}/auth/verify-email/resend", headers=user["headers"])
    token = _token(outbox[-1].text)
    execute("update email_verification_tokens set expires_at = now() - interval '1 minute' where user_id = %s", (user["id"],))
    assert client.post(f"{API}/auth/verify-email", json={"token": token}).status_code == 400
    assert client.get(f"{API}/auth/me", headers=user["headers"]).json()["payload"]["user"]["emailVerified"] is False


def test_unverified_member_cannot_accept_an_org_invite(client, make_user):
    owner, invitee = make_user(), make_user(verified=False)
    org = client.post(f"{API}/organizations", headers=owner["headers"], data={"data": json.dumps({
        "name": f"Test Office {uuid.uuid4().hex[:6]}", "org_type": "sub_city_office", "representative_name": "A B",
        "representative_title": "Head", "official_email": "office@example.gov.et", "branches": []})}).json()["payload"]["organization"]
    r = client.post(f"{API}/org/{org['id']}/members", json={"email": invitee["email"], "role": "editor"}, headers=owner["headers"])
    assert r.status_code == 200, r.text
    invite = client.get(f"{API}/organizations/mine", headers=invitee["headers"]).json()["payload"]["invites"][0]
    r = client.post(f"{API}/organizations/invites/{invite['id']}/accept", headers=invitee["headers"])
    assert r.status_code == 403


def test_forgot_password_is_the_same_for_unknown_emails(client, make_user, outbox):
    user = make_user()
    outbox.clear()  # the sign-up confirmation
    known = client.post(f"{API}/auth/forgot-password", json={"email": user["email"]})
    unknown = client.post(f"{API}/auth/forgot-password", json={"email": f"nobody-{uuid.uuid4().hex[:8]}@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [m.to for m in outbox] == [user["email"]]
    execute("delete from password_reset_tokens where user_id = %s", (user["id"],))


def test_links_are_never_logged_in_production(monkeypatch, caplog):
    from config.config import settings

    monkeypatch.setattr(settings, "smtp_host", None)
    email = auth_service.Email(to="someone@example.com", subject="Reset", text="https://x/reset-password?token=secret-123")
    monkeypatch.setattr(settings, "environment", "production")
    with caplog.at_level(logging.DEBUG):
        auth_service.send_email(email)
    assert "secret-123" not in caplog.text and "someone@example.com" not in caplog.text
    caplog.clear()
    monkeypatch.setattr(settings, "environment", "development")
    with caplog.at_level(logging.DEBUG):
        auth_service.send_email(email)
    assert "secret-123" in caplog.text and "DEVELOPMENT ONLY" in caplog.text


# ---------------------------------------------------------------- rate limits


def test_forgot_password_is_rate_limited_with_retry_after(client, limits_on, outbox, monkeypatch):
    monkeypatch.setitem(ratelimit.RULES, "forgot_password", (ratelimit.Rule(2, 3600),))
    execute("delete from rate_limit_counters where bucket like 'forgot_password/%%' and key = 'ip:testclient'")
    codes = [client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"}) for _ in range(3)]
    assert [r.status_code for r in codes] == [202, 202, 429]
    assert int(codes[-1].headers["retry-after"]) >= 1


def test_limits_count_per_user_when_signed_in(client, make_user, limits_on, monkeypatch):
    a, b = make_user(verified=False), make_user(verified=False)
    monkeypatch.setitem(ratelimit.RULES, "verify_resend", (ratelimit.Rule(1, 3600),))
    monkeypatch.setattr(auth_service, "send_email", lambda e: None)
    assert client.post(f"{API}/auth/verify-email/resend", headers=a["headers"]).status_code == 202
    assert client.post(f"{API}/auth/verify-email/resend", headers=a["headers"]).status_code == 429
    # Same IP, different person: their own allowance
    assert client.post(f"{API}/auth/verify-email/resend", headers=b["headers"]).status_code == 202
    execute("delete from rate_limit_counters where key = any(%s)", ([f"user:{a['id']}", f"user:{b['id']}"],))


def test_limiter_windows_and_once():
    key = f"test-{uuid.uuid4().hex}"
    rules = (ratelimit.Rule(2, 60),)
    try:
        ratelimit.ENABLED, before = True, ratelimit.ENABLED
        assert ratelimit.hit("test", key, rules) is None
        assert ratelimit.hit("test", key, rules) is None
        assert 1 <= ratelimit.hit("test", key, rules) <= 60
    finally:
        ratelimit.ENABLED = before
        execute("delete from rate_limit_counters where key = %s", (key,))
    assert ratelimit.once("test", key, 60) and not ratelimit.once("test", key, 60)
    ratelimit.forget("test", key)
    assert ratelimit.once("test", key, 60)
    execute("delete from once_keys where key = %s", (key,))


def test_transcribe_refuses_large_uploads(client, make_user, monkeypatch):
    from api.v1 import chat

    monkeypatch.setattr(chat, "MAX_AUDIO_BYTES", 1000)
    user = make_user()
    r = client.post(f"{API}/chat/transcribe", files={"file": ("a.webm", io.BytesIO(b"x" * 1001), "audio/webm")},
                    headers=user["headers"])
    assert r.status_code == 413


def test_webhook_replay_is_handled_once(client, monkeypatch):
    from config.config import settings
    from services import payment_service

    monkeypatch.setattr(settings, "chapa_webhook_secret", "whsec-test")
    body = json.dumps({"event": "charge.success", "tx_ref": f"cn-test-{uuid.uuid4().hex[:8]}"}).encode()
    calls = []
    monkeypatch.setattr(payment_service, "get", lambda tx_ref: {"tx_ref": tx_ref})
    monkeypatch.setattr(payment_service, "confirm", lambda tx_ref: calls.append(tx_ref))
    sig = hmac.new(b"whsec-test", body, hashlib.sha256).hexdigest()
    try:
        first = client.post(f"{API}/payments/chapa/webhook", content=body, headers={"x-chapa-signature": sig})
        again = client.post(f"{API}/payments/chapa/webhook", content=body, headers={"x-chapa-signature": sig})
        assert first.status_code == again.status_code == 200
        assert again.json()["payload"].get("duplicate") and len(calls) == 1
    finally:
        execute("delete from once_keys where bucket = 'chapa_webhook' and key = %s", (hashlib.sha256(body).hexdigest(),))


# ---------------------------------------------------------------- Fayda sandbox


def test_sandbox_never_runs_in_production(monkeypatch):
    from config.config import settings

    monkeypatch.setattr(settings, "fayda_mode", "sandbox")
    monkeypatch.setattr(settings, "environment", "production")
    assert id_verification.mode() == "off"
    monkeypatch.setattr(settings, "environment", "development")
    assert id_verification.mode() == "sandbox"


def test_sandbox_ids_show_as_test_and_are_retired_when_live(client, make_user, monkeypatch):
    from config.config import settings
    from fayda_helpers import sandbox_verify
    from test_providers import _accept_agreement

    user = make_user()
    _accept_agreement(client, user)
    assert sandbox_verify(client, user, name="Abebe Kebede").status_code == 200
    data = {"provider_type": "guday_geday", "entity_type": "individual", "display_name": "Abebe Kebede",
            "phone": "0911000000", "service_areas": ["bole"], "service_ids": ["mesob-728"]}
    r = client.post(f"{API}/providers/join", data={"data": json.dumps(data)}, headers=user["headers"])
    assert r.status_code == 201, r.text
    provider = r.json()["payload"]["provider"]
    # The public badge reads "Test ID only", never "ID verified"
    assert provider["id_verified"] and provider["id_test"]

    # Switching Fayda to live retires every sandbox check; snapshot the developer's own rows and put them back
    before_ids = [r["id"] for r in fetch_all_rows(
        "select id::text from id_verifications where method = 'fayda_sandbox' and status = 'verified'")]
    before_providers = [r["id"] for r in fetch_all_rows(
        "select id::text from providers where id_verification_method = 'fayda_sandbox' and national_id_verified")]
    monkeypatch.setattr(settings, "fayda_mode", "live")
    try:
        assert id_verification.retire_sandbox_verifications() >= 1
        row = fetch_one("select national_id_verified from providers where id = %s", (provider["id"],))
        assert row["national_id_verified"] is False
        assert id_verification.current(user["id"]) is None
    finally:
        execute("update id_verifications set status = 'verified', error = null where id = any(%s::uuid[])", (before_ids,))
        execute("update providers set national_id_verified = true where id = any(%s::uuid[])", (before_providers,))
    monkeypatch.setattr(settings, "fayda_mode", "sandbox")
    assert id_verification.retire_sandbox_verifications() == 0


def fetch_all_rows(sql: str) -> list[dict]:
    from services.db import fetch_all

    return fetch_all(sql)


def _production_kwargs(**overrides) -> dict:
    good = dict(
        environment="production", secret_key="x" * 40,
        minio_access_key="minio-key", minio_secret_key="minio-secret-value",
        database_url="postgresql://app:strong-password@db:5432/cn", auth_cookie_secure=True,
        cors_origins="https://navigator.example,https://admin.navigator.example",
        web_base_url="https://navigator.example", admin_base_url="https://admin.navigator.example",
        api_public_url="https://api.navigator.example", payments_mode="chapa", chapa_secret_key="CHASECK-live",
        chapa_webhook_secret="whsec", fayda_mode="live", fayda_client_id="id", fayda_authorize_url="https://f/a",
        fayda_token_url="https://f/t", fayda_userinfo_url="https://f/u", fayda_jwks_url="https://f/j",
        fayda_private_key="-----BEGIN KEY-----", fayda_issuer="https://f", fayda_redirect_uri="https://navigator.example/cb",
        id_hash_pepper="pepper", payout_encryption_key="fernet-key", smtp_host="smtp.example", log_level="INFO", demo_password=None,
    )
    return {**good, **overrides}


def test_production_config_guard_accepts_a_good_config():
    assert Settings(_env_file=None, **_production_kwargs()).production_problems() == []


def test_development_stays_permissive():
    s = Settings(_env_file=None, **_production_kwargs(environment="development", secret_key="change-me", payments_mode="simulated",
                                                      fayda_mode="sandbox", smtp_host=None, demo_password="demo"))
    assert s.production_problems() == []
    s.check_production()


@pytest.mark.parametrize("override, needle", [
    ({"secret_key": "change-me-in-production-but-long-enough-to-pass"}, "SECRET_KEY"),
    ({"secret_key": "short"}, "SECRET_KEY"),
    ({"minio_access_key": "minioadmin"}, "MINIO"),
    ({"database_url": "postgresql://navigator:navigator@localhost:5433/cn"}, "DATABASE_URL"),
    ({"database_url": "postgresql://navigator:change-me-postgres-password@db/cn"}, "DATABASE_URL"),
    ({"auth_cookie_secure": False}, "AUTH_COOKIE_SECURE"),
    ({"cors_origins": "https://navigator.example,http://localhost:3000"}, "CORS_ORIGINS"),
    ({"cors_origins": "*"}, "CORS_ORIGINS"),
    ({"cors_origins": "http://navigator.example"}, "CORS_ORIGINS"),
    ({"web_base_url": "http://navigator.example"}, "WEB_BASE_URL"),
    ({"admin_base_url": "http://admin.example"}, "ADMIN_BASE_URL"),
    ({"api_public_url": "http://api.example"}, "API_PUBLIC_URL"),
    ({"payments_mode": "simulated"}, "PAYMENTS_MODE"),
    ({"chapa_secret_key": "CHASECK_TEST-abc"}, "CHAPA_SECRET_KEY"),
    ({"chapa_secret_key": None}, "CHAPA_SECRET_KEY"),
    ({"chapa_webhook_secret": None}, "CHAPA_WEBHOOK_SECRET"),
    ({"fayda_mode": "sandbox"}, "FAYDA_MODE"),
    ({"fayda_jwks_url": None}, "FAYDA_JWKS_URL"),
    ({"fayda_issuer": None}, "FAYDA_ISSUER"),
    ({"id_hash_pepper": None}, "ID_HASH_PEPPER"),
    ({"smtp_host": None}, "SMTP_HOST"),
    ({"log_level": "debug"}, "LOG_LEVEL"),
    ({"demo_password": "demo-pass"}, "DEMO_PASSWORD"),
])
def test_production_config_guard_refuses(override, needle):
    problems = Settings(_env_file=None, **_production_kwargs(**override)).production_problems()
    assert any(needle in p for p in problems), problems


def test_production_guard_lists_every_problem_in_one_error():
    s = Settings(_env_file=None, **_production_kwargs(secret_key="change-me", smtp_host=None, payments_mode="off"))
    with pytest.raises(RuntimeError) as exc:
        s.check_production()
    text = str(exc.value)
    assert "SECRET_KEY" in text and "SMTP_HOST" in text and "PAYMENTS_MODE" in text
