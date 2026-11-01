"""The public marketplace: listing, profiles, reviews and recent jobs."""

from __future__ import annotations

from services import trust_score
from services.db import fetch_all, fetch_one

from .common import LIVE, PUBLIC_COLUMNS
from .profile import _services
from .teams import agency_of, team

# ---------------------------------------------------------------- public marketplace


SORTS = {
    "score": "p.trust_score desc, p.rating_count desc",
    "rating": "p.rating_avg desc, p.rating_count desc",
    "reviews": "p.rating_count desc, p.trust_score desc",
    "newest": "p.approved_at desc nulls last",
}


def public_list(
    *, provider_type: str | None = None, entity_type: str | None = None, specialty: str | None = None,
    service_id: str | None = None, area: str | None = None, min_score: int | None = None,
    verified_only: bool = False, q: str | None = None, sort: str = "score",
    limit: int = 24, offset: int = 0, language: str | None = None, max_fee: int | None = None,
) -> dict:
    where, params = [LIVE], {}
    if language:
        where.append("%(language)s = any(p.languages)")
        params["language"] = language
    if max_fee is not None:
        # Percent commissions aren't comparable with birr amounts, so they stay in the list
        where.append("(p.fee_unit = 'percent' or p.fee_from is null or p.fee_from <= %(max_fee)s)")
        params["max_fee"] = max_fee
    for key, val in (("provider_type", provider_type), ("entity_type", entity_type)):
        if val:
            where.append(f"p.{key} = %({key})s")
            params[key] = val
    if specialty:
        where.append("%(specialty)s = any(p.specialties)")
        params["specialty"] = specialty
    if service_id:
        where.append("%(service_id)s = any(p.service_ids)")
        params["service_id"] = service_id
    if area:
        where.append("(%(area)s = any(p.service_areas) or 'nationwide' = any(p.service_areas))")
        params["area"] = area
    if min_score:
        where.append("p.trust_score >= %(min_score)s")
        params["min_score"] = min_score
    if verified_only:
        where.append("p.national_id_verified")
    if q:
        where.append(
            "(p.display_name ilike %(q)s or p.display_name_am ilike %(q)s or p.legal_name ilike %(q)s "
            "or p.headline ilike %(q)s or p.registration_no ilike %(q)s)"
        )
        params["q"] = f"%{q}%"
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from providers p where {clause}", params)["c"]
    items = fetch_all(
        f"select {PUBLIC_COLUMNS} from providers p where {clause} "
        f"order by {SORTS.get(sort, SORTS['score'])}, p.display_name limit %(limit)s offset %(offset)s",
        {**params, "limit": limit, "offset": offset},
    )
    counts = {
        r["provider_type"]: r["c"]
        for r in fetch_all(f"select p.provider_type, count(*) as c from providers p where {LIVE} group by 1")
    }
    return {"total": total, "items": items, "countsByType": counts}


def public_profile(slug: str) -> dict | None:
    provider = fetch_one(
        f"select {PUBLIC_COLUMNS} from providers p where (p.slug = %s or p.id::text = %s) and {LIVE}",
        (slug, slug),
    )
    if not provider:
        return None
    provider["services"] = _services(provider["service_ids"])
    provider["team"] = team(provider["id"]) if provider["provider_type"] == "agency" else []
    provider["agency"] = agency_of(provider["id"])
    provider["licences"] = licences(provider["id"]) if provider["provider_type"] == "advisor" else []
    provider["reviews"] = list_reviews(provider["id"], limit=10)
    provider["is_new"] = provider["rating_count"] < trust_score.NEW_UNTIL_REVIEWS
    provider["rating_breakdown"] = fetch_one(
        """
        select avg(communication)::float as communication, avg(fee_honesty)::float as fee_honesty,
               avg(speed)::float as speed, avg(outcome)::float as outcome,
               avg(case when would_hire_again then 1.0 when would_hire_again = false then 0 end)::float
                 as would_hire_again
        from reviews where provider_id = %s and not hidden
        """,
        (provider["id"],),
    )
    counts = {
        r["rating"]: r["c"]
        for r in fetch_all(
            "select rating, count(*) as c from reviews where provider_id = %s and not hidden group by rating",
            (provider["id"],),
        )
    }
    provider["rating_distribution"] = {str(n): counts.get(n, 0) for n in range(5, 0, -1)}
    return provider


def licences(provider_id: str) -> list[dict]:
    """Professional licences staff verified and still in date: what, and until when. Never the copy
    itself or its number."""
    from services.vetting.rules import KINDS, LICENCE_KINDS

    rows = fetch_all(
        "select d.kind, d.expires_on as valid_until, d.reviewed_at as verified_at from provider_documents d "
        "where d.provider_id = %s and d.status = 'verified' and d.kind = any(%s) "
        "and (d.expires_on is null or d.expires_on >= current_date) order by d.kind",
        (provider_id, list(LICENCE_KINDS)),
    )
    return [{**r, "label": KINDS[r["kind"]].label} for r in rows]


REVIEW_SORTS = {
    "recent": "r.created_at desc",
    "highest": "r.rating desc, r.created_at desc",
    "lowest": "r.rating asc, r.created_at desc",
}


def list_reviews(
    provider_id: str, *, limit: int = 10, offset: int = 0, include_hidden: bool = False, sort: str = "recent"
) -> dict:
    hidden = "" if include_hidden else "and not r.hidden"
    total = fetch_one(
        f"select count(*) as c from reviews r where r.provider_id = %s {hidden}", (provider_id,)
    )["c"]
    # Staff also see the job title; the public never does, since clients write it freely and it can name people
    extra = ", r.hidden, r.hidden_reason, r.hidden_by, r.hidden_at, e.title as job_title" if include_hidden else ""
    items = fetch_all(
        f"""
        select r.id::text, r.rating, r.communication, r.fee_honesty, r.speed, r.outcome,
          r.would_hire_again, r.comment, r.reply, r.replied_at, r.created_at,
          e.service_name, (e.payment_status = 'paid') as paid_through_platform,
          -- First name and initial only: reviews are public
          coalesce(split_part(u.fullname, ' ', 1) || coalesce(' ' || left(split_part(u.fullname, ' ', 2), 1) || '.', ''),
                   'Client') as client_name
          {extra}
        from reviews r
        join engagements e on e.id = r.engagement_id
        left join users u on u.id = r.client_user_id
        where r.provider_id = %s {hidden}
        order by {REVIEW_SORTS.get(sort, REVIEW_SORTS["recent"])} limit %s offset %s
        """,
        (provider_id, limit, offset),
    )
    return {"total": total, "items": items}


def recent_jobs(provider_id: str, limit: int = 5) -> list[dict]:
    """Completed work, for the public: what and when, with the client's rating. Never who, and never the
    client's own words for the job (they can name people): the title is the service or specialty."""
    return fetch_all(
        """
        select coalesce(e.service_name, initcap(replace(e.specialty, '_', ' ')), 'Completed job') as title,
               e.service_name, e.sub_city, coalesce(e.completed_at, e.updated_at) as completed_at,
               r.rating, r.comment
        from engagements e left join reviews r on r.engagement_id = e.id and not r.hidden
        where e.provider_id = %s and e.status = 'completed'
        order by coalesce(e.completed_at, e.updated_at) desc limit %s
        """,
        (provider_id, limit),
    )
