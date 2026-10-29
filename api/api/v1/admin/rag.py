from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.deps import require_admin
from schemas.auth_user import AuthUser
from services.rag_service import ingest_text, search_legal_chunks

router = APIRouter(prefix="/admin/rag", tags=["Admin RAG"])


class IngestTextRequest(BaseModel):
    text: str = Field(..., min_length=20)
    document_id: str | None = None
    service_id: str | None = None
    proclamation_number: str | None = None
    article_number: str | None = None
    issuing_body: str | None = None
    source_url: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    sector_tags: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3)
    document_id: str | None = None
    service_id: str | None = None
    limit: int = Field(default=5, ge=1, le=20)


@router.post("/ingest", status_code=201)
def ingest_legal_text(
    body: IngestTextRequest,
    _: AuthUser = Depends(require_admin),
):
    result = ingest_text(
        body.text,
        document_id=body.document_id,
        service_id=body.service_id,
        proclamation_number=body.proclamation_number,
        article_number=body.article_number,
        issuing_body=body.issuing_body,
        topic_tags=body.topic_tags,
        sector_tags=body.sector_tags,
        source_url=body.source_url,
    )
    return {"message": "success", "payload": result}


@router.post("/search")
def search_legal_text(
    body: SearchRequest,
    _: AuthUser = Depends(require_admin),
):
    hits = search_legal_chunks(
        body.query,
        document_id=body.document_id,
        service_id=body.service_id,
        limit=body.limit,
    )
    return {"message": "success", "payload": {"results": hits}}
