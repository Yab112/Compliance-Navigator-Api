"""Refunds to clients: planning, sending, following up and the staff list."""

from __future__ import annotations

import logging
import re
import secrets
from decimal import Decimal

from services import payment_service
from services.db import connection, execute, fetch_all, fetch_one

from .earnings import _test_money
from .gateways import PaymentError, _money

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- refunds

REFUND_COLUMNS = """
  r.id::text, r.payment_id::text, r.engagement_id::text, r.reference, r.amount::float, r.price_part::float,
  r.provider_vat::float, r.commission::float, r.commission_vat::float, r.provider_amount::float, r.reason, r.method,
  r.status, r.applied, r.gateway, r.gateway_ref, r.is_test, r.client_bank_name, r.client_account_name,
  r.client_account_last4, r.transfer_reference, r.requested_by, r.approved_by, r.confirmed_by, r.error, r.note,
  r.created_at, r.updated_at, r.completed_at
"""


def _share(total, refunded_after: Decimal, refunded_before: Decimal, amount: Decimal) -> Decimal:
    """This refund's part of one figure, so all partial refunds together add up to the whole figure exactly."""
    total = Decimal(str(total or 0))
    return _money(total * refunded_after / amount) - _money(total * refunded_before / amount)


def refund_figures(payment: dict, amount) -> dict:
    """
    How a refund of `amount` (what the client gets back) splits, in proportion to the original payment:
      amount = price part + provider VAT = commission + VAT on commission + provider's share
    Money that was never credited (a duplicate payment) is returned entirely from our side.
    Chapa's own fee on the payment is not refunded by Chapa, so the platform carries it.
    """
    amount = _money(amount)
    total = _money(payment["amount"])
    before = _money(payment.get("refunded_amount") or 0)
    after = before + amount
    if payment.get("unapplied_reason"):
        return {"amount": amount, "price_part": amount, "provider_vat": Decimal("0.00"), "commission": Decimal("0.00"),
                "commission_vat": Decimal("0.00"), "provider_amount": Decimal("0.00")}
    pvat = _share(payment["provider_vat"], after, before, total)
    commission = _share(payment["commission_amount"], after, before, total)
    cvat = _share(payment["commission_vat"], after, before, total)
    return {"amount": amount, "price_part": amount - pvat, "provider_vat": pvat, "commission": commission,
            "commission_vat": cvat, "provider_amount": amount - commission - cvat}


def _payment_for_refund(tx_ref: str, conn=None) -> dict | None:
    sql = """
      select p.id::text, p.tx_ref, p.engagement_id::text, p.gateway, p.status, p.amount, p.price, p.provider_vat,
             p.commission_amount, p.commission_vat, p.provider_amount, p.refunded_amount, p.is_test, p.unapplied_reason,
             coalesce((select sum(r.amount) from refunds r where r.payment_id = p.id and r.status = 'sending'), 0)
               as sending,
             e.title, e.client_name, e.client_user_id::text, e.provider_id::text, pr.display_name as provider_name,
             pr.user_id::text as provider_user_id
      from payments p join engagements e on e.id = p.engagement_id left join providers pr on pr.id = e.provider_id
      where p.tx_ref = %s
    """
    if conn is None:
        return fetch_one(sql, (tx_ref,))
    return conn.execute(sql + " for update of p", (tx_ref,)).fetchone()


