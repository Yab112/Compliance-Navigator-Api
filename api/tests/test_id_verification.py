import json

from conftest import API
from fayda_helpers import random_fin, sandbox_verify, start_state
from services.db import execute

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
    assert bad.status_code == 400 and "111111" in bad.json()["detail"]
    # A failed attempt burns the state
    again = client.post(f"{API}/guday/fayda/sandbox/complete", json={**body, "otp": "111111"}, headers=user["headers"])
    assert again.status_code == 409

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
    data = {"provider_type": "guday_geday", "entity_type": "individual", "display_name": "Abebe Kebede",
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
    assert detail["national_id"].endswith(fin[-4:]) and "TYPED" not in detail["national_id"]
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
    data = {"provider_type": "guday_geday", "entity_type": "individual", "display_name": "Abebe Kebede",
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
