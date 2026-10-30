"""Staff payout review and sending payouts to the provider's bank."""

from __future__ import annotations

import logging
from decimal import Decimal

from services import notifications, payment_service, platform_settings
from services.db import connection, execute, fetch_all, fetch_one

from .earnings import PAYOUT_COLUMNS, _balances, _test_money
from .gateways import PaymentError, _money, mode
from .payout_account import names_match

log = logging.getLogger(__name__)


def _mark_paid(payout: dict, gateway_reference: str | None) -> bool:
    with connection() as conn, conn.transaction():
        done = conn.execute(
            "update payouts set status = 'paid', paid_at = now(), needs_check = false, "
            "gateway_reference = coalesce(%s, gateway_reference) "
            "where id = %s and status in ('requested', 'approved') returning id, is_test",
            (gateway_reference, payout["id"]),
        ).fetchone()
        if done:
            conn.execute(
                "insert into provider_ledger (provider_id, kind, amount, payout_id, note, is_test) "
                "values (%s, 'payout', %s, %s, %s, %s)",
                (payout["provider_id"], -Decimal(str(payout["amount"])), payout["id"],
                 f"Paid to {payout['bank_name']} ••••{payout['account_last4']}", done["is_test"]),
            )
    return bool(done)


def _mark_failed(payout: dict, note: str) -> bool:
    """Releases the held money. Only for an approved payout the gateway says did not go out."""
    done = fetch_one("update payouts set status = 'failed', needs_check = false, check_note = %s "
                     "where id = %s and status = 'approved' returning id", (note[:500], payout["id"]))
    return bool(done)


def _tell_provider(payout: dict, title: str, body: str | None = None) -> None:
    owner = fetch_one("select user_id::text from providers where id = %s", (payout["provider_id"],))
    if owner and owner["user_id"]:
        notifications.notify([owner["user_id"]], kind="payout", title=title, body=body, link="/me/provider?tab=earnings")


def payout_review(payout_id: str) -> dict:
    """What staff check before sending money: who gets it, whether the account is theirs, and what it pays for."""
    payout = fetch_one(f"select {PAYOUT_COLUMNS}, (po.account_enc is not null) as account_stored "
                       "from payouts po where po.id = %s", (payout_id,))
    if not payout:
        raise PaymentError("Payout not found", 404)
    provider = fetch_one(
        """
        select id::text, slug, display_name, legal_name, verified_name, provider_type, status, national_id_verified,
               id_verification_method, coalesce(tin, '') <> '' as has_tin, trade_license_no, vat_registered,
               payout_set_at, payout_bank_code, payout_bank_name, payout_account_name, payout_account_last4, created_at
        from providers where id = %s
        """,
        (payout["provider_id"],),
    )
    earnings_rows = fetch_all(
        """
        select l.amount::float, l.created_at, l.is_test, e.id::text as hire_id, e.title as job_title,
               p.tx_ref, p.gateway, p.amount::float as client_paid, coalesce(u.fullname, u.email) as client
        from provider_ledger l
        left join engagements e on e.id = l.engagement_id
        left join payments p on p.id = l.payment_id
        left join users u on u.id = p.payer_user_id
        where l.provider_id = %s and l.kind = 'earning'
        order by l.created_at desc limit 50
        """,
        (payout["provider_id"],),
    )
    history = fetch_one(
        """
        select count(*) filter (where status = 'paid') as paid_count,
               coalesce(sum(amount) filter (where status = 'paid'), 0)::float as paid_total,
               count(*) filter (where status in ('rejected', 'failed')) as refused_count
        from payouts where provider_id = %s and id <> %s
        """,
        (payout["provider_id"], payout_id),
    )
    balances = _balances(payout["provider_id"])
    # The account the money goes to is the one stored on the payout, shown next to the name on the verified ID
    destination = {"bank_name": payout["bank_name"], "account_name": payout["account_name"],
                   "account_last4": payout["account_last4"], "stored": payout.pop("account_stored"),
                   "fayda_name": provider["verified_name"], "id_verified": provider["national_id_verified"]}
    return {"payout": payout, "provider": provider, "balances": balances, "destination": destination,
            "earnings": earnings_rows, "history": history,
            "checks": _payout_checks(payout, provider, history, balances, destination)}