def refund_plan(tx_ref: str, *, amount=None, reason: str, method: str = "gateway",
                client_bank: dict | None = None) -> dict:
    """
    Check a refund request and turn it into the exact payload a second staff member approves.
    The client's account number (manual refunds) is encrypted before it is stored anywhere.
    """
    from core.crypto import encrypt

    payment = _payment_for_refund(tx_ref)
    if not payment:
        raise PaymentError("Payment not found", 404)
    if payment["status"] != "success":
        raise PaymentError("Only a payment that went through can be refunded", 409)
    refundable = _money(payment["amount"]) - _money(payment["refunded_amount"]) - _money(payment["sending"])
    if refundable <= 0:
        raise PaymentError("This payment has already been refunded in full", 409)
    amount = refundable if amount in (None, "") else _money(amount)
    if amount <= 0:
        raise PaymentError("Enter an amount above zero")
    if amount > refundable:
        raise PaymentError(f"You can refund up to {refundable:,.2f} ETB of this payment", 409)
    reason = re.sub(r"\s+", " ", reason or "").strip()
    if len(reason) < 5:
        raise PaymentError("Write the reason for the refund")
    if method not in ("gateway", "manual"):
        raise PaymentError("Choose how the money goes back")
    payload = {"tx_ref": tx_ref, "amount": str(amount), "reason": reason[:500], "method": method}
    if method == "manual":
        bank = client_bank or {}
        number = re.sub(r"\s", "", str(bank.get("account_number") or ""))
        name = re.sub(r"\s+", " ", str(bank.get("account_name") or "")).strip()
        bank_name = str(bank.get("bank_name") or "").strip()
        if not bank_name or len(name) < 2 or not re.fullmatch(r"\d{6,20}", number):
            raise PaymentError("For a manual refund, enter the client's bank, account holder name and account number")
        payload["client_bank"] = {"bank_name": bank_name[:80], "account_name": name[:120],
                                  "account_enc": encrypt(number), "last4": number[-4:]}
    elif payment["gateway"] == "chapa" and payment["is_test"] and not _test_money():
        raise PaymentError("This was a test payment and payments are live now, so Chapa can't refund it. "
                           "No real money was taken.", 409)
    full = amount == _money(payment["amount"]) - _money(payment["refunded_amount"])
    figures = refund_figures(payment, amount)
    summary = (f"Refund {amount:,.2f} ETB of {_money(payment['amount']):,.2f} ETB ({'in full' if full else 'part'}) to "
               f"{payment['client_name'] or 'the client'} for \"{payment['title']}\" (payment {tx_ref}), "
               f"{'through Chapa' if method == 'gateway' and payment['gateway'] == 'chapa' else 'by bank transfer from us' if method == 'manual' else 'test refund'}. "
               f"Taken back from {payment['provider_name'] or 'the provider'}: {figures['provider_amount']:,.2f} ETB. "
               f"Reason: {reason[:200]}")
    return {"payload": payload, "summary": summary, "figures": {k: float(v) for k, v in figures.items()},
            "refundable": float(refundable)}


def _apply_refund(conn, refund: dict, payment: dict, actor: str) -> None:
    """Count a refund: payment figures, a negative ledger line for the provider, the hire's status and history."""
    conn.execute(
        """
        update payments set refunded_amount = refunded_amount + %s, refunded_commission = refunded_commission + %s,
          refunded_commission_vat = refunded_commission_vat + %s, refunded_provider_amount = refunded_provider_amount + %s,
          refunded_provider_vat = refunded_provider_vat + %s, updated_at = now()
        where id = %s
        """,
        (_money(refund["amount"]), _money(refund["commission"]), _money(refund["commission_vat"]),
         _money(refund["provider_amount"]), _money(refund["provider_vat"]), payment["id"]),
    )
    credited = conn.execute("select provider_id::text from provider_ledger where payment_id = %s and kind = 'earning'",
                            (payment["id"],)).fetchone()
    if credited and Decimal(str(refund["provider_amount"])) > 0:
        # The provider's balance may go below zero; it is recovered from their next earnings before any payout
        conn.execute(
            "insert into provider_ledger (provider_id, kind, amount, engagement_id, payment_id, refund_id, note, is_test) "
            "values (%s, 'refund', %s, %s, %s, %s, %s, %s) on conflict do nothing",
            (credited["provider_id"], -_money(refund["provider_amount"]), payment["engagement_id"], payment["id"],
             refund["id"], f"Refund {refund['reference']} to the client: {refund['reason'][:120]}", payment["is_test"]),
        )
    left = conn.execute("select (amount - refunded_amount) as left from payments where id = %s", (payment["id"],)).fetchone()
    full = left["left"] <= 0
    # A full refund of the payment that paid for the job marks the job refunded; a duplicate's refund doesn't
    if full and not payment["unapplied_reason"]:
        conn.execute("update engagements set payment_status = 'refunded', updated_at = now() "
                     "where id = %s and payment_status = 'paid'", (payment["engagement_id"],))
    conn.execute("update engagements set refund_needed = false where id = %s", (payment["engagement_id"],))
    conn.execute("update refunds set applied = true, updated_at = now() where id = %s", (refund["id"],))
    from services import provider_service

    provider_service._event(
        conn, payment["engagement_id"], "refunded" if full else "partly_refunded", who="staff", actor=actor,
        note=f"{_money(refund['amount']):,.2f} ETB refund approved ({refund['reference']}, "
             f"{'bank transfer by staff' if refund['method'] == 'manual' else 'through the payment service'}). "
             f"{refund['reason']}")


