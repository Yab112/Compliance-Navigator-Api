"""Clients pay the platform after delivery; providers see earnings and withdraw through approved payouts."""

import hashlib
import hmac

from conftest import API
from test_providers import _approved, _deliver, _hire, _job, _pay


def _payout_account(client, agent, bank="sim-cbe"):
    return client.put(f"{API}/providers/me/payout", json={"bank_code": bank, "account_number": "1000 2345 6789",
                                                          "account_name": "Test Agent"}, headers=agent["headers"])


def _earnings(client, agent):
    return client.get(f"{API}/providers/me/earnings", headers=agent["headers"]).json()["payload"]


def test_pay_after_delivery_credits_earnings_once(client, make_user):
    admin, agent, customer, stranger = make_user("admin"), make_user(), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    pay = lambda who: client.post(f"{API}/hires/{hire['id']}/pay", headers=who["headers"])  # noqa: E731
    _job(client, agent, hire["id"], "accept", price=1200)
    assert pay(customer).status_code == 409  # not delivered yet

    _deliver(client, agent, hire["id"])  # no payout account needed for the client to pay
    assert pay(stranger).status_code == 404
    started = pay(customer).json()["payload"]
    assert started["checkout_url"].endswith(f"/pay/test/{started['tx_ref']}")
    assert pay(customer).json()["payload"]["tx_ref"] == started["tx_ref"]  # no second checkout for the same job
    tx = started["tx_ref"]
    assert client.post(f"{API}/payments/{tx}/simulate", json={"outcome": "success"},
                       headers=stranger["headers"]).status_code == 404
    r = client.post(f"{API}/payments/{tx}/simulate", json={"outcome": "success"}, headers=customer["headers"])
    payment = r.json()["payload"]["payment"]
    # 10% commission (120) plus 15% VAT on it (18) come out of the provider's share
    assert payment["status"] == "success" and payment["commission_amount"] == 120.0 and payment["provider_amount"] == 1062.0
    client.get(f"{API}/payments/{tx}", headers=customer["headers"])  # confirming again must not pay twice

    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert mine["payment_status"] == "paid" and mine["client_confirmed_at"]
    assert pay(customer).status_code == 409
    e = _earnings(client, agent)
    assert e["balance"] == 1062.0 and e["available"] == 1062.0 and e["earned_total"] == 1062.0
    assert [(x["kind"], x["amount"], x["job_title"]) for x in e["ledger"]] == [("earning", 1062.0, "Renew my passport")]
    bell = client.get(f"{API}/notifications", headers=agent["headers"]).json()["payload"]["items"]
    assert any("Add your bank account" in n["title"] for n in bell)  # earned money, no account yet

    client.post(f"{API}/hires/{hire['id']}/review", json={"rating": 5}, headers=customer["headers"])
    reviews = client.get(f"{API}/providers/{provider['slug']}").json()["payload"]["provider"]["reviews"]["items"]
    assert reviews[0]["paid_through_platform"] is True
    totals = client.get(f"{API}/admin/marketplace/payments", headers=admin["headers"]).json()["payload"]["totals"]
    assert totals["paid_count"] >= 1 and totals["commission"] >= 120


def test_failed_payment_can_be_retried(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=500)
    _deliver(client, agent, hire["id"])
    tx = client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"]).json()["payload"]["tx_ref"]
    r = client.post(f"{API}/payments/{tx}/simulate", json={"outcome": "failed"}, headers=customer["headers"])
    assert r.json()["payload"]["payment"]["status"] == "failed"
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert mine["payment_status"] == "unpaid" and not mine["client_confirmed_at"]
    assert _earnings(client, agent)["balance"] == 0
    retry = client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"]).json()["payload"]
    assert retry["tx_ref"] != tx


