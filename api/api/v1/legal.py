"""Our legal documents, and accepting new versions of them after sign-up."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from auth.service import ClientInfo, record_event
from core.deps import client_info, get_current_user
from schemas.auth_user import AuthUser
from services import legal

router = APIRouter(prefix="/legal", tags=["Legal"])


def _ok(payload):
    return {"message": "success", "payload": payload}


class AcceptBody(BaseModel):
    # {"terms": "1.0", "privacy": "1.0"}: document key -> the version the person read
    accept: dict[str, str] = Field(..., max_length=10)


@router.get("/documents")
def documents():
    """Current version of every document, and which ones people must accept."""
    return _ok({
        "documents": [d.public() for d in legal.DOCUMENTS.values()],
        "clientRequired": list(legal.CLIENT_REQUIRED),
        "providerRequired": list(legal.PROVIDER_REQUIRED),
    })


@router.get("/status")
def my_status(user: AuthUser = Depends(get_current_user)):
    """What this person must accept, and whether they accepted the current version of each."""
    return _ok(legal.status(user.id))


@router.post("/accept")
def accept(body: AcceptBody, user: AuthUser = Depends(get_current_user), client: ClientInfo = Depends(client_info)):
    legal.accept(user.id, body.accept, client.ip, client.user_agent)
    record_event("legal_accepted", user_id=user.id, client=client,
                 detail=", ".join(f"{k} {v}" for k, v in sorted(body.accept.items())))
    return _ok(legal.status(user.id))


@router.get("/consents")
def my_consents(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                user: AuthUser = Depends(get_current_user)):
    """Every version this person agreed to and when, newest first."""
    return _ok(legal.list_consents(user.id, limit, offset))
