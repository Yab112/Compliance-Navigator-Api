"""Staff realm, roles and permissions, invitations, second-person approval and the policy table."""

import uuid

import pytest
from fastapi import Depends
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import app
from conftest import API, LEGAL_ACCEPT, approve_pending
from core.deps import require_admin
from services import access
from services.db import execute, fetch_one


def _fresh():
    return TestClient(app)


def _role_id(key: str) -> str:
    return fetch_one("select id::text from staff_roles where builtin_key = %s", (key,))["id"]


def _uses_require_admin(dependant) -> bool:
    return any(d.call is require_admin or _uses_require_admin(d) for d in dependant.dependencies)


@pytest.fixture
def cleanup_staff():
    emails: list[str] = []
    roles: list[str] = []
    yield emails, roles
    for email in emails:
        execute("delete from approval_requests where target = %s", (f"staff-email:{email}",))
        execute("delete from staff_users where lower(email) = lower(%s)", (email,))
    for role_id in roles:
        execute("delete from approval_requests where target = %s", (f"role:{role_id}",))
        execute("delete from staff_roles where id = %s", (role_id,))


# ---------------------------------------------------------------- policy table


def test_every_admin_route_has_a_policy_and_known_permission():
    missing, unknown = [], []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not (_uses_require_admin(route.dependant) or route.path.startswith(f"{API}/admin")):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            policy = access.policy_for(method, route.path)
            if policy is None:
                missing.append(f"{method} {route.path}")
            elif policy.permission != "*" and policy.permission not in access.BY_KEY:
                unknown.append(f"{method} {route.path}: {policy.permission}")
            elif not _uses_require_admin(route.dependant):
                missing.append(f"{method} {route.path} (does not depend on require_admin)")
    assert not missing, "Admin routes without an entry in services/access.ROUTE_POLICY:\n" + "\n".join(missing)
    assert not unknown, "Policies naming unknown permissions:\n" + "\n".join(unknown)
    for policy in access.ROUTE_POLICY.values():
        assert all(v in access.BY_KEY for v in policy.by_value.values())


def test_builtin_roles_only_use_known_permissions():
    for key, perms in access.BUILTIN_ROLES.items():
        assert perms <= access.ALL, key
    assert access.BUILTIN_ROLES["super_admin"] == access.ALL
    assert "vetting.view_criminal_records" in access.BUILTIN_ROLES["compliance_reviewer"]
    assert not any(p.endswith(("manage", "approve", "edit", "decide")) for p in access.BUILTIN_ROLES["viewer"])


def test_route_without_policy_is_denied(client, make_user):
    admin = make_user("admin")
    app.add_api_route(f"{API}/admin/zz-unlisted-test", lambda: {"ok": True}, dependencies=[Depends(require_admin)])
    try:
        r = client.get(f"{API}/admin/zz-unlisted-test", headers=admin["headers"])
        assert r.status_code == 403  # deny by default, even for a Super admin
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != f"{API}/admin/zz-unlisted-test"]


# ---------------------------------------------------------------- realms


def test_realms_are_separate_both_ways(client, make_user, make_staff):
    user, staff = make_user(), make_staff()
    # Public token: signed in, but not staff
    assert client.get(f"{API}/admin/overview", headers=user["headers"]).status_code == 403
    assert client.get(f"{API}/staff/me", headers=user["headers"]).status_code == 403
    # Staff token: never a public user
    assert client.get(f"{API}/auth/me", headers=staff["headers"]).status_code == 401
    assert client.get(f"{API}/hires", headers=staff["headers"]).status_code == 401
    assert client.get(f"{API}/admin/overview", headers=staff["headers"]).status_code == 200
    # Staff credentials don't sign in on the public site, and public ones not on the staff side
    assert client.post(f"{API}/auth/login", json={"email": staff["email"], "password": staff["password"]}).status_code == 401
    assert client.post(f"{API}/staff/auth/login", json={"email": user["email"], "password": user["password"]}).status_code == 401


