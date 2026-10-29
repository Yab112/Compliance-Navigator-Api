"""The signed-in user's notifications (shown under the header bell)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.deps import get_current_user
from schemas.auth_user import AuthUser
from services import notifications

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class MarkRead(BaseModel):
    """Omit ids to mark everything read."""

    ids: list[str] | None = Field(None, max_length=200)


@router.get("")
def my_notifications(user: AuthUser = Depends(get_current_user)):
    return {"message": "success", "payload": notifications.list_for(user.id)}


@router.post("/read")
def mark_read(body: MarkRead, user: AuthUser = Depends(get_current_user)):
    return {"message": "success", "payload": {"marked": notifications.mark_read(user.id, body.ids)}}