def _unapply_refund(conn, refund: dict, actor: str, why: str) -> None:
    """A refund that was counted did not reach the client: undo the figures and give the provider their share back."""
    if not refund["applied"]:
        return
    payment = conn.execute("select id::text, engagement_id::text, is_test, unapplied_reason from payments where id = %s "
                           "for update", (refund["payment_id"],)).fetchone()
    conn.execute(
        """
        update payments set refunded_amount = refunded_amount - %s, refunded_commission = refunded_commission - %s,
          refunded_commission_vat = refunded_commission_vat - %s, refunded_provider_amount = refunded_provider_amount - %s,
          refunded_provider_vat = refunded_provider_vat - %s, updated_at = now()
        where id = %s
        """,
        (_money(refund["amount"]), _money(refund["commission"]), _money(refund["commission_vat"]),
         _money(refund["provider_amount"]), _money(refund["provider_vat"]), payment["id"]),
    )
    taken = conn.execute("select provider_id::text, amount from provider_ledger where refund_id = %s and kind = 'refund'",
                         (refund["id"],)).fetchone()
    if taken:
        conn.execute(
            "insert into provider_ledger (provider_id, kind, amount, engagement_id, payment_id, refund_id, note, is_test) "
            "values (%s, 'adjustment', %s, %s, %s, %s, %s, %s)",
            (taken["provider_id"], -taken["amount"], payment["engagement_id"], payment["id"], refund["id"],
             f"Refund {refund['reference']} did not go through; your share is back", payment["is_test"]),
        )
    if not payment["unapplied_reason"]:
        conn.execute("update engagements set payment_status = 'paid', updated_at = now() "
                     "where id = %s and payment_status = 'refunded'", (payment["engagement_id"],))
    conn.execute("update engagements set refund_needed = true, refund_flagged_at = now(), refund_flagged_by = %s "
                 "where id = %s", (actor, payment["engagement_id"]))
    conn.execute("update refunds set applied = false, updated_at = now() where id = %s", (refund["id"],))
    from services import provider_service

    provider_service._event(conn, payment["engagement_id"], "refund_failed", who="staff", actor=actor,
                            note=f"Refund {refund['reference']} did not go through: {why}")


def _refund_row(refund_id: str, conn=None) -> dict | None:
    sql = f"select {REFUND_COLUMNS} from refunds r where r.id = %s"
    if conn is None:
        return fetch_one(sql, (refund_id,))
    return conn.execute(sql + " for update", (refund_id,)).fetchone()


