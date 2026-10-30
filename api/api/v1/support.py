"""Support desk: customers write to the team; staff work the queues."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from core.deps import client_info, get_current_user, get_optional_user, require_admin
from schemas.auth_user import AuthUser
from schemas.staff_user import StaffActor
from services import support_service as svc
from services.support_service import SupportError

router = APIRouter(prefix="/support", tags=["Support"])

admin_router = APIRouter(prefix="/admin/support", tags=["Admin Support"], dependencies=[Depends(require_admin)])

Queue = Literal["customer_support", "compliance", "marketplace", "organizations", "technical"]


def _ok(payload):
    return {"message": "success", "payload": payload}


def _raise(exc: SupportError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


def _author(user: StaffActor) -> dict:
    return {"id": user.id, "name": user.fullname or user.email, "email": user.email}


class TicketCreate(BaseModel):
    queue: Queue = "customer_support"
    subject: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=3, max_length=4000)
    name: str | None = Field(None, max_length=120)
    phone: str | None = Field(None, pattern=r"^\+?[0-9 ]{9,16}$")
    email: str | None = Field(None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    conversation_id: str | None = None
    # An older request of theirs that ended too long ago to reopen
    follow_up_of: str | None = None


class MessageBody(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    internal: bool = False


class StaffMessageBody(MessageBody):
    # Reply and resolve in one step, so a failed resolve can never send the reply twice
    resolve: bool = False
    canned_reply_id: str | None = None


class CannedReplyBody(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    body: str = Field(..., min_length=1, max_length=4000)
    queue: Queue | None = None


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
    if body.conversation_id and user:
        from assistant import store

        # Only your own assistant conversation can go with your ticket (staff replies are written into it)
        convo = store.get(str(body.conversation_id), user.id)
        if not convo or convo["user_id"] not in (None, user.id):
            raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        ticket = svc.create_ticket(
            subject=body.subject, body=body.body, queue=body.queue, source="contact_form",
            user_id=user.id if user else None, name=body.name, phone=body.phone, email=body.email,
            conversation_id=body.conversation_id if user else None, ip=client_info(request).ip,
            follow_up_of=body.follow_up_of if user else None,
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
def summary(user: StaffActor = Depends(require_admin)):
    return _ok(svc.summary(user.id))


StatusFilter = Literal["active", "overdue", "all", "new", "open", "waiting_customer", "resolved", "closed"]
Sort = Literal["triage", "newest", "oldest", "updated"]


def _list_filters(
    queue: Queue | None = None,
    status: StatusFilter = "active",
    assigned: str | None = Query(None, max_length=36, description="me, none or a staff id"),
    priority: Literal["low", "normal", "high", "urgent"] | None = None,
    source: Literal["assistant", "contact_form", "report"] | None = None,
    waiting: Literal["us", "customer"] | None = None,
    q: str | None = Query(None, max_length=200),
    since: date | None = None,
    until: date | None = None,
    sort: Sort = "triage",
) -> dict:
    return {"queue": queue, "status": status, "assigned": assigned, "priority": priority, "source": source,
            "waiting": waiting, "q": q, "since": since and since.isoformat(), "until": until and until.isoformat(),
            "sort": sort}


@admin_router.get("/tickets")
def list_tickets(filters: dict = Depends(_list_filters), limit: int = Query(25, ge=1, le=100),
                 offset: int = Query(0, ge=0), user: StaffActor = Depends(require_admin)):
    return _ok(svc.admin_list(**filters, staff_id=user.id, limit=limit, offset=offset))


# Declared before /tickets/{ticket_id} so "tickets.csv" is never read as an id
@admin_router.get("/tickets.csv")
def export_tickets(request: Request, filters: dict = Depends(_list_filters), user: StaffActor = Depends(require_admin)):
    text, rows = svc.export_csv(**filters, staff_id=user.id)
    svc.log_staff_action("support.export", _author(user), "support_tickets",
               {"rows": rows, "filters": {k: v for k, v in filters.items() if v}}, client_info(request))
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="support-requests-{datetime.now(UTC).date().isoformat()}.csv"',
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@admin_router.get("/tickets/{ticket_id}")
def ticket_detail(ticket_id: str):
    detail = svc.admin_detail(ticket_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Request not found")
    return _ok(detail)


@admin_router.get("/tickets/{ticket_id}/customer")
def ticket_customer(ticket_id: str, user: StaffActor = Depends(require_admin)):
    context = svc.customer_context(ticket_id, can=user.can)
    if context is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return _ok(context)


@admin_router.post("/tickets/{ticket_id}/messages")
def staff_reply(ticket_id: str, body: StaffMessageBody, user: StaffActor = Depends(require_admin)):
    try:
        return _ok(svc.staff_reply(ticket_id, author=_author(user), body=body.body, internal=body.internal,
                                   resolve=body.resolve, canned_reply_id=body.canned_reply_id))
    except SupportError as exc:
        _raise(exc)


@admin_router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, body: TicketUpdate, request: Request, user: StaffActor = Depends(require_admin)):
    try:
        return _ok(svc.update(ticket_id, body.model_dump(exclude_unset=True), author=_author(user),
                              client=client_info(request)))
    except SupportError as exc:
        _raise(exc)


# ---------------------------------------------------------------- saved replies


@admin_router.get("/replies")
def list_replies(queue: Queue | None = None, q: str | None = Query(None, max_length=200),
                 ticket_id: str | None = None, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                 user: StaffActor = Depends(require_admin)):
    try:
        return _ok(svc.list_replies(queue=queue, q=q, ticket_id=ticket_id, agent_name=_author(user)["name"],
                                    limit=limit, offset=offset))
    except SupportError as exc:
        _raise(exc)


@admin_router.post("/replies", status_code=status.HTTP_201_CREATED)
def create_reply(body: CannedReplyBody, user: StaffActor = Depends(require_admin)):
    try:
        return _ok(svc.create_reply(body.model_dump(), author=_author(user)))
    except SupportError as exc:
        _raise(exc)


@admin_router.put("/replies/{reply_id}")
def update_reply(reply_id: str, body: CannedReplyBody, user: StaffActor = Depends(require_admin)):
    try:
        return _ok(svc.update_reply(reply_id, body.model_dump(), author=_author(user)))
    except SupportError as exc:
        _raise(exc)


@admin_router.delete("/replies/{reply_id}")
def delete_reply(reply_id: str, user: StaffActor = Depends(require_admin)):
    try:
        svc.delete_reply(reply_id, author=_author(user))
    except SupportError as exc:
        _raise(exc)
    return _ok({"deleted": reply_id})
