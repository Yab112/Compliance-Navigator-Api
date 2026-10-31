"""Provider earnings: balances, the ledger, payout requests and the staff payout queue."""

from __future__ import annotations

import secrets
from datetime import timedelta
from decimal import Decimal

from config.config import settings
from services import platform_settings
from services.db import connection, fetch_all, fetch_one

from .gateways import PaymentError, _money, mode
from .payout_account import payout_view

# ---------------------------------------------------------------- earnings and payouts


def _min_payout() -> Decimal:
    return Decimal(str(platform_settings.get("min_payout_etb")))


def _hold_days() -> int:
    return platform_settings.get_int("payout_hold_days")


PAYOUT_COLUMNS = """
  po.id::text, po.provider_id::text, po.amount::float, po.status, po.bank_code, po.bank_name, po.account_name,
  po.account_last4, po.reference, po.gateway, po.gateway_reference, po.note, po.decided_by, po.decided_at, po.paid_at,
  po.created_at, po.is_test, po.needs_check, po.check_note, po.returned_at, po.returned_by, po.return_note
"""


def _test_money() -> bool:
    return mode() == "simulated" or (mode() == "chapa" and (settings.chapa_secret_key or "").startswith("CHASECK_TEST"))


def _balances(provider_id: str) -> dict:
    """
    In live mode only real money counts: earnings from test checkouts (and payouts of them) are shown apart
    as test_balance and can never be withdrawn. In test mode everything counts, so the flow can be tried.
    A refund can make the balance negative; it is recovered from the next earnings before any payout.
    paid_out counts a transfer that came back (a 'payout_return' line) as not paid out.
    """
    live = not _test_money()
    only = "and not is_test" if live else ""
    row = fetch_one(
        f"""
        select coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s {only}), 0)::float as balance,
               coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s and kind = 'earning' {only}), 0)::float
                 as earned_total,
               coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s and kind = 'earning' {only}
                         and created_at >= date_trunc('month', now())), 0)::float as earned_this_month,
               coalesce((select sum(amount) from payouts where provider_id = %(p)s and status in ('requested', 'approved')
                         {only}), 0)::float as in_payout,
               coalesce((select -sum(amount) from provider_ledger where provider_id = %(p)s
                         and kind in ('payout', 'payout_return') {only}), 0)::float as paid_out,
               coalesce((select -sum(amount) from provider_ledger where provider_id = %(p)s and kind in ('refund', 'adjustment')
                         and refund_id is not null {only}), 0)::float as refunded,
               coalesce((select sum(amount) from provider_ledger where provider_id = %(p)s and is_test), 0)::float
                 as test_balance
        """,
        {"p": provider_id},
    )
    if not live:
        row["test_balance"] = 0.0
    # Dispute window: an earning can be withdrawn only some days after it was credited. Refunds already taken
    # from that payment count against its hold, so the same money is never subtracted twice.
    days = _hold_days()
    recent = fetch_all(
        f"""
        select l.created_at,
               greatest(l.amount + coalesce((select sum(r.amount) from provider_ledger r
                                             where r.payment_id = l.payment_id and r.provider_id = l.provider_id
                                               and r.kind in ('refund', 'adjustment')), 0), 0)::float as net
        from provider_ledger l
        where l.provider_id = %(p)s and l.kind = 'earning' and l.created_at > now() - make_interval(days => %(d)s)
              {only.replace("is_test", "l.is_test")}
        order by l.created_at desc
        """,
        {"p": provider_id, "d": days},
    ) if days > 0 else []
    # Payouts use the oldest money first, so the held earnings are the newest ones and can never add up to more
    # than what is still in the balance (money already withdrawn is not held again).
    unpaid = max(row["balance"] - row["in_payout"], 0.0)
    held, held_until = 0.0, None
    for e in recent:
        if held >= unpaid:
            break
        held += min(e["net"], unpaid - held)
        if e["net"] > 0:
            held_until = e["created_at"] + timedelta(days=days)
    row["held"] = round(held, 2)
    row["held_until"] = held_until if row["held"] > 0 else None
    row["hold_days"] = days
    # Money already asked for is held until the payout is paid or refused, and new earnings until the window
    # ends. A negative balance (a refund took more than was left) still blocks payouts.
    row["available"] = round(row["balance"] - row["in_payout"] - row["held"], 2)
    row["live"] = live
    return row


LEDGER_SELECT = """
  select l.id, l.kind, l.amount::float, l.note, l.created_at, l.is_test, e.title as job_title, e.client_name,
         p.amount::float as gross, p.commission_amount::float as commission, p.commission_vat::float,
         p.provider_vat::float, p.tx_ref, po.reference as payout_reference, po.id::text as payout_id,
         l.refund_id::text, rf.reference as refund_reference
  from provider_ledger l
  left join engagements e on e.id = l.engagement_id
  left join payments p on p.id = l.payment_id
  left join payouts po on po.id = l.payout_id
  left join refunds rf on rf.id = l.refund_id
"""