def test_staff_login_refresh_and_logout_use_their_own_cookie(make_staff):
    staff = make_staff("viewer")
    with _fresh() as browser:
        r = browser.post(f"{API}/staff/auth/login", json={"email": staff["email"], "password": staff["password"]})
        assert r.status_code == 200 and "cn_refresh" not in browser.cookies
        cookie = r.headers["set-cookie"].lower()
        assert "cn_staff_refresh" in cookie and "path=/api/v1/staff/auth" in cookie and "httponly" in cookie
        headers = {"Authorization": f"Bearer {r.json()['payload']['accessToken']}"}
        me = browser.get(f"{API}/staff/me", headers=headers).json()["payload"]
        assert "settings.view" in me["permissions"] and "settings.edit" not in me["permissions"]
        refreshed = browser.post(f"{API}/staff/auth/refresh")
        assert refreshed.status_code == 200
        # The public refresh endpoint ignores the staff cookie
        assert browser.post(f"{API}/auth/refresh").status_code == 401
        new_headers = {"Authorization": f"Bearer {refreshed.json()['payload']['accessToken']}"}
        assert browser.post(f"{API}/staff/auth/logout", headers=new_headers).status_code == 200
        assert browser.get(f"{API}/staff/me", headers=new_headers).status_code == 401


def test_staff_lockout(client, make_staff):
    staff = make_staff("viewer")
    for _ in range(5):
        client.post(f"{API}/staff/auth/login", json={"email": staff["email"], "password": "wrong-pass-1"})
    r = client.post(f"{API}/staff/auth/login", json={"email": staff["email"], "password": staff["password"]})
    assert r.status_code == 429


def test_staff_password_reset_clears_the_lockout(client, make_staff):
    from auth import staff_service

    staff = make_staff("viewer")
    for _ in range(6):
        client.post(f"{API}/staff/auth/login", json={"email": staff["email"], "password": "wrong-pass-1"})
    link = staff_service.issue_link(staff_service.get_staff_by_email(staff["email"]), "reset", "test")
    r = client.post(f"{API}/staff/auth/reset-password",
                    json={"token": link.split("token=")[1], "new_password": "after-reset-14"})
    assert r.status_code == 200, r.text
    r = client.post(f"{API}/staff/auth/login", json={"email": staff["email"], "password": "after-reset-14"})
    assert r.status_code == 200, r.text


def test_admin_emails_no_longer_grants_anything(client, make_user, monkeypatch):
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"
    monkeypatch.setenv("ADMIN_EMAILS", email)
    r = client.post(f"{API}/auth/register", json={"email": email, "password": "test-password-1", "fullname": "Test Person",
                                                    "accept": LEGAL_ACCEPT})
    try:
        assert r.status_code == 201
        login = client.post(f"{API}/auth/login", json={"email": email, "password": "test-password-1"})
        assert login.json()["payload"]["user"]["role"] == "user"
        headers = {"Authorization": f"Bearer {login.json()['payload']['accessToken']}"}
        assert client.get(f"{API}/admin/overview", headers=headers).status_code == 403
        assert fetch_one("select 1 as x from staff_users where lower(email) = %s", (email,)) is None
    finally:
        execute("delete from user_consents where user_id in (select id from users where email = %s)", (email,))
        execute("delete from users where email = %s", (email,))


# ---------------------------------------------------------------- permissions


def test_permissions_are_enforced_per_route(client, make_staff):
    support = make_staff("support_agent")
    viewer = make_staff("viewer")
    assert client.get(f"{API}/admin/support/summary", headers=support["headers"]).status_code == 200
    assert client.get(f"{API}/admin/settings", headers=support["headers"]).status_code == 403
    assert client.get(f"{API}/admin/settings", headers=viewer["headers"]).status_code == 200
    r = client.patch(f"{API}/admin/settings", json={"values": {"follow_up_hours": 30}}, headers=viewer["headers"])
    assert r.status_code == 403
    assert client.get(f"{API}/admin/access/audit", headers=viewer["headers"]).status_code == 403
    assert client.get(f"{API}/admin/access/staff", headers=support["headers"]).status_code == 403
    # Suspending needs a stricter permission than approving, chosen from the request body
    reviewer = make_staff("finance")
    r = client.post(f"{API}/admin/marketplace/providers/{uuid.uuid4()}/review", json={"action": "suspend"},
                    headers=reviewer["headers"])
    assert r.status_code == 403 and "Suspend" in r.json()["detail"]


