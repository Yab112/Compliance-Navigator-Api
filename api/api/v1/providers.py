"""Provider marketplace: public profiles, joining as a provider, hires and reviews."""

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError

from core.deps import get_current_user
from schemas.auth_user import AuthUser
from schemas.providers import (
    ClientAction,
    HireCreate,
    JobAction,
    JoinAgency,
    MembershipAction,
    ProviderJoin,
    ProviderProfile,
    ReviewCreate,
    ReviewReply,
    TeamInvite,
)
from services import id_verification, provider_service as svc
from services.provider_service import MarketplaceError
from services.storage_service import IMAGE_TYPES, delete_public_file, save_agent_file

router = APIRouter(tags=["Marketplace"])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: MarketplaceError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


async def _store(file: UploadFile | None, *, public: bool) -> str | None:
    if not file or not file.filename:
        return None
    try:
        return save_agent_file(await file.read(), file.filename, file.content_type, public=public)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------- public


@router.get("/providers")
def list_providers(
    type: str | None = Query(None, pattern="^(guday_geday|agency)$"),
    entity: str | None = Query(None, pattern="^(individual|company)$"),
    specialty: str | None = None,
    service_id: str | None = None,
    area: str | None = None,
    min_score: int | None = Query(None, ge=0, le=100),
    verified_only: bool = False,
    q: str | None = None,
    language: str | None = Query(None, max_length=20),
    max_fee: int | None = Query(None, ge=0),
    sort: str = Query("score", pattern="^(score|rating|reviews|newest)$"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return _ok(svc.public_list(
        provider_type=type, entity_type=entity, specialty=specialty, service_id=service_id,
        area=area, min_score=min_score, verified_only=verified_only, q=q, sort=sort,
        limit=limit, offset=offset, language=language, max_fee=max_fee,
    ))


@router.get("/providers/options")
def provider_options():
    """Allowed specialties and areas, for forms and filters."""
    return _ok({
        "types": svc.PROVIDER_TYPES, "entities": svc.ENTITY_TYPES,
        "specialties": svc.SPECIALTIES, "subCities": svc.SUB_CITIES, "regions": svc.REGIONS,
        "idVerificationRequired": id_verification.is_required(),
    })


# ---------------------------------------------------------------- my provider profile


@router.post("/providers/join", status_code=status.HTTP_201_CREATED)
async def join(
    data: str = Form(..., description="ProviderJoin as JSON"),
    photo: UploadFile | None = File(None),
    license_document: UploadFile | None = File(None),
    id_document: UploadFile | None = File(None),
    user: AuthUser = Depends(get_current_user),
):
    try:
        body = ProviderJoin(**json.loads(data))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    fields = body.model_dump()
    # Individuals and a company's representative both prove who they are with Fayda
    if id_verification.is_required():
        identity = id_verification.current(user.id)
        if not identity:
            raise HTTPException(status_code=400, detail="Verify your national ID with Fayda first")
        fields["national_id"] = identity["masked_id"]
        fields["national_id_verified"] = True
        fields["id_verification_method"] = identity["method"]
        fields["verified_name"] = identity["verified_name"]
    else:
        if not fields.get("national_id"):
            raise HTTPException(status_code=422, detail="national_id is required")
        if not id_document or not id_document.filename:
            raise HTTPException(status_code=400, detail="A copy of your national ID is required")
    if body.entity_type == "company" and not (license_document and license_document.filename):
        raise HTTPException(status_code=400, detail="Upload a copy of the company's trade licence")

    fields["photo_url"] = await _store(photo, public=True)
    fields["license_document_url"] = await _store(license_document, public=False)
    fields["id_document_url"] = await _store(id_document, public=False)
    try:
        provider = svc.join(fields, user_id=user.id, actor=user.email)
    except MarketplaceError as exc:
        _raise(exc)
    provider.pop("national_id", None)
    return _ok({"provider": provider})


@router.get("/providers/me")
def my_profile(user: AuthUser = Depends(get_current_user)):
    return _ok({"provider": svc.owner_view(user.id)})


@router.patch("/providers/me")
def update_my_profile(body: ProviderProfile, user: AuthUser = Depends(get_current_user)):
    try:
        svc.update_me(user.id, body.model_dump(exclude_unset=True), user.email)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"provider": svc.owner_view(user.id)})


@router.post("/providers/me/photo")
async def upload_photo(photo: UploadFile = File(...), user: AuthUser = Depends(get_current_user)):
    """Profile photo (individuals) or logo (companies). The previous file is deleted."""
    if photo.content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Upload a JPG, PNG or WEBP image")
    previous = (svc.get_for_user(user.id) or {}).get("photo_url")
    url = await _store(photo, public=True)
    try:
        svc.update_me(user.id, {"photo_url": url}, user.email)
    except MarketplaceError as exc:
        delete_public_file(url)
        _raise(exc)
    if previous != url:
        delete_public_file(previous)
    return _ok({"photo_url": url})


@router.delete("/providers/me/photo")
def remove_photo(user: AuthUser = Depends(get_current_user)):
    previous = (svc.get_for_user(user.id) or {}).get("photo_url")
    try:
        svc.update_me(user.id, {"photo_url": None}, user.email)
    except MarketplaceError as exc:
        _raise(exc)
    delete_public_file(previous)
    return _ok({"photo_url": None})


@router.post("/providers/me/license-document")
async def upload_license(document: UploadFile = File(...), user: AuthUser = Depends(get_current_user)):
    url = await _store(document, public=False)
    try:
        svc.update_me(user.id, {"license_document_url": url}, user.email)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"uploaded": True})


