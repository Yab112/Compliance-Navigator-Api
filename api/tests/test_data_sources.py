"""Data sources: staff-added sources (web page / pasted text), pause and resume, run date filter, stuck runs."""

import socket
import uuid
from datetime import date, timedelta

import pytest
from conftest import API, approve_pending

from services import custom_sources, data_sources, rag_service
from services.db import execute, fetch_one

TEXT = "Proclamation 1150/2019 article 5: a commercial registration certificate must be renewed every year. " * 3
PAGE = (
    b"<html><head><title>T</title><script>var x = 1;</script><style>p{}</style></head>"
    b"<body><nav>Home | About</nav><main><h1>Trade licence directive</h1>"
    b"<p>Every trader must renew the trade licence before the end of the Ethiopian fiscal year.</p>"
    b"<p>Late renewal carries a penalty set by the Ministry of Trade and Regional Integration.</p></main>"
    b"<footer>Copyright</footer></body></html>"
)


@pytest.fixture
def admin(make_user):
    return make_user("admin")


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    """No embedding model in tests: every passage gets the same small vector."""
    monkeypatch.setattr(rag_service, "embed_texts", lambda texts: [[0.01] * 384 for _ in texts])


@pytest.fixture
def cleanup():
    """Collects created custom source ids and removes their rows, passages and runs afterwards."""
    ids: list[str] = []
    yield ids
    for i in ids:
        execute("delete from legal_chunks where service_id = %s", (custom_sources.chunk_service_id(i),))
        execute("delete from data_source_runs where source = %s", (custom_sources.source_key(i),))
        execute("delete from custom_data_sources where id = %s", (i,))


def _body(**over):
    return {"name": "Trade licence directive", "description": "Why it matters", "kind": "pasted_text",
            "text": TEXT, "issuing_body": "Ministry of Trade", "language": "en", "tags": ["Trade Licence", "renewal"],
            "schedule": "manual", "enabled": True, **over}


def _create(client, admin, cleanup, **over):
    r = client.post(f"{API}/admin/data-sources/custom", json=_body(**over), headers=admin["headers"])
    assert r.status_code == 201, r.text
    cleanup.append(r.json()["payload"]["source"]["id"])
    return r.json()["payload"]


def _chunks(source_id: str) -> int:
    return fetch_one("select count(*) as c from legal_chunks where service_id = %s",
                     (custom_sources.chunk_service_id(source_id),))["c"]