def test_role_crud_and_no_escalation(client, make_staff, cleanup_staff):
    _, roles = cleanup_staff
    admin, checker = make_staff(), make_staff()
    name = f"Test role {uuid.uuid4().hex[:6]}"
    r = client.post(f"{API}/admin/access/roles", json={"name": name, "permissions": ["support.view"]},
                    headers=admin["headers"])
    assert r.status_code == 201, r.text
    role = r.json()["payload"]["role"]
    roles.append(role["id"])
    assert role["permissions"] == ["support.view"] and not role["built_in"]
    dup = client.post(f"{API}/admin/access/roles", json={"name": name.upper(), "permissions": []}, headers=admin["headers"])
    assert dup.status_code == 409

    # Changing permissions waits for a second person
    r = client.put(f"{API}/admin/access/roles/{role['id']}",
                   json={"name": name, "permissions": ["support.view", "support.reply"]}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["approval"]["status"] == "pending"
    req = r.json()["payload"]["approval"]
    assert client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={},
                       headers=admin["headers"]).status_code == 403  # not your own
    done = client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={"note": "fine"},
                       headers=checker["headers"]).json()["payload"]["approval"]
    assert done["status"] == "executed"
    assert client.get(f"{API}/admin/access/roles/{role['id']}", headers=admin["headers"]).json()["payload"]["role"][
        "permissions"] == ["support.reply", "support.view"]

    # Built-in roles are read-only
    r = client.put(f"{API}/admin/access/roles/{_role_id('viewer')}", json={"name": "Viewer", "permissions": []},
                   headers=admin["headers"])
    assert r.status_code == 403

    # You can only hand out what you hold
    support = make_staff("support_agent", role_ids=[])
    execute("insert into staff_role_permissions (role_id, permission) values (%s, 'roles.manage')", (role["id"],))
    execute("insert into staff_user_roles (staff_id, role_id) values (%s, %s)", (support["id"], role["id"]))
    r = client.post(f"{API}/admin/access/roles", json={"name": name + " x", "permissions": ["settings.edit"]},
                    headers=support["headers"])
    assert r.status_code == 403
    # Nor add permissions to a role you hold yourself
    r = client.put(f"{API}/admin/access/roles/{role['id']}",
                   json={"name": name, "permissions": ["support.view", "support.reply", "roles.manage", "support.assign"]},
                   headers=support["headers"])
    assert r.status_code == 403
    execute("delete from staff_user_roles where staff_id = %s and role_id = %s", (support["id"], role["id"]))

    perms = client.get(f"{API}/admin/access/permissions", headers=admin["headers"]).json()["payload"]
    entry = next(p for a in perms["areas"] for p in a["permissions"] if p["key"] == "support.reply")
    assert name in entry["roles"] and "Support agent" in entry["roles"]

    r = client.delete(f"{API}/admin/access/roles/{role['id']}", headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["deleted"]


# ---------------------------------------------------------------- staff and invitations


def test_invite_flow_single_use_and_expiry(client, make_staff, cleanup_staff):
    emails, _ = cleanup_staff
    admin, checker = make_staff(), make_staff()
    email = f"test-staff-invite-{uuid.uuid4().hex[:8]}@example.com"
    emails.append(email)
    r = client.post(f"{API}/admin/access/staff", json={"email": email, "fullname": "New Person",
                                                       "role_ids": [_role_id("support_agent")]}, headers=admin["headers"])
    assert r.status_code == 201 and r.json()["payload"]["approval"]["status"] == "pending"
    again = client.post(f"{API}/admin/access/staff", json={"email": email, "role_ids": [_role_id("viewer")]},
                        headers=admin["headers"])
    assert again.status_code == 409
    req = r.json()["payload"]["approval"]
    r = client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={}, headers=checker["headers"])
    assert r.json()["payload"]["approval"]["status"] == "executed", r.text
    staff_id = r.json()["payload"]["approval"]["result"]["staff_id"]
    staff = client.get(f"{API}/admin/access/staff/{staff_id}", headers=admin["headers"]).json()["payload"]["staff"]
    assert staff["status"] == "invited" and staff["roles"][0]["name"] == "Support agent"

    # No SMTP in tests: resending gives the link to pass on by hand
    link = client.post(f"{API}/admin/access/staff/{staff_id}/resend-invite", headers=admin["headers"]).json()["payload"]
    assert link["email_sent"] is False and "/accept-invite?token=" in link["link"]
    token = link["link"].split("token=")[1]
    assert client.get(f"{API}/staff/auth/link", params={"token": token}).json()["payload"]["email"] == email
    assert client.post(f"{API}/staff/auth/accept-invite", json={"token": token, "new_password": "weak"}).status_code == 422
    assert client.post(f"{API}/staff/auth/accept-invite", json={"token": token, "new_password": "good-pass-12"}).status_code == 200
    assert client.post(f"{API}/staff/auth/accept-invite", json={"token": token, "new_password": "good-pass-13"}).status_code == 400
    login = client.post(f"{API}/staff/auth/login", json={"email": email, "password": "good-pass-12"})
    assert login.status_code == 200

    # Reset links expire
    reset = client.post(f"{API}/admin/access/staff/{staff_id}/reset-password", headers=admin["headers"]).json()["payload"]
    reset_token = reset["link"].split("token=")[1]
    execute("update staff_tokens set expires_at = now() - interval '1 minute' where staff_id = %s and kind = 'reset'",
            (staff_id,))
    assert client.post(f"{API}/staff/auth/reset-password",
                       json={"token": reset_token, "new_password": "other-pass-14"}).status_code == 400
    execute("delete from staff_audit_log where lower(actor_email) = %s or target = %s", (email, f"staff:{staff_id}"))