def _tell_refund(refund: dict, payment: dict) -> None:
    from services import provider_service

    eng = provider_service.get_engagement(payment["engagement_id"])
    if not eng:
        return
    amount = f"{Decimal(str(refund['amount'])):,.2f} ETB"
    done = refund["status"] == "refunded"
    if refund["method"] == "manual":
        client_body = f"We will send it to your {refund['client_bank_name']} account ending {refund['client_account_last4']}."
    else:
        client_body = "It goes back to how you paid. Banks can take a few days." if not done else "It is on its way back to how you paid."
    provider_service._tell(eng, "client", f"Refund of {amount} for {eng['title']}", f"Reference {refund['reference']}. {client_body}")
    if Decimal(str(refund["provider_amount"])) > 0:
        provider_service._tell(eng, "provider", f"{eng['client_name'] or 'A client'} was refunded {amount}",
                               f"{Decimal(str(refund['provider_amount'])):,.2f} ETB was taken back from your earnings. "
                               f"Reason: {refund['reason'][:200]}")


def _refund_done(refund: dict, actor: str) -> None:
    """The money reached the client: the hire's refund flag is cleared and its history says so."""
    from services import provider_service

    execute("update engagements set refund_needed = false where id = %s", (refund["engagement_id"],))
    how = f"bank transfer {refund['transfer_reference']}" if refund.get("transfer_reference") else \
        f"payment service reference {refund.get('gateway_ref') or refund['reference']}"
    provider_service._event(None, refund["engagement_id"], "refund_done", who="staff", actor=actor,
                            note=f"{_money(refund['amount']):,.2f} ETB returned to the client ({refund['reference']}, {how}).")


def execute_refund(payload: dict, actor: str) -> dict:
    """
    Carry out an approved refund (called by the approval workflow, or by the route when no second person
    exists). Gateway refunds go through Chapa's refund API; manual ones wait for staff to send the money
    and confirm. A gateway error that does not prove the refund failed leaves it "needs checking".
    """
    tx_ref = payload["tx_ref"]
    amount = _money(payload["amount"])
    method = payload.get("method", "gateway")
    bank = payload.get("client_bank") or {}
    reference = f"rf-{secrets.token_hex(8)}"
    with connection() as conn, conn.transaction():
        # Lock the payment so two refunds at once can't add up to more than was paid
        payment = _payment_for_refund(tx_ref, conn)
        if not payment or payment["status"] != "success":
            raise PaymentError("Payment not found", 404)
        refundable = _money(payment["amount"]) - _money(payment["refunded_amount"]) - _money(payment["sending"])
        if amount > refundable:
            raise PaymentError(f"Only {max(refundable, Decimal(0)):,.2f} ETB of this payment is left to refund", 409)
        figures = refund_figures(payment, amount)
        refund = conn.execute(
            f"""
            insert into refunds (payment_id, engagement_id, reference, amount, price_part, provider_vat, commission,
              commission_vat, provider_amount, reason, method, status, gateway, is_test, client_bank_name,
              client_account_name, client_account_enc, client_account_last4, requested_by, approved_by)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning {REFUND_COLUMNS.replace('r.', '')}
            """,
            (payment["id"], payment["engagement_id"], reference, amount, figures["price_part"], figures["provider_vat"],
             figures["commission"], figures["commission_vat"], figures["provider_amount"], payload["reason"], method,
             "manual_pending" if method == "manual" else "sending", payment["gateway"], payment["is_test"],
             bank.get("bank_name"), bank.get("account_name"), bank.get("account_enc"), bank.get("last4"),
             actor.split(" (")[0], actor),
        ).fetchone()
        if method == "manual":
            # We owe the client this money from now on, so it is counted at once
            _apply_refund(conn, refund, payment, actor)
    if method == "gateway":
        try:
            result = payment_service.gateway_named(payment["gateway"]).refund(tx_ref=tx_ref, amount=amount, reason=payload["reason"],
                                                              reference=reference)
        except PaymentError as exc:
            with connection() as conn, conn.transaction():
                refund = _refund_row(refund["id"], conn)
                if exc.uncertain:
                    # Chapa may have carried it out: count it, and let staff confirm with Chapa before undoing anything
                    conn.execute("update refunds set status = 'needs_check', error = %s, updated_at = now() where id = %s",
                                 (str(exc)[:500], refund["id"]))
                    _apply_refund(conn, refund, payment, actor)
                else:
                    conn.execute("update refunds set status = 'failed', error = %s, updated_at = now() where id = %s",
                                 (str(exc)[:500], refund["id"]))
            if not exc.uncertain:
                raise PaymentError(f"Chapa refused the refund: {exc}. Nothing was refunded. You can refund it by "
                                   "bank transfer instead.", 409) from exc
            log.error("Refund %s for %s: uncertain gateway error %s", reference, tx_ref, exc)
        else:
            with connection() as conn, conn.transaction():
                refund = _refund_row(refund["id"], conn)
                done = result["status"] == "refunded"
                conn.execute(
                    "update refunds set status = %s, gateway_ref = %s, updated_at = now(), "
                    "completed_at = case when %s then now() else completed_at end where id = %s",
                    (result["status"], result.get("ref_id"), done, refund["id"]),
                )
                _apply_refund(conn, refund, payment, actor)
    refund = _refund_row(refund["id"])
    if refund["status"] == "refunded" and refund["engagement_id"]:
        _refund_done(refund, actor)
    _tell_refund(refund, payment)
    return {"refund_id": refund["id"], "reference": refund["reference"], "status": refund["status"],
            "amount": refund["amount"]}