def test_payouts_need_an_account_a_balance_and_staff_approval(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=1000)
    _deliver(client, agent, hire["id"])
    _pay(client, customer, hire["id"])  # 1000 - 100 commission - 15 VAT on it = 885 ETB earned
    ask = lambda amount: client.post(f"{API}/providers/me/payouts", json={"amount": amount},  # noqa: E731
                                     headers=agent["headers"])

    assert ask(500).status_code == 409  # no bank account yet
    assert _payout_account(client, agent, bank="nope").status_code == 400
    r = _payout_account(client, agent)
    assert r.status_code == 200 and r.json()["payload"]["payout"]["account_last4"] == "6789"
    me = client.get(f"{API}/providers/me", headers=agent["headers"]).json()["payload"]["provider"]
    assert "1000 2345 6789" not in str(me) and "100023456789" not in str(me)  # never sent back in full

    assert ask(50).status_code == 400  # below the minimum
    assert ask(886).status_code == 409  # more than earned
    first = ask(600)
    assert first.status_code == 201 and first.json()["payload"]["payout"]["status"] == "requested"
    assert _earnings(client, agent)["available"] == 285.0  # held while waiting
    assert ask(286).status_code == 409

    assert client.get(f"{API}/admin/marketplace/payouts", headers=agent["headers"]).status_code == 403
    queue = client.get(f"{API}/admin/marketplace/payouts", headers=admin["headers"]).json()["payload"]
    item = next(i for i in queue["items"] if i["id"] == first.json()["payload"]["payout"]["id"])
    decide = lambda pid, body: client.post(f"{API}/admin/marketplace/payouts/{pid}", json=body,  # noqa: E731
                                           headers=admin["headers"])
    assert decide(item["id"], {"decision": "reject"}).status_code == 400  # a reason is required
    r = decide(item["id"], {"decision": "approve"})
    assert r.status_code == 200 and r.json()["payload"]["payout"]["status"] == "paid"  # simulated transfer
    assert decide(item["id"], {"decision": "approve"}).status_code == 409

    e = _earnings(client, agent)
    assert e["balance"] == 285.0 and e["available"] == 285.0 and e["paid_out"] == 600.0
    assert e["ledger"][0]["kind"] == "payout" and e["ledger"][0]["amount"] == -600.0
    assert e["payouts"][0]["status"] == "paid" and e["payouts"][0]["account_last4"] == "6789"

    second = ask(200).json()["payload"]["payout"]
    decide(second["id"], {"decision": "reject", "note": "Account name doesn't match"})
    e = _earnings(client, agent)
    assert e["available"] == 285.0 and e["payouts"][0]["status"] == "rejected"  # money released back
    bell = client.get(f"{API}/notifications", headers=agent["headers"]).json()["payload"]["items"]
    assert bell[0]["title"].startswith("Payout of 200.00 ETB was not approved")

    # A paid withdrawal has a receipt for its provider only
    paid_id = item["id"]
    r = client.get(f"{API}/payouts/{paid_id}/receipt", headers=agent["headers"])
    assert r.status_code == 200 and r.json()["payload"]["receipt"]["amount"] == 600.0
    assert client.get(f"{API}/payouts/{paid_id}/receipt", headers=customer["headers"]).status_code == 404
    assert client.get(f"{API}/payouts/{second['id']}/receipt", headers=agent["headers"]).status_code == 404  # rejected


def test_vat_registered_provider_and_receipts(client, make_user):
    admin, agent, customer, stranger = make_user("admin"), make_user(), make_user(), make_user()
    provider = _approved(client, admin, agent)
    vat = lambda body: client.patch(f"{API}/providers/me", json=body, headers=agent["headers"])  # noqa: E731
    assert vat({"vat_registered": True}).status_code == 400  # needs the VAT number
    assert vat({"vat_registered": True, "vat_number": "0012345678"}).status_code == 200
    # An approved provider's VAT change waits for staff to check the certificate
    detail = client.get(f"{API}/admin/marketplace/providers/{provider['id']}", headers=admin["headers"]).json()["payload"]["provider"]
    assert detail["vat_registered"] is False
    assert client.post(f"{API}/admin/marketplace/providers/{provider['id']}/changes/{detail['pending_change']['id']}",
                       json={"decision": "approve", "note": "VAT certificate matches the number"},
                       headers=admin["headers"]).status_code == 200
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=1000)
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert mine["amount_due"] == 1150.0 and mine["vat_due"] == 150.0  # the client sees the total before paying
    _deliver(client, agent, hire["id"])
    tx = client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"]).json()["payload"]["tx_ref"]
    assert client.get(f"{API}/payments/{tx}/receipt", headers=customer["headers"]).status_code == 404  # not paid yet
    client.post(f"{API}/payments/{tx}/simulate", json={"outcome": "success"}, headers=customer["headers"])

    receipt = client.get(f"{API}/payments/{tx}/receipt", headers=customer["headers"]).json()["payload"]["receipt"]
    assert receipt["total"] == 1150.0 and [line["amount"] for line in receipt["lines"]] == [1000.0, 150.0]
    assert receipt["provider"]["vat_number"] == "0012345678" and "statement" not in receipt
    statement = client.get(f"{API}/payments/{tx}/receipt", headers=agent["headers"]).json()["payload"]["receipt"]["statement"]
    # provider gets price - commission - VAT on commission + the VAT they collected (and must file)
    assert statement == {**statement, "price": 1000.0, "provider_vat": 150.0, "commission": 100.0,
                         "commission_vat": 15.0, "provider_amount": 1035.0}
    assert client.get(f"{API}/payments/{tx}/receipt", headers=stranger["headers"]).status_code == 404
    assert _earnings(client, agent)["balance"] == 1035.0


