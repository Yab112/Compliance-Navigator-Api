"""Client records, providers rating clients, and staff-approved review changes."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.deps import get_current_user, require_admin
from schemas.auth_user import AuthUser
from services import reputation
from services.reputation import ReputationError

router = APIRouter(tags=["Reputation"])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: ReputationError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


class ClientRating(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=1000)


class ReviewChange(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=2000)
    reason: str = Field(..., min_length=5, max_length=1000)


class ChangeDecision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(None, max_length=500)


@router.get("/hires/me/record")
def my_record(user: AuthUser = Depends(get_current_user)):
    """The client's own record, exactly as providers see it."""
    return _ok({"record": reputation.client_record(user.id)})


@router.post("/providers/me/jobs/{engagement_id}/rate-client")
def rate_client(engagement_id: UUID, body: ClientRating, user: AuthUser = Depends(get_current_user)):
    from services import provider_service

    try:
        job = reputation.rate_client(str(engagement_id), user_id=user.id, rating=body.rating, comment=body.comment)
    except ReputationError as exc:
        _raise(exc)
    return _ok({"job": provider_service.provider_view(job)})


@router.post("/hires/{engagement_id}/review/change")
def request_review_change(engagement_id: UUID, body: ReviewChange, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"change": reputation.request_change(str(engagement_id), user_id=user.id, rating=body.rating,
                                                         comment=body.comment, reason=body.reason)})
    except ReputationError as exc:
        _raise(exc)


@router.get("/admin/marketplace/review-changes", dependencies=[Depends(require_admin)])
def review_changes(status: Literal["pending", "approved", "rejected"] = "pending",
                   limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _ok(reputation.list_changes(status, limit, offset))


@router.post("/admin/marketplace/review-changes/{change_id}")
def decide_review_change(change_id: UUID, body: ChangeDecision, user: AuthUser = Depends(require_admin)):
    try:
        return _ok({"change": reputation.decide_change(str(change_id), approve=body.decision == "approve",
                                                        note=body.note, actor=user.email)})
    except ReputationError as exc:
        _raise(exc)
