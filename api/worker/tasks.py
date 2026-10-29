import logging

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_source(source: str, triggered_by: str) -> dict:
    """Same pipeline the admin dashboard runs, recorded in data_source_runs."""
    from database.database import initiate_database
    from services import data_sources

    initiate_database()
    run = data_sources.start_run(source, triggered_by)
    data_sources.execute_run(run["id"], source)
    runs = data_sources.list_runs(source, limit=1)
    return runs[0] if runs else {"source": source}


@celery_app.task(name="worker.tasks.scrape_government_source", bind=True)
def scrape_government_source(self, source: str) -> dict:
    """Scrape a government source. Only MESOB has a live scraper today."""
    logger.info("Starting scrape for source=%s task_id=%s", source, self.request.id)
    if source == "mesob":
        return _run_source("mesob_catalog", f"celery:{self.request.id}")
    return {"source": source, "status": "not_implemented", "task_id": self.request.id}


@celery_app.task(name="worker.tasks.ingest_legal_corpus", bind=True)
def ingest_legal_corpus(self, source: str = "all") -> dict:
    logger.info("Starting ingest source=%s task_id=%s", source, self.request.id)
    results = {}
    if source in ("graph", "all", "seed"):
        results["compliance_graph"] = _run_source("compliance_graph", f"celery:{self.request.id}")
    if source in ("rag", "legal", "all"):
        results["legal_corpus"] = _run_source("legal_corpus", f"celery:{self.request.id}")
    if source in ("mesob", "all"):
        results["mesob_knowledge"] = _run_source("mesob_knowledge", f"celery:{self.request.id}")
    return {"source": source, "results": results, "task_id": self.request.id}


@celery_app.task(name="worker.tasks.flag_stale_graph_nodes", bind=True)
def flag_stale_graph_nodes(self) -> dict:
    """Mark Document nodes where last_verified > 30 days as stale."""
    logger.info("Checking stale nodes task_id=%s", self.request.id)
    return _run_source("stale_check", f"celery:{self.request.id}")
