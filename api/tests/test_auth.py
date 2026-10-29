import uuid

from fastapi.testclient import TestClient

from app import app
from conftest import API, LEGAL_ACCEPT
from services.db import execute


def _fresh_client():
    """A separate cookie jar, like a second browser."""
    return TestClient(app)


def test_login_rejects_wrong_password(client, make_user):
    user = make_user()
    r = client.post(f"{API}/auth/login", json={"email": user["email"], "password": "wrong-password1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"


def test_unknown_email_gets_same_error(client):
    r = client.post(f"{API}/auth/login", json={"email": "nobody-here@example.com", "password": "whatever1"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"


def test_register_then_sign_in_and_password_rules(client):
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    weak = client.post(f"{API}/auth/register", json={"email": email, "password": "short", "fullname": "Weak Pw", "accept": LEGAL_ACCEPT})
    assert weak.status_code == 422
    letters_only = client.post(f"{API}/auth/register", json={"email": email, "password": "onlyletters", "fullname": "Weak Pw", "accept": LEGAL_ACCEPT})
    assert "number" in letters_only.json()["detail"]

    with _fresh_client() as browser:
        r = browser.post(f"{API}/auth/register", json={"email": email, "password": "good-pass-1", "fullname": "Good Pw", "accept": LEGAL_ACCEPT})
        assert r.status_code == 201, r.text
        # Registering never signs in by itself (the answer is the same for a taken email)
        assert "accessToken" not in r.json()["payload"] and "cn_refresh" not in browser.cookies
        r = browser.post(f"{API}/auth/login", json={"email": email, "password": "good-pass-1"})
        assert r.status_code == 200, r.text
        body = r.json()["payload"]
        assert body["accessToken"] and body["user"]["email"] == email
        assert body["user"]["emailVerified"] is False
        assert "cn_refresh" in browser.cookies
        cookie_header = r.headers["set-cookie"].lower()
        assert "httponly" in cookie_header and "path=/api/v1/auth" in cookie_header
    execute("delete from user_consents where user_id in (select id from users where email = %s)", (email,))
    execute("delete from users where email = %s", (email,))


def test_me_returns_role(client, make_user):
    # Staff are a separate realm: their token works on /staff/me, never on the public /auth/me
    admin = make_user("admin")
    assert client.get(f"{API}/auth/me", headers=admin["headers"]).status_code == 401
    r = client.get(f"{API}/staff/me", headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["superAdmin"]
    user = make_user()
    assert client.get(f"{API}/auth/me", headers=user["headers"]).json()["payload"]["user"]["role"] == "user"


def test_admin_routes_require_admin(client, make_user):
    user = make_user()
    for path in ("/admin/overview", "/admin/marketplace/providers", "/admin/users", "/admin/auth/events"):
        assert client.get(f"{API}{path}", headers=user["headers"]).status_code == 403
    assert client.get(f"{API}/admin/overview").status_code == 401


def test_garbage_token_is_401(client):
    r = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_public_users_cannot_be_made_admin(client, make_user):
    admin, user = make_user("admin"), make_user()
    r = client.patch(f"{API}/admin/users/{user['id']}", json={"role": "admin"}, headers=admin["headers"])
    assert r.status_code == 422


def test_refresh_rotates_and_detects_reuse(make_user):
    user = make_user()
    with _fresh_client() as browser:
        login = browser.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
        first_refresh = browser.cookies["cn_refresh"]

        r = browser.post(f"{API}/auth/refresh")
        assert r.status_code == 200
        new_access = r.json()["payload"]["accessToken"]
        assert browser.cookies["cn_refresh"] != first_refresh
        # The access token from the rotated session no longer works; the new one does
        old_headers = {"Authorization": f"Bearer {login.json()['payload']['accessToken']}"}
        assert browser.get(f"{API}/auth/me", headers=old_headers).status_code == 401
        new_headers = {"Authorization": f"Bearer {new_access}"}
        assert browser.get(f"{API}/auth/me", headers=new_headers).status_code == 200

        # Replaying the old refresh token after the grace window revokes the whole family
        execute(
            "update auth_sessions set revoked_at = now() - interval '5 minutes' where refresh_hash = encode(sha256(%s::bytea), 'hex')",
            (first_refresh,),
        )
        with _fresh_client() as attacker:
            attacker.cookies.set("cn_refresh", first_refresh, path="/api/v1/auth")
            assert attacker.post(f"{API}/auth/refresh").status_code == 401
        assert browser.get(f"{API}/auth/me", headers=new_headers).status_code == 401
        assert browser.post(f"{API}/auth/refresh").status_code == 401


def test_concurrent_refresh_within_grace_is_not_reuse(make_user):
    user = make_user()
    with _fresh_client() as browser:
        browser.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
        stale = browser.cookies["cn_refresh"]
        assert browser.post(f"{API}/auth/refresh").status_code == 200
        with _fresh_client() as other_tab:
            other_tab.cookies.set("cn_refresh", stale, path="/api/v1/auth")
            r = other_tab.post(f"{API}/auth/refresh")
            assert r.status_code == 200
            headers = {"Authorization": f"Bearer {r.json()['payload']['accessToken']}"}
            assert other_tab.get(f"{API}/auth/me", headers=headers).status_code == 200
        assert browser.post(f"{API}/auth/refresh").status_code == 200


def test_logout_revokes_session_immediately(make_user):
    user = make_user()
    with _fresh_client() as browser:
        r = browser.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
        headers = {"Authorization": f"Bearer {r.json()['payload']['accessToken']}"}
        assert browser.post(f"{API}/auth/logout", headers=headers).status_code == 200
        assert browser.get(f"{API}/auth/me", headers=headers).status_code == 401
        assert browser.post(f"{API}/auth/refresh").status_code == 401


def test_lockout_after_repeated_failures(client, make_user):
    user = make_user()
    for _ in range(5):
        client.post(f"{API}/auth/login", json={"email": user["email"], "password": "nope-nope-1"})
    r = client.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
    assert r.status_code == 429


def test_change_password_signs_out_other_sessions(make_user):
    user = make_user()
    with _fresh_client() as a, _fresh_client() as b:
        ra = a.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
        rb = b.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
        ha = {"Authorization": f"Bearer {ra.json()['payload']['accessToken']}"}
        hb = {"Authorization": f"Bearer {rb.json()['payload']['accessToken']}"}
        bad = a.post(f"{API}/auth/change-password", json={"current_password": "wrong-1", "new_password": "new-pass-22"}, headers=ha)
        assert bad.status_code == 400
        ok = a.post(f"{API}/auth/change-password", json={"current_password": user["password"], "new_password": "new-pass-22"}, headers=ha)
        assert ok.status_code == 200 and ok.json()["payload"]["otherSessionsSignedOut"] >= 1
        assert a.get(f"{API}/auth/me", headers=ha).status_code == 200
        assert b.get(f"{API}/auth/me", headers=hb).status_code == 401
        assert a.post(f"{API}/auth/login", json={"email": user["email"], "password": "new-pass-22"}).status_code == 200


def test_admin_reset_link_flow(client, make_user):
    admin, user = make_user("admin"), make_user()
    r = client.post(f"{API}/admin/users/{user['id']}/reset-link", headers=admin["headers"])
    assert r.status_code == 200
    token = r.json()["payload"]["link"].split("token=")[1]
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "weak"}).status_code == 422
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "reset-pass-9"}).status_code == 200
    # Single use, and existing sessions are gone
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "reset-pass-10"}).status_code == 400
    assert client.get(f"{API}/auth/me", headers=user["headers"]).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": user["email"], "password": "reset-pass-9"}).status_code == 200


