"""Organizations: public directory and service pages, plus the organization's own workspace.

Public reads live under /organizations; everything an organization member edits lives
under /org/{org_id}, so membership is checked in one place per request.
"""

import json
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from core.deps import get_current_user
from schemas.auth_user import AuthUser
from schemas.organizations import (
    BranchIn,
    EligibilityIn,
    MemberInvite,
    OrgRegistration,
    OrgUpdate,
    RegistrationSubmit,
    ReportResponse,
    ServiceIn,
    ServiceSubmit,
)
from services import org_import, org_service
from services.org_service import OrgError
from services.storage_service import save_agent_file

router = APIRouter(tags=["Organizations"])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: OrgError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


async def _store(file: UploadFile, *, public: bool, pdf_only: bool = False, images_only: bool = False) -> str:
    if pdf_only and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Upload a PDF file")
    if images_only and not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload a JPG, PNG or WEBP image")
    try:
        return save_agent_file(await file.read(), file.filename or "upload", file.content_type, public=public)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _member(org_id: UUID, user: AuthUser, *, owner: bool = False) -> str:
    try:
        return org_service.require_member(str(org_id), user.id, owner=owner, is_admin=user.is_admin)
    except OrgError as exc:
        _raise(exc)


# ---------------------------------------------------------------- public


