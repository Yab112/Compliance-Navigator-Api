from fastapi import APIRouter, Depends, HTTPException, status

from core.deps import get_current_user, get_optional_user
from schemas.auth_user import AuthUser
from schemas.roadmaps import RoadmapCreateRequest, StepCompleteRequest
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


@router.get("/{roadmap_id}")
def read_roadmap(
    roadmap_id: str,
    _user: AuthUser | None = Depends(get_optional_user),
):
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "success", "payload": {"roadmap": roadmap}}


@router.patch("/{roadmap_id}/steps/{step_id}")
def update_step(
    roadmap_id: str,
    step_id: str,
    body: StepCompleteRequest,
    _user: AuthUser = Depends(get_current_user),
):
    roadmap = mark_step(roadmap_id, step_id, body.completed)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return {"message": "success", "payload": {"roadmap": roadmap}}
