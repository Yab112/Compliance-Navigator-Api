"""Admin: marketplace providers, licences, hires, complaints and review moderation."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from auth import staff_service
from core.deps import client_info, require_admin
from schemas.auth_user import AuthUser
from schemas.providers import (
    DisputeDecision,
    EngagementAdminUpdate,
    LicenseDecision,
    ProviderProfile,
    ProviderReview,
    ReviewModeration,
)
from schemas.vetting import ChangeDecision, DocumentDecision, ReferenceDecision
from services import provider_service as svc
from services import vetting
from services.provider_service import MarketplaceError
from services.storage_service import safe_file_headers
from services.vetting import VettingError

router = APIRouter(prefix="/admin/marketplace", tags=["Admin Marketplace"], dependencies=[Depends(require_admin)])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: MarketplaceError | VettingError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/stats")
def stats():
    return _ok(svc.marketplace_stats())


@router.get("/providers")
def list_providers(
    type: str | None = Query(None, pattern="^(guday_geday|agency)$"),
    status_: str | None = Query(None, alias="status"),
    license_status: str | None = Query(None, pattern="^(none|pending|verified|rejected)$"),
    q: str | None = Query(None, max_length=100),
    expiring: int | None = Query(None, ge=1, le=365, description="Approved, licence ends within this many days"),
    area: str | None = Query(None, max_length=40),
    id_verified: bool | None = None,
    accepting_work: bool | None = None,
    sort: str = Query("queue", pattern="^(queue|newest|score|complaints|expiry)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return _ok(svc.admin_list(provider_type=type, status=status_, q=q, license_status=license_status,
                              expiring_days=expiring, area=area, id_verified=id_verified,
                              accepting_work=accepting_work, sort=sort, limit=limit, offset=offset))


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


@router.post("/providers/{provider_id}/changes/{change_id}")
def decide_change(provider_id: str, change_id: str, body: ChangeDecision, admin: AuthUser = Depends(require_admin)):
    """Approve or refuse a name, registration or VAT change an approved provider asked for."""
    _provider_or_404(provider_id)
    try:
        svc.decide_change(provider_id, change_id, body.decision, actor=admin.email, note=body.note)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"provider": svc.admin_detail(provider_id)})


# ---------------------------------------------------------------- vetting documents


def _provider_or_404(provider_id: str) -> dict:
    provider = svc.get(provider_id) if vetting._uuid_like(provider_id) else None
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


def _can(admin, permission: str) -> bool:
    has = getattr(admin, "has", None)
    return bool(has(permission)) if callable(has) else True


def _may_see_criminal_records(admin) -> bool:
    """The one place that decides who may open a police clearance: only staff holding that permission."""
    return admin.has("vetting.view_criminal_records")


@router.get("/providers/{provider_id}/documents")
def provider_documents(provider_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    """Every document this provider uploaded, newest first, including replaced and rejected copies."""
    _provider_or_404(provider_id)
    return _ok(vetting.history(provider_id, limit=limit, offset=offset))


@router.get("/providers/{provider_id}/documents/{document_id}/file")
def provider_document_file(provider_id: str, document_id: str, admin: AuthUser = Depends(require_admin)):
    """Opening a police clearance is written to the provider's audit log (who and when)."""
    try:
        content, content_type, _ = vetting.read_file(provider_id, document_id, actor=admin.email, by_staff=True,
                                                       may_see_sensitive=_may_see_criminal_records(admin))
    except VettingError as exc:
        _raise(exc)
    return Response(content, media_type=content_type, headers=safe_file_headers(content_type))


@router.post("/providers/{provider_id}/documents/{document_id}/review")
def review_document(provider_id: str, document_id: str, body: DocumentDecision,
                    admin: AuthUser = Depends(require_admin)):
    _provider_or_404(provider_id)
    try:
        vetting.review_document(provider_id, document_id, body.decision, actor=admin.email, note=body.note,
                                issued_on=body.issued_on, expires_on=body.expires_on,
                                reference_no=body.reference_no, level=body.level)
    except VettingError as exc:
        _raise(exc)
    return _ok({"provider": svc.admin_detail(provider_id)})


@router.post("/providers/{provider_id}/references/{reference_id}")
def check_reference(provider_id: str, reference_id: str, body: ReferenceDecision,
                    admin: AuthUser = Depends(require_admin)):
    _provider_or_404(provider_id)
    try:
        vetting.check_reference(provider_id, reference_id, body.decision, actor=admin.email, note=body.note)
    except VettingError as exc:
        _raise(exc)
    return _ok({"provider": svc.admin_detail(provider_id)})


