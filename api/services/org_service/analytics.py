"""Usage counts for organizations' services."""

from __future__ import annotations

import logging

from services.db import execute, fetch_all

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- analytics


def record_stat(service_id: str, metric: str) -> None:
    try:
        execute(
            """
            insert into org_service_stats (service_id, metric, day, count) values (%s, %s, current_date, 1)
            on conflict (service_id, metric, day) do update set count = org_service_stats.count + 1
            """,
            (service_id, metric),
        )
    except Exception:
        log.exception("Could not record %s for %s", metric, service_id)


def org_analytics(org_id: str) -> dict:
    rows = fetch_all(
        """
        select s.id::text as service_id, s.name,
          coalesce(sum(st.count) filter (where st.metric = 'view'), 0) as views,
          coalesce(sum(st.count) filter (where st.metric = 'eligibility_check'), 0) as eligibility_checks,
          coalesce(sum(st.count) filter (where st.metric = 'path_view'), 0) as path_views,
          coalesce(sum(st.count) filter (where st.day > current_date - 30), 0) as last_30_days
        from org_services s left join org_service_stats st on st.service_id = s.id
        where s.org_id = %s and s.status <> 'archived'
        group by s.id, s.name order by views desc
        """,
        (org_id,),
    )
    return {"services": rows}
