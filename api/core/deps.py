import json
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import security, service, staff_service
from schemas.auth_user import AuthUser
from schemas.staff_user import StaffActor
from services import access, approvals

log = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


def _resolve_user(token: str) -> AuthUser | None:
    resolved = service.resolve_access_token(token)
    if not resolved:
        return None
    user, session_id = resolved
    user.session_id = session_id
    return user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthUser:
    user = _resolve_user(credentials.credentials) if credentials else None
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not signed in or session expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> AuthUser | None:
    if not credentials:
        return None
    return _resolve_user(credentials.credentials)


# ---------------------------------------------------------------- staff realm


def _staff_from(credentials: HTTPAuthorizationCredentials | None) -> StaffActor:
    staff = staff_service.resolve_access_token(credentials.credentials) if credentials else None
    if staff:
        return staff
    if credentials and security.decode_access_token(credentials.credentials):
        # A valid public account token: signed in, but not as staff
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in or session expired",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_staff(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> StaffActor:
    """Any signed-in staff member, for their own account (/staff/...). No permission needed."""
    return _staff_from(credentials)


_REDACT = ("password", "token", "secret", "account_number")
_READS = ("GET", "HEAD", "OPTIONS")


def _redacted(body, depth: int = 0):
    if isinstance(body, dict) and depth < 3:
        return {k: ("[hidden]" if any(w in k.lower() for w in _REDACT) else _redacted(v, depth + 1))
                for k, v in list(body.items())[:30]}
    if isinstance(body, str):
        return body[:300]
    if isinstance(body, list):
        return [_redacted(v, depth + 1) for v in body[:20]]
    return body


async def require_admin(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
):
    """
    Every admin route depends on this. It signs the staff member in, looks the route up in
    services/access.ROUTE_POLICY and refuses anything without an entry (deny by default) or
    without the permission. When the entry has an approval rule and the change needs a second
    person, the request is stored and the route never runs (202, see app.py). Every change
    (anything but a read) is written to the staff audit log with its outcome.
    """
    staff = await run_in_threadpool(_staff_from, credentials)
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    policy = access.policy_for(request.method, route_path) if route_path else None
    if policy is None:
        log.error("Admin route without an access policy: %s %s", request.method, route_path)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action isn't assigned to any permission yet")
    if staff.must_change_password:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Change your password before continuing")

    mutation = request.method not in _READS
    body = None
    content_type = request.headers.get("content-type", "").lower()
    # FastAPI also reads a body with no content type (or "application/JSON") as JSON, so the checks
    # below must see that same body; otherwise leaving the header out would skip approvals
    if (mutation or policy.body_field) and ("json" in content_type or not content_type):
        try:
            raw = await request.body()
            body = json.loads(raw) if raw else None
        except (json.JSONDecodeError, UnicodeDecodeError, RuntimeError):
            body = None
    permission = policy.permission
    if policy.body_field and isinstance(body, dict):
        permission = policy.by_value.get(str(body.get(policy.body_field)), permission)
    client = client_info(request)
    if permission != "*" and not staff.can(permission):
        perm = access.BY_KEY.get(permission)
        if mutation:
            await run_in_threadpool(staff_service.audit, "access.denied", actor=staff, target=request.url.path,
                                    client=client, details={"method": request.method, "permission": permission})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"You don't have permission for this ({perm.label if perm else permission})")

    if policy.approval:
        rule = approvals.ROUTE_RULES[policy.approval]
        try:
            await run_in_threadpool(rule, body if isinstance(body, dict) else {}, staff,
                                    dict(request.path_params), client)
        except approvals.ApprovalError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    # The staff access routes write their own, more detailed audit entries
    if not mutation or route_path.startswith(f"{access.API_PREFIX}/admin/access/"):
        yield staff
        return
    details = {"method": request.method, "path_params": dict(request.path_params),
               "query": dict(request.query_params) or None, "body": _redacted(body)}
    try:
        yield staff
    except HTTPException as exc:
        details["status"] = exc.status_code
        details["error"] = str(exc.detail)[:300]
        await run_in_threadpool(staff_service.audit, permission, actor=staff, target=request.url.path,
                                client=client, details=details)
        raise
    except Exception as exc:
        details["status"] = 500
        details["error"] = exc.__class__.__name__
        await run_in_threadpool(staff_service.audit, permission, actor=staff, target=request.url.path,
                                client=client, details=details)
        raise
    details["status"] = "ok"
    await run_in_threadpool(staff_service.audit, permission, actor=staff, target=request.url.path,
                            client=client, details=details)


def client_info(request: Request) -> service.ClientInfo:
    # Behind a reverse proxy, run uvicorn with --proxy-headers so client.host is the real IP
    return service.ClientInfo(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
