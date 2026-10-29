from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import service
from schemas.auth_user import AuthUser

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


def require_admin(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def client_info(request: Request) -> service.ClientInfo:
    # Behind a reverse proxy, run uvicorn with --proxy-headers so client.host is the real IP
    return service.ClientInfo(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
