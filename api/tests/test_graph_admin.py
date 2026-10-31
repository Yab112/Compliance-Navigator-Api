"""Admin knowledge graph: diagram data, paged documents, document edits.
Needs the seeded compliance graph, like the other integration tests."""

import pytest

from services import graph_admin
from services.db import Jsonb, execute, fetch_one

API = "/api/v1/admin"


@pytest.fixture(scope="module")
def admin(make_user):
    return make_user("admin")


# ---------------------------------------------------------------- API


def test_graph_routes_require_admin(client, make_user):
    user = make_user()
    assert client.get(f"{API}/graph/view", headers=user["headers"]).status_code == 403
    assert client.get(f"{API}/graph/documents", headers=user["headers"]).status_code == 403


def test_cypher_console_is_gone(client, admin):
    r = client.post(f"{API}/graph/query", json={"query": "MATCH (n) RETURN n LIMIT 1"}, headers=admin["headers"])
    assert r.status_code in (404, 405)


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
    row = fetch_one("select id, props from graph_nodes where label = 'Document' order by id limit 1")
    if not row:
        pytest.skip("no documents in the graph")
    doc_id, props = row["id"], row["props"]
    yield doc_id, props
    execute("update graph_nodes set props = %s where label = 'Document' and id = %s", (Jsonb(props), doc_id))


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
