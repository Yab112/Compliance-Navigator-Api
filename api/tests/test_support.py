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
