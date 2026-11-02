"""Actions the assistant offers and the person confirms: nothing happens before the Confirm tap."""

from datetime import date, timedelta
from types import SimpleNamespace as NS

from assistant import llm_agent
from conftest import API
from services.db import execute, fetch_one
from test_assistant import _turn


def _path(client, headers=None):
    p = _turn(client, message="I need a TIN", headers=headers)
    cid = p["conversationId"]
    p = _turn(client, cid, action={"type": "sub_city", "value": "bole"}, headers=headers)
    if p["reply"].get("widget"):
        p = _turn(client, cid, action={"type": "documents", "value": []}, headers=headers)
    return p


def _count(user_id):
    return fetch_one("select count(*) as c from user_reminders where user_id = %s and cancelled_at is null",
                     (user_id,))["c"]


def test_remind_me_under_a_path_is_set_only_after_confirm(client, make_user):
    user = make_user()
    h = user["headers"]
    p = _path(client, h)
    chip = next(q for q in p["reply"]["quick_replies"] if q["label"] == "Remind me in a week")
    p = _turn(client, p["conversationId"], action=chip["action"], headers=h)
    assert p["reply"]["cards"][0]["kind"] == "summary" and _count(user["id"]) == 0  # proposed, not done
    confirm = next(a for a in p["reply"]["actions"] if a["action"]["type"] == "confirm_proposal")
    p = _turn(client, p["conversationId"], action=confirm["action"], headers=h)
    assert "I'll remind you on" in p["reply"]["text"] and _count(user["id"]) == 1
    # The same confirm again does nothing more
    p = _turn(client, p["conversationId"], action=confirm["action"], headers=h)
    assert "expired" in p["reply"]["text"] and _count(user["id"]) == 1
    items = client.get(f"{API}/notifications/reminders", headers=h).json()["payload"]["items"]
    assert items[0]["title"].startswith("Continue: ") and items[0]["link"].startswith("/roadmap/")


def test_cancel_and_signed_out_never_create_a_reminder(client, make_user):
    user = make_user()
    p = _path(client, user["headers"])
    chip = next(q for q in p["reply"]["quick_replies"] if q["label"] == "Remind me in a week")
    p = _turn(client, p["conversationId"], action=chip["action"], headers=user["headers"])
    cancel = next(a for a in p["reply"]["actions"] if a["action"]["type"] == "cancel_proposal")
    p = _turn(client, p["conversationId"], action=cancel["action"], headers=user["headers"])
    assert "didn't do it" in p["reply"]["text"] and _count(user["id"]) == 0

    p = _path(client)  # signed out
    chip = next(q for q in p["reply"]["quick_replies"] if q["label"] == "Remind me in a week")
    p = _turn(client, p["conversationId"], action=chip["action"])
    assert "Sign in" in p["reply"]["text"] and p["reply"]["actions"][0]["href"].startswith("/login")


def test_due_reminders_reach_the_bell_once(client, make_user):
    user = make_user()
    h = user["headers"]
    r = client.post(f"{API}/notifications/reminders", json={"title": "Renew trade licence", "due_on":
                                                            (date.today() + timedelta(days=3)).isoformat()}, headers=h)
    assert r.status_code == 201, r.text
    execute("update user_reminders set due_on = current_date where id = %s", (r.json()["payload"]["id"],))
    titles = [n["title"] for n in client.get(f"{API}/notifications", headers=h).json()["payload"]["items"]]
    assert titles.count("Reminder: Renew trade licence") == 1
    titles = [n["title"] for n in client.get(f"{API}/notifications", headers=h).json()["payload"]["items"]]
    assert titles.count("Reminder: Renew trade licence") == 1  # delivered once


def test_reminder_rules(client, make_user):
    user = make_user()
    h = user["headers"]
    past = client.post(f"{API}/notifications/reminders", json={"title": "Too late", "due_on": "2020-01-01"}, headers=h)
    assert past.status_code == 400
    offsite = client.post(f"{API}/notifications/reminders", json={"title": "Phish", "due_on": date.today().isoformat(),
                                                                  "link": "https://evil.example"}, headers=h)
    assert offsite.status_code == 422
    other = make_user()
    rid = client.post(f"{API}/notifications/reminders", json={"title": "Mine only", "due_on":
                                                              date.today().isoformat()}, headers=h).json()["payload"]["id"]
    assert client.delete(f"{API}/notifications/reminders/{rid}", headers=other["headers"]).status_code == 404
    assert client.delete(f"{API}/notifications/reminders/{rid}", headers=h).status_code == 200


def test_the_ai_can_only_propose_a_reminder(client, make_user, monkeypatch):
    user = make_user()
    due = (date.today() + timedelta(days=30)).isoformat()
    queue = [
        NS(content=[NS(type="tool_use", id="t1", name="propose_action",
                       input={"kind": "remind", "title": "VAT return", "due_on": due})], stop_reason="tool_use",
           model="claude-opus-5-5"),
        NS(content=[NS(type="text", text="I can remind you; tap Set reminder to confirm.", citations=None)],
           stop_reason="end_turn", model="claude-opus-5-5"),
    ]
    monkeypatch.setattr(llm_agent, "enabled", lambda: True)
    monkeypatch.setattr(llm_agent, "_create", lambda messages: queue.pop(0))
    p = _turn(client, message="remind me to file VAT next month", headers=user["headers"])
    assert p["reply"]["intent"] == "agentic" and _count(user["id"]) == 0
    confirm = next(a for a in p["reply"]["actions"] if a["action"]["type"] == "confirm_proposal")
    monkeypatch.setattr(llm_agent, "enabled", lambda: False)
    _turn(client, p["conversationId"], action=confirm["action"], headers=user["headers"])
    assert _count(user["id"]) == 1


def test_hiring_an_unlisted_provider_is_refused():
    from assistant import actions

    try:
        actions.propose({"lang": "en"}, NS(id="x"), "hire", provider_slug="nobody-like-this")
    except actions.ActionError as exc:
        assert "isn't listed" in str(exc)
    else:
        raise AssertionError("expected a refusal")
