"""Clients pay online; providers see their earnings and request payouts that staff approve."""

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core.deps import get_current_user, require_admin
from schemas.auth_user import AuthUser
from services import payment_service, platform_settings
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
    tx_ref = event.get("tx_ref")
    if tx_ref and payment_service.get(tx_ref):
        try:
            payment_service.confirm(tx_ref)  # verifies with Chapa again before recording anything
        except PaymentError:
            pass
    return _ok({"received": True})


class PayoutRequest(BaseModel):
    amount: float = Field(..., gt=0, le=10_000_000)


class PayoutDecision(BaseModel):
    decision: Literal["approve", "reject", "refresh"]
    note: str | None = Field(None, max_length=500)


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
def request_payout(body: PayoutRequest, user: AuthUser = Depends(get_current_user)):
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


@router.get("/payouts/{payout_id}/receipt")
def payout_receipt(payout_id: str, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"receipt": payment_service.payout_receipt(payout_id, user=user)})
    except PaymentError as exc:
        _raise(exc)


# ---------------------------------------------------------------- staff


@router.get("/admin/marketplace/payments", dependencies=[Depends(require_admin)])
def admin_payments(status: Literal["pending", "success", "failed", "cancelled"] | None = None,
                   limit: int = 50, offset: int = 0):
    return _ok(payment_service.admin_list(status, min(max(limit, 1), 200), max(offset, 0)))


@router.get("/admin/marketplace/payouts", dependencies=[Depends(require_admin)])
def admin_payouts(status: Literal["requested", "approved", "paid", "rejected", "failed"] | None = "requested",
                  limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _ok(payment_service.admin_payouts(status, limit, offset))


@router.get("/admin/marketplace/payouts/{payout_id}", dependencies=[Depends(require_admin)])
def payout_review(payout_id: UUID):
    try:
        return _ok(payment_service.payout_review(str(payout_id)))
    except PaymentError as exc:
        _raise(exc)


@router.post("/admin/marketplace/payouts/{payout_id}")
def decide_payout(payout_id: str, body: PayoutDecision, user: AuthUser = Depends(require_admin)):
    try:
        return _ok({"payout": payment_service.decide_payout(payout_id, decision=body.decision, note=body.note,
                                                            actor=user.email)})
    except PaymentError as exc:
        _raise(exc)