def test_telegram_shared_only_after_accept(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    assert client.patch(f"{API}/providers/me", json={"telegram_username": "bad name!"},
                        headers=agent["headers"]).status_code == 422
    client.patch(f"{API}/providers/me", json={"telegram_username": "https://t.me/test_agent_1"}, headers=agent["headers"])
    r = client.post(f"{API}/hires", json={"provider_id": provider["slug"], "title": "Renew my passport",
                                          "client_name": "Test Client", "client_phone": "0922000000",
                                          "client_telegram": "@test_client_1"}, headers=customer["headers"])
    hire = r.json()["payload"]["hire"]
    assert hire["provider_telegram"] is None  # hidden until accepted
    job = client.get(f"{API}/providers/me/jobs", headers=agent["headers"]).json()["payload"]["items"][0]
    assert job["client_telegram"] is None
    _job(client, agent, hire["id"], "accept")
    job = client.get(f"{API}/providers/me/jobs", headers=agent["headers"]).json()["payload"]["items"][0]
    mine = client.get(f"{API}/hires", headers=customer["headers"]).json()["payload"]["items"][0]
    assert job["client_telegram"] == "test_client_1" and mine["provider_telegram"] == "test_agent_1"
    me = client.get(f"{API}/auth/me", headers=customer["headers"]).json()["payload"]
    assert (me.get("user") or me)["telegramUsername"] == "test_client_1"  # remembered for next time


def test_webhook_needs_a_valid_signature(client, monkeypatch):
    from config.config import settings

    monkeypatch.setattr(settings, "chapa_webhook_secret", "whsec-test")
    body = b'{"event":"charge.success","tx_ref":"cn-nothing"}'
    assert client.post(f"{API}/payments/chapa/webhook", content=body,
                       headers={"x-chapa-signature": "bad"}).status_code == 401
    good = hmac.new(b"whsec-test", body, hashlib.sha256).hexdigest()
    assert client.post(f"{API}/payments/chapa/webhook", content=body,
                       headers={"x-chapa-signature": good}).status_code == 200
    # The webhook remembers each delivery for a week (replay protection); forget this test one
    from services.db import execute

    execute("delete from once_keys where bucket = 'chapa_webhook' and key = %s", (hashlib.sha256(body).hexdigest(),))


def test_payout_review_shows_what_it_pays_for_and_blocks_someone_elses_account(client, make_user):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider, title="Passport renewal for review")
    _job(client, agent, hire["id"], "accept", price=1000)
    _deliver(client, agent, hire["id"])
    _pay(client, customer, hire["id"])
    client.put(f"{API}/providers/me/payout", json={"bank_code": "sim-cbe", "account_number": "1000 2345 6789",
                                                   "account_name": "Someone Else"}, headers=agent["headers"])
    payout = client.post(f"{API}/providers/me/payouts", json={"amount": 500},
                         headers=agent["headers"]).json()["payload"]["payout"]

    assert client.get(f"{API}/admin/marketplace/payouts/{payout['id']}", headers=agent["headers"]).status_code == 403
    review = client.get(f"{API}/admin/marketplace/payouts/{payout['id']}", headers=admin["headers"]).json()["payload"]
    assert review["earnings"][0]["job_title"] == "Passport renewal for review" and review["earnings"][0]["client_paid"] == 1000
    codes = {c["code"]: c["level"] for c in review["checks"]}
    assert codes["name_mismatch"] == "block" and codes["first_payout"] == "info" and codes["new_account"] == "warn"
    assert review["balances"]["in_payout"] == 500

    decide = lambda body: client.post(f"{API}/admin/marketplace/payouts/{payout['id']}", json=body,  # noqa: E731
                                      headers=admin["headers"])
    blocked = decide({"decision": "approve"})
    assert blocked.status_code == 409 and "Someone Else" in blocked.json()["detail"]
    assert decide({"decision": "approve", "note": "too short"}).status_code == 409
    ok = decide({"decision": "approve", "note": "Called the provider; account is her sister's, signed letter on file"})
    assert ok.status_code == 200 and ok.json()["payload"]["payout"]["status"] == "paid"


def test_names_match_allows_middle_names_and_company_accounts():
    from services.payment_service import names_match
    assert names_match("Meron Tadesse Alemu", "Meron Tadesse")
    assert names_match("MERON TADESSE", None, "Meron Tadesse")
    assert names_match("Abay Clearing and Forwarding PLC", "Abebe Kebede", "Abay Clearing & Forwarding PLC")
    assert not names_match("Nardos Teshome", "Meron Tadesse")
    assert not names_match("Meron Bekele", "Meron Tadesse")
