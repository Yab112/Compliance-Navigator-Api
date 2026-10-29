from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from core.deps import get_current_user, get_optional_user
from schemas.auth_user import AuthUser
from schemas.roadmaps import RoadmapCreateRequest, StepCompleteRequest
from services import roadmap_store
from services.roadmap_service import (
    generate_roadmap,
    get_roadmap,
    mark_step,
    save_roadmap,
)

router = APIRouter(prefix="/roadmaps", tags=["Roadmaps"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_roadmap(
    body: RoadmapCreateRequest,
    user: AuthUser | None = Depends(get_optional_user),
):
    roadmap = generate_roadmap(
        goal=body.goal,
        sub_city=body.subCity,
        documents_held=body.documentsHeld,
        industry=body.industry,
    )
    save_roadmap(roadmap, user=user)
    return {"message": "success", "payload": {"roadmap": roadmap}}


def _visible(roadmap_id: str, user: AuthUser | None) -> None:
    """A saved path belongs to its owner; an unsaved one is reachable by its (unguessable) id."""
    exists, owner = roadmap_store.owner_of(roadmap_id)
    if exists and owner and (not user or user.id != owner):
        raise HTTPException(status_code=404, detail="Roadmap not found")


@router.get("")
def my_roadmaps(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                user: AuthUser = Depends(get_current_user)):
    return {"message": "success", "payload": {"items": roadmap_store.list_for_user(user.id, limit, offset),
                                              "total": roadmap_store.count_for_user(user.id)}}


@router.post("/{roadmap_id}/save")
def save_to_account(roadmap_id: str, user: AuthUser = Depends(get_current_user)):
    if not get_roadmap(roadmap_id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    if not roadmap_store.claim(roadmap_id, user.id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "success", "payload": {"saved": True}}


@router.delete("/{roadmap_id}")
def remove_saved(roadmap_id: str, user: AuthUser = Depends(get_current_user)):
    if not roadmap_store.remove(roadmap_id, user.id):
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "success", "payload": {"removed": True}}


class PathFeedback(BaseModel):
    accuracy: int = Field(..., ge=1, le=5)
    days_taken: int | None = Field(None, ge=0, le=3650)
    steps_different: list[str] = Field(default_factory=list, max_length=30)
    what_was_different: str | None = Field(None, max_length=2000)
    would_recommend: bool | None = None
    comment: str | None = Field(None, max_length=2000)


@router.get("/{roadmap_id}/feedback")
def read_feedback(roadmap_id: str, user: AuthUser | None = Depends(get_optional_user)):
    _visible(roadmap_id, user)
    return {"message": "success", "payload": {"feedback": roadmap_store.get_feedback(roadmap_id)}}


@router.post("/{roadmap_id}/feedback", status_code=status.HTTP_201_CREATED)
def give_feedback(roadmap_id: str, body: PathFeedback, user: AuthUser | None = Depends(get_optional_user)):
    _visible(roadmap_id, user)
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    if roadmap_store.get_feedback(roadmap_id):
        raise HTTPException(status_code=409, detail="You already told us about this path. Thank you!")
    feedback = roadmap_store.save_feedback(roadmap, user.id if user else None, body.model_dump())
    return {"message": "success", "payload": {"feedback": feedback}}


@router.get("/{roadmap_id}")
def read_roadmap(
    roadmap_id: str,
    user: AuthUser | None = Depends(get_optional_user),
):
    _visible(roadmap_id, user)
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    exists, owner = roadmap_store.owner_of(roadmap_id)
    # Whether it's in *my* saved paths: a direct answer, not a search through a paged list
    return {"message": "success", "payload": {"roadmap": roadmap, "saved": bool(user and owner == user.id)}}


@router.patch("/{roadmap_id}/steps/{step_id}")
def update_step(
    roadmap_id: str,
    step_id: str,
    body: StepCompleteRequest,
    user: AuthUser = Depends(get_current_user),
):
    _visible(roadmap_id, user)
    roadmap = mark_step(roadmap_id, step_id, body.completed)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "success", "payload": {"roadmap": roadmap}}
