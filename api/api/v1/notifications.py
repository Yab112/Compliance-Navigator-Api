"""The signed-in user's notifications (shown under the header bell)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.deps import get_current_user
from schemas.auth_user import AuthUser
from services import notifications, reminders

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class MarkRead(BaseModel):
    """Omit ids to mark everything read."""

    ids: list[str] | None = Field(None, max_length=200)


@router.get("")
def my_notifications(user: AuthUser = Depends(get_current_user)):
    reminders.deliver_due_for(user.id)  # no worker on the free plan: due reminders arrive when the bell loads
    return {"message": "success", "payload": notifications.list_for(user.id)}


@router.post("/read")
def mark_read(body: MarkRead, user: AuthUser = Depends(get_current_user)):
    return {"message": "success", "payload": {"marked": notifications.mark_read(user.id, body.ids)}}


# ---------------------------------------------------------------- reminders


class ReminderIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    due_on: date
    body: str | None = Field(None, max_length=1000)
    link: str | None = Field(None, max_length=300, pattern=r"^/")


@router.get("/reminders")
def my_reminders(user: AuthUser = Depends(get_current_user)):
    return {"message": "success", "payload": {"items": reminders.list_for(user.id)}}


@router.post("/reminders", status_code=201)
def add_reminder(body: ReminderIn, user: AuthUser = Depends(get_current_user)):
    try:
        row = reminders.create(user.id, title=body.title, due_on=body.due_on, body=body.body, link=body.link,
                               source="account")
    except reminders.ReminderError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    return {"message": "success", "payload": row}


@router.delete("/reminders/{reminder_id}")
def cancel_reminder(reminder_id: str, user: AuthUser = Depends(get_current_user)):
    if not reminders.cancel(user.id, reminder_id):
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"message": "success", "payload": {"cancelled": True}}
