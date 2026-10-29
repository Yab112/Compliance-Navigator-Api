"""Sandbox Fayda verification for tests (FAYDA_MODE=sandbox, the default)."""

import random
from urllib.parse import parse_qs, urlparse

from conftest import API


def random_fin() -> str:
    return "".join(random.choice("0123456789") for _ in range(12))


def start_state(client, user) -> str:
    r = client.post(f"{API}/guday/fayda/start", headers=user["headers"])
    assert r.status_code == 200, r.text
    return parse_qs(urlparse(r.json()["payload"]["redirect_url"]).query)["state"][0]


def sandbox_verify(client, user, *, fin: str | None = None, name: str = "Test Agent", otp: str = "111111"):
    state = start_state(client, user)
    return client.post(
        f"{API}/guday/fayda/sandbox/complete",
        json={"state": state, "id_number": fin or random_fin(), "full_name": name, "otp": otp},
        headers=user["headers"],
    )


def ensure_verified(client, user) -> None:
    status = client.get(f"{API}/guday/fayda/status", headers=user["headers"]).json()["payload"]
    if not status["verification"]:
        r = sandbox_verify(client, user)
        assert r.status_code == 200, r.text
