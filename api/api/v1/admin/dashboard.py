"""Admin dashboard API, every route requires role=admin."""

from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth import service as auth_service
from core.deps import require_admin
from schemas.auth_user import AuthUser
from services import (
    ai_admin,
    catalog_service,
    custom_sources,
    data_sources,
    feedback_service,
    graph_admin,
    org_service,
    provider_service,
    user_store,
)
from services.db import fetch_all, fetch_one
from services.storage_service import read_admin_file, safe_file_headers

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"], dependencies=[Depends(require_admin)])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: Exception):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _safe(fn, fallback=None):
    """Overview tiles degrade independently when a backing store is down."""
    try:
        return fn()
    except Exception as exc:
        return fallback if fallback is not None else {"error": str(exc)}


# ---------------------------------------------------------------- overview


@router.get("/overview")
def overview():
    users = fetch_one(
        """
        select count(*) as total,
               count(*) filter (where created_at > now() - interval '30 days') as new_30d,
               (select count(*) from staff_users where status = 'active') as admins,
               count(*) filter (where role = 'agent') as agents
        from users
        """
    )
    roadmaps = fetch_one(
        """
        select count(*) as total,
               count(*) filter (where created_at > now() - interval '30 days') as last_30d,
               count(distinct user_id) as users
        from roadmaps
        """
    )
    roadmaps_by_day = fetch_all(
        """
        select d::date as day, count(r.id) as count
        from generate_series(current_date - 29, current_date, interval '1 day') d
        left join roadmaps r on r.created_at::date = d::date
        group by d order by d
        """
    )
    roadmaps_by_goal = fetch_all(
        "select goal, count(*) as count from roadmaps group by goal order by count desc"
    )
    cases_by_day = fetch_all(
        """
        select d::date as day, count(c.id) as count
        from generate_series(current_date - 29, current_date, interval '1 day') d
        left join engagements c on c.created_at::date = d::date
        group by d order by d
        """
    )
    flags = fetch_one("select count(*) filter (where status = 'open') as open from feedback_flags")
    return _ok({
        "users": users,
        "roadmaps": roadmaps,
        "roadmapsByDay": roadmaps_by_day,
        "roadmapsByGoal": roadmaps_by_goal,
        "casesByDay": cases_by_day,
        "guday": provider_service.marketplace_stats(),
        "catalog": catalog_service.catalog_stats(),
        "graph": _safe(graph_admin.graph_counts),
        "ai": _safe(ai_admin.status),
        "openFlags": flags["open"],
        "dataSources": _safe(data_sources.list_sources, fallback=[]),
        "organizations": _safe(org_service.admin_counts),
    })


# ---------------------------------------------------------------- data sources


@router.get("/data-sources")
def list_data_sources():
    return _ok({"sources": data_sources.list_sources()})


