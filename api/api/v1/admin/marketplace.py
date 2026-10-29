"""Admin: marketplace providers, licences, hires, complaints and review moderation."""

from fastapi import APIRouter, Depends, HTTPException, Query

from core.deps import require_admin
from schemas.auth_user import AuthUser
from schemas.providers import (
    DisputeDecision,
    EngagementAdminUpdate,
    LicenseDecision,
    ProviderProfile,
    ProviderReview,
    ReviewModeration,
)
from services import provider_service as svc
from services.provider_service import MarketplaceError

router = APIRouter(prefix="/admin/marketplace", tags=["Admin Marketplace"], dependencies=[Depends(require_admin)])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: MarketplaceError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/stats")
def stats():
    return _ok(svc.marketplace_stats())


@router.get("/providers")
def list_providers(
    type: str | None = Query(None, pattern="^(guday_geday|agency)$"),
    status_: str | None = Query(None, alias="status"),
    license_status: str | None = Query(None, pattern="^(none|pending|verified|rejected)$"),
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return _ok(svc.admin_list(provider_type=type, status=status_, q=q, license_status=license_status,
                              limit=limit, offset=offset))


@router.get("/providers/{provider_id}")
def provider_detail(provider_id: str):
    provider = svc.admin_detail(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _ok({"provider": provider})


@router.post("/providers/{provider_id}/review")
def review_provider(provider_id: str, body: ProviderReview, admin: AuthUser = Depends(require_admin)):
    try:
        svc.review_provider(provider_id, body.action, actor=admin.email, note=body.note)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"provider": svc.admin_detail(provider_id)})


@router.post("/providers/{provider_id}/license")
def license_decision(provider_id: str, body: LicenseDecision, admin: AuthUser = Depends(require_admin)):
    try:
        svc.verify_external_license(provider_id, body.decision, actor=admin.email, note=body.note)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"provider": svc.admin_detail(provider_id)})


@router.patch("/providers/{provider_id}")
def update_provider(provider_id: str, body: ProviderProfile, admin: AuthUser = Depends(require_admin)):
    try:
        svc.admin_update(provider_id, body.model_dump(exclude_unset=True), admin.email)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"provider": svc.admin_detail(provider_id)})


@router.get("/engagements")
def list_engagements(
    status_: str | None = Query(None, alias="status"),
    disputed: bool | None = None,
    follow_up: bool = False,
    provider_id: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return _ok(svc.list_engagements(status=status_, disputed=disputed, provider_id=provider_id, q=q,
                                    limit=limit, offset=offset, follow_up=follow_up))


@router.patch("/engagements/{engagement_id}")
def update_engagement(engagement_id: str, body: EngagementAdminUpdate):
    try:
        hire = svc.admin_update_engagement(
            engagement_id, provider_id=body.provider_id, status=body.status, note=body.note
        )
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"hire": hire})


@router.post("/engagements/{engagement_id}/dispute")
def decide_dispute(engagement_id: str, body: DisputeDecision, admin: AuthUser = Depends(require_admin)):
    try:
        hire = svc.resolve_dispute(engagement_id, body.decision, note=body.note, actor=admin.email)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"hire": hire})


@router.get("/reviews")
def list_reviews(
    hidden: bool | None = None,
    max_rating: int | None = Query(None, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return _ok(svc.list_reviews_admin(hidden=hidden, max_rating=max_rating, limit=limit, offset=offset))


@router.post("/reviews/{review_id}/moderate")
def moderate(review_id: str, body: ReviewModeration, admin: AuthUser = Depends(require_admin)):
    try:
        return _ok(svc.moderate_review(review_id, hide=body.hidden, reason=body.reason, actor=admin.email))
    except MarketplaceError as exc:
        _raise(exc)


@router.post("/samples/purge")
def purge_samples():
    """Remove the demo providers, hires and reviews created by scripts/seed_providers.py."""
    return _ok(svc.purge_samples())
