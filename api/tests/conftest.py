"""Integration tests, need `docker compose up -d postgres neo4j` and a seeded graph."""

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402
from config.config import settings  # noqa: E402
from services.db import execute  # noqa: E402

# Tests never talk to a real payment gateway, whatever .env says
settings.payments_mode = "simulated"

# Earnings are withdrawable at once in tests; tests/test_payment_reconcilers.py turns the dispute-window hold on
import importlib  # noqa: E402

importlib.import_module("services.payment_service.earnings")._hold_days = lambda: 0

API = "/api/v1"

# What the sign-up form sends when every legal box is ticked
from services.legal import client_acceptance  # noqa: E402

LEGAL_ACCEPT = client_acceptance()


@pytest.fixture(scope="session")
def client():
    # Every test request comes from the same "IP", so lift the per-network limits
    from auth import service, staff_service

    service.MAX_REGISTRATIONS_PER_IP_HOUR = 10_000
    service.MAX_FAILED_PER_IP = 10_000
    staff_service.MAX_FAILED_PER_IP = 10_000
    from core import ratelimit

    ratelimit.ENABLED = False  # tests/test_ratelimit.py switches it back on where it matters
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def make_staff(client):
    """A staff member (default: Super admin) with a staff access token. make_user("admin") uses this."""
    from auth import security, staff_service
    from services.db import fetch_one

    created: list[str] = []

    def _make(builtin_role: str | None = "super_admin", *, role_ids: list[str] | None = None,
              password: str = "staff-password-1") -> dict:
        email = f"test-staff-{uuid.uuid4().hex[:10]}@example.com"
        staff = fetch_one(
            "insert into staff_users (email, fullname, password_hash, status, created_by) "
            "values (%s, 'Test Staff', %s, 'active', 'pytest') returning id::text",
            (email, security.hash_password(password)),
        )
        created.append(staff["id"])
        ids = list(role_ids or [])
        if builtin_role:
            ids.append(fetch_one("select id::text from staff_roles where builtin_key = %s", (builtin_role,))["id"])
        for rid in ids:
            execute("insert into staff_user_roles (staff_id, role_id, granted_by) values (%s, %s, 'pytest')",
                    (staff["id"], rid))
        session = staff_service._session(staff_service.get_staff(staff["id"]), staff_service.ClientInfo(ip="testclient"))
        return {"id": staff["id"], "email": email, "password": password,
                "headers": {"Authorization": f"Bearer {session.access_token}"}}

    yield _make
    for sid in created:
        execute("update approval_requests set requested_by = null where requested_by = %s", (sid,))
        execute("delete from approval_requests where requested_by_email in "
                "(select email from staff_users where id = %s)", (sid,))
        execute("delete from staff_audit_log where actor_id = %s", (sid,))
        execute("delete from staff_users where id = %s", (sid,))
    execute("delete from staff_audit_log where ip = 'testclient' or actor_email like 'test-staff-%%@example.com'")
    execute("delete from staff_audit_log where action like 'approval.%%' and actor_id is null")


@pytest.fixture(scope="session")
def make_user(client, make_staff):
    created: list[str] = []

    def _make(role: str = "user", *, verified: bool = True) -> dict:
        """A signed-in public account. verified=False leaves the email unconfirmed, as right after sign-up."""
        if role == "admin":
            return make_staff()
        email = f"test-{uuid.uuid4().hex[:10]}@example.com"
        password = "test-password-1"
        r = client.post(f"{API}/auth/register", json={"email": email, "password": password, "fullname": "Test User",
                                                       "accept": LEGAL_ACCEPT})
        assert r.status_code == 201, r.text
        if verified:
            execute("update users set email_verified_at = now() where lower(email) = lower(%s)", (email,))
        r = client.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        user_id = r.json()["payload"]["user"]["id"]
        created.append(user_id)
        if role != "user":
            execute("update users set role = %s where id = %s", (role, user_id))
        token = r.json()["payload"]["accessToken"]
        return {"id": user_id, "email": email, "password": password, "headers": {"Authorization": f"Bearer {token}"}}

    yield _make
    # Hires and providers reference users with ON DELETE SET NULL, so clean those first
    for uid in created:
        execute("delete from engagements where client_user_id = %s", (uid,))
        execute("delete from engagements where provider_id in (select id from providers where user_id = %s)", (uid,))
        execute("delete from providers where user_id = %s", (uid,))
        execute("delete from organizations where created_by = %s", (uid,))
        execute("delete from roadmaps where user_id = %s", (uid,))
        execute("delete from users where id = %s", (uid,))
        execute("delete from user_consents where user_id = %s", (uid,))
    # Attempts against unknown emails aren't tied to a user, so they survive the deletes above
    execute("delete from auth_events where ip = 'testclient'")
    execute("delete from support_tickets where ip = 'testclient'")
    execute("delete from feedback_flags where message like '%%[test]%%'")


def approve_pending(client, response, approver: dict) -> dict:
    """A risky admin action answered 202: have a second staff member approve it; returns the decided request."""
    assert response.status_code == 202, response.text
    req = response.json()["payload"]["approval"]
    r = client.post(f"{API}/admin/access/approvals/{req['id']}/approve", json={"note": "ok"}, headers=approver["headers"])
    assert r.status_code == 200, r.text
    return r.json()["payload"]["approval"]