def _payout_checks(payout: dict, provider: dict, history: dict, balances: dict, destination: dict) -> list[dict]:
    """block: approving needs a written reason (hard: can't be approved at all). warn: look first. info: worth knowing."""
    checks = []
    new_account_days = platform_settings.get_int("payout_new_account_days")
    if payout["is_test"] != _test_money():
        checks.append({"level": "hard", "code": "test_money",
                       "text": "This payout was asked for from test-mode earnings. Payments are live now, so it can't be "
                               "sent. Refuse it." if payout["is_test"] else
                               "This payout was asked for while payments were live, but they are in test mode now. "
                               "Switch back to live payments to send it."})
    if not destination["stored"]:
        checks.append({"level": "hard", "code": "no_account",
                       "text": "This request has no bank account stored with it (it was made before accounts were "
                               "kept on each request). Refuse it and ask the provider to ask again."})
    if not names_match(payout["account_name"], provider["verified_name"], provider["legal_name"], provider["display_name"]):
        checks.append({"level": "block", "code": "name_mismatch",
                       "text": f"The bank account is in the name of {payout['account_name']}, not "
                               f"{provider['verified_name'] or provider['display_name']}. Money should only go to the "
                               "provider's own account or their company's."})
    if not provider["national_id_verified"]:
        checks.append({"level": "block", "code": "id_not_verified", "text": "The provider's national ID is not verified."})
    if provider["status"] != "approved":
        checks.append({"level": "block", "code": "not_approved", "text": f"The provider is {provider['status']}, not approved."})
    if balances["balance"] < balances["in_payout"] and payout["status"] == "requested" and payout["is_test"] == _test_money():
        checks.append({"level": "block", "code": "balance_short",
                       "text": f"After refunds the provider's balance ({balances['balance']:,.2f} ETB) no longer covers "
                               f"the payouts waiting ({balances['in_payout']:,.2f} ETB)."})
    if not provider["has_tin"]:
        checks.append({"level": "warn", "code": "no_tin",
                       "text": "No TIN on file. Ethiopian income tax rules require 30% withholding on payments to "
                               "suppliers without a TIN; get it before paying."})
    if provider["payout_set_at"] and (payout["created_at"] - provider["payout_set_at"]).total_seconds() < new_account_days * 24 * 3600:
        checks.append({"level": "warn", "code": "new_account",
                       "text": f"The bank account was added or changed less than {new_account_days} days before this request."})
    if provider["payout_account_last4"] and (provider["payout_account_last4"] != payout["account_last4"]
                                              or provider["payout_bank_code"] != payout["bank_code"]):
        checks.append({"level": "warn", "code": "account_changed",
                       "text": "The provider's bank account on file is different now. The money goes to the account "
                               "shown here, the one the request was made with."})
    if payout["needs_check"]:
        checks.append({"level": "warn", "code": "needs_check",
                       "text": payout["check_note"] or "The transfer could not be confirmed. Check with Chapa."})
    if not history["paid_count"]:
        checks.append({"level": "info", "code": "first_payout", "text": "First payout to this provider."})
    if _test_money():
        checks.append({"level": "info", "code": "test_mode",
                       "text": "Payments are in test mode: no real money was collected and none will be sent."})
    return checks


