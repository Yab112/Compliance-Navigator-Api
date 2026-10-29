"""Admin knowledge graph: diagram data, paged documents, document edits, read-only Cypher console.
Needs Neo4j with the seeded compliance graph, like the other integration tests."""

import pytest

from services import graph_admin
from services.graph_service import _query_rows

API = "/api/v1/admin"


@pytest.fixture(scope="module")
def admin(make_user):
    return make_user("admin")


# ---------------------------------------------------------------- Cypher guard (no database needed)


@pytest.mark.parametrize(
    "query",
    [
        "MATCH (n) SET n.x = 1",
        "create (n:Hack) return n",
        "MATCH (n) DETACH DELETE n",
        "MERGE (n:X {id: 1}) RETURN n",
        "MATCH (n) REMOVE n.name RETURN n",
        "MATCH (n) FOREACH (x IN [1] | SET n.y = x)",
        "LOAD CSV FROM 'https://example.com/a.csv' AS row RETURN row",
        "load   csv with headers from 'file:///etc/passwd' AS r RETURN r",
        "CALL dbms.listConfig()",
        "CALL apoc.load.json('https://example.com')",
        "RETURN apoc.version()",
        "CALL { MATCH (n) RETURN n } IN TRANSACTIONS RETURN 1",
        "CALL db.createLabel('X')",
        "SHOW USERS",
        "DROP INDEX foo",
        "MATCH (n) // harmless comment\nSET n.x = 1",
    ],
)
def test_cypher_guard_rejects_writes_and_admin_calls(query):
    with pytest.raises(graph_admin.CypherRejected):
        graph_admin.check_readonly_cypher(query)


@pytest.mark.parametrize(
    "query",
    [
        "MATCH (d:Document) RETURN d.name AS name LIMIT 5",
        "MATCH (d:Document {name: 'SET CREATE DELETE'}) RETURN d",  # keywords inside strings are fine
        "MATCH (n) RETURN n.offset, n.created_at, n.settings LIMIT 1",  # words that merely contain keywords
        "CALL db.labels()",
        "MATCH (d) /* CREATE in a comment */ RETURN count(d) AS c",
    ],
)
def test_cypher_guard_allows_reads(query):
    graph_admin.check_readonly_cypher(query)


# ---------------------------------------------------------------- API


def test_graph_routes_require_admin(client, make_user):
    user = make_user()
    assert client.get(f"{API}/graph/view", headers=user["headers"]).status_code == 403
    r = client.post(f"{API}/graph/query", json={"query": "MATCH (n) RETURN n LIMIT 1"}, headers=user["headers"])
    assert r.status_code == 403


