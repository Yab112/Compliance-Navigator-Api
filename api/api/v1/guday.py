"""Fayda national ID verification, used when joining the provider marketplace.

The rest of Guday Geday moved to the marketplace (api/v1/providers.py); these routes keep
their /guday prefix because Fayda redirect URIs are registered against them.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.deps import get_current_user
from schemas.auth_user import AuthUser
from services import id_verification
from services.id_verification import VerificationError

router = APIRouter(prefix="/guday", tags=["ID verification"])


def _ok(payload):
    return {"message": "success", "payload": payload}


# ---------------------------------------------------------------- Fayda ID verification


def _verr(exc: VerificationError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/fayda/status")
def fayda_status(user: AuthUser = Depends(get_current_user)):
    return _ok(id_verification.status(user.id))


@router.post("/fayda/start")
def fayda_start(user: AuthUser = Depends(get_current_user)):
    try:
        return _ok(id_verification.start(user.id))
    except VerificationError as exc:
        _verr(exc)


class FaydaCallback(BaseModel):
    code: str = Field(..., min_length=1, max_length=2000)
    state: str = Field(..., min_length=10, max_length=200)


@router.post("/fayda/complete")
def fayda_complete(body: FaydaCallback, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"verification": id_verification.complete_live(user.id, code=body.code, state=body.state)})
    except VerificationError as exc:
        _verr(exc)


class FaydaSandbox(BaseModel):
    state: str = Field(..., min_length=10, max_length=200)
    id_number: str = Field(..., min_length=12, max_length=24)
    full_name: str = Field(..., min_length=3, max_length=120)
    otp: str = Field(..., min_length=4, max_length=8)
    birthdate: str | None = Field(None, max_length=10)
    gender: str | None = Field(None, pattern="^(Male|Female)$")


@router.post("/fayda/sandbox/complete")
def fayda_sandbox_complete(body: FaydaSandbox, user: AuthUser = Depends(get_current_user)):
    if id_verification.mode() != "sandbox":
        raise HTTPException(status_code=404, detail="Not found")
    try:
        verification = id_verification.complete_sandbox(
            user.id, state=body.state, id_number=body.id_number, full_name=body.full_name,
            otp=body.otp, birthdate=body.birthdate, gender=body.gender,
        )
    except VerificationError as exc:
        _verr(exc)
    return _ok({"verification": verification})
