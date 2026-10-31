import logging

from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_source(source: str, triggered_by: str) -> dict:
    """Same pipeline the admin dashboard runs, recorded in data_source_runs."""
    from services import data_sources

    try:
        run = data_sources.start_run(source, triggered_by)
    except data_sources.SourcePaused:
        logger.info("Skipping %s: paused by staff", source)
        return {"source": source, "status": "paused"}
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


@celery_app.task(name="worker.tasks.run_scheduled_custom_sources", bind=True)
def run_scheduled_custom_sources(self) -> dict:
    """Refresh staff-added data sources whose daily or weekly schedule is due."""
    from services import data_sources

    return data_sources.run_due_custom_sources(f"schedule:celery:{self.request.id}")


@celery_app.task(name="worker.tasks.check_processing_payouts", bind=True)
def check_processing_payouts(self) -> dict:
    """Record payouts Chapa has finished sending (or failed to send)."""
    from services import payment_service

    return payment_service.check_processing_payouts()


@celery_app.task(name="worker.tasks.check_paid_payouts", bind=True)
def check_paid_payouts(self) -> dict:
    """Flag paid transfers Chapa now reports failed or returned; changes no money."""
    from services import payment_service

    return payment_service.check_paid_payouts()


@celery_app.task(name="worker.tasks.check_sending_refunds", bind=True)
def check_sending_refunds(self) -> dict:
    """Settle refunds whose gateway answer was never recorded; never sends a refund again."""
    from services import payment_service

    return payment_service.check_sending_refunds()


@celery_app.task(name="worker.tasks.check_pending_payments", bind=True)
def check_pending_payments(self) -> dict:
    """Record checkouts the client paid whose Chapa webhook never arrived, and give up on abandoned ones."""
    from services import payment_service

    return payment_service.check_pending_payments()
