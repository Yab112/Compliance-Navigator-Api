"""Actions that need a confirmed email address.

A new account works straight away, but until the person opens the link we emailed them they can't
become a provider, create or join an organization, or receive payouts (see auth/service.verify_email).
"""

from fastapi import Depends, HTTPException, status

from core.deps import get_current_user
from schemas.auth_user import AuthUser

UNVERIFIED_DETAIL = (
    "Confirm your email address first. Open the link we emailed you, "
    "or ask for a new one from the notice at the top of the page."
)


def get_verified_user(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if not user.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=UNVERIFIED_DETAIL)
    return user
