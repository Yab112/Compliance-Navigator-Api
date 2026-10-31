"""The compliance graph tables (graph_nodes, graph_edges) and the helpers over them."""

import uuid

import pytest

from models.compliance_nodes import DocumentNode
from models.compliance_relationships import RequiresRel
from services import graph_store
from services.db import connection, fetch_one

LABEL = "ZzGraphStoreTest"


@pytest.fixture
def label(client):
    """A label of its own per test, removed afterwards (with every link, by cascade)."""
    name = f"{LABEL}{uuid.uuid4().hex[:8]}"
    yield name
    with connection() as conn:
        conn.execute("delete from graph_nodes where label = %s", (name,))


def _edge_count(label: str) -> int:
    return fetch_one("select count(*)::int as c from graph_edges where src_label = %s or dst_label = %s",
                     (label, label))["c"]


def test_merge_node_is_idempotent_and_merges_properties(label):
    graph_store.merge_node(label, "a", {"id": "a", "name": "First", "fee": 10})
    graph_store.merge_node(label, "a", {"id": "a", "name": "First", "fee": 10})
    props = graph_store.merge_node(label, "a", {"fee": 20, "tags": ["x"], "name": None})
    assert props == {"id": "a", "fee": 20, "tags": ["x"]}, "new values win, None removes, the rest stays"
    assert fetch_one("select count(*)::int as c from graph_nodes where label = %s", (label,))["c"] == 1
    assert graph_store.get_node(label, "a") == props
    assert graph_store.get_node(label, "missing") is None


def test_merge_edge_needs_both_nodes_and_is_idempotent(label):
    graph_store.merge_node(label, "a", {"id": "a"})
    graph_store.merge_node(label, "b", {"id": "b"})
    assert graph_store.merge_edge("LINKS", (label, "a"), (label, "b"), {"why": "test"})
    assert graph_store.merge_edge("LINKS", (label, "a"), (label, "b"), {"also": 1})
    assert not graph_store.merge_edge("LINKS", (label, "a"), (label, "nope"))
    assert _edge_count(label) == 1
    out = graph_store.neighbors(label, "a", "LINKS", "out")
    assert [(n["id"], n["edge"]) for n in out] == [("b", {"why": "test", "also": 1})]
    assert [n["id"] for n in graph_store.neighbors(label, "b", "LINKS", "in")] == ["a"]
    assert graph_store.neighbors(label, "b", "LINKS", "out") == []


def test_deleting_a_node_deletes_its_links(label):
    for n in "abc":
        graph_store.merge_node(label, n, {"id": n})
    graph_store.merge_edge("LINKS", (label, "a"), (label, "b"))
    graph_store.merge_edge("LINKS", (label, "b"), (label, "c"))
    assert graph_store.delete_node(label, "b") == 1
    assert _edge_count(label) == 0
    assert graph_store.get_node(label, "a") and graph_store.get_node(label, "c")


def test_ancestors_follow_chains_and_stop_on_cycles(label):
    # d -> a -> b -> c -> a (a cycle), and e is unrelated
    for n in "abcde":
        graph_store.merge_node(label, n, {"id": n})
    for src, dst in [("d", "a"), ("a", "b"), ("b", "c"), ("c", "a")]:
        graph_store.merge_edge("NEEDS", (label, src), (label, dst))
    graph_store.merge_edge("OTHER", (label, "e"), (label, "c"))
    found = {i for _, i in graph_store.ancestors_via("NEEDS", label, "c")}
    assert found == {"a", "b", "c", "d"}
    assert graph_store.ancestors_via("NEEDS", label, "d") == []


def test_find_nodes_filters_and_searches(label):
    graph_store.merge_node(label, "x1", {"id": "x1", "name": "Trade License", "kind": "permit"})
    graph_store.merge_node(label, "x2", {"id": "x2", "name": "Passport", "kind": "id"})
    assert [n["id"] for n in graph_store.find_nodes(label)] == ["x2", "x1"]
    assert [n["id"] for n in graph_store.find_nodes(label, search="LICENSE")] == ["x1"]
    assert [n["id"] for n in graph_store.find_nodes(label, filters={"kind": "id"})] == ["x2"]
    assert [n["id"] for n in graph_store.find_nodes(label, limit=1, offset=1)] == ["x1"]
    assert graph_store.count_by_label()[label] == 2


def test_writes_roll_back_with_the_transaction(label):
    with pytest.raises(RuntimeError):
        with connection() as conn, conn.transaction():
            graph_store.merge_node(label, "a", {"id": "a"}, conn)
            assert graph_store.get_node(label, "a", conn) is not None
            raise RuntimeError("something else failed")
    assert graph_store.get_node(label, "a") is None


def test_models_round_trip_through_the_store():
    a = DocumentNode(id=f"zz-doc-{uuid.uuid4().hex[:8]}", name="Test prerequisite")
    b = DocumentNode(id=f"zz-doc-{uuid.uuid4().hex[:8]}", name="Test document", required_input_labels=["Photo"])
    try:
        a.merge()
        b.merge()
        assert RequiresRel(source=a, target=b).merge()
        got = DocumentNode.match(b.id)
        assert got == b
        assert [n["id"] for n in graph_store.neighbors("Document", b.id, "REQUIRES", "in")] == [a.id]
    finally:
        graph_store.delete_node("Document", a.id)
        graph_store.delete_node("Document", b.id)
