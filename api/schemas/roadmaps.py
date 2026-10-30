from pydantic import BaseModel, Field


class RoadmapCreateRequest(BaseModel):
    goal: str = Field(..., max_length=120, examples=["passport"])
    subCity: str = Field(..., max_length=80, examples=["bole"])
    industry: str | None = Field(None, max_length=120)
    documentsHeld: list[str] = Field(default_factory=list, max_length=50)


class StepCompleteRequest(BaseModel):
    completed: bool = True