def test_cypher_console_rejects_write_and_caps_rows(client, admin):
    before = _query_rows("MATCH (n:ZzConsoleTest) RETURN count(n) AS c")[0]["c"]
    r = client.post(f"{API}/graph/query", json={"query": "CREATE (n:ZzConsoleTest) RETURN n"}, headers=admin["headers"])
    assert r.status_code == 400
    assert "Rejected" in r.json()["detail"]
    assert _query_rows("MATCH (n:ZzConsoleTest) RETURN count(n) AS c")[0]["c"] == before

    r = client.post(
        f"{API}/graph/query",
        json={"query": "UNWIND range(1, 500) AS x RETURN x"},
        headers=admin["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()["payload"]
    assert body["count"] == graph_admin.CYPHER_MAX_ROWS
    assert body["truncated"] is True


def test_readonly_session_blocks_writes_that_slip_past_the_guard(monkeypatch):
    # Even with the keyword check switched off, Neo4j refuses writes in the READ session
    monkeypatch.setattr(graph_admin, "check_readonly_cypher", lambda q: None)
    with pytest.raises(Exception, match="(?i)read|access"):
        graph_admin.run_cypher_readonly("CREATE (n:ZzConsoleTest) RETURN n")
    assert _query_rows("MATCH (n:ZzConsoleTest) RETURN count(n) AS c")[0]["c"] == 0


def test_view_edges_connect_drawn_nodes(client, admin):
    r = client.get(f"{API}/graph/view", headers=admin["headers"])
    assert r.status_code == 200
    view = r.json()["payload"]
    keys = {n["key"] for n in view["nodes"]}
    assert len(keys) == len(view["nodes"]), "node keys must be unique"
    assert view["edges"], "the seeded graph has links"
    for e in view["edges"]:
        assert e["source"] in keys and e["target"] in keys, e
    # Prerequisite edges point from what comes first to what needs it
    if "Document:kebele_id" in keys and "Document:passport" in keys:
        assert {"source": "Document:kebele_id", "target": "Document:passport", "type": "REQUIRES"} in view["edges"]


def test_documents_are_paged_searched_and_filtered(client, admin):
    h = admin["headers"]
    full = client.get(f"{API}/graph/documents", params={"limit": 100}, headers=h).json()["payload"]
    assert full["total"] == len(full["items"]) or full["total"] > 100
    if full["total"] < 2:
        pytest.skip("needs at least two documents in the graph")

    first = client.get(f"{API}/graph/documents", params={"limit": 1, "offset": 0}, headers=h).json()["payload"]
    second = client.get(f"{API}/graph/documents", params={"limit": 1, "offset": 1}, headers=h).json()["payload"]
    assert first["total"] == full["total"]
    assert len(first["items"]) == 1 and len(second["items"]) == 1
    assert first["items"][0]["id"] != second["items"][0]["id"]

    target = full["items"][0]
    found = client.get(f"{API}/graph/documents", params={"q": target["name"][:6]}, headers=h).json()["payload"]
    assert target["id"] in [d["id"] for d in found["items"]]

    stale = client.get(f"{API}/graph/documents", params={"status": "stale", "limit": 100}, headers=h).json()["payload"]
    fresh = client.get(f"{API}/graph/documents", params={"status": "verified", "limit": 100}, headers=h).json()["payload"]
    assert all(d.get("stale") for d in stale["items"])
    assert not any(d.get("stale") for d in fresh["items"])
    assert stale["total"] + fresh["total"] == full["total"]

    assert client.get(f"{API}/graph/documents", params={"status": "bogus"}, headers=h).status_code == 422
    assert client.get(f"{API}/graph/documents", params={"limit": 1000}, headers=h).status_code == 422


@pytest.fixture
def restored_document():
    """A real document whose properties are put back exactly as they were after the test."""
    rows = _query_rows("MATCH (d:Document) RETURN d.id AS id, properties(d) AS props ORDER BY d.id LIMIT 1")
    if not rows:
        pytest.skip("no documents in the graph")
    doc_id, props = rows[0]["id"], rows[0]["props"]
    yield doc_id, props
    _query_rows("MATCH (d:Document {id: $id}) SET d = $props", {"id": doc_id, "props": props})


def test_document_edit_validates_and_records_verifier(client, admin, restored_document):
    doc_id, props = restored_document
    h = admin["headers"]
    url = f"{API}/graph/documents/{doc_id}"
    assert client.patch(url, json={"fee_etb": -5}, headers=h).status_code == 422
    assert client.patch(url, json={"fee_etb": 5_000_000}, headers=h).status_code == 422
    assert client.patch(url, json={"avg_processing_days": 99999}, headers=h).status_code == 422
    assert client.patch(url, json={"source_url": "javascript:alert(1)"}, headers=h).status_code == 422
    assert client.patch(f"{API}/graph/documents/no-such-doc", json={"fee_etb": 1}, headers=h).status_code == 404

    r = client.patch(
        url,
        json={"fee_etb": props.get("fee_etb") or 0, "rejection_reasons": ["  a  ", "", "b"], "mark_verified": True},
        headers=h,
    )
    assert r.status_code == 200, r.text
    doc = r.json()["payload"]["document"]
    assert doc["verified_by"] == admin["email"]
    assert doc["stale"] is False
    assert doc["rejection_reasons"] == ["a", "b"]

    got = client.get(url, headers=h).json()["payload"]["document"]
    assert got["verified_by"] == admin["email"]
    # Roadmaps and the assistant load Document nodes through the model; the new fields must not break that
    assert any(d["id"] == doc_id for d in graph_admin.list_documents())


def test_institutions_are_paged(client, admin):
    h = admin["headers"]
    page = client.get(f"{API}/graph/institutions", params={"limit": 2}, headers=h).json()["payload"]
    assert set(page) == {"items", "total"}
    assert len(page["items"]) <= 2
    if page["items"]:
        name = page["items"][0]["name"]
        found = client.get(f"{API}/graph/institutions", params={"q": name}, headers=h).json()["payload"]
        assert name in [i["name"] for i in found["items"]]


def test_assistant_review_turns_are_paged(client, admin):
    h = admin["headers"]
    r = client.get(f"{API}/assistant/turns", params={"limit": 2, "max_confidence": 1, "include_labelled": True}, headers=h)
    assert r.status_code == 200
    body = r.json()["payload"]
    assert set(body) == {"items", "total"}
    assert len(body["items"]) <= 2 and body["total"] >= len(body["items"])


def test_assistant_activate_rejects_paths(client, admin):
    r = client.post(f"{API}/assistant/activate/..%2F..%2Fetc", headers=admin["headers"])
    assert r.status_code == 404
    assert client.post(f"{API}/assistant/activate/.hidden", headers=admin["headers"]).status_code == 404
