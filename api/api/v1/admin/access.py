"""Admin: staff, roles, permissions, approvals and the audit log (the Access pages)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from auth import staff_service
from auth.service import ClientInfo
from core.deps import client_info, require_admin
from schemas.staff_user import StaffActor
from services import access, approvals, staff_admin
from services.approvals import ApprovalError
from services.staff_admin import StaffAdminError

router = APIRouter(prefix="/admin/access", tags=["Admin Access"], dependencies=[Depends(require_admin)])


def _ok(payload):
    return {"message": "success", "payload": payload}


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (StaffAdminError, ApprovalError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


class RoleBody(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    description: str = Field("", max_length=300)
    permissions: list[str] = Field(default_factory=list, max_length=200)


class StaffCreate(BaseModel):
    email: EmailStr
    fullname: str = Field("", max_length=120)
    role_ids: list[str] = Field(..., min_length=1, max_length=20)


class StaffPatch(BaseModel):
    fullname: str = Field(..., max_length=120)


class StaffRoles(BaseModel):
    role_ids: list[str] = Field(..., max_length=20)


class Decision(BaseModel):
    note: str | None = Field(None, max_length=1000)


# ---------------------------------------------------------------- permissions and roles


@router.get("/permissions")
def permissions():
    return _ok({"areas": access.catalogue(), "risk_levels": list(access.RISK_LEVELS)})


@router.get("/roles")
def roles(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return _ok(staff_admin.list_roles(limit, offset))


@router.get("/roles/{role_id}")
def role(role_id: str):
    found = staff_admin.get_role(role_id)
    if not found:
        raise HTTPException(status_code=404, detail="Role not found")
    return _ok({"role": found})


@router.post("/roles", status_code=201)
def create_role(body: RoleBody, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok({"role": _call(staff_admin.create_role, actor, body.name, body.description, body.permissions, client)})


@router.put("/roles/{role_id}")
def update_role(role_id: str, body: RoleBody, actor: StaffActor = Depends(require_admin),
                client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.update_role, actor, role_id, body.name, body.description, body.permissions, client))


@router.delete("/roles/{role_id}")
def delete_role(role_id: str, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.delete_role, actor, role_id, client))


# ---------------------------------------------------------------- staff


@router.get("/staff")
def list_staff(q: str | None = Query(None, max_length=100), status: str | None = Query(None, pattern="^(invited|active|disabled)$"),
               role_id: str | None = None, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _ok(staff_admin.list_staff(q, status, role_id, limit, offset))


@router.get("/staff/{staff_id}")
def get_staff(staff_id: str, actor: StaffActor = Depends(require_admin)):
    found = staff_admin.get_staff(staff_id)
    if not found:
        raise HTTPException(status_code=404, detail="Staff member not found")
    # Their recent actions come from the audit log, which needs its own permission
    found["recent_actions"] = (staff_service.list_audit(actor=staff_id, limit=10)["items"]
                               if actor.can("audit.view") else None)
    return _ok({"staff": found})


@router.get("/staff/{staff_id}/sessions")
def staff_sessions(staff_id: str, limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0)):
    if not staff_service.get_staff(staff_id):
        raise HTTPException(status_code=404, detail="Staff member not found")
    return _ok(staff_service.list_sessions(staff_id, limit, offset))


@router.post("/staff", status_code=201)
def create_staff(body: StaffCreate, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.create_staff, actor, body.email, body.fullname, body.role_ids, client))


@router.patch("/staff/{staff_id}")
def patch_staff(staff_id: str, body: StaffPatch, actor: StaffActor = Depends(require_admin),
                client: ClientInfo = Depends(client_info)):
    return _ok({"staff": _call(staff_admin.update_profile, actor, staff_id, body.fullname, client)})


@router.put("/staff/{staff_id}/roles")
def set_roles(staff_id: str, body: StaffRoles, actor: StaffActor = Depends(require_admin),
              client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.set_roles, actor, staff_id, body.role_ids, client))


@router.post("/staff/{staff_id}/disable")
def disable(staff_id: str, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.disable, actor, staff_id, client))


@router.post("/staff/{staff_id}/enable")
def enable(staff_id: str, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.enable, actor, staff_id, client))


@router.post("/staff/{staff_id}/resend-invite")
def resend_invite(staff_id: str, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.send_link, actor, staff_id, "invite", client))


@router.post("/staff/{staff_id}/revoke-invite")
def revoke_invite(staff_id: str, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.revoke_invite, actor, staff_id, client))


@router.post("/staff/{staff_id}/reset-password")
def reset_password(staff_id: str, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.send_link, actor, staff_id, "reset", client))


@router.post("/staff/{staff_id}/sign-out")
def sign_out(staff_id: str, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok(_call(staff_admin.sign_out, actor, staff_id, client))


# ---------------------------------------------------------------- approvals


@router.get("/approvals")
def list_approvals(box: str = Query("waiting", pattern="^(waiting|mine|all)$"),
                   status: str | None = Query(None, pattern="^(pending|approved|rejected|cancelled|expired|executed|failed)$"),
                   limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                   actor: StaffActor = Depends(require_admin)):
    return _ok(approvals.list_requests(actor, box, status, limit, offset))


@router.get("/approvals/{request_id}")
def get_approval(request_id: str, actor: StaffActor = Depends(require_admin)):
    req = approvals.get(request_id)
    if not req or not approvals.can_view(req, actor):
        raise HTTPException(status_code=404, detail="Request not found")
    return _ok({"approval": req})


@router.post("/approvals/{request_id}/approve")
def approve(request_id: str, body: Decision, actor: StaffActor = Depends(require_admin),
            client: ClientInfo = Depends(client_info)):
    return _ok({"approval": _call(approvals.approve, request_id, actor, body.note, client)})


@router.post("/approvals/{request_id}/reject")
def reject(request_id: str, body: Decision, actor: StaffActor = Depends(require_admin),
           client: ClientInfo = Depends(client_info)):
    return _ok({"approval": _call(approvals.reject, request_id, actor, body.note, client)})


@router.post("/approvals/{request_id}/cancel")
def cancel(request_id: str, actor: StaffActor = Depends(require_admin), client: ClientInfo = Depends(client_info)):
    return _ok({"approval": _call(approvals.cancel, request_id, actor, client)})


# ---------------------------------------------------------------- audit


@router.get("/audit")
def audit_log(actor_q: str | None = Query(None, alias="actor", max_length=100),
              action: str | None = Query(None, max_length=60), target: str | None = Query(None, max_length=100),
              since: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
              until: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
              limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _ok(staff_service.list_audit(actor=actor_q, action=action, target=target, since=since, until=until,
                                        limit=limit, offset=offset))