def decide_payout(payout_id: str, *, decision: str, note: str | None, actor: str) -> dict:
    """
    approve:     claim the payout (only one approval wins), then send it to the account stored on it
                 (simulated: paid at once; Chapa: queued, then refresh)
    reject:      refuse a payout that is still waiting; the held money is released
    refresh:     ask the gateway about an approved payout
    mark_failed: release an approved payout, only once the gateway says it failed or never received it
    A payout with a blocking check (name mismatch, unverified ID) is only approved with a written reason.
    """
    from core.crypto import decrypt

    payout = fetch_one(f"select {PAYOUT_COLUMNS}, po.account_enc from payouts po where po.id = %s", (payout_id,))
    if not payout:
        raise PaymentError("Payout not found", 404)
    note = (note or "").strip()
    if decision == "reject":
        if not note:
            raise PaymentError("Tell the provider why")
        # Only a payout nobody has sent yet can be refused; an approved one may already be in the bank
        row = fetch_one("update payouts set status = 'rejected', note = %s, decided_by = %s, decided_at = now() "
                        "where id = %s and status = 'requested' returning id", (note, actor, payout_id))
        if not row:
            raise PaymentError("Only a payout that is still waiting can be refused. An approved one may already be on "
                               "its way: use Check with Chapa, or Mark failed once Chapa confirms it failed.", 409)
        _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB was not approved", note)
    elif decision == "approve":
        if payout["status"] != "requested":
            raise PaymentError("This payout was already decided", 409)
        checks = payout_review(payout_id)["checks"]
        hard = [c["text"] for c in checks if c["level"] == "hard"]
        if hard:
            raise PaymentError(" ".join(hard), 409)
        blocks = [c["text"] for c in checks if c["level"] == "block"]
        if blocks and len(note) < 10:
            raise PaymentError("Check before paying: " + " ".join(blocks) + " To approve anyway, write why.", 409)
        account = decrypt(payout["account_enc"])
        if not account:
            raise PaymentError("The bank account on this request can't be read. Refuse it and ask the provider to "
                               "ask again.", 409)
        gw = payment_service.gateway()
        # Claim it: of two approvals at the same moment only one gets the row back, and only that one sends money
        claimed = fetch_one(
            "update payouts set status = 'approved', decided_by = %s, decided_at = now(), note = %s, gateway = %s "
            "where id = %s and status = 'requested' returning id",
            (actor, note or None, gw.name, payout_id),
        )
        if not claimed:
            raise PaymentError("This payout was already decided", 409)
        try:
            result = gw.transfer(account_name=payout["account_name"], account_number=account,
                                 bank_code=payout["bank_code"], amount=_money(payout["amount"]),
                                 reference=payout["reference"])
        except PaymentError as exc:
            # The money may have left even though we got an error (a timeout after Chapa accepted it). Keep it
            # held as approved and check with Chapa before anyone releases it.
            log.error("Payout %s transfer error (%s): %s", payout_id, "uncertain" if exc.uncertain else "refused", exc)
            execute("update payouts set needs_check = true, check_note = %s where id = %s",
                    (f"The transfer request got an error: {str(exc)[:200]}. The money stays held. Use Check "
                     f"with Chapa; release it only when Chapa says it failed."[:500], payout_id))
            raise PaymentError("The transfer could not be confirmed. The money stays held until Chapa confirms what "
                               "happened: use Check with Chapa.", 502) from exc
        if result["status"] == "paid":
            _mark_paid(payout, result.get("reference"))
            _tell_provider(payout, f"{payout['amount']:,.2f} ETB sent to your bank",
                           f"{payout['bank_name']} ••••{payout['account_last4']}")
        else:
            execute("update payouts set gateway_reference = %s where id = %s", (result.get("reference"), payout_id))
            _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB approved", "It is on its way to your bank.")
    elif decision in ("refresh", "mark_failed"):
        if payout["status"] != "approved":
            if decision == "mark_failed":
                raise PaymentError("Only an approved payout can be marked failed", 409)
            return _public_staff_payout(payout_id)
        if decision == "mark_failed" and len(note) < 10:
            raise PaymentError("Write what you checked (at least 10 characters)")
        status = payment_service.gateway_named(payout["gateway"] or mode()).verify_transfer(payout["reference"])
        if status == "paid":
            if _mark_paid(payout, None):
                _tell_provider(payout, f"{payout['amount']:,.2f} ETB arrived in your bank",
                               f"{payout['bank_name']} ••••{payout['account_last4']}")
            if decision == "mark_failed":
                raise PaymentError("Chapa says this transfer was paid, so it was recorded as paid instead.", 409)
        elif status == "failed" or (status == "missing" and decision == "mark_failed"):
            why = "Chapa reports the transfer failed" if status == "failed" else \
                f"Chapa has no record of the transfer. Checked by {actor}: {note}"
            if _mark_failed(payout, why):
                _tell_provider(payout, f"Payout of {payout['amount']:,.2f} ETB failed",
                               "The money is back in your balance. Our team will contact you.")
        elif status == "missing":
            execute("update payouts set check_note = %s where id = %s and status = 'approved'",
                    ("Chapa has no record of this transfer yet. If it still has none, mark it failed with a note.",
                     payout_id))
        elif decision == "mark_failed":
            raise PaymentError("Chapa still shows the transfer on its way (or can't be reached), so the money can't be "
                               "released yet. Try again later.", 409)
    else:
        raise PaymentError("Unknown decision")
    return _public_staff_payout(payout_id)


def check_processing_payouts(min_age_minutes: int = 5) -> dict:
    """Ask the gateway about every approved payout that has waited a few minutes, so a transfer that
    landed (or failed) is recorded without staff pressing "Check with Chapa". Runs every 15 minutes."""
    rows = fetch_all(
        "select id::text from payouts where status = 'approved' and decided_at < now() - make_interval(mins => %s) "
        "order by decided_at limit 100",
        (min_age_minutes,),
    )
    counts = {"checked": 0, "paid": 0, "failed": 0, "errors": 0}
    for row in rows:
        try:
            after = decide_payout(row["id"], decision="refresh", note=None, actor="automatic Chapa check")
        except Exception:
            counts["errors"] += 1
            log.exception("Automatic check of payout %s failed", row["id"])
            continue
        counts["checked"] += 1
        if after and after.get("status") in ("paid", "failed"):
            counts[after["status"]] += 1
    return counts


def _public_staff_payout(payout_id: str) -> dict:
    return fetch_one(f"select {PAYOUT_COLUMNS} from payouts po where po.id = %s", (payout_id,))