def refund_action(refund_id: str, *, action: str, note: str | None, transfer_reference: str | None, actor: str) -> dict:
    """
    refresh:   ask Chapa about a refund that is processing or needs checking
    confirm:   staff sent a manual refund (or saw in Chapa's dashboard that it went through)
    mark_failed: the money did not reach the client; the figures and the provider's share are restored
    """
    note = (note or "").strip()
    refund = _refund_row(refund_id)
    if not refund:
        raise PaymentError("Refund not found", 404)
    payment = fetch_one("select id::text, engagement_id::text, tx_ref from payments where id = %s", (refund["payment_id"],))
    if action == "refresh":
        if refund["status"] not in ("processing", "needs_check") or not refund["gateway_ref"]:
            if refund["status"] == "needs_check":
                raise PaymentError("Chapa gave no reference for this refund. Check the Chapa dashboard, then confirm "
                                   "or mark it failed.", 409)
            return _admin_refund(refund_id)
        status = payment_service.gateway_named(refund["gateway"]).verify_refund(refund["gateway_ref"])
        if status == "refunded":
            execute("update refunds set status = 'refunded', completed_at = now(), updated_at = now() "
                    "where id = %s and status in ('processing', 'needs_check')", (refund_id,))
        elif status == "failed":
            with connection() as conn, conn.transaction():
                row = _refund_row(refund_id, conn)
                if row["status"] in ("processing", "needs_check"):
                    conn.execute("update refunds set status = 'failed', error = 'Chapa reversed the refund', "
                                 "updated_at = now() where id = %s", (refund_id,))
                    _unapply_refund(conn, row, actor, "Chapa reversed it; the money is back in our Chapa balance")
    elif action == "confirm":
        if refund["status"] not in ("manual_pending", "needs_check"):
            raise PaymentError("Only a refund waiting to be sent or checked can be confirmed", 409)
        if refund["status"] == "manual_pending" and actor == refund.get("requested_by"):
            raise PaymentError("The person who asked for this refund can't also confirm it was sent. "
                               "Ask another staff member.", 403)
        ref = (transfer_reference or "").strip()
        if refund["status"] == "manual_pending" and len(ref) < 3:
            raise PaymentError("Enter the bank transfer reference")
        if len(note) < 5 and not ref:
            raise PaymentError("Write what you checked")
        row = fetch_one(
            "update refunds set status = 'refunded', transfer_reference = coalesce(%s, transfer_reference), "
            "confirmed_by = %s, note = %s, completed_at = now(), updated_at = now() "
            "where id = %s and status in ('manual_pending', 'needs_check') returning id",
            (ref or None, actor, note or None, refund_id),
        )
        if not row:
            raise PaymentError("This refund was already decided", 409)
    elif action == "mark_failed":
        if refund["status"] not in ("manual_pending", "needs_check"):
            raise PaymentError("Only a refund waiting to be sent or checked can be marked failed", 409)
        if len(note) < 10:
            raise PaymentError("Write what you checked (at least 10 characters)")
        if refund["status"] == "needs_check" and refund["gateway"] == "chapa":
            # Chapa may already have sent this money; failing it re-opens the refund and could pay twice
            if refund["gateway_ref"]:
                if payment_service.gateway_named("chapa").verify_refund(refund["gateway_ref"]) != "failed":
                    raise PaymentError("Chapa doesn't show this refund as failed, so it can't be marked failed. "
                                       "Check again later or confirm it.", 409)
            elif actor in (refund.get("requested_by"), refund.get("approved_by")):
                raise PaymentError("Chapa gave no reference for this refund. Someone other than the people who "
                                   "asked for and approved it must check the Chapa dashboard and mark it failed.", 403)
        with connection() as conn, conn.transaction():
            row = _refund_row(refund_id, conn)
            if row["status"] not in ("manual_pending", "needs_check"):
                raise PaymentError("This refund was already decided", 409)
            conn.execute("update refunds set status = 'failed', note = %s, confirmed_by = %s, updated_at = now() "
                         "where id = %s", (note, actor, refund_id))
            _unapply_refund(conn, row, actor, note)
    else:
        raise PaymentError("Unknown action")
    after = _refund_row(refund_id)
    if after["status"] != refund["status"] and after["status"] == "refunded":
        from services import provider_service

        if after["engagement_id"]:
            _refund_done(after, actor)
        eng = provider_service.get_engagement(payment["engagement_id"])
        if eng:
            provider_service._tell(eng, "client", f"Your refund of {after['amount']:,.2f} ETB was sent",
                                   f"Reference {after['reference']}. Your refund receipt is ready.")
    return _admin_refund(refund_id)


