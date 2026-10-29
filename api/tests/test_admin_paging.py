"""Admin lists that page on the server: data source run history (with per-source health) and sign-in activity."""

import uuid

import pytest
from conftest import API
from services import data_sources
from services.db import execute, fetch_one


@pytest.fixture
def fake_source():
    """A source key no real pipeline uses, so counts are exact; its rows are removed afterwards."""
    key = f"test_src_{uuid.uuid4().hex[:8]}"
    yield key
    execute("delete from data_source_runs where source = %s", (key,))


def _run(source: str, status: str, days_ago: float, seconds: int = 10, error: str | None = None) -> str:
    return fetch_one(
        """
        insert into data_source_runs (source, status, error, started_at, finished_at)
        values (%(s)s, %(st)s, %(e)s, now() - make_interval(secs => %(ago)s),
                case when %(st)s = 'running' then null
                     else now() - make_interval(secs => %(ago)s) + make_interval(secs => %(dur)s) end)
        returning id::text
        """,
        {"s": source, "st": status, "e": error, "ago": days_ago * 86400, "dur": seconds},
    )["id"]


def test_run_history_pages_newest_first_with_filters(client, make_user, fake_source):
    admin = make_user("admin")
    ids = [_run(fake_source, "success" if i % 3 else "failed", days_ago=i) for i in range(7)]  # ids[0] newest
    get = lambda **p: client.get(f"{API}/admin/data-sources/runs", params={"source": fake_source, **p},  # noqa: E731
                                 headers=admin["headers"]).json()["payload"]

    first = get(limit=3)
    assert first["total"] == 7 and [r["id"] for r in first["items"]] == ids[:3]
    assert [r["id"] for r in get(limit=3, offset=6)["items"]] == ids[6:]
    failed = get(status="failed")
    assert failed["total"] == 3 and [r["id"] for r in failed["items"]] == [ids[0], ids[3], ids[6]]
    assert get(status="running")["total"] == 0
    assert client.get(f"{API}/admin/data-sources/runs", params={"status": "nope"},
                      headers=admin["headers"]).status_code == 422
    assert client.get(f"{API}/admin/data-sources/runs", params={"limit": 101},
                      headers=admin["headers"]).status_code == 422


def test_source_health_counts_last_30_days(client, make_user, fake_source):
    _run(fake_source, "success", days_ago=0.1, seconds=20)
    _run(fake_source, "success", days_ago=2, seconds=40)
    _run(fake_source, "failed", days_ago=1, seconds=30, error="Boom\nTraceback line")
    _run(fake_source, "failed", days_ago=45, seconds=99)  # outside the window
    _run(fake_source, "running", days_ago=0)

    h = data_sources._source_health([fake_source])[fake_source]
    assert (h["runs"], h["successes"], h["failures"]) == (4, 2, 1)
    assert h["successRate"] == pytest.approx(2 / 3, abs=1e-3)
    assert h["avgDurationS"] == 30 and h["lastDurationS"] == 20
    assert h["lastFailureError"] == "Boom\nTraceback line"
    assert h["lastSuccessAt"] > h["lastFailureAt"]
    assert len(h["daily"]) == 30 and sum(d["success"] for d in h["daily"]) == 2
    assert sum(d["failed"] for d in h["daily"]) == 1
    assert h["daily"][-1]["day"] > h["daily"][0]["day"]

    empty = data_sources._source_health(["never_ran_" + fake_source])["never_ran_" + fake_source]
    assert empty["runs"] == 0 and empty["successRate"] is None and empty["lastSuccessAt"] is None

    admin = make_user("admin")
    sources = client.get(f"{API}/admin/data-sources", headers=admin["headers"]).json()["payload"]["sources"]
    assert all(len(s["health"]["daily"]) == 30 for s in sources)


def test_sign_in_activity_pages_with_total(client, make_user):
    admin = make_user("admin")
    someone = make_user()
    for _ in range(3):  # register already logged one event for this user
        client.post(f"{API}/auth/login", json={"email": someone["email"], "password": "wrong-password-9"})
    get = lambda **p: client.get(f"{API}/admin/auth/events", params=p, headers=admin["headers"]).json()["payload"]  # noqa: E731

    mine = get(user_id=someone["id"], limit=2)
    assert mine["total"] == 4 and len(mine["events"]) == 2
    rest = get(user_id=someone["id"], limit=2, offset=2)["events"]
    assert len(rest) == 2 and not {e["id"] for e in rest} & {e["id"] for e in mine["events"]}
    assert mine["events"][0]["created_at"] >= rest[0]["created_at"]

    everyone = get(limit=25)
    assert everyone["total"] >= 4 and len(everyone["events"]) == min(25, everyone["total"])
