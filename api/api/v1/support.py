"""Support desk: customers write to the team; staff work the queues."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.deps import client_info, get_current_user, get_optional_user, require_admin
from schemas.auth_user import AuthUser
from services import support_service as svc
from services.support_service import SupportError

router = APIRouter(prefix="/support", tags=["Support"])
admin_router = APIRouter(prefix="/admin/support", tags=["Admin Support"], dependencies=[Depends(require_admin)])

Queue = Literal["customer_support", "compliance", "marketplace", "organizations", "technical"]


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: SupportError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


def _author(user: AuthUser) -> dict:
    return {"id": user.id, "name": user.fullname or user.email}


class TicketCreate(BaseModel):
    queue: Queue = "customer_support"
    subject: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=3, max_length=4000)
    name: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, pattern=r"^\+?[0-9 ]{9,16}$")
    email: str | None = Field(None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    conversation_id: str | None = None


class MessageBody(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    internal: bool = False


class TicketUpdate(BaseModel):
    status: Literal["new", "open", "waiting_customer", "resolved", "closed"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    queue: Queue | None = None
    assignee_id: str | None = None


@router.get("/meta")
def meta():
    return _ok(svc.meta())


@router.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(body: TicketCreate, request: Request, user: AuthUser | None = Depends(get_optional_user)):
    try:
        ticket = svc.create_ticket(
            subject=body.subject, body=body.body, queue=body.queue, source="contact_form",
            user_id=user.id if user else None, name=body.name, phone=body.phone, email=body.email,
            conversation_id=body.conversation_id if user else None, ip=client_info(request).ip,
        )
    except SupportError as exc:
        _raise(exc)
    return _ok({"ticket": ticket})


@router.get("/tickets")
def my_tickets(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
               user: AuthUser = Depends(get_current_user)):
    return _ok({"items": svc.list_for_user(user.id, limit, offset), "total": svc.count_for_user(user.id)})


def _mine(ticket_id: str, user: AuthUser) -> dict:
    ticket = svc.get_for_user(ticket_id, user.id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Request not found")
    return ticket


@router.get("/tickets/{ticket_id}")
def my_ticket(ticket_id: str, user: AuthUser = Depends(get_current_user)):
    ticket = _mine(ticket_id, user)
    return _ok({"ticket": ticket, "messages": svc.messages(ticket["id"], include_internal=False)})


@router.post("/tickets/{ticket_id}/messages")
def reply(ticket_id: str, body: MessageBody, user: AuthUser = Depends(get_current_user)):
    _mine(ticket_id, user)
    try:
        ticket = svc.customer_reply(ticket_id, user.id, body.body)
    except SupportError as exc:
        _raise(exc)
    return _ok({"ticket": ticket, "messages": svc.messages(ticket_id, include_internal=False)})


# ---------------------------------------------------------------- staff


@admin_router.get("/summary")
def summary(user: AuthUser = Depends(require_admin)):
    return _ok(svc.summary(user.id))


@admin_router.get("/tickets")
def list_tickets(
    queue: Queue | None = None, status: str | None = "active", assigned: Literal["me", "none"] | None = None,
    priority: Literal["low", "normal", "high", "urgent"] | None = None, q: str | None = None,
    limit: int = 25, offset: int = 0, user: AuthUser = Depends(require_admin),
):
    return _ok(svc.admin_list(queue=queue, status=status, assigned=assigned, priority=priority, q=q,
                              staff_id=user.id, limit=min(max(limit, 1), 100), offset=max(offset, 0)))


@admin_router.get("/tickets/{ticket_id}")
def ticket_detail(ticket_id: str):
    detail = svc.admin_detail(ticket_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Request not found")
    return _ok(detail)


@admin_router.post("/tickets/{ticket_id}/messages")
def staff_reply(ticket_id: str, body: MessageBody, user: AuthUser = Depends(require_admin)):
    try:
        return _ok(svc.staff_reply(ticket_id, author=_author(user), body=body.body, internal=body.internal))
    except SupportError as exc:
        _raise(exc)


@admin_router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, body: TicketUpdate, user: AuthUser = Depends(require_admin)):
    try:
        return _ok(svc.update(ticket_id, body.model_dump(exclude_unset=True), author=_author(user)))
    except SupportError as exc:
        _raise(exc)