def test_nobody_changes_their_own_access(client, make_staff):
    admin = make_staff()
    r = client.put(f"{API}/admin/access/staff/{admin['id']}/roles", json={"role_ids": [_role_id("viewer")]},
                   headers=admin["headers"])
    assert r.status_code == 403
    assert client.post(f"{API}/admin/access/staff/{admin['id']}/disable", headers=admin["headers"]).status_code == 403


def test_only_super_admins_touch_super_admins(client, make_staff):
    admin = make_staff()
    manager = make_staff(None, role_ids=[])
    # A custom role with staff.manage but not Super admin
    role = fetch_one("insert into staff_roles (name) values (%s) returning id::text", (f"Test mgr {uuid.uuid4().hex[:6]}",))
    try:
        execute("insert into staff_role_permissions (role_id, permission) values (%s, 'staff.manage'), (%s, 'staff.view')",
                (role["id"], role["id"]))
        execute("insert into staff_user_roles (staff_id, role_id) values (%s, %s)", (manager["id"], role["id"]))
        r = client.post(f"{API}/admin/access/staff/{admin['id']}/sign-out", headers=manager["headers"])
        assert r.status_code == 403
    finally:
        execute("delete from staff_roles where id = %s", (role["id"],))


def test_last_super_admin_cannot_be_disabled_or_demoted(client, make_staff, monkeypatch):
    admin, target = make_staff(), make_staff()
    monkeypatch.setattr(access, "active_super_admin_ids", lambda: [target["id"]])
    assert client.post(f"{API}/admin/access/staff/{target['id']}/disable", headers=admin["headers"]).status_code == 409
    r = client.put(f"{API}/admin/access/staff/{target['id']}/roles", json={"role_ids": [_role_id("viewer")]},
                   headers=admin["headers"])
    assert r.status_code == 409


def test_disable_needs_approval_and_ends_sessions(client, make_staff):
    admin, checker, target = make_staff(), make_staff(), make_staff("viewer")
    r = client.post(f"{API}/admin/access/staff/{target['id']}/disable", headers=admin["headers"])
    req = r.json()["payload"]["approval"]
    assert client.get(f"{API}/staff/me", headers=target["headers"]).status_code == 200  # not yet
    # Reject needs a reason
    assert client.post(f"{API}/admin/access/approvals/{req['id']}/reject", json={},
                       headers=checker["headers"]).status_code == 400
    done = client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={}, headers=checker["headers"])
    assert done.json()["payload"]["approval"]["status"] == "executed"
    assert client.get(f"{API}/staff/me", headers=target["headers"]).status_code == 401
    assert client.post(f"{API}/staff/auth/login", json={"email": target["email"], "password": target["password"]}).status_code == 403


