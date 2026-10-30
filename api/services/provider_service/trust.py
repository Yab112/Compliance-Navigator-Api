"""Trust score and job success, recomputed for a provider and its agencies."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from services import platform_settings, trust_score, vetting
from services.db import connection

from .readiness import refresh_readiness

# ---------------------------------------------------------------- trust score


def _provider_group(conn, provider_id: str) -> list[str]:
    """An agency's stats include its active members' work."""
    rows = conn.execute(
        "select member_id::text from provider_members where agency_id = %s and status = 'active'",
        (provider_id,),
    ).fetchall()
    return [provider_id] + [r["member_id"] for r in rows]


# Job Success, over closed jobs in the last 24 months:
#   success  closed, no upheld complaint, rated 4-5 stars or not rated
#   failure  upheld complaint, or rated 1-2 stars
#   neutral  3 stars (not counted); requests cancelled before payment never close, so never count
# Shown once a provider has enough closed jobs (platform setting job_success_min_jobs); "New" before that.
JOB_SUCCESS_SQL = """
select count(*) as closed,
       count(*) filter (where not coalesce(e.disputed and e.dispute_status = 'upheld', false)
                          and (r.rating is null or r.rating >= 4)) as success,
       count(*) filter (where coalesce(e.disputed and e.dispute_status = 'upheld', false)
                          or r.rating <= 2) as failure
from engagements e left join reviews r on r.engagement_id = e.id and not r.hidden
where e.provider_id = any(%s::uuid[])
  and ((e.status = 'completed' and e.client_confirmed_at > now() - interval '24 months')
       or (e.disputed and e.dispute_status = 'upheld' and e.updated_at > now() - interval '24 months'))
"""


def recompute(provider_id: str) -> dict | None:
    with connection() as conn, conn.transaction():
        p = conn.execute(
            "select id::text, provider_type, entity_type, phone, tin, trade_license_no, "
            "national_id_verified, external_license_status, approved_at from providers where id = %s",
            (provider_id,),
        ).fetchone()
        if not p:
            return None
        group = _provider_group(conn, provider_id)
        reviews = conn.execute(
            "select count(*) as n, coalesce(sum(rating), 0) as s, avg(rating)::float as avg "
            "from reviews where provider_id = any(%s::uuid[]) and not hidden",
            (group,),
        ).fetchone()
        jobs = conn.execute(
            """
            select
              -- closed: delivered and confirmed by the client (or closed automatically)
              count(*) filter (where status = 'completed' and client_confirmed_at is not null) as completed,
              count(*) filter (where status = 'declined'
                or (status = 'cancelled' and accepted_at is not null)) as failed,
              count(*) filter (where disputed and dispute_status = 'upheld') as upheld,
              avg(extract(epoch from accepted_at - created_at) / 3600)
                filter (where accepted_at is not null) as response_hours
            from engagements where provider_id = any(%s::uuid[])
            """,
            (group,),
        ).fetchone()
        js = conn.execute(JOB_SUCCESS_SQL, (group,)).fetchone()
        job_success = (round(100 * js["success"] / (js["success"] + js["failure"]))
                       if js["closed"] >= platform_settings.get_int("job_success_min_jobs") and js["success"] + js["failure"] else None)
        suspensions = conn.execute(
            "select count(*) as c from provider_events where provider_id = %s and action = 'suspend'",
            (provider_id,),
        ).fetchone()["c"]
        checked = vetting.verified_kinds(conn, provider_id)
        result = trust_score.compute({
            "review_count": reviews["n"], "review_sum": float(reviews["s"]),
            "fayda_verified": p["national_id_verified"], "has_phone": bool(p["phone"]),
            "has_tin": bool(p["tin"]), "has_trade_license": bool(p["trade_license_no"]),
            "entity_type": p["entity_type"],
            "external_license_verified": p["external_license_status"] == "verified",
            "completed": jobs["completed"], "failed": jobs["failed"] + js["failure"],
            "approved_at": p["approved_at"], "upheld_disputes": jobs["upheld"],
            "suspensions": suspensions,
            "police_clearance_verified": "police_clearance" in checked,
            "education_verified": "education" in checked,
        })
        conn.execute(
            """
            update providers set trust_score = %s, score_breakdown = %s, rating_avg = %s,
              rating_count = %s, completed_count = %s, response_hours = %s, job_success = %s, closed_jobs = %s
            where id = %s
            """,
            (result["score"], Jsonb(result["parts"]), round(reviews["avg"] or 0, 2), reviews["n"],
             jobs["completed"], jobs["response_hours"], job_success, js["closed"], provider_id),
        )
        agencies = conn.execute(
            "select agency_id::text from provider_members where member_id = %s and status = 'active'",
            (provider_id,),
        ).fetchall()
    for a in agencies:
        recompute(a["agency_id"])
    refresh_readiness(provider_id)
    return result
