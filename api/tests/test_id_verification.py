import json

from conftest import API
from fayda_helpers import random_fin, sandbox_verify, start_state
from services.db import execute, fetch_one

PASSPORT_RENEWAL = "mesob-728"


def _all_text(client, user, admin=None, agent_id=None) -> str:
    """Every response that could carry the ID number, concatenated."""
    out = [client.get(f"{API}/guday/fayda/status", headers=user["headers"]).text,
           client.get(f"{API}/providers/me", headers=user["headers"]).text]
    if admin and agent_id:
        out.append(client.get(f"{API}/admin/marketplace/providers/{agent_id}", headers=admin["headers"]).text)
        out.append(client.get(f"{API}/admin/marketplace/providers", headers=admin["headers"]).text)
    return "".join(out)


def test_sandbox_happy_path_and_masking(client, make_user):
    user = make_user()
    status = client.get(f"{API}/guday/fayda/status", headers=user["headers"]).json()["payload"]
    assert status["mode"] == "sandbox" and status["required"] and status["verification"] is None

    fin = random_fin()
    r = sandbox_verify(client, user, fin=fin, name="Abebe Kebede")
    assert r.status_code == 200, r.text
    v = r.json()["payload"]["verification"]
    assert v["method"] == "fayda_sandbox" and v["id_type"] == "FIN" and v["id_last4"] == fin[-4:]
    assert v["masked_id"].endswith(fin[-4:]) and fin not in r.text
    assert fin not in _all_text(client, user)


def test_wrong_otp_and_state_reuse(client, make_user):
    user = make_user()
    state = start_state(client, user)
    body = {"state": state, "id_number": random_fin(), "full_name": "Abebe Kebede", "otp": "000000"}
    bad = client.post(f"{API}/guday/fayda/sandbox/complete", json=body, headers=user["headers"])
    assert bad.status_code == 400 and "111111" in bad.json()["detail"] and "2 tries left" in bad.json()["detail"]
    # A wrong code can be corrected on the same verification
    fixed = client.post(f"{API}/guday/fayda/sandbox/complete", json={**body, "otp": "111111"}, headers=user["headers"])
    assert fixed.status_code == 200, fixed.text
    # A finished verification can't be used again
    again = client.post(f"{API}/guday/fayda/sandbox/complete", json={**body, "otp": "111111"}, headers=user["headers"])
    assert again.status_code == 409 and "start" in again.json()["detail"]

    # Three wrong codes burn the state, and the right code after that is refused
    burn = start_state(client, user)
    tries = [client.post(f"{API}/guday/fayda/sandbox/complete", json={**body, "state": burn},
                         headers=user["headers"]) for _ in range(3)]
    assert [t.status_code for t in tries] == [400, 400, 409]
    assert "1 try left" in tries[1].json()["detail"] and "start" in tries[2].json()["detail"]
    late = client.post(f"{API}/guday/fayda/sandbox/complete", json={**body, "state": burn, "otp": "111111"},
                       headers=user["headers"])
    assert late.status_code == 409

    # Another user's state is rejected
    other = make_user()
    state2 = start_state(client, user)
    stolen = client.post(f"{API}/guday/fayda/sandbox/complete",
                         json={**body, "state": state2, "otp": "111111"}, headers=other["headers"])
    assert stolen.status_code == 400

    # Expired state
    state3 = start_state(client, user)
    execute("update id_verifications set expires_at = now() - interval '1 minute' where state = %s", (state3,))
    expired = client.post(f"{API}/guday/fayda/sandbox/complete",
                          json={**body, "state": state3, "otp": "111111"}, headers=user["headers"])
    assert expired.status_code == 410

    # Bad number format
    bad_num = sandbox_verify(client, user, fin="12345")
    assert bad_num.status_code in (400, 422)


def test_same_id_cannot_verify_two_accounts(client, make_user):
    a, b = make_user(), make_user()
    fin = random_fin()
    assert sandbox_verify(client, a, fin=fin).status_code == 200
    dup = sandbox_verify(client, b, fin=fin)
    assert dup.status_code == 409
    # Re-verifying the same person on the same account is fine
    assert sandbox_verify(client, a, fin=fin).status_code == 200


