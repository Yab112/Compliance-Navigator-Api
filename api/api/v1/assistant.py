"""Interactive assistant: one endpoint per turn. Works signed out; signing in links the conversation."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from assistant import dialogue, rephrase, store
from core.deps import client_info, get_optional_user
from schemas.auth_user import AuthUser
from services import support_service

router = APIRouter(prefix="/assistant", tags=["Assistant"])


class TurnBody(BaseModel):
    conversation_id: str | None = None
    message: str | None = Field(None, max_length=1000)
    action: dict[str, Any] | None = None
    language: str | None = Field(None, pattern="^(en|am)$")
    # The service the page is about (e.g. the goal picked in Find my path); used until the person names another
    context_service: str | None = Field(None, max_length=200, pattern=r"^(path|org|mesob):[\w.-]+$")


def _ok(payload):
    return {"message": "success", "payload": payload}


def _label_for(action: dict, reply_widget_options: list | None = None) -> str:
    """What the person 'said' when they tapped a chip or submitted a widget, for the transcript."""
    value = action.get("label") or action.get("value")
    if isinstance(value, list):
        return ", ".join(map(str, value)) or "None"
    return str(value or action.get("type", ""))


def _ticket(state: dict) -> dict | None:
    return support_service.brief(support_service.get(state["ticket_id"])) if state.get("ticket_id") else None


def _handover(conversation: dict, state: dict, message: str, user: AuthUser | None) -> dict | None:
    """While a person on our team has the case, typed messages go to them, not to the bot."""
    ticket = support_service.get(state["ticket_id"]) if state.get("ticket_id") else None
    if not ticket or ticket["status"] in ("resolved", "closed"):
        state["channel"] = "agent"
        return None
    store.add_message(conversation["id"], "user", message)
    support_service.customer_reply(ticket["id"], user.id if user else None, message)
    store.save_state(conversation["id"], state["lang"], state)
    return _ok({"conversationId": conversation["id"], "language": state["lang"], "reply": None, "delivered": True,
                "channel": "human", "ticket": _ticket(state), "service": state.get("service"),
                "subCity": state.get("sub_city"), "held": state.get("held") or []})


@router.post("/turn")
def turn(body: TurnBody, request: Request, user: AuthUser | None = Depends(get_optional_user)):
    if not body.message and not body.action:
        raise HTTPException(status_code=422, detail="Send a message or an action")
    conversation = store.get(body.conversation_id, user.id if user else None) if body.conversation_id else None
    if not conversation:
        state = dialogue.new_state(body.language or "en")
        if body.language:
            state["lang_locked"] = True
        conversation = store.create(user.id if user else None, state["lang"], state)
    state = conversation["state"] or dialogue.new_state()
    if body.language and body.language != state.get("lang"):
        state["lang"] = body.language
        state["lang_locked"] = True

    if body.context_service and not state.get("service"):
        dialogue.adopt_context(state, body.context_service)

    if state.get("channel") == "human" and body.message and not body.action:
        delivered = _handover(conversation, state, body.message, user)
        if delivered:
            return delivered

    user_text = body.message if body.message else _label_for(body.action)
    # Taps are marked so the hand-off summary only quotes what the person wrote
    store.add_message(conversation["id"], "user", user_text, None if body.message else {"tap": True})
    reply, info = dialogue.handle(state, message=body.message, action=body.action, user=user,
                                  ctx={"conversation_id": conversation["id"], "ip": client_info(request).ip})
    reply["text"] = rephrase.maybe_rephrase(reply["text"], state["lang"])
    reply.update(intent=info.get("routed_intent") or info["intent"], confidence=info["confidence"])
    store.add_message(conversation["id"], "assistant", reply["text"], reply)
    store.save_state(conversation["id"], state["lang"], state)
    if body.message:
        store.log_turn(conversation["id"], body.message, state["lang"], info["intent"], info["confidence"],
                       info["ranked"], info["service"], info["version"])
    return _ok({"conversationId": conversation["id"], "language": state["lang"], "reply": reply,
                "channel": state.get("channel") or "agent", "ticket": _ticket(state),
                "service": state.get("service"), "subCity": state.get("sub_city"), "held": state.get("held") or []})


def _message(m: dict) -> dict:
    out = {"id": m["id"], "role": m["role"], "text": m["content"], "createdAt": m["created_at"].isoformat(),
           "reply": m["payload"] if m["role"] == "assistant" else None}
    if m["role"] == "staff":
        out["staff"] = (m["payload"] or {}).get("staff") or {"name": None, "team": None}
    return out


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, after: int | None = None, user: AuthUser | None = Depends(get_optional_user)):
    conversation = store.get(conversation_id, user.id if user else None)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    state = conversation["state"] or {}
    ticket = _ticket(state)
    channel = state.get("channel") or "agent"
    if channel == "human" and (not ticket or ticket["status"] in ("resolved", "closed")):
        channel = "agent"
    messages = [_message(m) for m in store.history(conversation_id, after=after)]
    return _ok({"conversationId": conversation["id"], "language": conversation["language"], "messages": messages,
                "service": state.get("service"), "channel": channel, "ticket": ticket})


@router.get("/welcome")
def welcome(language: str = "en"):
    state = dialogue.new_state("am" if language == "am" else "en")
    return _ok({"reply": dialogue.welcome(state)})