@router.get("/providers/me/jobs")
def my_jobs(
    status_: str | None = Query(None, alias="status"),
    group: str | None = Query(None, pattern="^(new|in_progress|completed|declined)$"),
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    user: AuthUser = Depends(get_current_user),
):
    me = svc.get_for_user(user.id)
    if not me:
        return _ok({"total": 0, "items": [], "counts": {g: 0 for g in svc.JOB_GROUPS}})
    result = svc.list_engagements(provider_id=me["id"], status=status_, statuses=svc.JOB_GROUPS.get(group),
                                  limit=limit, offset=offset)
    return _ok({**result, "items": [svc.provider_view(e) for e in result["items"]],
                "counts": svc.job_group_counts(me["id"])})


@router.get("/me/attention")
def my_attention(user: AuthUser = Depends(get_current_user)):
    """How many hires (as client) and jobs (as provider) wait on this person: the header badges."""
    return _ok(svc.attention(user.id))


@router.post("/providers/me/jobs/{engagement_id}")
def act_on_job(engagement_id: str, body: JobAction, user: AuthUser = Depends(get_current_user)):
    if body.action == "decline" and not body.reason:
        raise HTTPException(status_code=422, detail="Tell the client why you're declining")
    try:
        job = svc.provider_action(engagement_id, user_id=user.id, action=body.action, reason=body.reason,
                                  price=body.price, price_note=body.price_note, note=body.note)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"job": svc.provider_view(job)})


@router.get("/providers/me/reviews")
def my_reviews(limit: int = Query(10, ge=1, le=50), offset: int = Query(0, ge=0),
               user: AuthUser = Depends(get_current_user)):
    me = svc.get_for_user(user.id)
    if not me:
        return _ok({"total": 0, "items": []})
    return _ok(svc.list_reviews(me["id"], limit=limit, offset=offset))


@router.post("/providers/me/reviews/{review_id}/reply")
def reply(review_id: str, body: ReviewReply, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok({"review": svc.reply_to_review(review_id, user_id=user.id, reply=body.reply)})
    except MarketplaceError as exc:
        _raise(exc)


@router.post("/providers/me/team/invite", status_code=status.HTTP_201_CREATED)
def invite(body: TeamInvite, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok(svc.invite_member(user.id, body.member, body.role_title, user.email))
    except MarketplaceError as exc:
        _raise(exc)


@router.post("/providers/me/agency", status_code=status.HTTP_201_CREATED)
def join_agency(body: JoinAgency, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok(svc.request_to_join(user.id, body.agency, user.email))
    except MarketplaceError as exc:
        _raise(exc)


@router.post("/providers/me/memberships/{membership_id}")
def membership(membership_id: str, body: MembershipAction, user: AuthUser = Depends(get_current_user)):
    try:
        return _ok(svc.respond_membership(user.id, membership_id, body.action, user.email))
    except MarketplaceError as exc:
        _raise(exc)


# Registered after the /providers/me routes so "me" is never read as a slug
@router.get("/providers/{slug}")
def provider_profile(slug: str):
    provider = svc.public_profile(slug)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _ok({"provider": provider})


@router.get("/providers/{slug}/reviews")
def provider_reviews(
    slug: str,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    sort: str = Query("recent", pattern="^(recent|highest|lowest)$"),
):
    provider = svc.public_profile(slug)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return _ok(svc.list_reviews(provider["id"], limit=limit, offset=offset, sort=sort))


# ---------------------------------------------------------------- hires (client side)


@router.post("/hires", status_code=status.HTTP_201_CREATED)
def create_hire(body: HireCreate, user: AuthUser = Depends(get_current_user)):
    try:
        hire = svc.create_hire(body.model_dump(), user_id=user.id)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"hire": svc.client_view(hire)})


@router.get("/hires")
def my_hires(scope: str | None = Query(None, pattern="^(active|history)$"),
             limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
             user: AuthUser = Depends(get_current_user)):
    where = {"active": f"not {svc.CLIENT_HISTORY}", "history": svc.CLIENT_HISTORY}.get(scope or "")
    result = svc.list_engagements(client_user_id=user.id, where_sql=where, limit=limit, offset=offset)
    return _ok({**result, "items": [svc.client_view(e) for e in result["items"]],
                "counts": svc.client_scope_counts(user.id)})


def _client(engagement_id: str, action: str, user: AuthUser, reason: str | None = None):
    try:
        hire = svc.client_action(engagement_id, user_id=user.id, action=action, reason=reason)
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"hire": svc.client_view(hire)})


@router.post("/hires/{engagement_id}/cancel")
def cancel_hire(engagement_id: str, user: AuthUser = Depends(get_current_user)):
    return _client(engagement_id, "cancel", user)


@router.post("/hires/{engagement_id}/complete")
def confirm_hire(engagement_id: str, user: AuthUser = Depends(get_current_user)):
    return _client(engagement_id, "complete", user)


@router.post("/hires/{engagement_id}/dispute")
def dispute_hire(engagement_id: str, body: ClientAction, user: AuthUser = Depends(get_current_user)):
    return _client(engagement_id, "dispute", user, body.reason)


@router.post("/hires/{engagement_id}/review", status_code=status.HTTP_201_CREATED)
def review_hire(engagement_id: str, body: ReviewCreate, user: AuthUser = Depends(get_current_user)):
    try:
        hire = svc.leave_review(engagement_id, user_id=user.id, data=body.model_dump())
    except MarketplaceError as exc:
        _raise(exc)
    return _ok({"hire": svc.client_view(hire)})
