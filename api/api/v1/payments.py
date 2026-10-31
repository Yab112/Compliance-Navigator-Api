"""Clients pay online; providers see their earnings and request payouts that staff approve."""

import hashlib
import json
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from core.deps import client_info, get_current_user, require_admin
from core.verified import get_verified_user
from schemas.auth_user import AuthUser
from services import payment_service, platform_settings
from services.approvals import PendingApproval
from services.payment_service import PaymentError

router = APIRouter(tags=["Payments"])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: PaymentError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


class PayoutBody(BaseModel):
    bank_code: str = Field(..., min_length=1, max_length=40)
    account_number: str = Field(..., min_length=6, max_length=30)
    account_name: str = Field(..., min_length=2, max_length=120)


class SimulateBody(BaseModel):
    outcome: Literal["success", "failed"]


@router.get("/payments/config")
def config():
    return _ok({"mode": payment_service.mode(), "enabled": payment_service.enabled(),
                "commission_percent": platform_settings.get("commission_percent"),
                # So price estimates match exactly what payment_service.breakdown() will charge
                "vat_rate_percent": platform_settings.get("vat_rate_percent"),
                "platform_vat_registered": platform_settings.get("platform_vat_registered")})


@router.get("/payments/banks")
def banks(_: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"items": payment_service.banks()})
    except PaymentError as exc:
        _raise(exc)


@router.get("/providers/me/payout")
def my_payout(user: AuthUser = Depends(get_current_user)):
    from services import provider_service

    provider = provider_service.get_for_user(user.id)
    if not provider:
        raise HTTPException(status_code=404, detail="Join as a provider first")
    return _ok({"payout": payment_service.payout_view(provider)})


@router.put("/providers/me/payout")
def set_payout(body: PayoutBody, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"payout": payment_service.set_payout(user.id, bank_code=body.bank_code,
                                                         account_number=body.account_number,
                                                         account_name=body.account_name)})
    except PaymentError as exc:
        _raise(exc)


@router.post("/hires/{engagement_id}/pay")
def pay(engagement_id: str, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok(payment_service.start(engagement_id, user=user))
    except PaymentError as exc:
        _raise(exc)


def _public(payment: dict) -> dict:
    return {k: v for k, v in payment.items() if k not in ("payer_user_id", "checkout_url")}


@router.get("/payments/{tx_ref}")
def payment_status(tx_ref: str, user: AuthUser = Depends(get_current_user)):
    """Called when the client returns from the checkout: re-checks with the gateway."""
    payment = payment_service.get(tx_ref)
    if not payment or payment["payer_user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    try:
        return _ok({"payment": _public(payment_service.confirm(tx_ref))})
    except PaymentError as exc:
        _raise(exc)


@router.get("/payments/{tx_ref}/checkout")
def test_checkout(tx_ref: str, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"checkout": payment_service.checkout_view(tx_ref, user=user)})
    except PaymentError as exc:
        _raise(exc)


@router.post("/payments/{tx_ref}/simulate")
def simulate(tx_ref: str, body: SimulateBody, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"payment": _public(payment_service.simulate(tx_ref, user=user, outcome=body.outcome))})
    except PaymentError as exc:
        _raise(exc)


@router.api_route("/payments/chapa/callback", methods=["GET", "POST"])
async def chapa_callback(request: Request):
    """Chapa's callback after a payment. Nothing in it is trusted: we re-verify with Chapa."""
    tx_ref = request.query_params.get("trx_ref") or request.query_params.get("tx_ref")
    if not tx_ref and request.method == "POST":
        try:
            body = await request.json()
            tx_ref = body.get("trx_ref") or body.get("tx_ref")
        except Exception:
            tx_ref = None
    from core import ratelimit

    # Anyone can call this, so limit how often it makes us ask Chapa about the same payment
    if tx_ref and isinstance(tx_ref, str) and ratelimit.hit("chapa_webhook", f"cb:{tx_ref[:100]}") is not None:
        return _ok({"received": True})
    if tx_ref and payment_service.get(tx_ref):
        try:
            payment_service.confirm(tx_ref)
        except PaymentError:
            pass
    return _ok({"received": True})


