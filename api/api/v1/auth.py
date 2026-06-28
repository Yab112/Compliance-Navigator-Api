from fastapi import APIRouter, Depends

from core.deps import get_current_user
from schemas.auth_user import AuthUser

router = APIRouter(prefix="/auth", tags=["Auth"])


def _user_payload(user: AuthUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "fullname": user.fullname,
    }


@router.get("/me")
def get_current_user_profile(user: AuthUser = Depends(get_current_user)):
    return {
        "message": "success",
        "payload": {"user": _user_payload(user)},
    }


@router.post("/logout")
def logout():
    """Client calls Supabase signOut; this endpoint is a no-op for compatibility."""
    return {"message": "success", "payload": None}
