"""
Staff sign-in and "my account" for the admin app. A separate realm from /auth: its own accounts,
sessions, refresh cookie (cn_staff_refresh, scoped to /api/v1/staff/auth) and token issuer.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from auth import staff_service as svc
from auth.service import AuthError, ClientInfo
from config.config import settings
from core import ratelimit
from core.deps import client_info, get_current_staff
from schemas.staff_user import StaffActor
from services import approvals

router = APIRouter(prefix="/staff", tags=["Staff auth"])

REFRESH_COOKIE = "cn_staff_refresh"
COOKIE_PATH = "/api/v1/staff/auth"


class StaffLogin(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=200)


class SetPassword(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)
    new_password: str = Field(..., max_length=200)


class ChangePassword(BaseModel):
    current_password: str = Field(..., max_length=200)
    new_password: str = Field(..., max_length=200)


class ForgotPassword(BaseModel):
    email: EmailStr


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: AuthError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(REFRESH_COOKIE, token, max_age=svc.SESSION_TTL_HOURS * 3600, httponly=True,
                        secure=settings.auth_cookie_secure, samesite=settings.auth_cookie_samesite, path=COOKIE_PATH)


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, secure=settings.auth_cookie_secure,
                           samesite=settings.auth_cookie_samesite, httponly=True)


def _session_response(response: Response, session: svc.StaffSession) -> dict:
    if session.refresh_token:
        _set_cookie(response, session.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return _ok({"user": session.staff, "accessToken": session.access_token, "expiresIn": session.expires_in})


@router.post("/auth/login")
def login(body: StaffLogin, response: Response, client: ClientInfo = Depends(client_info)):
    try:
        session = svc.login(body.email, body.password, client)
    except AuthError as exc:
        _raise(exc)
    return _session_response(response, session)


@router.post("/auth/refresh")
def refresh(request: Request, response: Response, client: ClientInfo = Depends(client_info)):
    try:
        session = svc.refresh(request.cookies.get(REFRESH_COOKIE), client)
    except AuthError as exc:
        _clear_cookie(response)
        response.status_code = exc.status_code
        return {"detail": str(exc)}
    return _session_response(response, session)


@router.post("/auth/logout")
def logout(request: Request, response: Response, client: ClientInfo = Depends(client_info)):
    session_id = None
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        staff = svc.resolve_access_token(header[7:])
        session_id = staff.session_id if staff else None
    svc.logout(request.cookies.get(REFRESH_COOKIE), session_id, client)
    _clear_cookie(response)
    return _ok(None)


@router.post("/auth/logout-all")
def logout_all(response: Response, staff: StaffActor = Depends(get_current_staff),
               client: ClientInfo = Depends(client_info)):
    count = svc.revoke_all_sessions(staff.id, "logout_all")
    svc.audit("auth.logout_all", actor=staff, client=client, details={"sessions": count})
    _clear_cookie(response)
    return _ok({"signedOut": count})


@router.post("/auth/forgot-password", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(ratelimit.limit("forgot_password"))])
def forgot_password(body: ForgotPassword, background: BackgroundTasks, client: ClientInfo = Depends(client_info)):
    """Always answers the same, and as fast, so it can't reveal who is on staff."""
    staff = svc.get_staff_by_email(body.email)
    svc.audit("auth.password_reset_requested", actor=staff, actor_email=body.email, client=client)
    # A few links an hour per person; more are quietly not sent, so nobody can keep cancelling someone's link
    if staff and staff["status"] == "active" and not ratelimit.hit("forgot_password_email", f"staff:{staff['id']}"):
        background.add_task(svc.send_reset, staff, svc.issue_link(staff, "reset", "self"))
    return _ok({"message": "If that email belongs to an active staff account, a reset link has been sent."})


@router.get("/auth/link")
def check_link(token: str = Query(..., max_length=200), kind: str = Query("invite", pattern="^(invite|reset)$")):
    """Who an invitation or reset link is for, so the page can show the sign-in email."""
    row = svc.check_link(token, kind)
    if not row:
        raise HTTPException(status_code=400, detail="This link is invalid, already used or has expired.")
    return _ok({"email": row["email"], "fullname": row["fullname"]})


@router.post("/auth/accept-invite")
def accept_invite(body: SetPassword, client: ClientInfo = Depends(client_info)):
    try:
        staff = svc.use_link(body.token, "invite", body.new_password, client)
    except AuthError as exc:
        _raise(exc)
    return _ok({"email": staff["email"]})


@router.post("/auth/reset-password")
def reset_password(body: SetPassword, client: ClientInfo = Depends(client_info)):
    try:
        staff = svc.use_link(body.token, "reset", body.new_password, client)
    except AuthError as exc:
        _raise(exc)
    return _ok({"email": staff["email"]})


# ---------------------------------------------------------------- my account


@router.get("/me")
def me(staff: StaffActor = Depends(get_current_staff)):
    return _ok({**svc.me(staff.id), "approvalsWaiting": approvals.waiting_count(staff)})


@router.post("/me/change-password")
def change_password(body: ChangePassword, staff: StaffActor = Depends(get_current_staff),
                    client: ClientInfo = Depends(client_info)):
    try:
        signed_out = svc.change_password(staff.id, body.current_password, body.new_password, staff.session_id, client)
    except AuthError as exc:
        _raise(exc)
    return _ok({"otherSessionsSignedOut": signed_out})


@router.get("/me/sessions")
def my_sessions(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0),
                staff: StaffActor = Depends(get_current_staff)):
    page = svc.list_sessions(staff.id, limit, offset)
    for s in page["items"]:
        s["current"] = s["id"] == staff.session_id
    return _ok(page)


@router.delete("/me/sessions/{session_id}")
def end_session(session_id: UUID, staff: StaffActor = Depends(get_current_staff),
                client: ClientInfo = Depends(client_info)):
    if not svc.revoke_session(str(session_id), staff.id, "revoked_by_self"):
        raise HTTPException(status_code=404, detail="Session not found")
    svc.audit("auth.session_revoked", actor=staff, client=client, target=f"session:{session_id}")
    return _ok(None)


@router.get("/me/activity")
def my_activity(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0),
                staff: StaffActor = Depends(get_current_staff)):
    return _ok(svc.list_audit(actor=staff.id, limit=limit, offset=offset))