def test_forgot_password_does_not_reveal_accounts(client):
    r = client.post(f"{API}/auth/forgot-password", json={"email": "ghost@example.com"})
    assert r.status_code == 202


def test_deactivation_ends_sessions(client, make_user):
    admin, user = make_user("admin"), make_user()
    assert client.patch(f"{API}/admin/users/{user['id']}", json={"is_active": False}, headers=admin["headers"]).status_code == 200
    assert client.get(f"{API}/auth/me", headers=user["headers"]).status_code == 401
    r = client.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
    assert r.status_code == 403


def test_sessions_list_and_revoke(make_user):
    user = make_user()
    with _fresh_client() as browser:
        r = browser.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
        headers = {"Authorization": f"Bearer {r.json()['payload']['accessToken']}"}
        sessions = browser.get(f"{API}/auth/sessions", headers=headers).json()["payload"]["sessions"]
        assert any(s["current"] for s in sessions)
        other = next(s for s in sessions if not s["current"])  # the make_user registration session
        assert browser.delete(f"{API}/auth/sessions/{other['id']}", headers=headers).status_code == 200
        assert browser.delete(f"{API}/auth/sessions/{uuid.uuid4()}", headers=headers).status_code == 404


def test_sessions_and_activity_page_with_totals(make_user):
    user = make_user()
    for _ in range(3):  # four sessions in all with the registration one; each sign-in is an event too
        with _fresh_client() as browser:
            r = browser.post(f"{API}/auth/login", json={"email": user["email"], "password": user["password"]})
    headers = {"Authorization": f"Bearer {r.json()['payload']['accessToken']}"}
    with _fresh_client() as browser:
        get = lambda path, **p: browser.get(f"{API}{path}", params=p, headers=headers).json()["payload"]  # noqa: E731
        first, second = get("/auth/sessions", limit=3), get("/auth/sessions", limit=3, offset=3)
        assert first["total"] == 4 and len(first["sessions"]) == 3 and len(second["sessions"]) == 1
        assert not {s["id"] for s in first["sessions"]} & {s["id"] for s in second["sessions"]}
        events = get("/auth/activity", limit=2)
        assert events["total"] >= 4 and len(events["events"]) == 2
        assert events["events"][0]["created_at"] >= events["events"][1]["created_at"]  # newest first
