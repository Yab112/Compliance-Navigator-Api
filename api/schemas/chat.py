from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    roadmap_id: str | None = None
    documents_held: list[str] = Field(default_factory=list)
    sub_city: str | None = None
    goal: str | None = None
    sector: str | None = None
    industry: str | None = None
    conversation_history: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    needs_more_info: bool = False
    missing_slots: list[str] = Field(default_factory=list)
    suggested_goal: str | None = None
    suggested_sub_city: str | None = None
    suggested_documents_held: list[str] = Field(default_factory=list)
    intent: str = "new_roadmap"
    language: str = "en"
    roadmap: dict | None = None


class TranscribeResponse(BaseModel):
    text: str
    detected_language: str = "unknown"