def test_custom_source_crud_and_run(client, admin, cleanup, make_user):
    created = _create(client, admin, cleanup)
    src, key = created["source"], created["key"]
    assert key == f"custom:{src['id']}"
    assert src["tags"] == ["trade-licence", "renewal"] and src["created_by"] == admin["email"]

    listed = {s["id"]: s for s in client.get(f"{API}/admin/data-sources", headers=admin["headers"]).json()["payload"]["sources"]}
    assert listed[key]["builtIn"] is False and listed[key]["destinations"] == ["knowledge"]
    assert listed["mesob_catalog"]["builtIn"] is True and listed["mesob_catalog"]["schedule"] == "daily"

    # The background task runs inside the test client, so the run is finished on return
    r = client.post(f"{API}/admin/data-sources/{key}/run", headers=admin["headers"])
    assert r.status_code == 202, r.text
    run = data_sources.list_runs(key, limit=1)[0]
    assert run["status"] == "success", run["error"]
    assert run["stats"]["chunks_inserted"] >= 1 and run["source_label"] == "Trade licence directive"
    assert _chunks(src["id"]) == run["stats"]["chunks_inserted"]

    # Edit: full replacement; the stored text comes back for the edit form
    r = client.put(f"{API}/admin/data-sources/custom/{src['id']}", json=_body(name="Renamed", schedule="weekly"),
                   headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["source"]["name"] == "Renamed"
    assert r.json()["payload"]["source"]["schedule"] == "manual"  # pasted text never needs a timer
    got = client.get(f"{API}/admin/data-sources/custom/{src['id']}", headers=admin["headers"]).json()["payload"]
    assert got["source"]["text"].startswith("Proclamation 1150/2019")

    # Delete removes its passages from the AI knowledge base; run history keeps a readable label
    # Deleting needs a second staff member; it runs when they approve
    r = client.delete(f"{API}/admin/data-sources/custom/{src['id']}", headers=admin["headers"])
    assert r.status_code == 202 and _chunks(src["id"]) > 0
    decided = approve_pending(client, r, make_user("admin"))
    assert decided["status"] == "executed" and decided["result"]["deleted"]["chunks_removed"] >= 1
    assert _chunks(src["id"]) == 0
    assert data_sources.list_runs(key, limit=1)[0]["source_label"] == "Deleted source"
    assert client.delete(f"{API}/admin/data-sources/custom/{src['id']}", headers=admin["headers"]).status_code == 404


def test_custom_source_validation(client, admin):
    post = lambda **over: client.post(f"{API}/admin/data-sources/custom", json=_body(**over), headers=admin["headers"])
    assert post(text="too short").status_code == 422
    assert post(kind="web_page", url=None).status_code == 422
    assert post(kind="rss").status_code == 422
    assert post(language="fr").status_code == 422
    assert post(name="x").status_code == 422
    assert post(tags=[f"t{i}" for i in range(11)]).status_code == 422
    assert post(schedule="hourly").status_code == 422
    assert post(kind="web_page", url="ftp://example.com/file").status_code == 422
    for url in ("http://127.0.0.1/admin", "http://localhost:8000/", "http://10.0.0.5/x", "http://[::1]/",
                "http://169.254.169.254/latest/meta-data", "http://user:pw@example.com/"):
        r = post(kind="web_page", url=url)
        assert r.status_code == 422, url
    assert "not allowed" in post(kind="web_page", url="http://127.0.0.1/").json()["detail"]

    user = client.post  # non-admins are refused
    assert user(f"{API}/admin/data-sources/custom", json=_body()).status_code in (401, 403)


def test_fetch_blocks_private_addresses(monkeypatch):
    with pytest.raises(custom_sources.UnsafeURL):
        custom_sources.fetch_url("http://127.0.0.1/")
    with pytest.raises(custom_sources.UnsafeURL):
        custom_sources.fetch_url("http://localhost/")
    # A public-looking name that resolves to this machine is refused before connecting
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))])
    with pytest.raises(custom_sources.UnsafeURL):
        custom_sources.fetch_url("http://sneaky.example.com/")


def test_web_page_source_reads_html(client, admin, cleanup, monkeypatch):
    seen = []

    def fake_fetch(url):
        seen.append(url)
        return PAGE, "text/html; charset=utf-8"

    monkeypatch.setattr(custom_sources, "fetch_url", fake_fetch)
    created = _create(client, admin, cleanup, kind="web_page", url="https://www.motri.gov.et/directive", text=None,
                      schedule="daily")
    key = created["key"]
    assert created["source"]["schedule"] == "daily"
    assert client.post(f"{API}/admin/data-sources/{key}/run", headers=admin["headers"]).status_code == 202
    run = data_sources.list_runs(key, limit=1)[0]
    assert seen == ["https://www.motri.gov.et/directive"]
    assert run["status"] == "success", run["error"]
    assert run["stats"]["format"] == "html" and run["stats"]["chunks_inserted"] == 1
    content = fetch_one("select content, source_url, topic_tags from legal_chunks where service_id = %s",
                        (custom_sources.chunk_service_id(created["source"]["id"]),))
    assert "renew the trade licence" in content["content"]
    assert "var x" not in content["content"] and "Home | About" not in content["content"]
    assert content["source_url"] == "https://www.motri.gov.et/directive" and "custom" in content["topic_tags"]

    # A scheduled source that just succeeded isn't due again
    assert created["source"]["id"] not in custom_sources.due_for_schedule()
    execute("update data_source_runs set started_at = now() - interval '2 days' where source = %s", (key,))
    assert created["source"]["id"] in custom_sources.due_for_schedule()
    out = data_sources.run_due_custom_sources("test")
    assert out["succeeded"] >= 1
    assert created["source"]["id"] not in custom_sources.due_for_schedule()

    # A page with no readable text fails with a plain message
    monkeypatch.setattr(custom_sources, "fetch_url", lambda url: (b"<html><body></body></html>", "text/html"))
    client.post(f"{API}/admin/data-sources/{key}/run", headers=admin["headers"])
    failed = data_sources.list_runs(key, limit=1)[0]
    assert failed["status"] == "failed" and "No readable text" in failed["error"]