def _hire_filters(
    status_: str | None = Query(None, alias="status",
                                pattern="^(open|requested|accepted|in_progress|completed|declined|cancelled)$"),
    disputed: bool | None = None,
    follow_up: bool = False,
    provider_id: str | None = Query(None, max_length=40),
    payment_status: str | None = Query(None, pattern="^(unpaid|pending|paid|failed|refunded)$"),
    refund_needed: bool | None = None,
    q: str | None = Query(None, max_length=100),
) -> dict:
    return {"status": status_, "disputed": disputed, "follow_up": follow_up, "provider_id": provider_id,
            "payment_status": payment_status, "refund_needed": refund_needed, "q": q}


@router.get("/engagements")
def list_engagements(filters: dict = Depends(_hire_filters), limit: int = Query(50, ge=1, le=200),
                     offset: int = Query(0, ge=0)):
    from services import platform_settings

    return _ok({**svc.list_engagements(**filters, limit=limit, offset=offset),
                "follow_up_hours": platform_settings.get_int("follow_up_hours")})


# Declared before /engagements/{engagement_id} so "engagements.csv" is never read as an id
@router.get("/engagements.csv")
def export_engagements(request: Request, filters: dict = Depends(_hire_filters),
                       admin: AuthUser = Depends(require_admin)):
    """Spreadsheet of the filtered hires. It holds clients' phone numbers, so every export is logged."""
    text, rows = svc.export_engagements_csv(**filters)
    staff_service.audit("hires.export", actor=admin, target="engagements", client=client_info(request),
                        details={"rows": rows, "filters": {k: v for k, v in filters.items() if v}})
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="hires-{datetime.now(UTC).date().isoformat()}.csv"',
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/engagements/{engagement_id}")
def engagement_detail(engagement_id: UUID, admin: AuthUser = Depends(require_admin)):
    """One hire with its history, payments (for staff who may see money) and the people's support requests."""
    detail = svc.admin_hire_detail(str(engagement_id), can_see_payments=_can(admin, "payments.view"),
                                   can_see_support=_can(admin, "support.view"))
    if not detail:
        raise HTTPException(status_code=404, detail="Hire not found")
    return _ok(detail)


@router.get("/engagements/{engagement_id}/candidates")
def assign_candidates(
    engagement_id: UUID,
    q: str | None = Query(None, max_length=100),
    area: str | None = Query(None, max_length=40),
    specialty: str | None = Query(None, max_length=40),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """Providers who can take this request now (listed and taking work), best fit first."""
    result = svc.assign_candidates(str(engagement_id), q=q, area=area, specialty=specialty, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Hire not found")
    return _ok(result)


@router.patch("/engagements/{engagement_id}")
def update_engagement(engagement_id: UUID, body: EngagementAdminUpdate, admin: AuthUser = Depends(require_admin)):
    try:
        hire = svc.admin_update_engagement(str(engagement_id), action=body.action, provider_id=body.provider_id,
                                           note=body.note, actor=admin.email)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"hire": hire, "actions": svc.staff_actions(hire)})


@router.post("/engagements/{engagement_id}/dispute")
def decide_dispute(engagement_id: UUID, body: DisputeDecision, admin: AuthUser = Depends(require_admin)):
    try:
        hire = svc.resolve_dispute(str(engagement_id), body.decision, note=body.note, actor=admin.email)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"hire": hire})


@router.get("/reviews")
def list_reviews(
    hidden: bool | None = None,
    max_rating: int | None = Query(None, ge=1, le=5),
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return _ok(svc.list_reviews_admin(hidden=hidden, max_rating=max_rating, q=q, limit=limit, offset=offset))


@router.post("/reviews/{review_id}/moderate")
def moderate(review_id: UUID, body: ReviewModeration, admin: AuthUser = Depends(require_admin)):
    try:
        return _ok(svc.moderate_review(str(review_id), hide=body.hidden, reason=body.reason, actor=admin.email))
    except MarketplaceError as exc:
        _raise(exc)


@router.get("/samples")
def sample_status():
    """Whether "Remove sample data" may run here, and why not."""
    return _ok(svc.sample_status())


@router.post("/samples/purge")
def purge_samples(admin: AuthUser = Depends(require_admin)):
    """Remove the demo providers, hires and reviews created by scripts/seed_providers.py. Never in production,
    and never when a sample provider has payments, earnings, payouts or a real client's hire."""
    try:
        return _ok(svc.purge_samples(actor=admin.email))
    except MarketplaceError as exc:
        _raise(exc)
