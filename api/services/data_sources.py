"""
Data sources the admin dashboard manages: each one can be run on demand and
every run is recorded in data_source_runs with its stats or error.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable
from uuid import UUID

from services import catalog_service, custom_sources, graph_admin, rag_service
from services.db import Jsonb, fetch_all, fetch_one

logger = logging.getLogger(__name__)

STALE_AFTER_DAYS = 30
# A run still marked "running" after this long has almost certainly died (worker restart, crash)
STUCK_AFTER_MINUTES = 30


class SourcePaused(RuntimeError):
    """Paused sources can't be run by hand or by the schedule."""


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
    from services import vetting

    stats.update({f"vetting_{k}": v for k, v in vetting.run_daily().items()})
    from services import org_service

    stats["org_changes_went_live"] = org_service.promote_due_changes(force=True)
    stats["org_services_due_for_confirmation"] = org_service.count_services_due_for_confirmation()
    stats["custom_sources_refreshed"] = run_due_custom_sources("schedule:daily maintenance")
    from services import payment_service

    stats.update({f"payouts_{k}": v for k, v in payment_service.check_processing_payouts().items()})
    return stats


# schedule: how celery beat runs it (worker/celery_app.py); "manual" means only "Run now".
# destinations: where the data ends up (catalog, graph, knowledge, records).
SOURCES: dict[str, dict] = {
    "mesob_catalog": {
        "label": "MESOB service catalog",
        "description": "Reads the public MESOB website (mesobcenter.et) and copies every government service it lists: "
        "the institution, requirements, fee, processing time and the MESOB centers that offer it. "
        "It then updates the knowledge graph with the same information.",
        "kind": "scraper",
        "url": "https://mesobcenter.et/service-catalogue",
        "schedule": "daily",
        "destinations": ["catalog", "graph"],
        "run": _run_mesob_catalog,
    },
    "mesob_graph": {
        "label": "MESOB → knowledge graph",
        "description": "Copies the MESOB services we already have into the knowledge graph (services, institutions "
        "and centers, and how they connect) without visiting the MESOB website again.",
        "kind": "graph",
        "schedule": "manual",
        "destinations": ["graph"],
        "run": _run_mesob_graph,
    },
    "mesob_knowledge": {
        "label": "MESOB → AI knowledge base",
        "description": "Turns every MESOB service (requirements, fee, time) into searchable passages so the AI "
        "assistant can answer questions about it and show where the answer came from.",
        "kind": "rag",
        "schedule": "manual",
        "destinations": ["knowledge"],
        "run": _run_mesob_knowledge,
    },
    "compliance_graph": {
        "label": "Compliance dependency graph",
        "description": "Loads the documents, offices and sub-cities a business needs, and which document requires "
        "which. This is what step-by-step roadmaps are built from.",
        "kind": "graph",
        "schedule": "manual",
        "destinations": ["graph"],
        "run": _run_compliance_graph,
    },
    "legal_corpus": {
        "label": "Legal corpus samples",
        "description": "Reloads the selected proclamation excerpts that roadmap steps quote as their legal basis.",
        "kind": "rag",
        "schedule": "manual",
        "destinations": ["knowledge"],
        "run": _run_legal_corpus,
    },
    "stale_check": {
        "label": "Daily maintenance",
        "description": f"Housekeeping: marks documents nobody has checked in {STALE_AFTER_DAYS} days as needing review, "
        "suspends Guday Geday agents whose license has expired, puts scheduled organization changes live, counts "
        "organization services not confirmed in 90 days, and refreshes staff-added sources that are due.",
        "kind": "maintenance",
        "schedule": "daily",
        "destinations": ["graph", "records"],
        "run": _run_stale_check,
    },
}


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _builtin_state() -> dict[str, dict]:
    return {r["source"]: r for r in fetch_all("select source, enabled, paused_by, paused_at from data_source_state")}


def _resolve(source: str) -> dict:
    """Label, run function and on/off state for a built-in or staff-added source. KeyError when unknown."""
    if source in SOURCES:
        state = fetch_one("select enabled from data_source_state where source = %s", (source,))
        return {**SOURCES[source], "enabled": state["enabled"] if state else True}
    if source.startswith("custom:"):
        source_id = source.removeprefix("custom:")
        row = custom_sources.get_custom(source_id) if _is_uuid(source_id) else None
        if row:
            return {"label": row["name"], "enabled": row["enabled"],
                    "run": lambda: custom_sources.run_source(source_id)}
    raise KeyError(source)