@router.post("/payments/chapa/webhook")
async def chapa_webhook(request: Request):
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not payment_service.webhook_signature_ok(raw, headers):
        raise HTTPException(status_code=401, detail="Bad signature")
    try:
        event = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad payload") from None
    # Replay protection: an identical delivery is handled once a week, and each payment is checked with
    # Chapa at most a few times a minute, so a captured signature can't be used to hammer us or Chapa
    from core import ratelimit

    digest = hashlib.sha256(raw).hexdigest()
    if not ratelimit.once("chapa_webhook", digest, 7 * 86400):
        return _ok({"received": True, "duplicate": True})
    tx_ref = event.get("tx_ref")
    if tx_ref and isinstance(tx_ref, str) and ratelimit.hit("chapa_webhook", tx_ref[:100]) is not None:
        ratelimit.forget("chapa_webhook", digest)  # so Chapa's own retry later still counts
        return _ok({"received": True, "throttled": True})
    if tx_ref and payment_service.get(tx_ref):
        try:
            payment_service.confirm(tx_ref)  # verifies with Chapa again before recording anything
        except PaymentError:
            ratelimit.forget("chapa_webhook", digest)
    return _ok({"received": True})


class PayoutRequest(BaseModel):
    amount: float = Field(..., gt=0, le=10_000_000)


class PayoutDecision(BaseModel):
    decision: Literal["approve", "reject", "refresh", "mark_failed", "returned"]
    note: str | None = Field(None, max_length=500)


class ClientBank(BaseModel):
    bank_name: str = Field(..., min_length=2, max_length=80)
    account_name: str = Field(..., min_length=2, max_length=120)
    account_number: str = Field(..., min_length=6, max_length=30)


class RefundBody(BaseModel):
    amount: float | None = Field(None, gt=0, le=10_000_000)  # empty: everything not refunded yet
    reason: str = Field(..., min_length=5, max_length=500)
    method: Literal["gateway", "manual"] = "gateway"
    client_bank: ClientBank | None = None


class RefundAction(BaseModel):
    action: Literal["refresh", "confirm", "mark_failed"]
    note: str | None = Field(None, max_length=500)
    transfer_reference: str | None = Field(None, max_length=120)


@router.get("/providers/me/earnings")
def my_earnings(user: AuthUser = Depends(get_current_user)):
    try:
        return _ok(payment_service.earnings(user.id))
    except PaymentError as exc:
        _raise(exc)


@router.get("/providers/me/earnings/ledger")
def my_ledger(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), user: AuthUser = Depends(get_current_user)):
    try:
        return _ok(payment_service.ledger_page(user.id, limit, offset))
    except PaymentError as exc:
        _raise(exc)


@router.get("/providers/me/payouts")
def my_payouts(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), user: AuthUser = Depends(get_current_user)):
    try:
        return _ok(payment_service.payouts_page(user.id, limit, offset))
    except PaymentError as exc:
        _raise(exc)


@router.post("/providers/me/payouts", status_code=201)
def request_payout(body: PayoutRequest, user: AuthUser = Depends(get_verified_user)):
    try:
        return _ok({"payout": payment_service.request_payout(user.id, body.amount)})
    except PaymentError as exc:
        _raise(exc)


@router.get("/payments/{tx_ref}/receipt")
def payment_receipt(tx_ref: str, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"receipt": payment_service.payment_receipt(tx_ref, user=user)})
    except PaymentError as exc:
        _raise(exc)


@router.get("/refunds/{refund_id}/receipt")
def refund_receipt(refund_id: UUID, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"receipt": payment_service.refund_receipt(str(refund_id), user=user)})
    except PaymentError as exc:
        _raise(exc)


@router.get("/payouts/{payout_id}/receipt")
def payout_receipt(payout_id: str, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"receipt": payment_service.payout_receipt(payout_id, user=user)})
    except PaymentError as exc:
        _raise(exc)


# ---------------------------------------------------------------- staff


PaymentStatus = Literal["pending", "success", "failed", "cancelled"]


@router.get("/admin/marketplace/payments", dependencies=[Depends(require_admin)])
def admin_payments(status: PaymentStatus | None = None, limit: int = 50, offset: int = 0,
                   q: str | None = Query(None, max_length=120), date_from: date | None = Query(None, alias="from"),
                   date_to: date | None = Query(None, alias="to"), needs_refund: bool | None = None,
                   engagement_id: UUID | None = None):
    return _ok(payment_service.admin_list(status, min(max(limit, 1), 200), max(offset, 0), q=q, date_from=date_from,
                                          date_to=date_to, needs_refund=needs_refund,
                                          engagement_id=str(engagement_id) if engagement_id else None))