# ---------------------------------------------------------------- approvals


def test_approval_lists_cancel_and_expiry(client, make_staff):
    admin, checker, viewer = make_staff(), make_staff(), make_staff("viewer")
    target = make_staff("viewer")
    r = client.post(f"{API}/admin/access/staff/{target['id']}/disable", headers=admin["headers"])
    req = r.json()["payload"]["approval"]
    mine = client.get(f"{API}/admin/access/approvals", params={"box": "mine"}, headers=admin["headers"]).json()["payload"]
    assert any(i["id"] == req["id"] for i in mine["items"])
    waiting = client.get(f"{API}/admin/access/approvals", params={"box": "waiting"}, headers=checker["headers"]).json()["payload"]
    assert any(i["id"] == req["id"] for i in waiting["items"])
    own_waiting = client.get(f"{API}/admin/access/approvals", params={"box": "waiting"}, headers=admin["headers"]).json()["payload"]
    assert not any(i["id"] == req["id"] for i in own_waiting["items"])
    # A viewer can't decide anything, or even see other people's requests
    assert client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={},
                       headers=viewer["headers"]).status_code == 403
    assert client.get(f"{API}/admin/access/approvals/{req['id']}", headers=viewer["headers"]).status_code == 404

    execute("update approval_requests set expires_at = now() - interval '1 minute' where id = %s", (req["id"],))
    assert client.get(f"{API}/admin/access/approvals/{req['id']}", headers=admin["headers"]).json()["payload"][
        "approval"]["status"] == "expired"
    assert client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={},
                       headers=checker["headers"]).status_code == 409

    r = client.post(f"{API}/admin/access/staff/{target['id']}/disable", headers=admin["headers"])
    req2 = r.json()["payload"]["approval"]
    assert client.post(f"{API}/admin/access/approvals/{req2['id']}/cancel", headers=checker["headers"]).status_code == 404
    cancelled = client.post(f"{API}/admin/access/approvals/{req2['id']}/cancel", headers=admin["headers"])
    assert cancelled.json()["payload"]["approval"]["status"] == "cancelled"
    assert client.get(f"{API}/staff/me", headers=target["headers"]).status_code == 200


def test_settings_money_change_waits_but_other_settings_do_not(client, make_staff):
    from services import platform_settings

    admin, checker = make_staff(), make_staff()
    saved = fetch_one("select value from platform_settings where key = 'follow_up_hours'")
    saved_vat = fetch_one("select value from platform_settings where key = 'vat_rate_percent'")
    try:
        r = client.patch(f"{API}/admin/settings", json={"values": {"follow_up_hours": 47}}, headers=admin["headers"])
        assert r.status_code == 200
        target_vat = 14 if platform_settings.get("vat_rate_percent") != 14 else 13
        r = client.patch(f"{API}/admin/settings", json={"values": {"vat_rate_percent": target_vat}}, headers=admin["headers"])
        assert r.status_code == 202 and "VAT rate" in r.json()["payload"]["approval"]["summary"]
        platform_settings.clear_cache()
        assert platform_settings.get("vat_rate_percent") != target_vat
        assert approve_pending(client, r, checker)["status"] == "executed"
        platform_settings.clear_cache()
        assert platform_settings.get("vat_rate_percent") == target_vat
    finally:
        for key, row in (("follow_up_hours", saved), ("vat_rate_percent", saved_vat)):
            execute("delete from platform_settings where key = %s", (key,))
            if row:
                execute("insert into platform_settings (key, value) values (%s, %s::jsonb)", (key, __import__("json").dumps(row["value"])))
        execute("delete from platform_settings_history where changed_by like %s", (admin["email"] + "%",))
        platform_settings.clear_cache()


def test_mutations_are_audited(client, make_staff):
    admin = make_staff()
    client.patch(f"{API}/admin/feedback/{uuid.uuid4()}", json={"status": "resolved"}, headers=admin["headers"])
    log = client.get(f"{API}/admin/access/audit", params={"actor": admin["email"]}, headers=admin["headers"]).json()["payload"]
    assert any(i["action"] == "feedback.manage" and i["details"]["status"] == 404 for i in log["items"])


