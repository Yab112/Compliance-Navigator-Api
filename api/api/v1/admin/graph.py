"""Admin: the knowledge graph (diagram, documents table, MESOB institutions)."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from core.deps import require_admin
from schemas.auth_user import AuthUser
from services import graph_admin

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/graph", tags=["Admin Knowledge Graph"], dependencies=[Depends(require_admin)])

# Sanity ceilings for the edit form: no government document costs a million birr or takes 5 years
MAX_FEE_ETB = 1_000_000
MAX_DAYS = 1_825


def _ok(payload):
    return {"message": "success", "payload": payload}


@router.get("/stats")
def graph_stats():
    return _ok(graph_admin.graph_counts())


@router.get("/view")
def graph_view():
    return _ok(graph_admin.compliance_graph_view())


@router.get("/documents")
def graph_documents(
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(None, pattern="^(verified|stale)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return _ok(graph_admin.page_documents(q, status, limit, offset))


@router.get("/documents/{doc_id}")
def graph_document(doc_id: str):
    doc = graph_admin.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _ok({"document": doc})


def _clean_lines(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return [v.strip()[:300] for v in values if v and v.strip()][:50]


class DocumentPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    name_am: str | None = Field(None, max_length=200)
    issuing_authority: str | None = Field(None, max_length=200)
    form_code: str | None = Field(None, max_length=60)
    fee_etb: int | None = Field(None, ge=0, le=MAX_FEE_ETB)
    avg_processing_days: int | None = Field(None, ge=0, le=MAX_DAYS)
    legal_basis: str | None = Field(None, max_length=300)
    source_url: str | None = Field(None, max_length=500)
    required_input_labels: list[str] | None = Field(None, max_length=50)
    rejection_reasons: list[str] | None = Field(None, max_length=50)
    mark_verified: bool = False

    @field_validator("source_url")
    @classmethod
    def _http_url(cls, v: str | None) -> str | None:
        if v and not re.match(r"^https?://[^\s]+$", v.strip()):
            raise ValueError("Source link must start with http:// or https://")
        return v.strip() if v else v

    @field_validator("required_input_labels", "rejection_reasons")
    @classmethod
    def _lines(cls, v: list[str] | None) -> list[str] | None:
        return _clean_lines(v)


@router.patch("/documents/{doc_id}")
def patch_document(doc_id: str, body: DocumentPatch, admin: AuthUser = Depends(require_admin)):
    changes = body.model_dump(exclude_unset=True, exclude={"mark_verified"})
    doc = graph_admin.update_document(doc_id, changes, mark_verified=body.mark_verified, actor=admin.email)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    log.info("graph document %s edited by %s (fields=%s, verified=%s)",
             doc_id, admin.email, sorted(changes), body.mark_verified)
    return _ok({"document": doc})


@router.get("/institutions")
def graph_institutions(
    q: str | None = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return _ok(graph_admin.page_institutions(q, limit, offset))

