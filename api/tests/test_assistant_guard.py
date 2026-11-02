"""The guard between the AI and our data, and the learning loop staff run from the dashboard."""

import json

from assistant import guard, learning
from conftest import API
from services.db import execute, fetch_one
from test_assistant import _turn

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["query"],
          "properties": {"query": {"type": "string"}, "kind": {"type": "string", "enum": ["a", "b"]}}}


def _guard():
    return guard.Guard({"search": guard.Rule(SCHEMA, 2, "test")}, None)


def test_guard_refuses_what_is_not_on_the_list_or_not_shaped_right():
    g, ran = _guard(), []

    def run():
        ran.append(1)
        return "{}"

    for tool, args, why in [
        ("read_users_table", {}, "not on the allowed list"),
        ("search", {"query": "x", "sql": "select * from users"}, "unknown field"),
        ("search", {}, "missing query"),
        ("search", {"query": "x", "kind": "c"}, "must be one of"),
        ("search", {"query": "x" * 500}, "too long"),
    ]:
        assert why in json.loads(g.request(tool, args, run))["denied"]
    assert ran == []  # none of them reached our code
    assert all(r["decision"] == "denied" for r in g.records)


def test_guard_limits_requests_per_turn_and_removes_personal_data():
    g = _guard()
    out = g.request("search", {"query": "a"}, lambda: '{"note": "mail me at abebe@example.com, FIN 123456789012"}')
    assert "abebe@example.com" not in out and "123456789012" not in out
    g.request("search", {"query": "b"}, lambda: "{}")
    assert "already asked 2" in json.loads(g.request("search", {"query": "c"}, lambda: "{}"))["denied"]


def test_learning_run_turns_gaps_into_findings_with_a_next_action(client, make_user):
    admin = make_user("admin")
    execute("delete from assistant_findings where dedupe_key like 'missing:%%driving%%'")
    for _ in range(2):
        _turn(client, message="how to get driving license in addis")
    assert fetch_one("select gap from assistant_turns order by id desc limit 1")["gap"] == "not_found"
    execute("update assistant_learning_runs set started_at = now() - interval '1 hour' where finished_at is not null")

    r = client.post(f"{API}/admin/assistant/learn", headers=admin["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["payload"]["by_kind"].get("missing_service")

    items = client.get(f"{API}/admin/assistant/findings", params={"status": "new"}, headers=admin["headers"]).json()
    finding = next(f for f in items["payload"]["items"] if "driving" in f["dedupe_key"])
    assert finding["action_type"] == "add_service_data" and finding["seen_count"] >= 2
    assert "Add or import" in finding["next_action"]

    r = client.patch(f"{API}/admin/assistant/findings/{finding['id']}", json={"status": "approved", "note": "MoT data"},
                     headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["status"] == "approved"


def test_learning_and_guard_screens_need_admin(client, make_user):
    user = make_user()
    for method, path in (("post", "/admin/assistant/learn"), ("get", "/admin/assistant/findings"),
                         ("get", "/admin/assistant/guard")):
        assert getattr(client, method)(f"{API}{path}", headers=user["headers"]).status_code == 403


def test_a_correction_message_becomes_a_verify_fact_finding():
    assert learning.CORRECTION.search("that's wrong, the office said it costs 500")
    assert not learning.CORRECTION.search("how much is a passport")
