"""Marketplace overview numbers for the admin dashboard."""

from __future__ import annotations

from services.db import fetch_all, fetch_one

from .common import TODAY

# ---------------------------------------------------------------- stats


def marketplace_stats() -> dict:
    """Admin overview numbers (keeps the shape the dashboard already reads)."""
    agents = {r["status"]: r["c"] for r in fetch_all("select status, count(*) as c from providers group by status")}
    cases = {r["status"]: r["c"] for r in fetch_all("select status, count(*) as c from engagements group by status")}
    by_type = fetch_all(
        "select provider_type, entity_type, count(*) as c from providers where status = 'approved' group by 1, 2"
    )
    by_area = fetch_all(
        "select unnest(service_areas) as sub_city, count(*) as c from providers where status = 'approved' "
        "group by 1 order by c desc"
    )
    expiring = fetch_one(
        "select count(*) as c from providers where status = 'approved' "
        f"and license_expires_at between {TODAY} and {TODAY} + 30"
    )["c"]
    extra = fetch_one(
        """
        select
          (select count(*) from providers where external_license_status = 'pending') as licenses_pending,
          (select count(*) from engagements where disputed and dispute_status = 'open') as open_disputes,
          (select count(*) from reviews) as reviews,
          (select count(*) from reviews where hidden) as hidden_reviews
        """
    )
    return {
        "agents": agents, "cases": cases, "approvedBySubCity": by_area,
        "licensesExpiringIn30Days": expiring, "byType": by_type,
        "licensesPending": extra["licenses_pending"], "openDisputes": extra["open_disputes"],
        "reviews": extra["reviews"], "hiddenReviews": extra["hidden_reviews"],
    }
