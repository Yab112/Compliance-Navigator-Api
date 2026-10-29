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

API = "/api/v1"


@pytest.fixture(scope="session")
def client():
    # Every test request comes from the same "IP", so lift the per-network limits
    from auth import service

    service.MAX_REGISTRATIONS_PER_IP_HOUR = 10_000
    service.MAX_FAILED_PER_IP = 10_000
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def make_user(client):
    created: list[str] = []

    def _make(role: str = "user") -> dict:
        email = f"test-{uuid.uuid4().hex[:10]}@example.com"
        password = "test-password-1"
        r = client.post(f"{API}/auth/register", json={"email": email, "password": password, "fullname": "Test User"})
        assert r.status_code == 201, r.text
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
    # Attempts against unknown emails aren't tied to a user, so they survive the deletes above
    execute("delete from auth_events where ip = 'testclient'")
    execute("delete from support_tickets where ip = 'testclient'")
    execute("delete from feedback_flags where message like '%%[test]%%'")
