import logging

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.tasks.scrape_government_source", bind=True)
def scrape_government_source(self, source: str) -> dict:
    """
    Background scrape for MoTRI, ERCA, NBE, Negarit, etc.
    Long-running Playwright / PDF jobs must not block the FastAPI event loop.
    """
    logger.info("Starting scrape for source=%s task_id=%s", source, self.request.id)
    # TODO: call scrapers/{source}_scraper.py and return ingest stats
    return {"source": source, "status": "queued_stub", "task_id": self.request.id}


@celery_app.task(name="worker.tasks.ingest_legal_corpus", bind=True)
def ingest_legal_corpus(self, source: str = "all") -> dict:
    """Seed graph or chunk legal text into Qdrant when source=graph."""
    logger.info("Starting ingest source=%s task_id=%s", source, self.request.id)
    if source in ("graph", "all", "seed"):
        try:
            from scripts.seed_graph import main as seed_main

            seed_main()
            return {"source": source, "status": "graph_seeded", "task_id": self.request.id}
        except Exception as exc:
            logger.exception("Graph seed failed")
            return {
                "source": source,
                "status": "error",
                "error": str(exc),
                "task_id": self.request.id,
            }
    if source in ("rag", "legal", "all"):
        try:
            from scripts.seed_rag_samples import main as seed_rag

            seed_rag()
            return {"source": source, "status": "rag_seeded", "task_id": self.request.id}
        except Exception as exc:
            logger.exception("RAG seed failed")
            return {
                "source": source,
                "status": "error",
                "error": str(exc),
                "task_id": self.request.id,
            }
    return {"source": source, "status": "queued_stub", "task_id": self.request.id}


@celery_app.task(name="worker.tasks.flag_stale_graph_nodes", bind=True)
def flag_stale_graph_nodes(self) -> dict:
    """Mark Document nodes where last_verified > 30 days as STALE."""
    logger.info("Checking stale nodes task_id=%s", self.request.id)
    return {"status": "queued_stub", "task_id": self.request.id}