@router.get("/organizations")
def directory(
    type_: str | None = Query(None, alias="type"),
    sector: str | None = None,
    region: str | None = None,
    q: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return _ok(org_service.public_orgs(org_type=type_, sector=sector, region=region, q=q, limit=limit, offset=offset))


@router.get("/organizations/mine")
def my_organizations(user: AuthUser = Depends(get_current_user)):
    return _ok({"organizations": org_service.my_orgs(user.id, user.email)})


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def register(
    data: str = Form(..., description="OrgRegistration as JSON"),
    authorization_letter: UploadFile | None = File(None),
    logo: UploadFile | None = File(None),
    user: AuthUser = Depends(get_current_user),
):
    try:
        body = OrgRegistration(**json.loads(data))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    fields = body.model_dump()
    fields["branches"] = [b for b in fields["branches"]]
    try:
        org = org_service.register_org(fields, user_id=user.id, user_email=user.email)
    except OrgError as exc:
        _raise(exc)
    if authorization_letter and authorization_letter.filename:
        key = await _store(authorization_letter, public=False)
        org = org_service.set_org_file(org["id"], "authorization_letter_key", key, user.email)
    if logo and logo.filename:
        url = await _store(logo, public=True, images_only=True)
        org = org_service.set_org_file(org["id"], "logo_url", url, user.email)
    return _ok({"organization": org})


@router.get("/organizations/import-template.csv", response_class=PlainTextResponse)
def import_template():
    """Spreadsheet template for adding many services at once (opens in Excel)."""
    return PlainTextResponse(
        org_import.template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="services-template.csv"'},
    )


@router.get("/organizations/requirement-options")
def requirement_options(q: str | None = None, user: AuthUser = Depends(get_current_user)):
    return _ok(org_service.requirement_options(q))


@router.post("/organizations/services/{service_id}/eligibility")
def eligibility(service_id: UUID, body: EligibilityIn):
    try:
        return _ok(org_service.check_eligibility(str(service_id), body.answers))
    except OrgError as exc:
        _raise(exc)


@router.get("/organizations/services/{service_id}/path")
def path(service_id: UUID):
    try:
        result = org_service.service_path(str(service_id))
    except OrgError as exc:
        _raise(exc)
    org_service.record_stat(str(service_id), "path_view")
    return _ok(result)


@router.get("/organizations/{slug}")
def public_profile(slug: str):
    org = org_service.public_org(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _ok({"organization": org})


@router.get("/organizations/{slug}/services/{service_slug}")
def public_service(slug: str, service_slug: str):
    service = org_service.public_service(slug, service_slug)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return _ok({"service": service})


# ---------------------------------------------------------------- organization workspace


@router.get("/org/{org_id}")
def workspace(org_id: UUID, user: AuthUser = Depends(get_current_user)):
    role = _member(org_id, user)
    org = org_service.member_org(str(org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _ok({"organization": {**org, "my_role": role}, "services": org_service.list_org_services(str(org_id))})


@router.patch("/org/{org_id}")
def update_organization(org_id: UUID, body: OrgUpdate, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    try:
        return _ok({"organization": org_service.update_org(str(org_id), body.model_dump(exclude_unset=True), user.email)})
    except OrgError as exc:
        _raise(exc)


@router.post("/org/{org_id}/logo")
async def upload_logo(org_id: UUID, logo: UploadFile = File(...), user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    url = await _store(logo, public=True, images_only=True)
    return _ok({"organization": org_service.set_org_file(str(org_id), "logo_url", url, user.email)})


@router.post("/org/{org_id}/authorization-letter")
async def upload_letter(org_id: UUID, letter: UploadFile = File(...), user: AuthUser = Depends(get_current_user)):
    _member(org_id, user, owner=True)
    key = await _store(letter, public=False)
    return _ok({"organization": org_service.set_org_file(str(org_id), "authorization_letter_key", key, user.email)})


@router.post("/org/{org_id}/forms")
async def upload_form(org_id: UUID, form: UploadFile = File(...), user: AuthUser = Depends(get_current_user)):
    """Application forms are public PDFs; the returned URL goes into a service's forms list."""
    _member(org_id, user)
    return _ok({"url": await _store(form, public=True, pdf_only=True), "title": form.filename})


@router.post("/org/{org_id}/members")
def invite(org_id: UUID, body: MemberInvite, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user, owner=True)
    try:
        return _ok({"organization": org_service.invite_member(str(org_id), body.email, body.role, user.email)})
    except OrgError as exc:
        _raise(exc)


@router.delete("/org/{org_id}/members/{member_id}")
def remove(org_id: UUID, member_id: UUID, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user, owner=True)
    try:
        return _ok({"organization": org_service.remove_member(str(org_id), str(member_id), user.id, user.email)})
    except OrgError as exc:
        _raise(exc)


@router.post("/org/{org_id}/branches")
def add_branch(org_id: UUID, body: BranchIn, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    return _ok({"branches": org_service.add_branch(str(org_id), body.model_dump())})


@router.put("/org/{org_id}/branches/{branch_id}")
def edit_branch(org_id: UUID, branch_id: UUID, body: BranchIn, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    try:
        return _ok({"branches": org_service.update_branch(str(org_id), str(branch_id), body.model_dump())})
    except OrgError as exc:
        _raise(exc)


@router.delete("/org/{org_id}/branches/{branch_id}")
def remove_branch(org_id: UUID, branch_id: UUID, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    return _ok({"branches": org_service.delete_branch(str(org_id), str(branch_id))})


@router.post("/org/{org_id}/services", status_code=status.HTTP_201_CREATED)
def create_service(org_id: UUID, body: ServiceIn, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    try:
        return _ok({"service": org_service.save_service(str(org_id), None, body.model_dump(), user.email)})
    except OrgError as exc:
        _raise(exc)


@router.get("/org/{org_id}/services/{service_id}")
def get_service(org_id: UUID, service_id: UUID, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    service = org_service.working_copy(str(service_id), str(org_id))
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return _ok({"service": service})


@router.put("/org/{org_id}/services/{service_id}")
def update_service(org_id: UUID, service_id: UUID, body: ServiceIn, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    try:
        return _ok({"service": org_service.save_service(str(org_id), str(service_id), body.model_dump(), user.email)})
    except OrgError as exc:
        _raise(exc)


@router.post("/org/{org_id}/services/{service_id}/submit")
def submit(org_id: UUID, service_id: UUID, body: ServiceSubmit | None = Body(None),
           user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    change = body.model_dump() if body else {}
    try:
        return _ok({"service": org_service.submit_service(str(org_id), str(service_id), user.email, change)})
    except OrgError as exc:
        _raise(exc)


@router.post("/org/{org_id}/services/import")
async def import_services(
    org_id: UUID,
    file: UploadFile = File(...),
    dry_run: bool = Form(True),
    user: AuthUser = Depends(get_current_user),
):
    """Check a CSV of services row by row; with dry_run=false, save the valid rows as drafts."""
    _member(org_id, user)
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="The file is larger than 2 MB")
    try:
        return _ok(org_import.import_services(str(org_id), raw, actor=user.email, dry_run=dry_run))
    except OrgError as exc:
        _raise(exc)


@router.post("/org/{org_id}/services/confirm-all")
def confirm_all(org_id: UUID, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    return _ok({"confirmed": org_service.confirm_services(str(org_id), None, user.email)})


@router.post("/org/{org_id}/services/{service_id}/confirm")
def confirm_one(org_id: UUID, service_id: UUID, user: AuthUser = Depends(get_current_user)):
    """'Still accurate': the organization checked the live service and nothing changed."""
    _member(org_id, user)
    count = org_service.confirm_services(str(org_id), [str(service_id)], user.email)
    if not count:
        raise HTTPException(status_code=404, detail="Only live services can be confirmed")
    return _ok({"confirmed": count})


@router.get("/org/{org_id}/registration-check")
def registration_check(org_id: UUID, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    try:
        problems = org_service.registration_problems(str(org_id))
    except OrgError as exc:
        _raise(exc)
    return _ok({"problems": problems, "services": org_service.list_org_services(str(org_id))})


@router.post("/org/{org_id}/submit-registration")
def submit_registration(org_id: UUID, body: RegistrationSubmit, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user, owner=True)
    try:
        return _ok(org_service.submit_registration(str(org_id), submit_services=body.submit_services, actor=user.email))
    except OrgError as exc:
        _raise(exc)


@router.get("/org/{org_id}/reports")
def reports(org_id: UUID, status_: str | None = Query(None, alias="status", pattern="^(open|resolved|dismissed)$"),
            user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    return _ok({"reports": org_service.org_reports(str(org_id), status_)})


@router.post("/org/{org_id}/reports/{flag_id}")
def respond_report(org_id: UUID, flag_id: UUID, body: ReportResponse, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    try:
        return _ok({"report": org_service.respond_report(str(org_id), str(flag_id), status=body.status,
                                                         response=body.response, actor=user.email)})
    except OrgError as exc:
        _raise(exc)


@router.post("/org/{org_id}/services/{service_id}/archive")
def archive(org_id: UUID, service_id: UUID, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    try:
        return _ok({"service": org_service.archive_service(str(org_id), str(service_id), user.email)})
    except OrgError as exc:
        _raise(exc)


@router.get("/org/{org_id}/analytics")
def analytics(org_id: UUID, user: AuthUser = Depends(get_current_user)):
    _member(org_id, user)
    return _ok(org_service.org_analytics(str(org_id)))
