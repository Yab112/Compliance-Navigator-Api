"""Staff review of organizations and their service submissions."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from core.deps import require_admin
from schemas.auth_user import AuthUser
from schemas.organizations import OrgReview, SubmissionReview
from services import org_service
from services.org_service import OrgError

log = logging.getLogger(__name__)
ORG_STATUS = "^(pending|verified|suspended|rejected|draft|all)$"

router = APIRouter(prefix="/admin", tags=["Admin Organizations"], dependencies=[Depends(require_admin)])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: OrgError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/organizations/stats")
def stats():
    return _ok(org_service.admin_counts())


@router.get("/organizations")
def list_organizations(
    status_: str | None = Query("pending", alias="status", pattern=ORG_STATUS),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return _ok(org_service.list_orgs_admin(status_, q, limit, offset))


@router.get("/organizations/export.csv")
def export_organizations(status_: str | None = Query("all", alias="status", pattern=ORG_STATUS),
                         q: str | None = Query(None, max_length=200), admin: AuthUser = Depends(require_admin)):
    """The list with the same filters, for a spreadsheet. Holds representatives' contact details, so it is logged."""
    log.info("Organizations export by %s (status=%s, q=%s)", admin.email, status_, q)
    return Response(
        org_service.orgs_admin_csv(status_, q),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="organizations.csv"', "Cache-Control": "no-store"},
    )


@router.get("/organizations/{org_id}")
def get_organization(org_id: UUID):
    org = org_service.admin_org(str(org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _ok({"organization": org})


@router.post("/organizations/{org_id}/review")
def review_organization(org_id: UUID, body: OrgReview, admin: AuthUser = Depends(require_admin)):
    try:
        org = org_service.review_org(str(org_id), body.action, actor=admin.email, note=body.note,
                                     catalog_institution_id=body.catalog_institution_id)
    except OrgError as exc:
        _raise(exc)
    return _ok({"organization": org})


@router.get("/submissions")
def list_submissions(status_: str = Query("pending", alias="status", pattern="^(pending|scheduled|published|changes_requested|superseded|all)$"),
                     org_id: UUID | None = None, q: str | None = Query(None, max_length=200),
                     limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    oid = str(org_id) if org_id else None
    return _ok({"submissions": org_service.list_submissions(status_, limit, offset, org_id=oid, q=q),
                "total": org_service.count_submissions(status_, org_id=oid, q=q)})


@router.get("/submissions/{revision_id}")
def get_submission(revision_id: UUID):
    sub = org_service.submission_detail(str(revision_id))
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _ok({"submission": sub})


@router.post("/submissions/{revision_id}/review")
def review_submission(revision_id: UUID, body: SubmissionReview, admin: AuthUser = Depends(require_admin)):
    try:
        sub = org_service.review_submission(str(revision_id), body.action, actor=admin.email, note=body.note)
    except OrgError as exc:
        _raise(exc)
    return _ok({"submission": sub})


@router.get("/organizations-freshness")
def freshness():
    """Live services nobody has confirmed within the confirmation period, oldest first."""
    return _ok({"services": org_service.services_due_for_confirmation()})
