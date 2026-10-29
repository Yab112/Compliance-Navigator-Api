from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from core.deps import client_info, get_optional_user
from schemas.auth_user import AuthUser
from services.feedback_service import FeedbackError, create_flag

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FlagCreate(BaseModel):
    target_type: str = Field(..., pattern="^(document|gov_service|office|agent|roadmap_step|org_service|other)$")
    target_id: str | None = Field(None, max_length=120)
    message: str = Field(..., min_length=5, max_length=1000)


@router.post("", status_code=status.HTTP_201_CREATED)
def flag_incorrect_information(body: FlagCreate, request: Request, user: AuthUser | None = Depends(get_optional_user)):
    try:
        flag = create_flag(body.target_type, body.target_id, body.message, user.id if user else None,
                           ip=client_info(request).ip)
    except FeedbackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    # The reporter only needs to know it arrived; the admin view carries other people's details
    return {"message": "success", "payload": {"flag": {"id": flag["id"], "status": flag["status"]}}}
