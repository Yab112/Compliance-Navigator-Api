from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from core.deps import get_optional_user
from schemas.auth_user import AuthUser
from services.feedback_service import create_flag

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FlagCreate(BaseModel):
    target_type: str = Field(..., pattern="^(document|gov_service|office|agent|roadmap_step|org_service|other)$")
    target_id: str | None = Field(None, max_length=120)
    message: str = Field(..., min_length=5, max_length=1000)


@router.post("", status_code=status.HTTP_201_CREATED)
def flag_incorrect_information(body: FlagCreate, user: AuthUser | None = Depends(get_optional_user)):
    flag = create_flag(body.target_type, body.target_id, body.message, user.id if user else None)
    return {"message": "success", "payload": {"flag": flag}}