def test_pause_blocks_runs(client, admin, cleanup):
    key = _create(client, admin, cleanup, enabled=False)["key"]
    listed = {s["id"]: s for s in client.get(f"{API}/admin/data-sources", headers=admin["headers"]).json()["payload"]["sources"]}
    assert listed[key]["enabled"] is False and listed[key]["pausedBy"] == admin["email"]
    assert client.post(f"{API}/admin/data-sources/{key}/run", headers=admin["headers"]).status_code == 409

    assert client.post(f"{API}/admin/data-sources/{key}/resume", headers=admin["headers"]).status_code == 200
    assert client.post(f"{API}/admin/data-sources/{key}/run", headers=admin["headers"]).status_code == 202
    assert client.post(f"{API}/admin/data-sources/{key}/pause", headers=admin["headers"]).status_code == 200
    assert client.post(f"{API}/admin/data-sources/{key}/run", headers=admin["headers"]).status_code == 409
    assert client.post(f"{API}/admin/data-sources/nope/pause", headers=admin["headers"]).status_code == 404
    assert client.post(f"{API}/admin/data-sources/custom:not-a-uuid/pause", headers=admin["headers"]).status_code == 404

    # Built-in pipelines pause too; put back whatever state the dev database had
    before = fetch_one("select enabled, paused_by, paused_at from data_source_state where source = 'legal_corpus'")
    try:
        assert client.post(f"{API}/admin/data-sources/legal_corpus/pause", headers=admin["headers"]).status_code == 200
        assert client.post(f"{API}/admin/data-sources/legal_corpus/run", headers=admin["headers"]).status_code == 409
        with pytest.raises(data_sources.SourcePaused):
            data_sources.start_run("legal_corpus", "schedule")
        listed = {s["id"]: s for s in client.get(f"{API}/admin/data-sources", headers=admin["headers"]).json()["payload"]["sources"]}
        assert listed["legal_corpus"]["enabled"] is False and listed["legal_corpus"]["pausedAt"]
    finally:
        if before:
            execute("update data_source_state set enabled = %s, paused_by = %s, paused_at = %s where source = 'legal_corpus'",
                    (before["enabled"], before["paused_by"], before["paused_at"]))
        else:
            execute("delete from data_source_state where source = 'legal_corpus'")


@pytest.fixture
def fake_source():
    key = f"test_src_{uuid.uuid4().hex[:8]}"
    yield key
    execute("delete from data_source_runs where source = %s", (key,))


def _run(source: str, status: str, ago: str) -> str:
    return fetch_one(
        f"""
        insert into data_source_runs (source, status, started_at, finished_at)
        values (%s, %s, now() - interval '{ago}', case when %s = 'running' then null else now() end)
        returning id::text
        """,
        (source, status, status),
    )["id"]


def test_runs_date_filter(client, admin, fake_source):
    _run(fake_source, "success", "1 minute")
    _run(fake_source, "success", "3 days")
    _run(fake_source, "failed", "10 days")
    today = date.today()
    get = lambda **p: client.get(f"{API}/admin/data-sources/runs", params={"source": fake_source, **p},
                                 headers=admin["headers"])
    assert get(**{"from": str(today - timedelta(days=5))}).json()["payload"]["total"] == 2
    assert get(to=str(today - timedelta(days=5))).json()["payload"]["total"] == 1
    assert get(**{"from": str(today - timedelta(days=11)), "to": str(today - timedelta(days=2))}).json()["payload"]["total"] == 2
    assert get(**{"from": str(today), "to": str(today)}).json()["payload"]["total"] == 1
    assert get(**{"from": str(today), "to": str(today - timedelta(days=1))}).status_code == 422
    assert get(**{"from": "not-a-date"}).status_code == 422


def test_mark_stuck_run_failed(client, admin, fake_source):
    stuck = _run(fake_source, "running", "45 minutes")
    fresh = _run(fake_source, "running", "1 minute")
    done = _run(fake_source, "success", "2 hours")
    url = lambda rid: f"{API}/admin/data-sources/runs/{rid}/mark-failed"

    r = client.post(url(stuck), headers=admin["headers"])
    assert r.status_code == 200, r.text
    row = fetch_one("select status, error, finished_at from data_source_runs where id = %s", (stuck,))
    assert row["status"] == "failed" and admin["email"] in row["error"] and row["finished_at"]
    assert client.post(url(fresh), headers=admin["headers"]).status_code == 409
    assert client.post(url(done), headers=admin["headers"]).status_code == 409
    assert client.post(url(uuid.uuid4()), headers=admin["headers"]).status_code == 404
