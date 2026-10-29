from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core.deps import require_admin
from schemas.auth_user import AuthUser
from worker.tasks import (
    flag_stale_graph_nodes,
    ingest_legal_corpus,
    scrape_government_source,
)

router = APIRouter(prefix="/admin/jobs", tags=["Admin Jobs"])

ALLOWED_SOURCES = {"mesob", "motri", "erca", "nbe", "negarit", "eca", "addis_ababa"}


class TaskEnqueueResponse(BaseModel):
    message: str
    payload: dict


class ScrapeJobRequest(BaseModel):
    source: str = Field(..., examples=["motri"])


class IngestJobRequest(BaseModel):
    source: str = Field(default="all", description="Use 'graph' or 'seed' to run Neo4j seed")


def _task_response(task_id: str, task_name: str) -> TaskEnqueueResponse:
    return TaskEnqueueResponse(
        message="Task enqueued",
        payload={"task_id": task_id, "task_name": task_name},
    )


@router.post("/scrape", status_code=status.HTTP_202_ACCEPTED)
def enqueue_scrape(
    body: ScrapeJobRequest,
    _: AuthUser = Depends(require_admin),
):
    source = body.source.lower().strip()
    if source not in ALLOWED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown source. Allowed: {sorted(ALLOWED_SOURCES)}",
        )
    result = scrape_government_source.delay(source)
    return _task_response(result.id, "scrape_government_source")


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
def enqueue_ingest(
    body: IngestJobRequest,
    _: AuthUser = Depends(require_admin),
):
    result = ingest_legal_corpus.delay(body.source)
    return _task_response(result.id, "ingest_legal_corpus")


@router.post("/stale-check", status_code=status.HTTP_202_ACCEPTED)
def enqueue_stale_check(_: AuthUser = Depends(require_admin)):
    result = flag_stale_graph_nodes.delay()
    return _task_response(result.id, "flag_stale_graph_nodes")
