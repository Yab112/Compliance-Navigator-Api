"""The dispute-window hold on new earnings, and the 15-minute checks that settle refunds and checkouts
whose gateway answer or webhook was lost. Each check is narrowed to this test's own rows, since the dev
database is shared."""

import importlib
import threading

import pytest

from conftest import API
from services import payment_service, platform_settings
from services.db import execute, fetch_all, fetch_one
from services.payment_service import PaymentError
from test_money_safety import _paid_job
from test_payments import _earnings, _payout_account
from test_providers import _approved, _deliver, _hire, _job

# The package re-exports functions named like its submodules (earnings), so load the modules themselves
checkout = importlib.import_module("services.payment_service.checkout")
earnings = importlib.import_module("services.payment_service.earnings")
refunds = importlib.import_module("services.payment_service.refunds")


def _only(monkeypatch, module, key, value):
    """Let a reconciler see only the rows this test made."""
    real = module.fetch_all
    monkeypatch.setattr(module, "fetch_all", lambda sql, params=None: [r for r in real(sql, params) if r[key] == value])


# ---------------------------------------------------------------- dispute-window hold


def test_new_earnings_are_held_for_the_dispute_window_then_released(client, make_user, monkeypatch):
    assert platform_settings.BY_KEY["payout_hold_days"].default() == 7
    monkeypatch.setattr(earnings, "_hold_days", lambda: 7)
    job = _paid_job(client, make_user)  # 885 ETB earned
    _payout_account(client, job["agent"])
    e = _earnings(client, job["agent"])
    assert e["balance"] == 885.0 and e["held"] == 885.0 and e["available"] == 0.0 and e["hold_days"] == 7
    assert e["held_until"]
    r = client.post(f"{API}/providers/me/payouts", json={"amount": 500}, headers=job["agent"]["headers"])
    assert r.status_code == 409 and "on hold until" in r.json()["detail"]

    # The window has passed
    execute("update provider_ledger set created_at = now() - interval '8 days' where payment_id = "
            "(select id from payments where tx_ref = %s) and kind = 'earning'", (job["tx"],))
    e = _earnings(client, job["agent"])
    assert e["held"] == 0.0 and e["held_until"] is None and e["available"] == 885.0
    r = client.post(f"{API}/providers/me/payouts", json={"amount": 500}, headers=job["agent"]["headers"])
    assert r.status_code == 201, r.text
    assert _earnings(client, job["agent"])["available"] == 385.0


def test_a_refund_of_a_held_earning_is_not_subtracted_twice(client, make_user, monkeypatch):
    monkeypatch.setattr(earnings, "_hold_days", lambda: 7)
    job = _paid_job(client, make_user)
    plan = payment_service.refund_plan(job["tx"], amount=500, reason="Part of the work was not done")
    payment_service.execute_refund(plan["payload"], "staff-a@example.com (Staff A)")
    e = _earnings(client, job["agent"])
    share = round(885.0 - e["balance"], 2)
    assert share > 0 and e["held"] == e["balance"] and e["available"] == 0.0


# ---------------------------------------------------------------- refunds stuck in "sending"


class RefundGateway:
    name = "simulated"

    def __init__(self, verify):
        self.verify, self.refunds, self.verified = verify, [], []

    def refund(self, **kw):
        self.refunds.append(kw)
        raise RuntimeError("the process stopped before the answer was recorded")

    def verify_refund(self, ref_id):
        self.verified.append(ref_id)
        if isinstance(self.verify, Exception):
            raise self.verify
        return self.verify


def _stuck_refund(client, make_user, monkeypatch, verify):
    job = _paid_job(client, make_user)
    gw = RefundGateway(verify)
    monkeypatch.setattr(payment_service, "gateway_named", lambda name: gw)
    plan = payment_service.refund_plan(job["tx"], reason="Client complaint upheld")
    with pytest.raises(RuntimeError):
        payment_service.execute_refund(plan["payload"], "staff-a@example.com (Staff A)")
    refund = fetch_one("select r.id::text, r.reference, r.status from refunds r join payments p on p.id = r.payment_id "
                       "where p.tx_ref = %s", (job["tx"],))
    assert refund["status"] == "sending" and len(gw.refunds) == 1
    _only(monkeypatch, refunds, "id", refund["id"])
    assert payment_service.check_sending_refunds()["checked"] == 0  # too fresh: the request may still be running
    execute("update refunds set created_at = now() - interval '20 minutes' where id = %s", (refund["id"],))
    return job, gw, refund


def test_a_stuck_refund_the_gateway_made_is_counted_once_and_never_sent_again(client, make_user, monkeypatch):
    job, gw, refund = _stuck_refund(client, make_user, monkeypatch, "refunded")
    assert payment_service.check_sending_refunds() == {"checked": 1, "refunded": 1, "failed": 0, "needs_check": 0,
                                                       "errors": 0}
    assert gw.verified == [refund["reference"]] and len(gw.refunds) == 1  # asked about, never sent again
    row = fetch_one("select status, applied from refunds where id = %s", (refund["id"],))
    assert row == {"status": "refunded", "applied": True}
    assert _earnings(client, job["agent"])["balance"] == 0.0
    assert fetch_one("select payment_status from engagements where id = %s", (job["hire"]["id"],))["payment_status"] == "refunded"
    # A second run changes nothing
    assert payment_service.check_sending_refunds()["checked"] == 0
    assert len(fetch_all("select id from provider_ledger where refund_id = %s", (refund["id"],))) == 1
    assert len(gw.refunds) == 1


