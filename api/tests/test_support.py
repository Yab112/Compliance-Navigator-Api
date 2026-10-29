"""The agent's actions (handoff, report, staff match, status) and the support desk behind them."""

from conftest import API


def _turn(client, cid=None, message=None, action=None, headers=None):
    r = client.post(f"{API}/assistant/turn", json={"conversation_id": cid, "message": message, "action": action},
                    headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()["payload"]


def _form(client, cid, key, value, headers=None):
    return _turn(client, cid, action={"type": "form", "key": key, "value": value}, headers=headers)


def test_contact_form_rules(client, make_user):
    meta = client.get(f"{API}/support/meta").json()["payload"]
    assert {q["key"] for q in meta["queues"]} >= {"compliance", "marketplace", "technical"} and meta["contact"]["phone"]
    anon = {"subject": "Question about TIN", "body": "Do I need a TIN before a trade license?"}
    assert client.post(f"{API}/support/tickets", json=anon).status_code == 400  # no way to reach them
    r = client.post(f"{API}/support/tickets", json={**anon, "queue": "compliance", "name": "Abebe", "phone": "0911223344"})
    assert r.status_code == 201, r.text
    ticket = r.json()["payload"]["ticket"]
    assert ticket["ref"].startswith("CN-") and ticket["status"] == "new" and ticket["queue_label"] == "Compliance and requirements"

    user = make_user()
    mine = client.post(f"{API}/support/tickets", json={**anon, "subject": "Urgent: deadline today"}, headers=user["headers"])
    assert mine.json()["payload"]["ticket"]["priority"] == "high"  # urgency words raise the priority
    assert len(client.get(f"{API}/support/tickets", headers=user["headers"]).json()["payload"]["items"]) == 1
    # Someone else's ticket is invisible
    assert client.get(f"{API}/support/tickets/{ticket['id']}", headers=user["headers"]).status_code == 404


def test_handoff_asks_what_it_needs_then_staff_reply_reaches_the_chat(client, make_user):
    admin, user = make_user("admin"), make_user()
    h = user["headers"]
    p = _turn(client, message="I want to talk to a person", headers=h)
    cid = p["conversationId"]
    assert p["reply"]["widget"]["key"] == "queue"  # nothing says what it's about: ask
    p = _turn(client, cid, action={"type": "choice", "key": "queue", "value": "compliance"}, headers=h)
    assert p["reply"]["widget"]["kind"] == "form" and p["reply"]["widget"]["key"] == "details"
    p = _form(client, cid, "details", {"details": "Which permits do I need to import medical equipment?"}, headers=h)
    assert p["reply"]["widget"]["key"] == "contact"  # this account has no phone yet
    p = _form(client, cid, "contact", {"phone": "12"}, headers=h)
    assert p["reply"]["widget"]["key"] == "contact"  # a bad number is asked again
    p = _form(client, cid, "contact", {"phone": "0911 22 33 44"}, headers=h)
    summary = p["reply"]["cards"][0]
    assert summary["kind"] == "summary" and any("medical equipment" in r["value"] for r in summary["rows"])
    assert [a["action"]["type"] for a in p["reply"]["actions"]] == ["confirm", "cancel_task"]

    p = _turn(client, cid, action={"type": "confirm", "value": "handoff"}, headers=h)
    card = p["reply"]["cards"][0]
    assert card["kind"] == "ticket" and p["channel"] == "human" and p["ticket"]["ref"] == card["ref"]
    tid = card["id"]

    # While the team has it, typed messages go to the ticket, not the bot
    p = _turn(client, cid, message="I also need it before Friday", headers=h)
    assert p["reply"] is None and p["delivered"] is True
    detail = client.get(f"{API}/admin/support/tickets/{tid}", headers=admin["headers"]).json()["payload"]
    assert detail["ticket"]["queue"] == "compliance" and detail["ticket"]["contact_phone"] == "0911223344"
    assert [m["author_kind"] for m in detail["messages"]] == ["customer", "customer"]
    assert detail["ticket"]["context"]["summary"] and detail["transcript"]

    # Staff: internal note stays internal, the reply reaches the chat and the bell
    client.post(f"{API}/admin/support/tickets/{tid}/messages", json={"body": "Check EFDA rules", "internal": True},
                headers=admin["headers"])
    r = client.post(f"{API}/admin/support/tickets/{tid}/messages",
                    json={"body": "You need an EFDA import permit. I'll send the list."}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["payload"]["ticket"]["status"] == "waiting_customer"
    conv = client.get(f"{API}/assistant/conversations/{cid}", headers=h).json()["payload"]
    staff = [m for m in conv["messages"] if m["role"] == "staff"]
    assert len(staff) == 1 and staff[0]["staff"]["team"] == "Compliance and requirements" and conv["channel"] == "human"
    newer = client.get(f"{API}/assistant/conversations/{cid}", params={"after": staff[0]["id"]}, headers=h).json()["payload"]
    assert newer["messages"] == []
    mine = client.get(f"{API}/support/tickets/{tid}", headers=h).json()["payload"]
    assert all(not m["internal"] for m in mine["messages"]) and len(mine["messages"]) == 3
    bell = client.get(f"{API}/notifications", headers=h).json()["payload"]["items"]
    assert any(n["kind"] == "support_reply" for n in bell)

    # Back to the bot whenever they like
    p = _turn(client, cid, action={"type": "channel", "value": "agent"}, headers=h)
    assert p["channel"] == "agent" and card["ref"] in p["reply"]["text"]
    p = _turn(client, cid, message="hi", headers=h)
    assert p["reply"] is not None


def test_complaint_is_routed_with_priority_and_needs_no_extra_questions(client, make_user):
    user = make_user()
    client.patch(f"{API}/auth/me", json={"phone": "0922334455"}, headers=user["headers"])
    p = _turn(client, message="The agent took my deposit of 5000 birr and disappeared last week", headers=user["headers"])
    rows = {r["label"]: r["value"] for r in p["reply"]["cards"][0]["rows"]}
    assert rows["Team"] == "Providers and hires" and rows["Priority"] == "High"
    p = _turn(client, p["conversationId"], message="yes", headers=user["headers"])
    assert p["ticket"] and p["channel"] == "human"


def test_signed_out_handoff_collects_name_and_phone(client):
    p = _turn(client, message="my fayda verification is not working, can someone from your team call me back")
    cid = p["conversationId"]
    form = p["reply"]["widget"]  # team and problem are clear from the message; only contact is missing
    assert form["key"] == "contact" and [f["key"] for f in form["fields"]] == ["name", "phone", "email"]
    p = _form(client, cid, "contact", {"name": "Test Person", "phone": "0911000111"})
    assert {r["value"] for r in p["reply"]["cards"][0]["rows"]} >= {"Account and website"}
    p = _turn(client, cid, action={"type": "cancel_task"})
    assert p["ticket"] is None and p["channel"] == "agent"


def test_report_and_status(client, make_user):
    user = make_user()
    h = user["headers"]
    p = _turn(client, message="check my requests")
    assert p["reply"]["actions"][0]["href"].startswith("/login")
    p = _turn(client, message="report wrong information", headers=h)
    cid = p["conversationId"]
    assert p["reply"]["widget"]["key"] == "service"
    p = _form(client, cid, "service", {"service": "Bole MESOB passport desk"}, headers=h)
    p = _form(client, cid, "what", {"what": "[test] They now open at 8:00, not 8:30"}, headers=h)
    p = _turn(client, cid, action={"type": "confirm", "value": "report_problem"}, headers=h)
    assert p["reply"]["cards"][0]["kind"] == "ticket"
    p = _turn(client, cid, action={"type": "channel", "value": "agent"}, headers=h)
    p = _turn(client, cid, message="what is the status of my request", headers=h)
    status = p["reply"]["cards"][0]
    assert status["kind"] == "status" and status["items"][0]["kind"] == "ticket"


def test_admin_desk_permissions_and_workflow(client, make_user):
    admin, user = make_user("admin"), make_user()
    assert client.get(f"{API}/admin/support/summary", headers=user["headers"]).status_code == 403
    t = client.post(f"{API}/support/tickets", json={"subject": "Login problem", "body": "OTP never arrives",
                                                    "queue": "technical"}, headers=user["headers"]).json()["payload"]["ticket"]
    summary = client.get(f"{API}/admin/support/summary", headers=admin["headers"]).json()["payload"]
    assert summary["totals"]["new"] >= 1 and next(q for q in summary["queues"] if q["key"] == "technical")["open"] >= 1
    assert set(summary["related"]) == {"hires_unmatched", "deals_to_follow_up", "wrong_info_reports", "providers_pending",
                                       "org_submissions_pending"}
    listing = client.get(f"{API}/admin/support/tickets", params={"queue": "technical", "assigned": "none"},
                         headers=admin["headers"]).json()["payload"]
    assert any(i["id"] == t["id"] for i in listing["items"])
    r = client.patch(f"{API}/admin/support/tickets/{t['id']}", json={"assignee_id": admin["id"], "priority": "urgent"},
                     headers=admin["headers"])
    ticket = r.json()["payload"]["ticket"]
    assert ticket["assignee_id"] == admin["id"] and ticket["priority"] == "urgent" and ticket["status"] == "open"
    assert client.patch(f"{API}/admin/support/tickets/{t['id']}", json={"assignee_id": user["id"]},
                        headers=admin["headers"]).status_code == 400  # only staff
    client.patch(f"{API}/admin/support/tickets/{t['id']}", json={"status": "resolved"}, headers=admin["headers"])
    # A customer reply reopens it
    r = client.post(f"{API}/support/tickets/{t['id']}/messages", json={"body": "Still broken"}, headers=user["headers"])
    assert r.json()["payload"]["ticket"]["status"] == "open"


# ---------------------------------------------------------------- desk tools (reopen window, SLA, saved replies,
# customer context, export)

import pytest  # noqa: E402

from services import platform_settings  # noqa: E402
from services.db import execute, fetch_one  # noqa: E402


@pytest.fixture(autouse=True)
def _no_ticket_limit(monkeypatch):
    """Every test request comes from one address; lift the per-address ticket limit."""
    real = platform_settings.get_int
    monkeypatch.setattr(platform_settings, "get_int",
                        lambda key: 10_000 if key == "support_tickets_per_ip_hour" else real(key))


def _ticket(client, headers=None, **extra):
    body = {"subject": "[test] Payment question", "body": "I paid but the hire still says unpaid", "queue": "marketplace",
            **extra}
    if not headers:
        body = {"name": "Test Person", "phone": "0911000999", **body}
    r = client.post(f"{API}/support/tickets", json=body, headers=headers or {})
    assert r.status_code == 201, r.text
    return r.json()["payload"]["ticket"]


def _cleanup_audit(*ids):
    for i in ids:
        execute("delete from staff_audit_log where actor_id::text = %s", (i,))


def test_send_and_resolve_is_one_step_and_the_reply_clock_restarts(client, make_user):
    admin, user = make_user("admin"), make_user()
    ah, uh = admin["headers"], user["headers"]
    t = _ticket(client, uh)
    assert t["next_response_due_at"] and t["waiting_on"] == "us"
    url = f"{API}/admin/support/tickets/{t['id']}/messages"
    assert client.post(url, json={"body": "note", "internal": True, "resolve": True}, headers=ah).status_code == 400
    r = client.post(url, json={"body": "Refund sent, sorry for the wait.", "resolve": True}, headers=ah)
    assert r.status_code == 200, r.text
    detail = r.json()["payload"]
    assert detail["ticket"]["status"] == "resolved" and detail["ticket"]["next_response_due_at"] is None
    assert [m["author_kind"] for m in detail["messages"]] == ["customer", "staff", "system"]
    bell = client.get(f"{API}/notifications", headers=uh).json()["payload"]["items"]
    assert sum(n["kind"] == "support_reply" for n in bell) == 1 and "resolved" in bell[0]["title"]

    # The customer writes again inside the window: it reopens and we owe an answer again
    mine = client.get(f"{API}/support/tickets/{t['id']}", headers=uh).json()["payload"]["ticket"]
    assert mine["can_reopen"] is True and mine["reopen_until"]
    r = client.post(f"{API}/support/tickets/{t['id']}/messages", json={"body": "It still shows unpaid"}, headers=uh)
    again = r.json()["payload"]["ticket"]
    assert again["status"] == "open" and again["next_response_due_at"] and again["waiting_on"] == "us"
    assert not again["overdue"]
    # Past the deadline it counts as overdue, although it was answered once
    execute("update support_tickets set next_response_due_at = now() - interval '1 minute' where id = %s", (t["id"],))
    listing = client.get(f"{API}/admin/support/tickets", params={"status": "overdue", "limit": 100}, headers=ah).json()
    assert any(i["id"] == t["id"] and i["overdue"] for i in listing["payload"]["items"])
    assert client.get(f"{API}/admin/support/summary", headers=ah).json()["payload"]["totals"]["overdue"] >= 1
    _cleanup_audit(admin["id"])


def test_a_long_closed_request_cannot_be_reopened_but_can_be_followed_up(client, make_user):
    admin, user, other = make_user("admin"), make_user(), make_user()
    t = _ticket(client, user["headers"])
    client.patch(f"{API}/admin/support/tickets/{t['id']}", json={"status": "closed"}, headers=admin["headers"])
    execute("update support_tickets set resolved_at = now() - interval '8 days' where id = %s", (t["id"],))
    mine = client.get(f"{API}/support/tickets/{t['id']}", headers=user["headers"]).json()["payload"]["ticket"]
    assert mine["can_reopen"] is False
    r = client.post(f"{API}/support/tickets/{t['id']}/messages", json={"body": "Hello?"}, headers=user["headers"])
    assert r.status_code == 409 and "new request" in r.json()["detail"]
    follow = _ticket(client, user["headers"], follow_up_of=t["id"])
    assert follow["follow_up_of"] == t["id"] and follow["follow_up_of_ref"] == t["ref"]
    # Nobody can link to someone else's request
    r = client.post(f"{API}/support/tickets", json={"subject": "Mine", "body": "Linking a stranger's request",
                                                    "follow_up_of": t["id"]}, headers=other["headers"])
    assert r.status_code == 404
    _cleanup_audit(admin["id"])


def test_assignment_and_status_changes_are_audited_and_the_customer_hears_what_matters(client, make_user):
    admin, user = make_user("admin"), make_user()
    t = _ticket(client, user["headers"])
    url = f"{API}/admin/support/tickets/{t['id']}"
    client.patch(url, json={"assignee_id": admin["id"]}, headers=admin["headers"])
    client.patch(url, json={"queue": "technical"}, headers=admin["headers"])
    rows = [r for r in [fetch_one("select count(*) as c from staff_audit_log where action = 'support.ticket.update' "
                                  "and target = %s", (t["ref"],))]]
    assert rows[0]["c"] == 2
    bell = client.get(f"{API}/notifications", headers=user["headers"]).json()["payload"]["items"]
    assert [n["title"] for n in bell] == [f"{t['ref']} moved to Account and website"]  # assignment stays internal
    _cleanup_audit(admin["id"])


def test_saved_replies_fill_in_the_ticket(client, make_user):
    admin, user = make_user("admin"), make_user()
    ah = admin["headers"]
    base = f"{API}/admin/support/replies"
    assert client.get(base, headers=user["headers"]).status_code == 403
    bad = client.post(base, json={"title": "[test] Refund", "body": "Hi {{nam}}"}, headers=ah)
    assert bad.status_code == 400 and "{{name}}" in bad.json()["detail"]
    r = client.post(base, json={"title": "[test] Refund", "body": "Hi {{name}}, about {{ref}}: {{agent}} here.",
                                "queue": "marketplace"}, headers=ah)
    assert r.status_code == 201, r.text
    reply = r.json()["payload"]
    try:
        assert client.post(base, json={"title": "[TEST] refund", "body": "x"}, headers=ah).status_code == 409
        t = _ticket(client)  # anonymous, contact name "Test Person"
        listed = client.get(base, params={"ticket_id": t["id"], "q": "[test]"}, headers=ah).json()["payload"]
        mine = next(i for i in listed["items"] if i["id"] == reply["id"])
        assert mine["rendered"].startswith(f"Hi Test, about {t['ref']}: ") and "{{" not in mine["rendered"]
        client.post(f"{API}/admin/support/tickets/{t['id']}/messages",
                    json={"body": mine["rendered"], "canned_reply_id": reply["id"]}, headers=ah)
        assert fetch_one("select use_count from support_canned_replies where id = %s", (reply["id"],))["use_count"] == 1
        # A reply for one team is not offered on another team's ticket
        other = _ticket(client, queue="technical")
        listed = client.get(base, params={"ticket_id": other["id"]}, headers=ah).json()["payload"]
        assert all(i["id"] != reply["id"] for i in listed["items"])
        r = client.put(f"{base}/{reply['id']}", json={"title": "[test] Refund sent", "body": "Done, {{name}}."},
                       headers=ah)
        assert r.status_code == 200 and r.json()["payload"]["queue"] is None
        assert client.delete(f"{base}/{reply['id']}", headers=ah).status_code == 200
        assert client.delete(f"{base}/{reply['id']}", headers=ah).status_code == 404
    finally:
        execute("delete from support_canned_replies where id = %s", (reply["id"],))
        _cleanup_audit(admin["id"])


def test_customer_context_shows_what_staff_need(client, make_user):
    admin, user = make_user("admin"), make_user()
    first = _ticket(client, user["headers"])
    second = _ticket(client, user["headers"], subject="[test] Another question")
    ctx = client.get(f"{API}/admin/support/tickets/{second['id']}/customer", headers=admin["headers"]).json()["payload"]
    assert ctx["account"]["id"] == user["id"] and ctx["account"]["email"] == user["email"]
    assert [i["id"] for i in ctx["tickets"]["items"]] == [first["id"]] and ctx["tickets"]["total"] == 1
    assert ctx["hires"]["total"] == 0 and ctx["payments"]["total"] == 0
    assert "password_hash" not in ctx["account"] and "national_id" not in str(ctx)
    # Without an account, other requests with the same phone are shown
    a1, a2 = _ticket(client, phone="0911000888"), _ticket(client, phone="0911000888")
    ctx = client.get(f"{API}/admin/support/tickets/{a2['id']}/customer", headers=admin["headers"]).json()["payload"]
    assert ctx["account"] is None and a1["id"] in [i["id"] for i in ctx["tickets"]["items"]]
    assert client.get(f"{API}/admin/support/tickets/not-an-id/customer", headers=admin["headers"]).status_code == 404
    assert client.get(f"{API}/admin/support/tickets/{a2['id']}/customer", headers=user["headers"]).status_code == 403


def test_search_filters_and_paging(client, make_user):
    admin = make_user("admin")
    ah = admin["headers"]
    t = _ticket(client, body="The zebra-striped receipt from Chapa is blank")
    found = client.get(f"{API}/admin/support/tickets", params={"q": "zebra-striped"}, headers=ah).json()["payload"]
    assert [i["id"] for i in found["items"]] == [t["id"]] and found["total"] == 1  # message text is searched
    assert client.get(f"{API}/admin/support/tickets", params={"q": "zebra%"}, headers=ah).json()["payload"]["total"] == 0
    waiting = client.get(f"{API}/admin/support/tickets", params={"q": "zebra-striped", "waiting": "customer"},
                         headers=ah).json()["payload"]
    assert waiting["total"] == 0
    assert client.get(f"{API}/admin/support/tickets", params={"limit": 1000}, headers=ah).status_code == 422
    assert client.get(f"{API}/admin/support/tickets", params={"status": "bogus"}, headers=ah).status_code == 422
    page = client.get(f"{API}/admin/support/tickets", params={"status": "all", "sort": "newest", "limit": 1},
                      headers=ah).json()["payload"]
    assert len(page["items"]) == 1 and page["total"] >= 1


def test_csv_export_is_filtered_and_safe_in_spreadsheets(client, make_user):
    admin = make_user("admin")
    t = _ticket(client, subject='=HYPERLINK("http://x","click")', name="@evil", phone="+251911000777")
    r = client.get(f"{API}/admin/support/tickets.csv", params={"q": t["ref"]}, headers=admin["headers"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("Ref,Subject") and len(lines) == 2
    assert "'=HYPERLINK" in lines[1] and ",'@evil," in lines[1] and ",'+251911000777," in lines[1]
    assert fetch_one("select count(*) as c from staff_audit_log where action = 'support.export' and actor_id::text = %s",
                     (admin["id"],))["c"] == 1
    assert client.get(f"{API}/admin/support/tickets.csv", headers={}).status_code == 401
    _cleanup_audit(admin["id"])
