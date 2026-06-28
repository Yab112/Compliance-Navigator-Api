from pydantic import BaseModel, Field


class RoadmapCreateRequest(BaseModel):
    goal: str = Field(..., examples=["passport"])
    subCity: str = Field(..., examples=["bole"])
    industry: str | None = None
    documentsHeld: list[str] = Field(default_factory=list)


class StepCompleteRequest(BaseModel):
    completed: bool = True
