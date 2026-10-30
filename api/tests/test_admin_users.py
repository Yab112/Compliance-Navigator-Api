"""Admin public-user routes: a malformed id is a client error, not a server crash."""

import uuid

from conftest import API


def test_patch_user_rejects_bad_ids(client, make_user):
    admin = make_user("admin")
    r = client.patch(f"{API}/admin/users/not-a-uuid", json={"is_active": True}, headers=admin["headers"])
    assert r.status_code == 422
    r = client.patch(f"{API}/admin/users/{uuid.uuid4()}", json={"is_active": True}, headers=admin["headers"])
    assert r.status_code == 404


def test_patch_user_still_works(client, make_user):
    admin, user = make_user("admin"), make_user()
    r = client.patch(f"{API}/admin/users/{user['id']}", json={"role": "agent"}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["user"]["role"] == "agent"
