"""
Data sources the admin dashboard manages: each one can be run on demand and
every run is recorded in data_source_runs with its stats or error.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable

from services import catalog_service, graph_admin, rag_service
from services.db import Jsonb, fetch_all, fetch_one

logger = logging.getLogger(__name__)

STALE_AFTER_DAYS = 30


def _run_mesob_catalog() -> dict:
    """Scrape mesobcenter.et, refresh the snapshot, and mirror it into Neo4j."""
    from scrapers import mesob

    stats = mesob.sync()
    catalog_service.reload_catalog()
    stats["graph"] = graph_admin.sync_catalog_to_graph()
    return stats


def _run_mesob_graph() -> dict:
    """Mirror the existing snapshot into Neo4j without re-scraping."""
    catalog_service.reload_catalog()
    return graph_admin.sync_catalog_to_graph()


def _run_mesob_knowledge() -> dict:
    """Embed every MESOB service so the AI assistant can cite it."""
    removed = rag_service.delete_chunks(service_id_prefix="mesob-")
    inserted = 0
    for service in catalog_service.load_catalog()["services"]:
        text = catalog_service.service_as_text(service)
        result = rag_service.ingest_text(
            text,
            service_id=service["id"],
            issuing_body=service.get("institution_name"),
            source_url=service.get("source_url"),
            language=service["language"],
            topic_tags=["mesob"],
        )
        inserted += result.get("chunks_inserted", 0)
    return {"chunks_removed": removed, "chunks_inserted": inserted}


def _run_compliance_graph() -> dict:
    from scripts.seed_graph import main as seed_graph

    seed_graph()
    return graph_admin.graph_counts()


def _run_legal_corpus() -> dict:
    from scripts.seed_rag_samples import SAMPLES

    removed = sum(rag_service.delete_chunks(service_id=s["service_id"]) for s in SAMPLES)
    inserted = sum(rag_service.ingest_text(**s).get("chunks_inserted", 0) for s in SAMPLES)
    return {"chunks_removed": removed, "chunks_inserted": inserted, "samples": len(SAMPLES)}


def _run_stale_check() -> dict:
    from services.provider_service import expire_licenses

    cutoff = date.today() - timedelta(days=STALE_AFTER_DAYS)
    stats = graph_admin.flag_stale_documents(cutoff)
    stats["agent_licenses_expired"] = expire_licenses()
    from services import org_service

    stats["org_changes_went_live"] = org_service.promote_due_changes(force=True)
    stats["org_services_due_for_confirmation"] = org_service.count_services_due_for_confirmation()
    return stats


SOURCES: dict[str, dict] = {
    "mesob_catalog": {
        "label": "MESOB service catalog",
        "description": "Scrapes mesobcenter.et (institutions, services, fees, processing times, centers) and mirrors it into the Neo4j graph.",
        "kind": "scraper",
        "url": "https://mesobcenter.et/service-catalogue",
        "run": _run_mesob_catalog,
    },
    "mesob_graph": {
        "label": "MESOB → knowledge graph",
        "description": "Re-links the current MESOB snapshot into Neo4j (GovService, Institution, MesobCenter nodes) without scraping.",
        "kind": "graph",
        "run": _run_mesob_graph,
    },
    "mesob_knowledge": {
        "label": "MESOB → AI knowledge base",
        "description": "Embeds every MESOB service (requirements, fee, time) into pgvector so the assistant can ground answers in it.",
        "kind": "rag",
        "run": _run_mesob_knowledge,
    },
    "compliance_graph": {
        "label": "Compliance dependency graph",
        "description": "Seeds documents, offices, sub-cities and REQUIRES edges used to build step-by-step roadmaps.",
        "kind": "graph",
        "run": _run_compliance_graph,
    },
    "legal_corpus": {
        "label": "Legal corpus samples",
        "description": "Re-ingests the curated proclamation excerpts used for legal citations on roadmap steps.",
        "kind": "rag",
        "run": _run_legal_corpus,
    },
    "stale_check": {
        "label": "Daily maintenance",
        "description": f"Flags Document nodes not verified in the last {STALE_AFTER_DAYS} days and suspends Guday Geday agents whose license has expired, puts scheduled organization changes live and counts organization services not confirmed in 90 days.",
        "kind": "maintenance",
        "run": _run_stale_check,
    },
}


def start_run(source: str, triggered_by: str | None) -> dict:
    if source not in SOURCES:
        raise KeyError(source)
    running = fetch_one(
        "select id::text from data_source_runs where source = %s and status = 'running' "
        "and started_at > now() - interval '30 minutes'",
        (source,),
    )
    if running:
        raise RuntimeError("A run for this source is already in progress")
    return fetch_one(
        "insert into data_source_runs (source, triggered_by) values (%s, %s) "
        "returning id::text, source, status, started_at",
        (source, triggered_by),
    )


def execute_run(run_id: str, source: str) -> None:
    """Runs in a background task; always records the outcome."""
    run: Callable[[], dict] = SOURCES[source]["run"]
    try:
        stats = run()
        fetch_one(
            "update data_source_runs set status = 'success', stats = %s, finished_at = now() "
            "where id = %s returning id",
            (Jsonb(stats), run_id),
        )
    except Exception as exc:
        logger.exception("Data source run %s (%s) failed", run_id, source)
        fetch_one(
            "update data_source_runs set status = 'failed', error = %s, finished_at = now() "
            "where id = %s returning id",
            (str(exc)[:2000], run_id),
        )


def list_sources() -> list[dict]:
    last_runs = {
        r["source"]: r
        for r in fetch_all(
            """
            select distinct on (source) id::text, source, status, stats, error,
                   triggered_by, started_at, finished_at
            from data_source_runs
            order by source, started_at desc
            """
        )
    }
    success_counts = {
        r["source"]: r
        for r in fetch_all(
            """
            select source,
                   count(*) filter (where status = 'success') as successes,
                   count(*) filter (where status = 'failed') as failures,
                   max(finished_at) filter (where status = 'success') as last_success_at
            from data_source_runs group by source
            """
        )
    }
    out = []
    for key, meta in SOURCES.items():
        counts = success_counts.get(key, {})
        out.append({
            "id": key,
            "label": meta["label"],
            "description": meta["description"],
            "kind": meta["kind"],
            "url": meta.get("url"),
            "lastRun": last_runs.get(key),
            "successes": counts.get("successes", 0),
            "failures": counts.get("failures", 0),
            "lastSuccessAt": counts.get("last_success_at"),
        })
    return out


def list_runs(source: str | None = None, limit: int = 50) -> list[dict]:
    return fetch_all(
        """
        select id::text, source, status, stats, error, triggered_by, started_at, finished_at,
               extract(epoch from (coalesce(finished_at, now()) - started_at))::int as duration_s
        from data_source_runs
        where %(source)s::text is null or source = %(source)s
        order by started_at desc
        limit %(limit)s
        """,
        {"source": source, "limit": limit},
    )
