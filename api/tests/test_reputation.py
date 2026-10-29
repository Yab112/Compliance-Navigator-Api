"""Both sides accountable: client records, providers rating clients, staff-approved review changes."""

from conftest import API
from test_providers import _approved, _deliver, _deliver_and_close, _hire, _job


def _closed_job(client, admin, agent, customer, provider=None, title="Renew my passport"):
    provider = provider or _approved(client, admin, agent)
    hire = _hire(client, customer, provider, title=title)
    _job(client, agent, hire["id"], "accept")
    _deliver_and_close(client, agent, customer, hire["id"])
    return provider, hire


def test_client_record_hire_rate_and_provider_rating(client, make_user):
    from services.db import execute

    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider, hire = _closed_job(client, admin, agent, customer)

    # Two more requests the provider accepted: one cancelled by the client, one delivered but never paid
    cancelled = _hire(client, customer, provider, title="Changed my mind")
    _job(client, agent, cancelled["id"], "accept")
    client.post(f"{API}/hires/{cancelled['id']}/cancel", headers=customer["headers"])
    ghosted = _hire(client, customer, provider, title="Never paid")
    _job(client, agent, ghosted["id"], "accept")
    _deliver(client, agent, ghosted["id"])
    execute("update engagements set completed_at = now() - interval '8 days' where id = %s", (ghosted["id"],))

    jobs = client.get(f"{API}/providers/me/jobs", headers=agent["headers"]).json()["payload"]["items"]
    record = jobs[0]["client_record"]
    assert record["paid_jobs"] == 1 and record["decided"] == 3 and record["hire_rate"] == 33
    assert record["cancelled_after_accept"] == 1 and record["left_unpaid"] == 1
    mine = client.get(f"{API}/hires/me/record", headers=customer["headers"]).json()["payload"]["record"]
    assert mine == {**record, "member_since": mine["member_since"]}  # the client sees what providers see

    rate = lambda hid, r: client.post(f"{API}/providers/me/jobs/{hid}/rate-client",  # noqa: E731
                                      json={"rating": r, "comment": "Clear and on time"}, headers=agent["headers"])
    assert rate(ghosted["id"], 5).status_code == 409  # only closed jobs
    assert rate(hire["id"], 4).status_code == 200 and rate(hire["id"], 5).status_code == 409  # once
    record = client.get(f"{API}/hires/me/record", headers=customer["headers"]).json()["payload"]["record"]
    assert record["rating_avg"] == 4.0 and record["rating_count"] == 1
    # A client's record is never part of a public profile
    public = client.get(f"{API}/providers/{provider['slug']}").json()["payload"]["provider"]
    assert "client_record" not in str(public)


def test_review_changes_need_staff_approval(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider, hire = _closed_job(client, admin, agent, customer)
    client.post(f"{API}/hires/{hire['id']}/review", json={"rating": 2, "comment": "Slow"}, headers=customer["headers"])
    ask = lambda body: client.post(f"{API}/hires/{hire['id']}/review/change", json=body,  # noqa: E731
                                   headers=customer["headers"])
    change = {"rating": 5, "comment": "Slow at first, but it all worked out", "reason": "The passport arrived after all"}
    assert ask({**change, "rating": 2, "comment": "Slow"}).status_code == 400  # nothing changes
    r = ask(change)
    assert r.status_code == 200 and r.json()["payload"]["change"]["status"] == "pending"
    assert ask(change).status_code == 409  # one open request at a time

    # Nothing changes until staff decide
    reviews = lambda: client.get(f"{API}/providers/{provider['slug']}").json()["payload"]["provider"]["reviews"]["items"]  # noqa: E731
    assert reviews()[0]["rating"] == 2
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert mine["review_change_status"] == "pending"

    assert client.get(f"{API}/admin/marketplace/review-changes", headers=customer["headers"]).status_code == 403
    pending = client.get(f"{API}/admin/marketplace/review-changes", headers=admin["headers"]).json()["payload"]["items"]
    item = next(i for i in pending if i["engagement_id"] == hire["id"])
    assert item["old_rating"] == 2 and item["new_rating"] == 5
    r = client.post(f"{API}/admin/marketplace/review-changes/{item['id']}", json={"decision": "approve"},
                    headers=admin["headers"])
    assert r.status_code == 200
    assert reviews()[0]["rating"] == 5 and reviews()[0]["comment"].startswith("Slow at first")
    assert client.post(f"{API}/admin/marketplace/review-changes/{item['id']}", json={"decision": "reject"},
                       headers=admin["headers"]).status_code == 409  # already decided

    # A rejected request leaves the review as it was
    ask({"rating": 1, "comment": "Changed my mind again", "reason": "Second thoughts"})
    item = next(i for i in client.get(f"{API}/admin/marketplace/review-changes", headers=admin["headers"])
                .json()["payload"]["items"] if i["engagement_id"] == hire["id"])
    client.post(f"{API}/admin/marketplace/review-changes/{item['id']}", json={"decision": "reject", "note": "No new facts"},
                headers=admin["headers"])
    assert reviews()[0]["rating"] == 5