@router.get("/admin/marketplace/payments.csv", dependencies=[Depends(require_admin)])
def admin_payments_csv(status: PaymentStatus | None = None, q: str | None = Query(None, max_length=120),
                       date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
                       needs_refund: bool | None = None):
    body = payment_service.admin_csv(status, q=q, date_from=date_from, date_to=date_to, needs_refund=needs_refund)
    return Response(content=body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="payments.csv"'})


@router.post("/admin/marketplace/payments/{tx_ref}/verify", dependencies=[Depends(require_admin)])
def admin_verify_payment(tx_ref: str):
    """Ask Chapa again about a payment (for one still pending because the client never came back)."""
    try:
        return _ok(payment_service.admin_verify(tx_ref))
    except PaymentError as exc:
        _raise(exc)


@router.post("/admin/marketplace/payments/{tx_ref}/refund")
def admin_refund(tx_ref: str, body: RefundBody, user=Depends(require_admin)):
    """
    A refund always needs a second staff member: require_admin stores it for approval (202) through the
    payment.refund rule. This body only runs when nobody else could approve (the waiver is audited).
    """
    try:
        plan = payment_service.refund_plan(tx_ref, amount=body.amount, reason=body.reason, method=body.method,
                                           client_bank=body.client_bank.model_dump() if body.client_bank else None)
        return _ok({"refund": payment_service.execute_refund(plan["payload"],
                                                             f"{user.email} (no second approver available)")})
    except PaymentError as exc:
        _raise(exc)


@router.get("/admin/marketplace/refunds")
def admin_refunds(tx_ref: str | None = Query(None, max_length=80),
                  status: Literal["sending", "processing", "refunded", "manual_pending", "needs_check", "failed"] | None = None,
                  limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), user=Depends(require_admin)):
    return _ok(payment_service.admin_refunds(tx_ref=tx_ref, status=status, limit=limit, offset=offset,
                                             show_account=user.can("payments.refund")))


@router.post("/admin/marketplace/refunds/{refund_id}")
def admin_refund_action(refund_id: UUID, body: RefundAction, user=Depends(require_admin)):
    try:
        return _ok({"refund": payment_service.refund_action(str(refund_id), action=body.action, note=body.note,
                                                            transfer_reference=body.transfer_reference,
                                                            actor=user.email)})
    except PaymentError as exc:
        _raise(exc)


@router.get("/admin/marketplace/payouts", dependencies=[Depends(require_admin)])
def admin_payouts(status: Literal["requested", "approved", "paid", "rejected", "failed", "returned"] | None = "requested",
                  limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _ok(payment_service.admin_payouts(status, limit, offset))


@router.get("/admin/marketplace/payouts/{payout_id}", dependencies=[Depends(require_admin)])
def payout_review(payout_id: UUID):
    try:
        return _ok(payment_service.payout_review(str(payout_id)))
    except PaymentError as exc:
        _raise(exc)


@router.post("/admin/marketplace/payouts/{payout_id}")
def decide_payout(payout_id: UUID, body: PayoutDecision, request: Request, user: AuthUser = Depends(require_admin)):
    """returned: a paid transfer came back. Once Chapa confirms it, it waits for a second staff member (202)."""
    try:
        return _ok({"payout": payment_service.decide_payout(str(payout_id), decision=body.decision, note=body.note,
                                                            actor=user.email, staff=user, client=client_info(request))})
    except PendingApproval as pending:
        # Answered here, not by the app's handler, so the staff audit entry records it as asked for, not as an error
        return JSONResponse(status_code=202, content={"message": "approval_required",
                                                      "payload": {"approval": jsonable_encoder(pending.request)}})
    except PaymentError as exc:
        _raise(exc)


# ---------------------------------------------------------------- payment health


@router.get("/admin/marketplace/payment-health")
def payment_health(hours: int = Query(24, ge=1, le=168, description="The period, in hours (up to 7 days)"),
                   user: AuthUser = Depends(require_admin)):
    """Chapa's status, every call in the period by operation, and money that needs a person now.
    Payouts in the list need payouts.view as well."""
    return _ok(payment_service.health_overview(hours, include_payouts=user.can("payouts.view")))


@router.get("/admin/marketplace/payment-health/errors", dependencies=[Depends(require_admin)])
def payment_health_errors(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _ok(payment_service.recent_errors(limit, offset))


@router.post("/admin/marketplace/payment-health/check", dependencies=[Depends(require_admin)])
def payment_health_check():
    """Ask Chapa for its bank list now (never the cached copy) and say how long it took."""
    return _ok(payment_service.live_check())