def test_payout_at_or_above_the_limit_needs_a_second_person(client, make_user, make_staff):
    import json

    from services import platform_settings
    from test_payments import _payout_account
    from test_providers import _approved, _deliver, _hire, _job, _pay

    admin, checker, agent, customer = make_staff(), make_staff(), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=1000)
    _deliver(client, agent, hire["id"])
    _pay(client, customer, hire["id"])
    _payout_account(client, agent)
    payout = client.post(f"{API}/providers/me/payouts", json={"amount": 600}, headers=agent["headers"]).json()["payload"]["payout"]
    saved = fetch_one("select value from platform_settings where key = 'payout_approval_threshold_etb'")
    execute("insert into platform_settings (key, value) values ('payout_approval_threshold_etb', '500') "
            "on conflict (key) do update set value = excluded.value")
    platform_settings.clear_cache()
    try:
        decide = lambda who: client.post(f"{API}/admin/marketplace/payouts/{payout['id']}",  # noqa: E731
                                         json={"decision": "approve"}, headers=who["headers"])
        r = decide(admin)
        assert r.status_code == 202
        assert fetch_one("select status from payouts where id = %s", (payout["id"],))["status"] == "requested"
        assert decide(admin).status_code == 409  # one open request per payout
        decided = approve_pending(client, r, checker)
        assert decided["status"] == "executed"
        row = fetch_one("select status, decided_by from payouts where id = %s", (payout["id"],))
        assert row["status"] == "paid" and checker["email"] in row["decided_by"] and admin["email"] in row["decided_by"]
    finally:
        execute("delete from platform_settings where key = 'payout_approval_threshold_etb'")
        if saved:
            execute("insert into platform_settings (key, value) values ('payout_approval_threshold_etb', %s::jsonb)",
                    (json.dumps(saved["value"]),))
        platform_settings.clear_cache()
        execute("delete from approval_requests where target = %s", (f"payout:{payout['id']}",))


@pytest.mark.parametrize("content_type", [None, "application/JSON"])
def test_leaving_out_the_json_content_type_does_not_skip_approval(client, make_staff, content_type):
    """FastAPI reads these bodies as JSON too, so the approval check must see the same body."""
    import json

    from services import platform_settings

    admin, _checker = make_staff(), make_staff()
    before = platform_settings.get("commission_percent")
    headers = dict(admin["headers"])
    if content_type:
        headers["content-type"] = content_type
    r = client.patch(f"{API}/admin/settings", content=json.dumps({"values": {"commission_percent": before + 1}}),
                     headers=headers)
    assert r.status_code == 202, r.text
    assert r.json()["payload"]["approval"]["status"] == "pending"
    assert platform_settings.get("commission_percent") == before
    execute("delete from approval_requests where id = %s", (r.json()["payload"]["approval"]["id"],))


def test_staff_sign_in_does_not_clear_the_network_count(monkeypatch, make_staff):
    from auth import staff_service
    from auth.common import ClientInfo

    staff, ip = make_staff("viewer"), f"198.51.100.7-{uuid.uuid4().hex[:6]}"
    monkeypatch.setattr(staff_service, "MAX_FAILED_PER_IP", 3)
    net = ClientInfo(ip=ip)
    try:
        for i in range(2):
            with pytest.raises(staff_service.AuthError):
                staff_service.login(f"nobody-{i}-{uuid.uuid4().hex[:6]}@example.com", "guess-1", net)
        staff_service.login(staff["email"], staff["password"], net)
        with pytest.raises(staff_service.AuthError):
            staff_service.login(f"nobody-x-{uuid.uuid4().hex[:6]}@example.com", "guess-1", net)
        # Three failures at other addresses: blocked, though this person signed in between
        with pytest.raises(staff_service.AuthError) as exc:
            staff_service.login(staff["email"], staff["password"], net)
        assert exc.value.status_code == 429
        assert staff_service._recent_failures("ip", ip) == 3
    finally:
        execute("delete from staff_audit_log where ip = %s", (ip,))