def set_paused(source: str, paused: bool, by: str | None) -> None:
    """Pause or resume a source. KeyError when unknown."""
    if source.startswith("custom:"):
        source_id = source.removeprefix("custom:")
        if not _is_uuid(source_id) or not custom_sources.set_enabled(source_id, not paused, by):
            raise KeyError(source)
        return
    if source not in SOURCES:
        raise KeyError(source)
    fetch_one(
        """
        insert into data_source_state (source, enabled, paused_by, paused_at)
        values (%(s)s, %(on)s, case when %(on)s then null else %(by)s end, case when %(on)s then null else now() end)
        on conflict (source) do update set enabled = excluded.enabled,
          paused_by = excluded.paused_by, paused_at = excluded.paused_at
        returning source
        """,
        {"s": source, "on": not paused, "by": by},
    )


def start_run(source: str, triggered_by: str | None) -> dict:
    if not _resolve(source)["enabled"]:
        raise SourcePaused("This source is paused. Resume it before running it.")
    running = fetch_one(
        "select id::text from data_source_runs where source = %s and status = 'running' "
        "and started_at > now() - make_interval(mins => %s)",
        (source, STUCK_AFTER_MINUTES),
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
    try:
        run: Callable[[], dict] = _resolve(source)["run"]
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


def mark_run_failed(run_id: str, by: str | None) -> dict:
    """Close a run that has been "running" too long to still be alive. KeyError / RuntimeError for 404 / 409."""
    row = fetch_one(
        """
        update data_source_runs
        set status = 'failed', finished_at = now(),
            error = 'Marked as failed by ' || coalesce(%(by)s, 'staff') || ': the run stopped responding.'
        where id = %(id)s and status = 'running' and started_at < now() - make_interval(mins => %(mins)s)
        returning id::text, source, status, error, started_at, finished_at
        """,
        {"id": run_id, "by": by, "mins": STUCK_AFTER_MINUTES},
    )
    if row:
        return row
    current = fetch_one("select status from data_source_runs where id = %s", (run_id,))
    if not current:
        raise KeyError(run_id)
    if current["status"] != "running":
        raise RuntimeError("This run has already finished")
    raise RuntimeError(f"This run started less than {STUCK_AFTER_MINUTES} minutes ago; give it more time")


def run_due_custom_sources(triggered_by: str) -> dict:
    """Run every staff-added source whose daily or weekly schedule is due. Used by the worker."""
    out = {"due": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    for source_id in custom_sources.due_for_schedule():
        out["due"] += 1
        key = custom_sources.source_key(source_id)
        try:
            run = start_run(key, triggered_by)
        except (KeyError, RuntimeError):
            out["skipped"] += 1
            continue
        execute_run(run["id"], key)
        status = fetch_one("select status from data_source_runs where id = %s", (run["id"],))["status"]
        out["succeeded" if status == "success" else "failed"] += 1
    return out


HEALTH_WINDOW_DAYS = 30


def _source_health(keys: list[str]) -> dict[str, dict]:
    """Per-source reliability over the last HEALTH_WINDOW_DAYS plus a zero-filled daily series."""
    totals = {
        r["source"]: r
        for r in fetch_all(
            """
            select source,
                   count(*) as runs,
                   count(*) filter (where status = 'success') as successes,
                   count(*) filter (where status = 'failed') as failures,
                   round(avg(extract(epoch from (finished_at - started_at)))
                         filter (where finished_at is not null))::int as avg_duration_s
            from data_source_runs
            where started_at > now() - make_interval(days => %s)
            group by source
            """,
            (HEALTH_WINDOW_DAYS,),
        )
    }
    # "Last" values look at all history so an old failure is still visible
    last = {
        r["source"]: r
        for r in fetch_all(
            """
            select s.source,
                   (select extract(epoch from (finished_at - started_at))::int
                      from data_source_runs where source = s.source and finished_at is not null
                      order by started_at desc limit 1) as last_duration_s,
                   (select max(finished_at) from data_source_runs
                      where source = s.source and status = 'success') as last_success_at,
                   f.finished_at as last_failure_at,
                   f.error as last_failure_error
            from unnest(%s::text[]) s(source)
            left join lateral (
              select finished_at, error from data_source_runs
              where source = s.source and status = 'failed'
              order by started_at desc limit 1
            ) f on true
            """,
            (keys,),
        )
    }
    daily: dict[str, list[dict]] = {k: [] for k in keys}
    for r in fetch_all(
        """
        select s.source, d::date as day,
               count(r.id) filter (where r.status = 'success') as success,
               count(r.id) filter (where r.status = 'failed') as failed
        from unnest(%s::text[]) s(source)
        cross join generate_series(current_date - (%s - 1), current_date, interval '1 day') d
        left join data_source_runs r
          on r.source = s.source and r.started_at >= d and r.started_at < d + interval '1 day'
        group by s.source, d
        order by s.source, d
        """,
        (keys, HEALTH_WINDOW_DAYS),
    ):
        daily[r["source"]].append({"day": r["day"], "success": r["success"], "failed": r["failed"]})

    out = {}
    for key in keys:
        t, l = totals.get(key, {}), last.get(key, {})
        successes, failures = t.get("successes", 0), t.get("failures", 0)
        finished = successes + failures
        out[key] = {
            "windowDays": HEALTH_WINDOW_DAYS,
            "runs": t.get("runs", 0),
            "successes": successes,
            "failures": failures,
            "successRate": round(successes / finished, 4) if finished else None,
            "avgDurationS": t.get("avg_duration_s"),
            "lastDurationS": l.get("last_duration_s"),
            "lastSuccessAt": l.get("last_success_at"),
            "lastFailureAt": l.get("last_failure_at"),
            "lastFailureError": l.get("last_failure_error"),
            "daily": daily[key],
        }
    return out


def list_sources() -> list[dict]:
    last_runs = {
        r["source"]: r
        for r in fetch_all(
            """
            select distinct on (source) id::text, source, status, stats, error,
                   triggered_by, started_at, finished_at,
                   extract(epoch from (coalesce(finished_at, now()) - started_at))::int as duration_s
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
    customs = custom_sources.list_custom()
    chunks = custom_sources.count_chunks([c["id"] for c in customs])
    state = _builtin_state()
    entries: list[tuple[str, dict]] = []
    for key, meta in SOURCES.items():
        st = state.get(key, {})
        entries.append((key, {
            "label": meta["label"],
            "description": meta["description"],
            "kind": meta["kind"],
            "url": meta.get("url"),
            "builtIn": True,
            "schedule": meta["schedule"],
            "destinations": meta["destinations"],
            "enabled": st.get("enabled", True),
            "pausedBy": st.get("paused_by"),
            "pausedAt": st.get("paused_at"),
            "custom": None,
        }))
    for c in customs:
        entries.append((custom_sources.source_key(c["id"]), {
            "label": c["name"],
            "description": c["description"],
            "kind": c["kind"],
            "url": c["url"],
            "builtIn": False,
            "schedule": c["schedule"],
            "destinations": ["knowledge"],
            "enabled": c["enabled"],
            "pausedBy": c["paused_by"],
            "pausedAt": c["paused_at"],
            "custom": {**c, "passages": chunks.get(c["id"], 0)},
        }))
    health = _source_health([k for k, _ in entries])
    out = []
    for key, item in entries:
        counts = success_counts.get(key, {})
        out.append({
            "id": key,
            **item,
            "lastRun": last_runs.get(key),
            "successes": counts.get("successes", 0),
            "failures": counts.get("failures", 0),
            "lastSuccessAt": counts.get("last_success_at"),
            "health": health[key],
        })
    return out


_RUN_FILTER = """
    where (%(source)s::text is null or source = %(source)s)
      and (%(status)s::text is null or status = %(status)s)
      and (%(date_from)s::date is null or started_at >= %(date_from)s::date)
      and (%(date_to)s::date is null or started_at < %(date_to)s::date + 1)
"""


def _labels(sources: set[str]) -> dict[str, str]:
    """Readable names for run rows, including staff-added sources (and ones since deleted)."""
    labels = {k: v["label"] for k, v in SOURCES.items() if k in sources}
    ids = [s.removeprefix("custom:") for s in sources if s.startswith("custom:")]
    if ids:
        rows = fetch_all(
            "select id::text, name from custom_data_sources where id::text = any(%s)", (ids,)
        )
        names = {r["id"]: r["name"] for r in rows}
        for i in ids:
            labels[f"custom:{i}"] = names.get(i, "Deleted source")
    return labels


def list_runs(
    source: str | None = None,
    limit: int = 50,
    *,
    status: str | None = None,
    offset: int = 0,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    rows = fetch_all(
        f"""
        select id::text, source, status, stats, error, triggered_by, started_at, finished_at,
               extract(epoch from (coalesce(finished_at, now()) - started_at))::int as duration_s
        from data_source_runs
        {_RUN_FILTER}
        order by started_at desc, id desc
        limit %(limit)s offset %(offset)s
        """,
        {"source": source, "status": status, "date_from": date_from, "date_to": date_to,
         "limit": limit, "offset": offset},
    )
    labels = _labels({r["source"] for r in rows})
    for r in rows:
        r["source_label"] = labels.get(r["source"], r["source"])
    return rows


def page_runs(
    source: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """One page of run history, newest first, with the total for the same filters."""
    params = {"source": source, "status": status, "date_from": date_from, "date_to": date_to}
    total = fetch_one(f"select count(*) as c from data_source_runs {_RUN_FILTER}", params)["c"]
    items = list_runs(source, limit, status=status, offset=offset, date_from=date_from, date_to=date_to)
    return {"items": items, "total": total}