def test_agent_registration_requires_verification(client, make_user):
    admin, user = make_user("admin"), make_user()
    data = {"provider_type": "guday_geday", "entity_type": "individual", "display_name": "Abebe Kebede", "telegram_username": "abebe_tg",
            "phone": "0911000000", "service_areas": ["bole"],
            "service_ids": [PASSPORT_RENEWAL], "national_id": "TYPED-123456"}
    from test_providers import _accept_agreement

    _accept_agreement(client, user)
    blocked = client.post(f"{API}/providers/join", data={"data": json.dumps(data)}, headers=user["headers"])
    assert blocked.status_code == 400

    fin = random_fin()
    assert sandbox_verify(client, user, fin=fin, name="Abebe Kebede").status_code == 200
    # No ID document needed once verified; the typed national_id is ignored
    r = client.post(f"{API}/providers/join", data={"data": json.dumps(data)}, headers=user["headers"])
    assert r.status_code == 201, r.text
    agent = r.json()["payload"]["provider"]
    assert agent["id_verified"] and agent["id_verification_method"] == "fayda_sandbox"
    assert agent["verified_name"] == "Abebe Kebede"

    detail = client.get(f"{API}/admin/marketplace/providers/{agent['id']}", headers=admin["headers"]).json()["payload"]["provider"]
    assert detail["national_id_last4"] == fin[-4:] and "national_id" not in detail
    from services import id_verification

    stored = fetch_one("select national_id, national_id_hash from providers where id = %s", (agent["id"],))
    assert stored["national_id"] is None and stored["national_id_hash"] == id_verification._hash_id(fin)
    assert detail["name_mismatch"] is False
    assert fin not in _all_text(client, user, admin, agent["id"])

    # Approved agents show as ID-verified publicly (once their vetting documents are checked)
    from test_providers import _vet

    _vet(agent["id"])
    client.post(f"{API}/admin/marketplace/providers/{agent['id']}/review", json={"action": "approve", "note": "Fayda verified, references checked"}, headers=admin["headers"])
    public = client.get(f"{API}/providers/{agent['slug']}").json()["payload"]["provider"]
    assert public["id_verified"] is True and "national_id" not in public


def test_name_mismatch_flagged(client, make_user):
    admin, user = make_user("admin"), make_user()
    assert sandbox_verify(client, user, name="Sara Tesfaye").status_code == 200
    data = {"provider_type": "guday_geday", "entity_type": "individual", "display_name": "Abebe Kebede", "telegram_username": "abebe_tg",
            "phone": "0911000000", "service_areas": ["bole"], "service_ids": [PASSPORT_RENEWAL]}
    from test_providers import _accept_agreement

    _accept_agreement(client, user)
    agent = client.post(f"{API}/providers/join", data={"data": json.dumps(data)}, headers=user["headers"]).json()["payload"]["provider"]
    detail = client.get(f"{API}/admin/marketplace/providers/{agent['id']}", headers=admin["headers"]).json()["payload"]["provider"]
    assert detail["name_mismatch"] is True


def test_goal_service_endpoint(client):
    r = client.get(f"{API}/catalog/goal-service/passport?sub_city=bole")
    assert r.status_code == 200
    p = r.json()["payload"]
    assert p["service"]["id"] == PASSPORT_RENEWAL and isinstance(p["agents"], list)
    none = client.get(f"{API}/catalog/goal-service/kebele_id").json()["payload"]
    assert none["service"] is None


def test_typed_national_id_is_stored_only_as_hash_and_last4(client, make_user):
    """With Fayda off, the typed number is hashed; staff find the provider by the exact number or last four."""
    from services import id_verification, provider_service

    admin, user = make_user("admin"), make_user()
    number = "FAN " + random_fin()
    provider = provider_service.join(
        {"provider_type": "guday_geday", "entity_type": "individual", "display_name": "Typed Id Agent", "telegram_username": "typed_id_tg",
         "phone": "0911000000", "service_areas": ["bole"], "service_ids": [PASSPORT_RENEWAL],
         "national_id": number}, user_id=user["id"], actor=user["email"])
    clean = id_verification.normalize_id(number)
    stored = fetch_one("select national_id, national_id_hash, national_id_last4 from providers where id = %s",
                       (provider["id"],))
    assert stored["national_id"] is None and stored["national_id_last4"] == clean[-4:]
    assert stored["national_id_hash"] == id_verification._hash_id(clean)

    def search(q):
        r = client.get(f"{API}/admin/marketplace/providers", params={"q": q, "limit": 100}, headers=admin["headers"])
        assert r.status_code == 200, r.text
        return {p["id"] for p in r.json()["payload"]["items"]}

    assert provider["id"] in search(number.lower().replace(" ", "-"))
    assert provider["id"] in search(clean[-4:])
    # Part of the number no longer matches: only the hash is stored
    assert provider["id"] not in search(clean[3:10])
    detail = client.get(f"{API}/admin/marketplace/providers/{provider['id']}", headers=admin["headers"]).text
    assert clean not in detail and clean[-4:] in detail