def earnings(user_id: str) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    ledger = fetch_all(f"{LEDGER_SELECT} where l.provider_id = %s order by l.created_at desc, l.id desc limit 100",
                       (provider["id"],))
    payouts = fetch_all(f"select {PAYOUT_COLUMNS} from payouts po where po.provider_id = %s order by po.created_at desc limit 50",
                        (provider["id"],))
    return {**_balances(provider["id"]), "ledger": ledger, "payouts": [_public_payout(p) for p in payouts],
            "min_payout": float(_min_payout()), "payout_account": payout_view(provider),
            "commission_percent": platform_settings.get("commission_percent")}


def _public_payout(payout: dict) -> dict:
    """What the provider sees of their payout: not the staff-only checking note."""
    return {k: v for k, v in payout.items()
            if k not in ("check_note", "needs_check", "bank_code", "returned_by", "return_note")}


def ledger_page(user_id: str, limit: int = 20, offset: int = 0) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    items = fetch_all(f"{LEDGER_SELECT} where l.provider_id = %s order by l.created_at desc, l.id desc limit %s offset %s",
                      (provider["id"], limit, offset))
    total = fetch_one("select count(*) as c from provider_ledger where provider_id = %s", (provider["id"],))["c"]
    return {"total": total, "items": items}


def payouts_page(user_id: str, limit: int = 20, offset: int = 0) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    items = fetch_all(f"select {PAYOUT_COLUMNS} from payouts po where po.provider_id = %s "
                      "order by po.created_at desc limit %s offset %s", (provider["id"], limit, offset))
    total = fetch_one("select count(*) as c from payouts where provider_id = %s", (provider["id"],))["c"]
    return {"total": total, "items": [_public_payout(p) for p in items]}


def request_payout(user_id: str, amount: float) -> dict:
    from services import provider_service

    provider = provider_service.get_for_user(user_id)
    if not provider:
        raise PaymentError("Join as a provider first", 404)
    if not provider.get("payout_ready"):
        raise PaymentError("Add the bank account to send your money to first", 409)
    amount = _money(amount)
    if amount < _min_payout():
        raise PaymentError(f"The smallest payout is {_min_payout():,.0f} ETB")
    with connection() as conn, conn.transaction():
        # Lock the provider row so two requests at once can't both pass the balance check, and read the
        # account inside the lock so the payout keeps exactly the account it was asked for
        acct = conn.execute(
            "select payout_account_enc, payout_bank_code, payout_bank_name, payout_account_name, payout_account_last4 "
            "from providers where id = %s for update", (provider["id"],),
        ).fetchone()
        if not acct or not acct["payout_account_enc"]:
            raise PaymentError("Add the bank account to send your money to first", 409)
        bal = _balances(provider["id"])
        available = Decimal(str(bal["available"]))
        if amount > available:
            held = (f". {bal['held']:,.2f} ETB of new earnings is on hold until {bal['held_until']:%d %b %Y} "
                    "(dispute window)") if bal["held"] > 0 and bal["held_until"] else ""
            raise PaymentError(f"You can withdraw up to {max(available, Decimal(0)):,.2f} ETB{held}", 409)
        row = conn.execute(
            """
            insert into payouts (provider_id, amount, bank_code, bank_name, account_name, account_last4, reference,
                                 account_enc, is_test)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id::text
            """,
            (provider["id"], amount, acct["payout_bank_code"], acct["payout_bank_name"], acct["payout_account_name"],
             acct["payout_account_last4"], f"po-{secrets.token_hex(8)}", acct["payout_account_enc"], _test_money()),
        ).fetchone()
    # Staff see it in the Payouts queue (and its count); they have no notification bell
    return _public_payout(fetch_one(f"select {PAYOUT_COLUMNS} from payouts po where po.id = %s", (row["id"],)))


def admin_payouts(status: str | None = "requested", limit: int = 25, offset: int = 0) -> dict:
    where, params = ("po.status = %s", [status]) if status else ("true", [])
    # Requests waiting for approval are a queue (oldest first); everything else is history (newest first)
    # Paid transfers flagged as maybe returned come first, so they are not lost among the paid ones
    order = "po.created_at" if status == "requested" else \
        "po.needs_check desc, coalesce(po.returned_at, po.paid_at, po.decided_at, po.created_at) desc"
    items = fetch_all(
        f"""
        select {PAYOUT_COLUMNS}, pr.display_name as provider_name, pr.slug as provider_slug
        from payouts po join providers pr on pr.id = po.provider_id
        where {where} order by {order} limit %s offset %s
        """,
        (*params, limit, offset),
    )
    total = fetch_one(f"select count(*) as c from payouts po where {where}", params)["c"]
    only = "and not is_test" if not _test_money() else ""
    totals = fetch_one(
        f"""
        select count(*) filter (where status = 'requested') as requested,
               coalesce(sum(amount) filter (where status = 'requested'), 0)::float as requested_amount,
               count(*) filter (where status = 'approved') as processing,
               count(*) filter (where status = 'approved' and needs_check) as needs_check,
               coalesce(sum(amount) filter (where status = 'paid'), 0)::float as paid_amount,
               count(*) filter (where status = 'paid' and needs_check) as paid_needs_check,
               count(*) filter (where status = 'returned') as returned,
               coalesce((select sum(amount) from provider_ledger where true {only}), 0)::float as owed_to_providers
        from payouts where true {only}
        """
    )
    return {"items": items, "total": total, "totals": totals, "mode": mode(), "test_mode": _test_money()}
