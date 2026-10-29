"""Lists page on the server: tab counts and header badges come from the database, not from a capped list."""

from conftest import API
from test_providers import _approved, _deliver, _deliver_and_close, _hire, _job


def test_hires_and_jobs_page_by_tab_with_real_counts(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hires = [_hire(client, customer, provider, title=f"Job {i}") for i in range(5)]
    for h in hires[:3]:
        _job(client, agent, h["id"], "accept")
    _deliver(client, agent, hires[0]["id"])                   # delivered, waiting for the client to pay
    _deliver_and_close(client, agent, customer, hires[1]["id"])  # paid and closed, not reviewed yet
    client.post(f"{API}/hires/{hires[4]['id']}/cancel", headers=customer["headers"])

    get = lambda url, who, **p: client.get(f"{API}{url}", params=p, headers=who["headers"]).json()["payload"]  # noqa: E731
    page = get("/hires", customer, scope="active", limit=2, offset=0)
    assert page["counts"] == {"active": 3, "history": 2} and page["total"] == 3 and len(page["items"]) == 2
    assert len(get("/hires", customer, scope="active", limit=2, offset=2)["items"]) == 1
    assert {h["title"] for h in get("/hires", customer, scope="history")["items"]} == {"Job 1", "Job 4"}

    jobs = get("/providers/me/jobs", agent, group="in_progress")
    # accepted (Job 2), plus the delivered-unpaid one is "completed" status-wise
    assert jobs["counts"] == {"new": 1, "in_progress": 1, "completed": 2, "declined": 1}
    assert [j["title"] for j in jobs["items"]] == ["Job 2"]

    # Header badges: the client must pay Job 0 and may review Job 1; the provider has Job 2 (start) and Job 3 (accept)
    assert get("/me/attention", customer) == {"hires": 2, "jobs": 0}
    assert get("/me/attention", agent) == {"hires": 0, "jobs": 2}


def test_earnings_history_and_admin_history_lists_page_newest_first(client, make_user):
    admin, agent = make_user("admin"), make_user()
    provider = _approved(client, admin, agent)
    for i in range(3):
        customer = make_user()
        h = _hire(client, customer, provider, title=f"Paid {i}")
        _job(client, agent, h["id"], "accept", price=500)
        _deliver_and_close(client, agent, customer, h["id"])
    ledger = client.get(f"{API}/providers/me/earnings/ledger", params={"limit": 2},
                        headers=agent["headers"]).json()["payload"]
    assert ledger["total"] == 3 and [r["job_title"] for r in ledger["items"]] == ["Paid 2", "Paid 1"]

    client.put(f"{API}/providers/me/payout", json={"bank_code": "sim-cbe", "account_number": "100023456789",
                                                   "account_name": "Test Agent"}, headers=agent["headers"])
    ids = []
    for amount in (100, 110):
        ids.append(client.post(f"{API}/providers/me/payouts", json={"amount": amount},
                               headers=agent["headers"]).json()["payload"]["payout"]["id"])
        client.post(f"{API}/admin/marketplace/payouts/{ids[-1]}", json={"decision": "approve"}, headers=admin["headers"])
    paid = client.get(f"{API}/admin/marketplace/payouts", params={"status": "paid", "limit": 100},
                      headers=admin["headers"]).json()["payload"]
    mine = [p["id"] for p in paid["items"] if p["id"] in ids]
    assert mine == [ids[1], ids[0]] and paid["total"] >= 2  # history: newest first
    mine_page = client.get(f"{API}/providers/me/payouts", params={"limit": 1}, headers=agent["headers"]).json()["payload"]
    assert mine_page["total"] == 2 and mine_page["items"][0]["id"] == ids[1]


def test_saved_flag_and_saved_paths_paging(client, make_user):
    me, other = make_user(), make_user()
    made = [client.post(f"{API}/roadmaps", json={"goal": "passport", "subCity": "bole", "documentsHeld": []},
                        headers=me["headers"]).json()["payload"]["roadmap"]["id"] for _ in range(3)]
    page = client.get(f"{API}/roadmaps", params={"limit": 2}, headers=me["headers"]).json()["payload"]
    assert page["total"] == 3 and len(page["items"]) == 2
    assert client.get(f"{API}/roadmaps/{made[0]}", headers=me["headers"]).json()["payload"]["saved"] is True
    anon = client.post(f"{API}/roadmaps", json={"goal": "passport", "subCity": "bole", "documentsHeld": []})
    rid = anon.json()["payload"]["roadmap"]["id"]
    assert client.get(f"{API}/roadmaps/{rid}", headers=other["headers"]).json()["payload"]["saved"] is False
