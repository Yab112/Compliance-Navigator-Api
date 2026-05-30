from fastapi import APIRouter, Depends, HTTPException, status

from auth.deps import get_current_user
from models.user import UserNode

AuthRouter = APIRouter()


def _user_payload(user: UserNode) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "fullname": user.fullname,
    }


@AuthRouter.get("/me")
def get_current_user_profile(user: UserNode = Depends(get_current_user)):
    return {
        "message": "success",
        "payload": {"user": _user_payload(user)},
    }


@AuthRouter.post("/logout")
def logout():
    """JWT is stateless; client clears the token."""
    return {"message": "success", "payload": None}
