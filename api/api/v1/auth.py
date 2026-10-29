"""Sign-up, sign-in, sessions and passwords.

The refresh token lives only in an httpOnly cookie scoped to /api/v1/auth, so page
scripts never see it; the short-lived access token is returned in the body and kept
in memory by the web app.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from auth import service
from auth.service import AuthError, ClientInfo, SessionTokens
from config.config import settings
from core.deps import client_info, get_current_user
from schemas.auth_user import AuthUser
from schemas.users import ForgotPassword, LoginBody, PasswordChange, PasswordReset, ProfileUpdate, UserCreate
from services import user_store

router = APIRouter(prefix="/auth", tags=["Auth"])

REFRESH_COOKIE = "cn_refresh"
COOKIE_PATH = "/api/v1/auth"


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: AuthError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path=COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        httponly=True,
    )


def _session_response(response: Response, tokens: SessionTokens) -> dict:
    if tokens.refresh_token:
        _set_refresh_cookie(response, tokens.refresh_token)
    response.headers["Cache-Control"] = "no-store"
    return _ok({
        "user": tokens.user,
        "accessToken": tokens.access_token,
        "expiresIn": tokens.expires_in,
    })


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, response: Response, client: ClientInfo = Depends(client_info)):
    try:
        tokens = service.register(body.email, body.password, body.fullname, body.phone, client)
    except AuthError as exc:
        _raise(exc)
    return _session_response(response, tokens)


@router.post("/login")
def login(body: LoginBody, response: Response, client: ClientInfo = Depends(client_info)):
    try:
        tokens = service.login(body.email, body.password, client)
    except AuthError as exc:
        _raise(exc)
    return _session_response(response, tokens)


@router.post("/refresh")
def refresh(request: Request, response: Response, client: ClientInfo = Depends(client_info)):
    try:
        tokens = service.refresh(request.cookies.get(REFRESH_COOKIE), client)
    except AuthError as exc:
        _clear_refresh_cookie(response)
        # Raising would drop the Set-Cookie header, so answer 401 directly
        response.status_code = exc.status_code
        return {"detail": str(exc)}
    return _session_response(response, tokens)


@router.post("/logout")
def logout(request: Request, response: Response, client: ClientInfo = Depends(client_info)):
    """Ends this browser's session. Works even when the access token has already expired."""
    session_id = None
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        resolved = service.resolve_access_token(header[7:])
        session_id = resolved[1] if resolved else None
    service.logout(request.cookies.get(REFRESH_COOKIE), session_id, client)
    _clear_refresh_cookie(response)
    return _ok(None)


@router.post("/logout-all")
def logout_everywhere(response: Response, user: AuthUser = Depends(get_current_user),
                      client: ClientInfo = Depends(client_info)):
    count = service.revoke_all_sessions(user.id, "logout_all")
    service.record_event("logout_all", user_id=user.id, client=client, detail=f"{count} sessions")
    _clear_refresh_cookie(response)
    return _ok({"signedOut": count})


@router.get("/me")
def me(user: AuthUser = Depends(get_current_user)):
    return _ok({"user": service.public_user(user_store.get_user(user.id))})


@router.patch("/me")
def update_me(body: ProfileUpdate, user: AuthUser = Depends(get_current_user)):
    updated = user_store.update_profile(user.id, body.model_dump(exclude_unset=True))
    return _ok({"user": service.public_user(updated)})


@router.post("/change-password")
def change_password(body: PasswordChange, user: AuthUser = Depends(get_current_user),
                    client: ClientInfo = Depends(client_info)):
    try:
        signed_out = service.change_password(
            user.id, body.current_password, body.new_password, user.session_id, client
        )
    except AuthError as exc:
        _raise(exc)
    return _ok({"otherSessionsSignedOut": signed_out})


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: ForgotPassword, client: ClientInfo = Depends(client_info)):
    service.request_password_reset(body.email, client)
    return _ok({"message": "If an account exists for that email, a reset link has been sent."})


@router.post("/reset-password")
def reset_password(body: PasswordReset, client: ClientInfo = Depends(client_info)):
    try:
        service.reset_password(body.token, body.new_password, client)
    except AuthError as exc:
        _raise(exc)
    return _ok(None)


@router.get("/sessions")
def my_sessions(user: AuthUser = Depends(get_current_user)):
    sessions = service.list_sessions(user.id)
    for s in sessions:
        s["current"] = s["id"] == user.session_id
    return _ok({"sessions": sessions})


@router.delete("/sessions/{session_id}")
def end_session(session_id: UUID, user: AuthUser = Depends(get_current_user),
                client: ClientInfo = Depends(client_info)):
    if not service.revoke_session(str(session_id), "revoked_by_user", user_id=user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    service.record_event("session_revoked", user_id=user.id, client=client)
    return _ok(None)


@router.get("/activity")
def my_activity(user: AuthUser = Depends(get_current_user)):
    return _ok({"events": service.list_events(user.id, limit=30)})