def _admin_refund(refund_id: str) -> dict:
    return fetch_one(f"select {REFUND_COLUMNS}, p.tx_ref from refunds r join payments p on p.id = r.payment_id "
                     "where r.id = %s", (refund_id,))


def admin_refunds(*, tx_ref: str | None = None, status: str | None = None, limit: int = 25, offset: int = 0,
                  show_account: bool = False) -> dict:
    """Refunds, newest first. Staff who can refund see the full client account number of a manual refund to send it."""
    from core.crypto import decrypt

    where, params = ["true"], []
    if tx_ref:
        where.append("p.tx_ref = %s")
        params.append(tx_ref)
    if status:
        where.append("r.status = %s")
        params.append(status)
    clause = " and ".join(where)
    items = fetch_all(
        f"""
        select {REFUND_COLUMNS}, r.client_account_enc, p.tx_ref, p.amount::float as payment_amount, e.title, e.client_name,
               pr.display_name as provider_name
        from refunds r join payments p on p.id = r.payment_id left join engagements e on e.id = r.engagement_id
        left join providers pr on pr.id = e.provider_id
        where {clause} order by r.created_at desc, r.id limit %s offset %s
        """,
        (*params, limit, offset),
    )
    for item in items:
        enc = item.pop("client_account_enc")
        item["client_account_number"] = decrypt(enc) if show_account and item["status"] == "manual_pending" else None
    total = fetch_one(f"select count(*) as c from refunds r join payments p on p.id = r.payment_id where {clause}",
                      params)["c"]
    return {"items": items, "total": total}