@router.get("/data-sources/runs")
def list_data_source_runs(
    source: str | None = None,
    status: str | None = Query(None, pattern="^(success|failed|running)$"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="The “from” date must be on or before the “to” date")
    return _ok(data_sources.page_runs(source, status, limit, offset, date_from, date_to))


@router.post("/data-sources/runs/{run_id}/mark-failed")
def mark_data_source_run_failed(run_id: UUID, admin: AuthUser = Depends(require_admin)):
    try:
        run = data_sources.mark_run_failed(str(run_id), admin.email)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found") from None
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _ok({"run": run})


@router.post("/data-sources/{source}/run", status_code=status.HTTP_202_ACCEPTED)
def run_data_source(source: str, background: BackgroundTasks, admin: AuthUser = Depends(require_admin)):
    try:
        run = data_sources.start_run(source, admin.email)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown data source") from None
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background.add_task(data_sources.execute_run, run["id"], source)
    return _ok({"run": run})


@router.post("/data-sources/{source}/pause")
def pause_data_source(source: str, admin: AuthUser = Depends(require_admin)):
    try:
        data_sources.set_paused(source, True, admin.email)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown data source") from None
    return _ok({"source": source, "enabled": False})


@router.post("/data-sources/{source}/resume")
def resume_data_source(source: str, admin: AuthUser = Depends(require_admin)):
    try:
        data_sources.set_paused(source, False, admin.email)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown data source") from None
    return _ok({"source": source, "enabled": True})


class CustomSourceBody(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: str = Field("", max_length=1000)
    kind: Literal["web_page", "pasted_text"]
    url: str | None = Field(None, max_length=2000)
    text: str | None = Field(None, max_length=custom_sources.MAX_TEXT_CHARS)
    issuing_body: str | None = Field(None, max_length=200)
    language: Literal["en", "am"] = "en"
    tags: list[str] = Field(default_factory=list, max_length=10)
    schedule: Literal["manual", "daily", "weekly"] = "manual"
    enabled: bool = True


def _custom_or_422(fn):
    try:
        return fn()
    except ValueError as exc:  # includes UnsafeURL
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/data-sources/custom/{source_id}")
def get_custom_source(source_id: UUID):
    source = custom_sources.get_custom(str(source_id), with_text=True)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    source["text"] = source.pop("body")
    return _ok({"source": source})


@router.post("/data-sources/custom", status_code=status.HTTP_201_CREATED)
def create_custom_source(body: CustomSourceBody, admin: AuthUser = Depends(require_admin)):
    source = _custom_or_422(lambda: custom_sources.create_custom(body.model_dump(), admin.email))
    return _ok({"source": source, "key": custom_sources.source_key(source["id"])})


@router.put("/data-sources/custom/{source_id}")
def update_custom_source(source_id: UUID, body: CustomSourceBody, admin: AuthUser = Depends(require_admin)):
    source = _custom_or_422(lambda: custom_sources.update_custom(str(source_id), body.model_dump(), admin.email))
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return _ok({"source": source})


@router.delete("/data-sources/custom/{source_id}")
def delete_custom_source(source_id: UUID):
    deleted = custom_sources.delete_custom(str(source_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Data source not found")
    return _ok({"deleted": deleted})


# Knowledge graph routes live in api/v1/admin/graph.py


@router.get("/files")
def admin_private_file(key: str):
    """ID documents uploaded during agent registration (never public)."""
    found = read_admin_file(key)  # local private/ files or private S3 objects, never vetting files
    if not found:
        raise HTTPException(status_code=404, detail="File not found")
    content, media_type, filename = found
    return Response(content, media_type=media_type, headers=safe_file_headers(media_type, filename=filename))


# ---------------------------------------------------------------- users


@router.get("/users")
def admin_list_users(
    q: str | None = None,
    role: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = user_store.list_users(q=q, role=role, limit=limit, offset=offset)
    sessions = auth_service.count_active_sessions([u["id"] for u in result["items"]])
    for u in result["items"]:
        u["active_sessions"] = sessions.get(u["id"], 0)
    return _ok(result)


class UserPatch(BaseModel):
    # Staff access is managed separately (Access pages); public accounts are customers or providers
    role: str | None = Field(None, pattern="^(user|agent)$")
    is_active: bool | None = None


@router.patch("/users/{user_id}")
def admin_patch_user(user_id: UUID, body: UserPatch, admin: AuthUser = Depends(require_admin)):
    user_id = str(user_id)
    user = user_store.update_user(user_id, role=body.role, is_active=body.is_active)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.is_active is False:
        auth_service.revoke_all_sessions(user_id, "deactivated")
    if body.role is not None or body.is_active is not None:
        auth_service.record_event(
            "admin_updated_user", user_id=user_id, detail=f"by {admin.email}: role={body.role} active={body.is_active}"
        )
    return _ok({"user": user})


@router.post("/users/{user_id}/revoke-sessions")
def admin_revoke_sessions(user_id: UUID, admin: AuthUser = Depends(require_admin)):
    if str(user_id) == admin.id:
        raise HTTPException(status_code=400, detail="Use “Sign out everywhere” on your own account page")
    count = auth_service.revoke_all_sessions(str(user_id), "revoked_by_admin")
    auth_service.record_event("sessions_revoked_by_admin", user_id=str(user_id), detail=f"by {admin.email}")
    return _ok({"signedOut": count})


@router.post("/users/{user_id}/reset-link")
def admin_reset_link(user_id: UUID, background: BackgroundTasks, admin: AuthUser = Depends(require_admin)):
    """
    A one-hour password reset link. In production it goes only to the user's own email, so no staff member
    can use it to take over the account; in development it is shown so it can be handed over.
    """
    user = user_store.get_user(str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    link = auth_service.create_reset_link(user, created_by=admin.email)
    auth_service.record_event("reset_link_issued", user_id=user["id"], detail=f"by {admin.email}")
    if auth_service.settings.is_production:
        background.add_task(auth_service.send_email, auth_service.Email(
            to=user["email"],
            subject="Reset your Compliance Navigator password",
            text=(f"Hello {user['fullname'] or ''},\n\nOur support team sent you a link to choose a new password. "
                  f"Use it within {auth_service.RESET_TTL_MINUTES} minutes:\n{link}\n\n"
                  "If you didn't ask our team for this, reply to this email so we can check your account.\n"),
        ))
        return _ok({"link": None, "emailed": True, "expiresInMinutes": auth_service.RESET_TTL_MINUTES})
    return _ok({"link": link, "emailed": False, "expiresInMinutes": auth_service.RESET_TTL_MINUTES})


@router.get("/auth/events")
def admin_auth_events(
    user_id: UUID | None = None,
    limit: int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    uid = str(user_id) if user_id else None
    return _ok({"events": auth_service.list_events(uid, limit, offset), "total": auth_service.count_events(uid)})


@router.get("/auth/summary")
def admin_auth_summary():
    return _ok(fetch_one(
        """
        select
          (select count(distinct user_id) from auth_sessions where revoked_at is null and expires_at > now()) as signed_in_users,
          (select count(*) from auth_sessions where revoked_at is null and expires_at > now()) as active_sessions,
          (select count(*) from auth_events where event = 'login_failed' and created_at > now() - interval '24 hours') as failed_logins_24h,
          (select count(*) from auth_events where event = 'login_blocked' and created_at > now() - interval '24 hours') as blocked_24h,
          (select count(*) from auth_events where event = 'refresh_reuse' and created_at > now() - interval '7 days') as token_reuse_7d,
          (select count(*) from auth_events where event = 'register' and created_at > now() - interval '7 days') as registrations_7d
        """
    ))


# ---------------------------------------------------------------- AI


@router.get("/ai/status")
def ai_status():
    return _ok(ai_admin.status())


class AISettings(BaseModel):
    provider: str = Field(..., pattern="^(ollama|anthropic|keyword)$")
    ollama_model: str | None = None


@router.put("/ai/settings")
def ai_settings(body: AISettings, admin: AuthUser = Depends(require_admin)):
    return _ok(ai_admin.save_settings(body.provider, body.ollama_model, admin.email))


class AITest(BaseModel):
    message: str = Field(..., min_length=2, max_length=1000)


@router.post("/ai/test")
def ai_test(body: AITest):
    return _ok(ai_admin.test_prompt(body.message))


class KnowledgeSearch(BaseModel):
    query: str = Field(..., min_length=3)
    limit: int = Field(5, ge=1, le=20)


@router.post("/ai/search")
def ai_knowledge_search(body: KnowledgeSearch):
    from services.rag_service import search_legal_chunks

    return _ok({"results": search_legal_chunks(body.query, limit=body.limit, threshold=0.3)})


# ---------------------------------------------------------------- feedback


@router.get("/feedback")
def admin_list_feedback(status_: str | None = Query(None, alias="status",
                                                    pattern="^(open|org_responded|resolved|dismissed|all)$"),
                        target_type: str | None = Query(None, pattern="^(document|gov_service|office|agent|roadmap_step|org_service|other)$"),
                        org_id: UUID | None = None, q: str | None = Query(None, max_length=200),
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    filters = {"target_type": target_type, "org_id": str(org_id) if org_id else None, "q": q}
    return _ok({"flags": feedback_service.list_flags(status_, limit, offset, **filters),
                "total": feedback_service.count_flags(status_, **filters)})


class FlagResolve(BaseModel):
    status: str = Field(..., pattern="^(resolved|dismissed|open)$")
    note: str | None = Field(None, max_length=500)


@router.patch("/feedback/{flag_id}")
def admin_resolve_feedback(flag_id: UUID, body: FlagResolve, admin: AuthUser = Depends(require_admin)):
    try:
        flag = feedback_service.resolve_flag(str(flag_id), body.status, body.note, admin.email)
    except feedback_service.FeedbackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    return _ok({"flag": flag})
