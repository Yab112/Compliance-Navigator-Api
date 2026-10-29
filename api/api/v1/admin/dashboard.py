"""Admin dashboard API, every route requires role=admin."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth import service as auth_service
from core.deps import require_admin
from schemas.auth_user import AuthUser
from services import (
    ai_admin,
    catalog_service,
    data_sources,
    feedback_service,
    graph_admin,
    provider_service,
    org_service,
    user_store,
)
from services.db import fetch_all, fetch_one
from services.storage_service import private_file_path

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
               count(*) filter (where role = 'admin') as admins,
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
def list_data_source_runs(source: str | None = None, limit: int = Query(50, ge=1, le=200)):
    return _ok({"runs": data_sources.list_runs(source, limit)})


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


# ---------------------------------------------------------------- knowledge graph


@router.get("/graph/stats")
def graph_stats():
    return _ok(graph_admin.graph_counts())


@router.get("/graph/view")
def graph_view():
    return _ok(graph_admin.compliance_graph_view())


@router.get("/graph/documents")
def graph_documents():
    return _ok({"documents": graph_admin.list_documents()})


class DocumentPatch(BaseModel):
    name: str | None = None
    name_am: str | None = None
    issuing_authority: str | None = None
    form_code: str | None = None
    fee_etb: int | None = Field(None, ge=0)
    avg_processing_days: int | None = Field(None, ge=0)
    legal_basis: str | None = None
    source_url: str | None = None
    required_input_labels: list[str] | None = None
    rejection_reasons: list[str] | None = None
    mark_verified: bool = False


@router.patch("/graph/documents/{doc_id}")
def patch_document(doc_id: str, body: DocumentPatch):
    changes = body.model_dump(exclude_unset=True, exclude={"mark_verified"})
    doc = graph_admin.update_document(doc_id, changes, mark_verified=body.mark_verified)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _ok({"document": doc})


@router.get("/graph/institutions")
def graph_institutions():
    return _ok({"institutions": graph_admin.institution_breakdown()})


class CypherQuery(BaseModel):
    query: str = Field(..., min_length=6, max_length=4000)


@router.post("/graph/query")
def graph_query(body: CypherQuery):
    try:
        rows = graph_admin.run_cypher_readonly(body.query)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Query failed (read-only console): {exc}") from exc
    return _ok({"rows": rows, "count": len(rows)})


@router.get("/files")
def admin_private_file(key: str):
    """ID documents uploaded during agent registration (never public)."""
    path = private_file_path(key)
    if not path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)


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
    role: str | None = Field(None, pattern="^(user|agent|admin)$")
    is_active: bool | None = None


@router.patch("/users/{user_id}")
def admin_patch_user(user_id: str, body: UserPatch, admin: AuthUser = Depends(require_admin)):
    if user_id == admin.id and (body.role not in (None, "admin") or body.is_active is False):
        raise HTTPException(status_code=400, detail="You can't remove your own admin access")
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
def admin_reset_link(user_id: UUID, admin: AuthUser = Depends(require_admin)):
    """A one-hour password reset link the admin can hand to the user (no email needed)."""
    user = user_store.get_user(str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    link = auth_service.create_reset_link(user, created_by=admin.email)
    auth_service.record_event("reset_link_issued", user_id=user["id"], detail=f"by {admin.email}")
    return _ok({"link": link, "expiresInMinutes": auth_service.RESET_TTL_MINUTES})


@router.get("/auth/events")
def admin_auth_events(user_id: UUID | None = None, limit: int = Query(100, ge=1, le=500)):
    return _ok({"events": auth_service.list_events(str(user_id) if user_id else None, limit)})


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
def admin_list_feedback(status_: str | None = Query(None, alias="status"),
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return _ok({"flags": feedback_service.list_flags(status_, limit, offset),
                "total": feedback_service.count_flags(status_)})


class FlagResolve(BaseModel):
    status: str = Field(..., pattern="^(resolved|dismissed|open)$")
    note: str | None = Field(None, max_length=500)


@router.patch("/feedback/{flag_id}")
def admin_resolve_feedback(flag_id: str, body: FlagResolve, admin: AuthUser = Depends(require_admin)):
    flag = feedback_service.resolve_flag(flag_id, body.status, body.note, admin.email)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    return _ok({"flag": flag})