def test_a_stuck_refund_the_gateway_cant_confirm_is_left_for_staff(client, make_user, monkeypatch):
    job, gw, refund = _stuck_refund(client, make_user, monkeypatch, PaymentError("timed out", 502, uncertain=True))
    assert payment_service.check_sending_refunds()["needs_check"] == 1
    row = fetch_one("select status, applied, error from refunds where id = %s", (refund["id"],))
    assert row["status"] == "needs_check" and row["applied"] and "Chapa dashboard" in row["error"]
    assert _earnings(client, job["agent"])["balance"] == 0.0  # counted until someone checks, as for an unclear error
    assert len(gw.refunds) == 1


def test_a_stuck_refund_the_gateway_failed_is_marked_failed_without_counting(client, make_user, monkeypatch):
    job, gw, refund = _stuck_refund(client, make_user, monkeypatch, "failed")
    assert payment_service.check_sending_refunds()["failed"] == 1
    assert fetch_one("select status, applied from refunds where id = %s", (refund["id"],)) == {"status": "failed",
                                                                                              "applied": False}
    assert _earnings(client, job["agent"])["balance"] == 885.0
    assert fetch_one("select refunded_amount from payments where tx_ref = %s", (job["tx"],))["refunded_amount"] == 0


# ---------------------------------------------------------------- checkouts whose webhook was lost


def _pending_checkout(client, make_user, price=400):
    admin, agent, customer = make_user("admin"), make_user(), make_user()
    provider = _approved(client, admin, agent)
    hire = _hire(client, customer, provider)
    _job(client, agent, hire["id"], "accept", price=price)
    _deliver(client, agent, hire["id"])
    tx = client.post(f"{API}/hires/{hire['id']}/pay", headers=customer["headers"]).json()["payload"]["tx_ref"]
    return agent, hire, tx


def test_a_paid_checkout_without_a_webhook_is_confirmed_once(client, make_user, monkeypatch):
    agent, hire, tx = _pending_checkout(client, make_user)
    _only(monkeypatch, checkout, "tx_ref", tx)
    # The client paid on Chapa's page; the webhook never came
    execute("update payments set raw = coalesce(raw, '{}'::jsonb) || '{\"simulated_outcome\": \"success\"}' "
            "where tx_ref = %s", (tx,))
    assert payment_service.check_pending_payments()["checked"] == 0  # too fresh: the webhook may still come
    execute("update payments set created_at = now() - interval '20 minutes' where tx_ref = %s", (tx,))

    # The check and a late webhook at the same moment
    start, results = threading.Barrier(2), []
    run = [lambda: payment_service.check_pending_payments(), lambda: payment_service.confirm(tx)]

    def go(fn):
        start.wait()
        results.append(fn())

    threads = [threading.Thread(target=go, args=(fn,)) for fn in run]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 2
    assert fetch_one("select status from payments where tx_ref = %s", (tx,))["status"] == "success"
    assert fetch_one("select payment_status from engagements where id = %s", (hire["id"],))["payment_status"] == "paid"
    credits = fetch_all("select amount from provider_ledger where engagement_id = %s and kind = 'earning'", (hire["id"],))
    assert [float(c["amount"]) for c in credits] == [354.0]
    assert _earnings(client, agent)["balance"] == 354.0
    assert payment_service.check_pending_payments()["checked"] == 0  # nothing left to check


def test_an_abandoned_checkout_is_given_up_after_three_days(client, make_user, monkeypatch):
    agent, hire, tx = _pending_checkout(client, make_user)
    _only(monkeypatch, checkout, "tx_ref", tx)
    execute("update payments set created_at = now() - interval '1 hour' where tx_ref = %s", (tx,))
    assert payment_service.check_pending_payments()["abandoned"] == 0  # still pending, still open
    assert fetch_one("select status from payments where tx_ref = %s", (tx,))["status"] == "pending"
    execute("update payments set created_at = now() - interval '4 days' where tx_ref = %s", (tx,))
    assert payment_service.check_pending_payments()["abandoned"] == 1
    assert fetch_one("select status from payments where tx_ref = %s", (tx,))["status"] == "cancelled"
    assert fetch_one("select payment_status from engagements where id = %s", (hire["id"],))["payment_status"] == "unpaid"
    assert _earnings(client, agent)["balance"] == 0.0


def test_money_already_withdrawn_is_not_held_again(client, make_user, monkeypatch):
    """Earning, full withdrawal, new earning, all inside the window: only the new earning is held (bug seen live:
    the hold counted the withdrawn earnings too and showed a negative balance)."""
    monkeypatch.setattr(earnings, "_hold_days", lambda: 7)
    job = _paid_job(client, make_user)  # 885 ETB earned now
    pid = job["provider"]["id"]
    flag = fetch_one("select is_test from provider_ledger where provider_id = %s and kind = 'earning'", (pid,))["is_test"]
    # Paid out in full a moment later (earlier money was released by staff), then a new 500 ETB earning arrives
    execute("insert into provider_ledger (provider_id, kind, amount, note, is_test) values (%s, 'payout', -885, 'test', %s)",
            (pid, flag))
    execute("insert into provider_ledger (provider_id, kind, amount, note, is_test, created_at) "
            "values (%s, 'earning', 500, 'test', %s, now() + interval '1 second')", (pid, flag))
    e = _earnings(client, job["agent"])
    assert e["balance"] == 500.0
    assert e["held"] == 500.0 and e["available"] == 0.0  # never negative because of money already paid out
    assert e["held_until"]
    # The window has passed for everything: all of the remaining 500 can be withdrawn
    execute("update provider_ledger set created_at = created_at - interval '8 days' where provider_id = %s", (pid,))
    e = _earnings(client, job["agent"])
    assert e["held"] == 0.0 and e["available"] == 500.0
