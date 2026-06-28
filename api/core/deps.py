from typing import Annotated



from fastapi import Depends, HTTPException, status

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer



from auth.supabase_auth import is_auth_configured, verify_access_token

from schemas.auth_user import AuthUser



bearer_scheme = HTTPBearer(auto_error=True)

bearer_optional = HTTPBearer(auto_error=False)





def _user_from_bearer(credentials: HTTPAuthorizationCredentials | None) -> AuthUser | None:

    if not credentials:

        return None

    if not is_auth_configured():

        raise HTTPException(

            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

            detail="Supabase Auth is not configured on the server",

        )

    user = verify_access_token(credentials.credentials)

    if not user:

        raise HTTPException(

            status_code=status.HTTP_401_UNAUTHORIZED,

            detail="Invalid or expired token",

        )

    return user





def get_current_user(

    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],

) -> AuthUser:

    return _user_from_bearer(credentials)





def get_optional_user(

    credentials: Annotated[

        HTTPAuthorizationCredentials | None,

        Depends(bearer_optional),

    ] = None,

) -> AuthUser | None:

    if not credentials:

        return None

    if not is_auth_configured():

        return None

    try:

        return verify_access_token(credentials.credentials)

    except Exception:

        return None