# ---------------------------------------------------------------- live mode checks


def _live_attempt(monkeypatch, user, fayda_key, *, id_claims=None, userinfo=None, signing_key=None):
    """Run one live verification against a stand-in Fayda. Returns the error (if any) and the stored row."""
    from urllib.parse import parse_qs, urlparse

    from fayda_helpers import fake_fayda_http, id_token_claims, sign, use_live_fayda
    from services import id_verification

    use_live_fayda(monkeypatch, fayda_key)
    started = id_verification.start(user["id"])
    state = parse_qs(urlparse(started["redirect_url"]).query)["state"][0]
    nonce = fetch_one("select nonce from id_verifications where state = %s", (state,))["nonce"]
    claims = id_token_claims(nonce, **(id_claims or {}))
    token = sign(claims, signing_key or fayda_key)
    info = userinfo if userinfo is not None else sign(
        {"sub": claims["sub"], "iss": claims["iss"], "aud": claims["aud"], "name": "Abebe Kebede",
         "individual_id": random_fin()}, fayda_key)
    fake_fayda_http(monkeypatch, id_token=token, userinfo=info(claims) if callable(info) else info)
    error = None
    try:
        id_verification.complete_live(user["id"], code="code", state=state)
    except id_verification.VerificationError as exc:
        error = exc
    row = fetch_one("select status, error from id_verifications where state = %s", (state,))
    return error, row


def test_live_happy_path(monkeypatch, make_user):
    from fayda_helpers import rsa_key

    user = make_user()
    error, row = _live_attempt(monkeypatch, user, rsa_key())
    assert error is None and row["status"] == "verified"


def test_live_rejects_wrong_issuer(monkeypatch, make_user):
    from fayda_helpers import rsa_key

    user = make_user()
    error, row = _live_attempt(monkeypatch, user, rsa_key(), id_claims={"iss": "https://evil.invalid"})
    assert error and "unexpected issuer" in str(error) and row["status"] == "failed"


def test_live_rejects_wrong_audience(monkeypatch, make_user):
    from fayda_helpers import rsa_key

    user = make_user()
    error, row = _live_attempt(monkeypatch, user, rsa_key(), id_claims={"aud": "someone-else"})
    assert error and "not issued for this service" in str(error) and row["status"] == "failed"


def test_live_rejects_bad_signature(monkeypatch, make_user):
    from fayda_helpers import rsa_key

    user = make_user()
    # Signed with a key that is not in Fayda's JWKS, under Fayda's key id
    error, row = _live_attempt(monkeypatch, user, rsa_key(), signing_key=rsa_key())
    assert error and "signature" in str(error) and row["status"] == "failed"


def test_live_rejects_badly_signed_userinfo(monkeypatch, make_user):
    from fayda_helpers import rsa_key, sign

    user = make_user()
    forged = rsa_key()
    error, row = _live_attempt(monkeypatch, user, rsa_key(), userinfo=lambda c: sign(
        {"sub": c["sub"], "iss": c["iss"], "aud": c["aud"], "individual_id": random_fin()}, forged))
    assert error and "signature" in str(error) and row["status"] == "failed"


def test_live_rejects_sub_mismatch(monkeypatch, make_user):
    import json as _json

    from fayda_helpers import rsa_key, sign

    user, key = make_user(), rsa_key()
    error, row = _live_attempt(monkeypatch, user, key, userinfo=lambda c: sign(
        {"sub": "someone-else", "iss": c["iss"], "aud": c["aud"], "individual_id": random_fin()}, key))
    assert error and "did not match the person" in str(error) and row["status"] == "failed"
    # Plain JSON userinfo without a sub is refused too
    error, row = _live_attempt(monkeypatch, make_user(), key,
                                  userinfo=_json.dumps({"name": "X", "individual_id": random_fin()}))
    assert error and "did not match the person" in str(error) and row["status"] == "failed"


def test_live_needs_issuer_setting(monkeypatch, make_user):
    import pytest

    from config.config import settings
    from fayda_helpers import rsa_key, use_live_fayda
    from services import id_verification

    use_live_fayda(monkeypatch, rsa_key())
    monkeypatch.setattr(settings, "fayda_issuer", None)
    with pytest.raises(id_verification.VerificationError) as exc:
        id_verification.start(make_user()["id"])
    assert exc.value.status_code == 503 and "FAYDA_ISSUER" in str(exc.value)
    monkeypatch.setattr(settings, "environment", "production")
    assert any("FAYDA_ISSUER" in p for p in settings.production_problems())
