"""Provider marketplace: Guday Geday agents and agencies that get things done with offices.

Property and car brokers (delala) are out of scope: their work is not about government or
institution requirements.

Providers are individuals or companies. Clients hire them through engagements; only
the client of a completed engagement can review it, and every review feeds the trust
score (services/trust_score.py) stored on the provider for sorting.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from difflib import SequenceMatcher

from psycopg.types.json import Jsonb

from services import catalog_service, trust_score
from services.db import connection, execute, fetch_all, fetch_one
from services import platform_settings

log = logging.getLogger(__name__)


PROVIDER_TYPES = ("guday_geday", "agency")
ENTITY_TYPES = ("individual", "company")
SPECIALTIES = {
    "guday_geday": (), # Guday Geday list MESOB / organisation services instead
    "agency": ("customs_clearing", "travel_visa", "employment",
               "legal_accounting", "consultancy", "other"),
}
SUB_CITIES = ("addis_ketema", "akaki", "arada", "bole", "gulele", "kirkos", "kolfe",
              "lideta", "nifas_silk", "yeka")
REGIONS = ("adama", "bahir_dar", "dire_dawa", "hawassa", "mekelle", "gondar", "jimma",
           "dessie", "harar", "bishoftu", "nationwide")
AREAS = SUB_CITIES + REGIONS
REG_PREFIX = {"guday_geday": "GG", "agency": "AG"}

# Status transitions an admin may apply, and the resulting status
ADMIN_ACTIONS = {
    "approve": ({"pending", "rejected"}, "approved"),
    "reject": ({"pending"}, "rejected"),
    "suspend": ({"approved"}, "suspended"),
    "reinstate": ({"suspended"}, "approved"),
    "renew": ({"approved", "suspended"}, None), # extends the licence, keeps status
}

ENGAGEMENT_STATUSES = ("open", "requested", "accepted", "in_progress", "completed", "declined", "cancelled")
ACTIVE_ENGAGEMENT = ("requested", "accepted", "in_progress")

# What anyone may see: never contact details, national ID, TIN, licence documents or staff notes.
# Phone and email reach a client only through an accepted hire, so the marketplace can't be scraped or bypassed.
PUBLIC_COLUMNS = """
  p.id::text, p.slug, p.provider_type, p.entity_type, p.registration_no, p.display_name,
  p.display_name_am, p.legal_name, p.headline, p.bio, p.photo_url, p.website,
  p.sub_city, p.service_areas, p.specialties, p.service_ids, p.institution_ids, p.languages,
  p.experience_years, p.fee_from::float, p.fee_to::float, p.fee_unit, p.pricing_notes,
  p.highlights, p.external_license_type, p.external_license_status, p.accepting_work,
  p.completed_count, p.response_hours::float, p.trust_score, p.score_breakdown,
  p.rating_avg::float, p.rating_count, p.national_id_verified as id_verified, p.job_success, p.closed_jobs,
  (p.tin is not null and (p.entity_type = 'individual' or p.trade_license_no is not null)) as registered_business,
  p.license_expires_at, p.approved_at, p.created_at, p.is_sample
"""

PRIVATE_COLUMNS = PUBLIC_COLUMNS + """,
  p.phone, p.telegram_username, p.email, p.vat_registered, p.vat_number, p.user_id::text, p.status, p.national_id, p.tin, p.trade_license_no, p.license_document_url,
  p.id_document_url, p.representative_title, p.address, p.external_license_no,
  p.external_license_verified_by, p.external_license_verified_at, p.reviewed_by,
  p.reviewed_at, p.review_note, p.updated_at, p.id_verification_method, p.verified_name,
  (p.payout_account_enc is not null) as payout_ready, p.payout_bank_code, p.payout_bank_name, p.payout_account_name, p.payout_account_last4,
  p.payout_set_at
"""

PROFILE_FIELDS = (
    "display_name", "display_name_am", "headline", "bio", "phone", "telegram_username", "email", "website",
    "vat_registered", "vat_number",
    "sub_city", "address", "service_areas", "specialties", "service_ids", "languages",
    "experience_years", "fee_from", "fee_to", "fee_unit", "pricing_notes", "highlights",
    "accepting_work", "legal_name", "tin", "trade_license_no", "representative_title",
    "external_license_type", "external_license_no", "photo_url", "license_document_url",
)
NULLABLE_FIELDS = {
    "display_name_am", "headline", "bio", "telegram_username", "email", "website", "sub_city", "address",
    "vat_number",
    "fee_from", "fee_to", "pricing_notes", "legal_name", "tin", "trade_license_no",
    "representative_title", "external_license_type", "external_license_no", "photo_url",
    "license_document_url",
}


class MarketplaceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _log(conn, provider_id: str, action: str, actor: str | None, note: str | None = None) -> None:
    conn.execute(
        "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
        (provider_id, action, actor, note),
    )


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "provider"
    slug, n = base[:60], 2
    while fetch_one("select 1 from providers where slug = %s", (slug,)):
        slug = f"{base[:56]}-{n}"
        n += 1
    return slug


def names_differ(typed: str | None, verified: str | None) -> bool:
    """True when a typed name is far from the name Fayda returned."""
    if not typed or not verified:
        return False

    def tokens(name: str) -> str:
        return " ".join(sorted(t for t in re.split(r"[^a-zሀ-፿]+", name.lower()) if t))

    return SequenceMatcher(None, tokens(typed), tokens(verified)).ratio() < 0.8


def _validate(fields: dict, provider_type: str, entity_type: str) -> dict:
    out = dict(fields)
    if "service_ids" in out and out["service_ids"] is not None:
        known = {s["id"] for s in catalog_service.services_by_ids(out["service_ids"])}
        unknown = [s for s in out["service_ids"] if s not in known]
        if unknown:
            raise MarketplaceError(f"Unknown services: {', '.join(unknown[:5])}")
        out["institution_ids"] = sorted(
            {s["institution_id"] for s in catalog_service.services_by_ids(out["service_ids"])}
        )
    if "specialties" in out and out["specialties"] is not None:
        allowed = SPECIALTIES[provider_type]
        bad = [s for s in out["specialties"] if s not in allowed]
        if bad:
            raise MarketplaceError(f"Unknown specialties for this provider type: {', '.join(bad)}")
    if "service_areas" in out and out["service_areas"] is not None:
        bad = [a for a in out["service_areas"] if a not in AREAS]
        if bad:
            raise MarketplaceError(f"Unknown areas: {', '.join(bad)}")
    if out.get("fee_from") is not None and out.get("fee_to") is not None and out["fee_to"] < out["fee_from"]:
        raise MarketplaceError("The highest fee can't be lower than the lowest fee")
    return out


def _requirements(provider: dict) -> None:
    """What a complete application needs, by type and entity."""
    t, e = provider["provider_type"], provider["entity_type"]
    if t == "guday_geday" and not provider.get("service_ids"):
        raise MarketplaceError("Pick at least one service you handle")
    if t == "agency" and not provider.get("specialties"):
        raise MarketplaceError("Pick at least one specialty")
    if not provider.get("service_areas"):
        raise MarketplaceError("Pick at least one area you work in")
    if e == "company":
        missing = [k for k in ("legal_name", "tin", "trade_license_no") if not provider.get(k)]
        if missing:
            raise MarketplaceError(f"Companies must provide: {', '.join(missing)}")


# ---------------------------------------------------------------- join / edit


def join(data: dict, *, user_id: str, actor: str) -> dict:
    if fetch_one("select 1 from providers where user_id = %s", (user_id,)):
        raise MarketplaceError("You already have a provider profile", 409)
    t, e = data["provider_type"], data["entity_type"]
    if t not in PROVIDER_TYPES or e not in ENTITY_TYPES:
        raise MarketplaceError("Unknown provider or entity type")
    fields = _validate({k: data[k] for k in PROFILE_FIELDS if data.get(k) not in (None, "")}, t, e)
    _requirements({**fields, "provider_type": t, "entity_type": e})
    if not fields.get("sub_city"):
        fields["sub_city"] = next((a for a in fields.get("service_areas") or [] if a in SUB_CITIES), None)
    if fields.get("external_license_no"):
        fields["external_license_status"] = "pending"

    fields |= {
        "user_id": user_id, "provider_type": t, "entity_type": e,
        "slug": _slugify(fields.get("legal_name") if e == "company" and fields.get("legal_name") else data["display_name"]),
        "national_id": data.get("national_id"),
        "national_id_verified": bool(data.get("national_id_verified")),
        "id_verification_method": data.get("id_verification_method"),
        "verified_name": data.get("verified_name"),
        "id_document_url": data.get("id_document_url"),
        "is_sample": bool(data.get("is_sample")),
    }
    for arr in ("service_ids", "institution_ids", "service_areas", "specialties", "languages", "highlights"):
        fields[arr] = fields.get(arr) or []
    fields["experience_years"] = fields.get("experience_years") or 0
    fields["fee_unit"] = fields.get("fee_unit") or "negotiable"

    cols = ", ".join(fields)
    vals = ", ".join(f"%({k})s" for k in fields)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            f"insert into providers as p ({cols}) values ({vals}) returning p.id::text", fields
        ).fetchone()
        _log(conn, row["id"], "registered", actor, f"{t} / {e}")
    recompute(row["id"])
    return get(row["id"])


def update_me(user_id: str, data: dict, actor: str) -> dict:
    provider = get_for_user(user_id)
    if not provider:
        raise MarketplaceError("You don't have a provider profile yet", 404)
    if provider["status"] == "suspended":
        raise MarketplaceError("Your profile is suspended. Contact the marketplace team.", 403)
    return _update(provider, data, actor, by_owner=True)


def _update(provider: dict, data: dict, actor: str, *, by_owner: bool) -> dict:
    fields = {}
    for k in PROFILE_FIELDS:
        if k not in data:
            continue
        v = data[k]
        if v in (None, "") and k not in NULLABLE_FIELDS:
            continue  # required fields can't be cleared
        fields[k] = v if v != "" else None
    fields = _validate(fields, provider["provider_type"], provider["entity_type"])
    merged = {**provider, **fields}
    _requirements(merged)
    if merged.get("vat_registered") and not merged.get("vat_number"):
        raise MarketplaceError("Enter your VAT registration number, or untick VAT registered")

    notes = []
    if "external_license_no" in fields and fields["external_license_no"] != provider["external_license_no"]:
        fields["external_license_status"] = "pending" if fields["external_license_no"] else "none"
        notes.append("sector licence changed, needs verification")
    if by_owner and provider["status"] == "rejected":
        fields["status"] = "pending"  # editing a rejected application resubmits it
        notes.append("resubmitted")
    if not fields:
        return get(provider["id"])

    assignments = ", ".join(f"{k} = %({k})s" for k in fields)
    with connection() as conn, conn.transaction():
        conn.execute(
            f"update providers set {assignments}, updated_at = now() where id = %(id)s",
            {**fields, "id": provider["id"]},
        )
        changed = sorted(k for k in fields if k not in ("status", "external_license_status", "institution_ids"))
        _log(conn, provider["id"], "updated", actor, "; ".join([", ".join(changed)] + notes))
    recompute(provider["id"])
    return get(provider["id"])


def get(provider_id: str) -> dict | None:
    return fetch_one(f"select {PRIVATE_COLUMNS} from providers p where p.id::text = %s", (provider_id,))


def get_for_user(user_id: str) -> dict | None:
    return fetch_one(f"select {PRIVATE_COLUMNS} from providers p where p.user_id = %s", (user_id,))


def _services(service_ids: list[str]) -> list[dict]:
    return [
        {"id": s["id"], "name": s["name"], "institution": s["institution"]["short_name"],
         "fee_text": s.get("fee_text"), "processing_time_text": s.get("processing_time_text")}
        for s in catalog_service.services_by_ids(service_ids or [])
    ]


def owner_view(user_id: str) -> dict | None:
    provider = get_for_user(user_id)
    if not provider:
        return None
    provider.pop("national_id", None)
    from services import payment_service

    provider["payout"] = payment_service.payout_view(provider)
    provider["services"] = _services(provider["service_ids"])
    provider["team"] = team(provider["id"], include_pending=True)
    provider["agency"] = agency_of(provider["id"], include_pending=True)
    provider["tips"] = trust_score.tips(
        {"parts": provider["score_breakdown"] or [], "is_new": provider["rating_count"] < trust_score.NEW_UNTIL_REVIEWS},
        provider,
    ) if provider["score_breakdown"] else []
    provider["completeness"] = completeness(provider)
    if provider["status"] not in ("rejected", "suspended"):
        provider.pop("review_note", None)
    return provider


def completeness(provider: dict) -> dict:
    checks = [
        ("photo", "Profile photo or logo", bool(provider.get("photo_url"))),
        ("headline", "Headline", bool(provider.get("headline"))),
        ("bio", "About (80+ characters)", len(provider.get("bio") or "") >= 80),
        ("work", "Services or specialties", bool(provider.get("service_ids") or provider.get("specialties"))),
        ("areas", "Areas you work in", bool(provider.get("service_areas"))),
        ("languages", "Languages", bool(provider.get("languages"))),
        ("pricing", "Pricing", provider.get("fee_from") is not None or bool(provider.get("pricing_notes"))),
        ("highlights", "Highlights or past work", bool(provider.get("highlights"))),
        ("id", "Fayda ID verified", bool(provider.get("id_verified"))),
        ("tin", "TIN", bool(provider.get("tin"))),
    ]
    done = sum(1 for _, _, ok in checks if ok)
    return {
        "percent": round(done / len(checks) * 100),
        "items": [{"key": k, "label": label, "done": ok} for k, label, ok in checks],
    }


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
        result = trust_score.compute({
            "review_count": reviews["n"], "review_sum": float(reviews["s"]),
            "fayda_verified": p["national_id_verified"], "has_phone": bool(p["phone"]),
            "has_tin": bool(p["tin"]), "has_trade_license": bool(p["trade_license_no"]),
            "entity_type": p["entity_type"],
            "external_license_verified": p["external_license_status"] == "verified",
            "completed": jobs["completed"], "failed": jobs["failed"] + js["failure"],
            "approved_at": p["approved_at"], "upheld_disputes": jobs["upheld"],
            "suspensions": suspensions,
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
    return result


# ---------------------------------------------------------------- public marketplace


SORTS = {
    "score": "p.trust_score desc, p.rating_count desc",
    "rating": "p.rating_avg desc, p.rating_count desc",
    "reviews": "p.rating_count desc, p.trust_score desc",
    "newest": "p.approved_at desc nulls last",
}
LIVE = "p.status = 'approved' and (p.license_expires_at is null or p.license_expires_at >= current_date)"


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
    extra = ", r.hidden, r.hidden_reason, r.hidden_by, r.hidden_at" if include_hidden else ""
    items = fetch_all(
        f"""
        select r.id::text, r.rating, r.communication, r.fee_honesty, r.speed, r.outcome,
          r.would_hire_again, r.comment, r.reply, r.replied_at, r.created_at,
          e.title as job_title, e.service_name, (e.payment_status = 'paid') as paid_through_platform,
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
    """Completed work, for the public: what and when, with the client's rating. Never who."""
    return fetch_all(
        """
        select e.title, e.service_name, e.sub_city, coalesce(e.completed_at, e.updated_at) as completed_at,
               r.rating, r.comment
        from engagements e left join reviews r on r.engagement_id = e.id and not r.hidden
        where e.provider_id = %s and e.status = 'completed'
        order by coalesce(e.completed_at, e.updated_at) desc limit %s
        """,
        (provider_id, limit),
    )


# ---------------------------------------------------------------- agency teams


def team(agency_id: str, include_pending: bool = False) -> list[dict]:
    statuses = ("active", "pending") if include_pending else ("active",)
    return fetch_all(
        """
        select m.id::text as membership_id, m.status, m.initiated_by, m.role_title, m.invited_email,
          p.id::text, p.slug, p.display_name, p.photo_url, p.headline, p.trust_score,
          p.rating_avg::float, p.rating_count, p.completed_count, p.national_id_verified as id_verified
        from provider_members m left join providers p on p.id = m.member_id
        where m.agency_id = %s and m.status = any(%s)
        order by m.status, p.trust_score desc nulls last
        """,
        (agency_id, list(statuses)),
    )


def agency_of(provider_id: str, include_pending: bool = False) -> dict | None:
    statuses = ("active", "pending") if include_pending else ("active",)
    return fetch_one(
        """
        select m.id::text as membership_id, m.status, m.initiated_by, a.id::text, a.slug,
          a.display_name, a.photo_url, a.trust_score
        from provider_members m join providers a on a.id = m.agency_id
        where m.member_id = %s and m.status = any(%s)
        order by m.created_at desc limit 1
        """,
        (provider_id, list(statuses)),
    )


def _agency_by_slug(slug: str) -> dict:
    agency = fetch_one(
        f"select {PRIVATE_COLUMNS} from providers p where p.slug = %s or p.id::text = %s", (slug, slug)
    )
    if not agency or agency["provider_type"] != "agency":
        raise MarketplaceError("Agency not found", 404)
    return agency


def request_to_join(user_id: str, agency_slug: str, actor: str) -> dict:
    me = get_for_user(user_id)
    if not me or me["entity_type"] != "individual" or me["provider_type"] == "agency":
        raise MarketplaceError("Only individual Guday Geday agents can join an agency", 403)
    agency = _agency_by_slug(agency_slug)
    if agency["status"] != "approved":
        raise MarketplaceError("This agency isn't active", 409)
    if agency_of(me["id"], include_pending=True):
        raise MarketplaceError("You already belong to, or asked to join, an agency", 409)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "insert into provider_members (agency_id, member_id, initiated_by) values (%s, %s, 'member') "
            "returning id::text",
            (agency["id"], me["id"]),
        ).fetchone()
        _log(conn, agency["id"], "member_requested", actor, me["display_name"])
    return {"membership_id": row["id"]}


def invite_member(user_id: str, member_slug: str, role_title: str | None, actor: str) -> dict:
    agency = get_for_user(user_id)
    if not agency or agency["provider_type"] != "agency":
        raise MarketplaceError("Only agencies can invite members", 403)
    member = fetch_one("select id::text, entity_type, provider_type, display_name from providers where slug = %s or id::text = %s",
                       (member_slug, member_slug))
    if not member or member["entity_type"] != "individual" or member["provider_type"] == "agency":
        raise MarketplaceError("Provider not found. Members must be individual Guday Geday agents.", 404)
    if agency_of(member["id"], include_pending=True):
        raise MarketplaceError("That provider already belongs to, or asked to join, an agency", 409)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "insert into provider_members (agency_id, member_id, initiated_by, role_title) "
            "values (%s, %s, 'agency', %s) returning id::text",
            (agency["id"], member["id"], role_title),
        ).fetchone()
        _log(conn, agency["id"], "member_invited", actor, member["display_name"])
    return {"membership_id": row["id"]}


def respond_membership(user_id: str, membership_id: str, action: str, actor: str) -> dict:
    """The side that didn't start the request accepts or declines; either side can remove."""
    me = get_for_user(user_id)
    m = fetch_one(
        "select id::text, agency_id::text, member_id::text, initiated_by, status from provider_members where id::text = %s",
        (membership_id,),
    )
    if not me or not m or me["id"] not in (m["agency_id"], m["member_id"]):
        raise MarketplaceError("Membership not found", 404)
    i_am_agency = me["id"] == m["agency_id"]
    if action in ("accept", "decline"):
        if m["status"] != "pending":
            raise MarketplaceError("This request was already answered", 409)
        responder_is_agency = m["initiated_by"] == "member"
        if i_am_agency != responder_is_agency:
            raise MarketplaceError("Waiting for the other side to respond", 403)
        new_status = "active" if action == "accept" else "declined"
    elif action == "remove":
        if m["status"] not in ("active", "pending"):
            raise MarketplaceError("Nothing to remove", 409)
        new_status = "removed"
    else:
        raise MarketplaceError("Unknown action")
    with connection() as conn, conn.transaction():
        conn.execute(
            "update provider_members set status = %s, responded_at = now() where id = %s",
            (new_status, membership_id),
        )
        _log(conn, m["agency_id"], f"member_{new_status}", actor)
    recompute(m["agency_id"])
    return {"status": new_status}


# ---------------------------------------------------------------- admin


def admin_list(
    *, provider_type: str | None = None, status: str | None = None, q: str | None = None,
    license_status: str | None = None, limit: int = 50, offset: int = 0,
) -> dict:
    where, params = ["true"], {}
    if provider_type:
        where.append("p.provider_type = %(t)s")
        params["t"] = provider_type
    if status:
        where.append("p.status = %(status)s")
        params["status"] = status
    if license_status:
        where.append("p.external_license_status = %(ls)s")
        params["ls"] = license_status
    if q:
        where.append(
            "(p.display_name ilike %(q)s or p.legal_name ilike %(q)s or p.phone ilike %(q)s "
            "or p.registration_no ilike %(q)s or p.national_id ilike %(q)s or p.tin ilike %(q)s)"
        )
        params["q"] = f"%{q}%"
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from providers p where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select {PRIVATE_COLUMNS},
          (select count(*) from engagements e where e.provider_id = p.id
             and e.status = any(array['requested','accepted','in_progress'])) as open_jobs,
          (select count(*) from engagements e where e.provider_id = p.id and e.disputed
             and e.dispute_status = 'open') as open_disputes
        from providers p where {clause}
        order by case p.status when 'pending' then 0 else 1 end,
          case p.external_license_status when 'pending' then 0 else 1 end, p.created_at desc
        limit %(limit)s offset %(offset)s
        """,
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": items}


def admin_detail(provider_id: str) -> dict | None:
    provider = get(provider_id)
    if not provider:
        return None
    provider["events"] = fetch_all(
        "select id, action, actor, note, created_at from provider_events "
        "where provider_id = %s order by created_at desc limit 100",
        (provider_id,),
    )
    provider["engagements"] = fetch_all(
        "select id::text, title, client_name, service_name, status, disputed, dispute_status, created_at "
        "from engagements where provider_id = %s order by created_at desc limit 50",
        (provider_id,),
    )
    provider["reviews"] = list_reviews(provider_id, limit=50, include_hidden=True)
    provider["services"] = _services(provider["service_ids"])
    provider["team"] = team(provider_id, include_pending=True)
    provider["agency"] = agency_of(provider_id, include_pending=True)
    provider["name_mismatch"] = names_differ(provider["display_name"], provider.get("verified_name")) \
        if provider["entity_type"] == "individual" else False
    return provider


def _next_registration_no(conn, provider_type: str) -> str:
    seq = conn.execute("select nextval('provider_registration_seq') as n").fetchone()["n"]
    return f"{REG_PREFIX[provider_type]}-{date.today().year}-{seq:05d}"


def review_provider(provider_id: str, action: str, *, actor: str, note: str | None = None) -> dict:
    if action not in ADMIN_ACTIONS:
        raise MarketplaceError(f"Unknown action '{action}'")
    allowed_from, new_status = ADMIN_ACTIONS[action]
    provider = get(provider_id)
    if not provider:
        raise MarketplaceError("Provider not found", 404)
    if provider["status"] not in allowed_from:
        raise MarketplaceError(f"Cannot {action} a provider that is {provider['status']}", 409)
    if action in ("reject", "suspend") and not note:
        raise MarketplaceError(f"A reason is required to {action}")

    with connection() as conn, conn.transaction():
        updates = {"reviewed_by": actor, "review_note": note}
        if new_status:
            updates["status"] = new_status
        if action in ("approve", "renew", "reinstate"):
            updates["license_expires_at"] = date.today() + timedelta(days=platform_settings.get_int("license_validity_days"))
        if action == "approve":
            if not provider["registration_no"]:
                updates["registration_no"] = _next_registration_no(conn, provider["provider_type"])
            if not provider["approved_at"]:
                conn.execute("update providers set approved_at = now() where id = %s", (provider_id,))
        assignments = ", ".join(f"{k} = %({k})s" for k in updates)
        conn.execute(
            f"update providers set {assignments}, reviewed_at = now(), updated_at = now() where id = %(id)s",
            {**updates, "id": provider_id},
        )
        if action in ("approve", "reinstate") and provider["user_id"]:
            conn.execute("update users set role = 'agent' where id = %s and role = 'user'", (provider["user_id"],))
        if action == "suspend":
            # A suspended provider can't keep client work: send it back to staff
            conn.execute(
                "update engagements set provider_id = null, status = 'open', updated_at = now(), "
                "admin_note = coalesce(admin_note || E'\\n', '') || 'Provider suspended. Reassign.' "
                "where provider_id = %s and status = any(%s)",
                (provider_id, list(ACTIVE_ENGAGEMENT)),
            )
        _log(conn, provider_id, action, actor, note)
    recompute(provider_id)
    return get(provider_id)


def verify_external_license(provider_id: str, decision: str, *, actor: str, note: str | None) -> dict:
    provider = get(provider_id)
    if not provider:
        raise MarketplaceError("Provider not found", 404)
    if not provider["external_license_no"]:
        raise MarketplaceError("This provider hasn't entered a sector licence", 409)
    if decision == "rejected" and not note:
        raise MarketplaceError("A reason is required to reject a licence")
    with connection() as conn, conn.transaction():
        conn.execute(
            "update providers set external_license_status = %s, external_license_verified_by = %s, "
            "external_license_verified_at = now(), updated_at = now() where id = %s",
            (decision, actor, provider_id),
        )
        _log(conn, provider_id, f"license_{decision}", actor, note)
    recompute(provider_id)
    return get(provider_id)


def admin_update(provider_id: str, data: dict, actor: str) -> dict:
    provider = get(provider_id)
    if not provider:
        raise MarketplaceError("Provider not found", 404)
    return _update(provider, data, actor, by_owner=False)


def expire_licenses() -> int:
    """Approved providers past their licence date drop out of the marketplace."""
    return execute(
        "update providers set status = 'suspended', review_note = 'License expired', "
        "updated_at = now() where status = 'approved' and license_expires_at < current_date"
    )


def purge_samples() -> dict:
    with connection() as conn, conn.transaction():
        users = conn.execute(
            "select user_id::text from providers where is_sample and user_id is not null"
        ).fetchall()
        conn.execute("delete from engagements where is_sample")
        n = conn.execute("delete from providers where is_sample returning id").fetchall()
        conn.execute(
            "delete from users where id = any(%s::uuid[]) "
            "and (email like '%%@sample.invalid' or email like '%%.sample@example.com')",
            ([u["user_id"] for u in users],),
        )
        conn.execute("delete from users where email like 'sample-client-%%@sample.invalid'")
    return {"providers_removed": len(n)}


# ---------------------------------------------------------------- engagements (hires)


ENGAGEMENT_COLUMNS = """
  e.id::text, e.client_user_id::text, e.client_name, e.client_phone, e.provider_id::text,
  e.title, e.service_id, e.service_name, e.specialty, e.sub_city, e.details, e.budget, e.status,
  e.admin_note, e.created_at, e.updated_at, e.accepted_at, e.completed_at, e.client_confirmed_at,
  e.declined_reason, e.disputed, e.dispute_reason, e.dispute_status, e.dispute_note,
  p.display_name as provider_name, p.slug as provider_slug, p.phone as provider_phone,
  p.registration_no as provider_registration_no, p.provider_type, p.photo_url as provider_photo_url,
  r.id::text as review_id, r.rating as review_rating,
  e.agreed_price::float, e.price_note, e.payment_status, e.paid_at, e.payment_requested_at,
  coalesce(p.vat_registered, false) as provider_vat_registered,
  (select pay.tx_ref from payments pay where pay.engagement_id = e.id and pay.status = 'success'
     order by pay.verified_at desc nulls last limit 1) as paid_tx_ref,
  e.client_telegram, p.telegram_username as provider_telegram, e.completion_note, e.auto_confirmed,
  r.comment as review_comment, r.reply as review_reply, r.edited_at as review_edited_at,
  cr.rating as client_rating, cr.comment as client_rating_comment,
  (select c.status from review_change_requests c where c.review_id = r.id order by c.created_at desc limit 1)
    as review_change_status
"""
ENGAGEMENT_FROM = (
    "engagements e left join providers p on p.id = e.provider_id "
    "left join reviews r on r.engagement_id = e.id "
    "left join client_reviews cr on cr.engagement_id = e.id"
)


def get_engagement(engagement_id: str) -> dict | None:
    return fetch_one(
        f"select {ENGAGEMENT_COLUMNS} from {ENGAGEMENT_FROM} where e.id::text = %s", (engagement_id,)
    )


# Both sides get the other's phone number only once the provider has taken the job
CONTACT_SHARED = ("accepted", "in_progress", "completed")


def client_view(engagement: dict) -> dict:
    """What the hiring client sees: staff notes stay internal."""
    from services import payment_service

    view = {k: v for k, v in engagement.items() if k != "admin_note"}
    view["contact_shared"] = engagement["status"] in CONTACT_SHARED
    if not view["contact_shared"]:
        view["provider_phone"] = None
        view["provider_telegram"] = None
    # What the client will pay: the price, plus VAT when the provider is VAT-registered
    if engagement.get("agreed_price"):
        b = payment_service.breakdown(engagement["agreed_price"], bool(engagement.get("provider_vat_registered")))
        view["amount_due"] = float(b["total"])
        view["vat_due"] = float(b["provider_vat"])
    return view


def provider_view(engagement: dict) -> dict:
    """What the provider sees: the client's number appears once they accept."""
    from services import reputation

    view = {k: v for k, v in engagement.items() if k != "admin_note"}
    view["contact_shared"] = engagement["status"] in CONTACT_SHARED
    if not view["contact_shared"]:
        view["client_phone"] = None
        view["client_telegram"] = None
    # What the provider needs to decide on this client; shown only to the provider of this job
    view["client_record"] = reputation.client_record(engagement.get("client_user_id"))
    return view


def _provider_user(provider_id: str | None) -> str | None:
    if not provider_id:
        return None
    row = fetch_one("select user_id::text from providers where id = %s", (provider_id,))
    return row["user_id"] if row else None


def _tell(eng: dict, to: str, title: str, body: str | None = None) -> None:
    """Hire updates go to the bell of the other side. to: 'client' | 'provider'."""
    from services import notifications

    if to == "client":
        user, link = eng.get("client_user_id"), "/account/requests"
    else:
        user, link = _provider_user(eng.get("provider_id")), "/me/provider?tab=jobs"
    if user:
        try:
            notifications.notify([user], kind=f"hire_{to}", title=title[:140], body=body, link=link)
        except Exception:  # a failed notification never blocks the hire itself
            log.exception("Hire notification failed")


def create_hire(data: dict, *, user_id: str) -> dict:
    service = None
    if data.get("service_id"):
        service = catalog_service.get_service(data["service_id"])
        if not service:
            raise MarketplaceError("Unknown service")
    provider_id = data.get("provider_id")
    if provider_id:
        provider = fetch_one(
            f"select {PRIVATE_COLUMNS} from providers p where (p.id::text = %s or p.slug = %s) and {LIVE}",
            (provider_id, provider_id),
        )
        if not provider:
            raise MarketplaceError("This provider is not available")
        if not provider["accepting_work"]:
            raise MarketplaceError("This provider isn't taking new work right now", 409)
        if provider["user_id"] == user_id:
            raise MarketplaceError("You can't hire yourself", 409)
        provider_id = provider["id"]
    elif not service:
        raise MarketplaceError("Choose a provider, or a service so staff can find one for you")
    title = (data.get("title") or (service["name"] if service else "")).strip()
    if not title:
        raise MarketplaceError("Describe what you need")
    row = fetch_one(
        """
        insert into engagements (client_user_id, client_name, client_phone, client_telegram, provider_id, title,
          service_id, service_name, specialty, sub_city, details, budget, status)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning id::text
        """,
        (user_id, data["client_name"], data["client_phone"], data.get("client_telegram"), provider_id, title[:200],
         service["id"] if service else None, service["name"] if service else None,
         data.get("specialty"), data.get("sub_city"), data.get("details"), data.get("budget"),
         "requested" if provider_id else "open"),
    )
    if data.get("client_telegram"):  # remembered for the next hire
        execute("update users set telegram_username = coalesce(telegram_username, %s) where id = %s",
                (data["client_telegram"], user_id))
    eng = get_engagement(row["id"])
    if provider_id:
        first = (eng["client_name"] or "A client").split()[0]
        where = f" in {eng['sub_city'].replace('_', ' ').title()}" if eng.get("sub_city") else ""
        _tell(eng, "provider", f"New request: {eng['title']}",
              f"{first}{where} wants to hire you. Accept to see their phone number.")
    return eng


AUTO_CONFIRM_DAYS = 7


def auto_confirm_due() -> int:
    """Without online payment, delivered jobs the client neither confirmed nor disputed close after a week.
    With online payment a job closes only when it is paid."""
    if _payments_on():
        return 0
    rows = fetch_all(
        f"""
        update engagements set client_confirmed_at = now(), auto_confirmed = true, updated_at = now()
        where status = 'completed' and client_confirmed_at is null and not coalesce(disputed, false)
          and completed_at < now() - interval '{AUTO_CONFIRM_DAYS} days'
        returning id::text
        """
    )
    for r in rows:
        eng = get_engagement(r["id"])
        if eng.get("provider_id"):
            recompute(eng["provider_id"])
        _tell(eng, "client", f"{eng['title']} was closed", "No problem was reported within a week. You can still leave a review.")
        _tell(eng, "provider", f"{eng['title']} is closed", "It now counts toward your Job Success.")
    return len(rows)


# Client "My hires" tabs: closed, declined and cancelled hires are history
CLIENT_HISTORY = ("(e.status in ('declined', 'cancelled') "
                  "or (e.status = 'completed' and e.client_confirmed_at is not null))")
# Provider "Jobs" tabs
JOB_GROUPS = {
    "new": ("open", "requested"),
    "in_progress": ("accepted", "in_progress"),
    "completed": ("completed",),
    "declined": ("declined", "cancelled"),
}
# What waits on each side (header badges), counted in the database, never from a capped list
CLIENT_MUST_ACT = (
    "(e.status = 'completed' and e.client_confirmed_at is null and e.payment_status <> 'paid') "
    "or (e.status = 'completed' and e.client_confirmed_at > now() - interval '30 days' and r.id is null)"
)
PROVIDER_MUST_ACT = "e.status in ('requested', 'accepted', 'in_progress')"


def job_group_counts(provider_id: str) -> dict:
    rows = fetch_all("select status, count(*) as c from engagements where provider_id = %s group by status", (provider_id,))
    by = {r["status"]: r["c"] for r in rows}
    return {g: sum(by.get(s, 0) for s in sts) for g, sts in JOB_GROUPS.items()}


def client_scope_counts(user_id: str) -> dict:
    row = fetch_one(
        f"select count(*) filter (where {CLIENT_HISTORY}) as history, count(*) filter (where not {CLIENT_HISTORY}) as active "
        "from engagements e where e.client_user_id = %s",
        (user_id,),
    )
    return {"active": row["active"], "history": row["history"]}


def attention(user_id: str) -> dict:
    hires = fetch_one(
        f"select count(*) as c from engagements e left join reviews r on r.engagement_id = e.id "
        f"where e.client_user_id = %s and ({CLIENT_MUST_ACT})",
        (user_id,),
    )["c"]
    me = get_for_user(user_id)
    jobs = fetch_one(f"select count(*) as c from engagements e where e.provider_id = %s and {PROVIDER_MUST_ACT}",
                     (me["id"],))["c"] if me else 0
    return {"hires": hires, "jobs": jobs}


def follow_up_sql() -> str:
    """Delivered but not paid for a while (platform setting follow_up_hours): staff call both sides."""
    hours = platform_settings.get_int("follow_up_hours")
    return ("e.status = 'completed' and e.client_confirmed_at is null and e.payment_status <> 'paid' "
            f"and coalesce(e.completed_at, e.updated_at) < now() - interval '{hours} hours'")


def list_engagements(
    *, status: str | None = None, client_user_id: str | None = None, provider_id: str | None = None,
    disputed: bool | None = None, q: str | None = None, limit: int = 50, offset: int = 0,
    follow_up: bool = False, statuses: tuple[str, ...] | None = None, where_sql: str | None = None,
) -> dict:
    auto_confirm_due()
    where, params = ["true"], {}
    if statuses:
        where.append("e.status = any(%(statuses)s)")
        params["statuses"] = list(statuses)
    if where_sql:
        where.append(where_sql)
    if follow_up:
        where.append(follow_up_sql())
    if status:
        where.append("e.status = %(status)s")
        params["status"] = status
    if client_user_id:
        where.append("e.client_user_id = %(client)s")
        params["client"] = client_user_id
    if provider_id:
        where.append("e.provider_id = %(provider)s")
        params["provider"] = provider_id
    if disputed:
        where.append("e.disputed")
    if q:
        where.append("(e.client_name ilike %(q)s or e.client_phone ilike %(q)s or e.title ilike %(q)s "
                     "or p.display_name ilike %(q)s)")
        params["q"] = f"%{q}%"
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from {ENGAGEMENT_FROM} where {clause}", params)["c"]
    items = fetch_all(
        f"select {ENGAGEMENT_COLUMNS} from {ENGAGEMENT_FROM} where {clause} "
        f"order by e.created_at desc limit %(limit)s offset %(offset)s",
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": items}


def _set_status(engagement_id: str, status: str, extra: str = "", params: tuple = ()) -> None:
    execute(
        f"update engagements set status = %s, updated_at = now() {extra} where id = %s",
        (status, *params, engagement_id),
    )


def _payments_on() -> bool:
    from services import payment_service

    return payment_service.enabled()


def _save_price(engagement_id: str, price: float, note: str | None) -> None:
    execute("update engagements set agreed_price = %s, price_note = %s, updated_at = now() where id = %s",
            (price, (note or "").strip() or None, engagement_id))


def provider_action(engagement_id: str, *, user_id: str, action: str, reason: str | None = None,
                    price: float | None = None, price_note: str | None = None, note: str | None = None) -> dict:
    """Providers move their own jobs forward: requested → accepted → in_progress → completed."""
    me = get_for_user(user_id)
    eng = get_engagement(engagement_id)
    if not me or not eng or eng["provider_id"] != me["id"]:
        raise MarketplaceError("Job not found", 404)
    if me["status"] != "approved":
        raise MarketplaceError("Your profile is not active", 403)
    moves = {
        "accept": ({"requested"}, "accepted", ", accepted_at = now()"),
        "decline": ({"requested"}, "declined", ", declined_reason = %s"),
        "start": ({"accepted"}, "in_progress", ""),
        # Delivered: the client then confirms, or it closes on its own after AUTO_CONFIRM_DAYS
        # Delivered: this also asks the client to pay; paying closes the job
        "complete": ({"in_progress"}, "completed", ", completed_at = now(), completion_note = %s, payment_requested_at = now()"),
    }
    if action == "set_price":
        if price is None or price <= 0:
            raise MarketplaceError("Enter the price in birr")
        # The price can change until the work is delivered; after that it is the amount the client pays
        if eng["status"] not in ("accepted", "in_progress"):
            raise MarketplaceError("Accept the job first" if eng["status"] == "requested"
                                   else "The price can't change once the work is delivered", 409)
        if eng["payment_status"] in ("paid", "pending"):
            raise MarketplaceError("The client already paid or is paying; the price can't change now", 409)
        _save_price(engagement_id, price, price_note)
        _tell(eng, "client", f"{me['display_name']} changed the price to {price:,.0f} ETB",
              price_note or "You pay once the work is delivered.")
        return get_engagement(engagement_id)
    if action not in moves:
        raise MarketplaceError("Unknown action")
    allowed, new_status, extra = moves[action]
    if eng["status"] not in allowed:
        raise MarketplaceError(f"Can't {action} a job that is {eng['status'].replace('_', ' ')}", 409)
    if action == "accept" and _payments_on() and not price:
        raise MarketplaceError("Set your price when you accept: the client pays it once you deliver")
    if action == "complete":
        if len((note or "").strip()) < 10:
            raise MarketplaceError("Tell the client what you delivered (at least a sentence)")
        if _payments_on() and not eng.get("agreed_price"):
            raise MarketplaceError("Set your price before delivering", 409)
    params = (reason,) if action == "decline" else ((note or "").strip()[:2000],) if action == "complete" else ()
    if action == "complete" and eng.get("payment_status") == "paid":
        # Paid before delivery (the old order): delivering closes it, there is nothing left to pay
        extra += ", client_confirmed_at = now()"
    _set_status(engagement_id, new_status, extra, params)
    if action == "accept" and price:
        _save_price(engagement_id, price, price_note)
    recompute(me["id"])
    name = me["display_name"]
    messages = {
        "accept": (f"{name} accepted your request",
                   (f"Price: {price:,.0f} ETB, paid once the work is delivered. " if price else "")
                   + "Their phone and Telegram are now on your request."),
        "decline": (f"{name} declined your request", reason or "You can choose another verified provider."),
        "start": (f"{name} started work on {eng['title']}", None),
        "complete": (f"{name} delivered {eng['title']}: please pay",
                     f"\"{(note or '').strip()[:120]}\" Pay {float(eng.get('agreed_price') or 0):,.0f} ETB to close the job, "
                     "or report a problem."),
    }
    _tell(eng, "client", *messages[action])
    return get_engagement(engagement_id)


def client_action(engagement_id: str, *, user_id: str, action: str, reason: str | None = None) -> dict:
    eng = get_engagement(engagement_id)
    if not eng or eng["client_user_id"] != user_id:
        raise MarketplaceError("Request not found", 404)
    if action == "cancel":
        if eng.get("payment_status") in ("paid", "pending"):
            raise MarketplaceError("This job is paid. If something is wrong, report a problem and our team will "
                                   "sort it out.", 409)
        if eng["status"] == "completed":
            raise MarketplaceError("The work is delivered. Pay to close the job, or report a problem if it isn't right.", 409)
        if eng["status"] not in ("open", "requested", "accepted", "in_progress"):
            raise MarketplaceError("This request can't be cancelled now", 409)
        _set_status(engagement_id, "cancelled")
    elif action == "complete":
        # Without online payment the client confirms delivery; with it, paying is the confirmation
        if _payments_on():
            raise MarketplaceError("Pay for the delivered work to close the job", 409)
        if eng["status"] != "completed":
            who = eng.get("provider_name") or "The provider"
            raise MarketplaceError(f"You can confirm once {who} marks the work as delivered", 409)
        if eng.get("client_confirmed_at"):
            raise MarketplaceError("You already confirmed this job", 409)
        execute("update engagements set client_confirmed_at = now(), updated_at = now() where id = %s", (engagement_id,))
    elif action == "dispute":
        if eng["status"] not in ("accepted", "in_progress", "completed"):
            raise MarketplaceError("You can report a problem once a provider has taken the job", 409)
        if eng["disputed"]:
            raise MarketplaceError("You already reported a problem with this job", 409)
        if not reason:
            raise MarketplaceError("Tell us what went wrong")
        execute("update engagements set disputed = true, dispute_status = 'open', dispute_reason = %s, "
                "updated_at = now() where id = %s", (reason, engagement_id))
    else:
        raise MarketplaceError("Unknown action")
    if eng["provider_id"]:
        recompute(eng["provider_id"])
        first = (eng["client_name"] or "The client").split()[0]
        messages = {
            "cancel": (f"Request cancelled: {eng['title']}", f"{first} cancelled this request."),
            "complete": (f"{first} confirmed {eng['title']} is done", "The job is closed and counts toward your Job Success."),
            "dispute": (f"A client reported a problem with {eng['title']}", "Our staff will look at it and contact you."),
        }
        _tell(eng, "provider", *messages[action])
    return get_engagement(engagement_id)


def leave_review(engagement_id: str, *, user_id: str, data: dict) -> dict:
    eng = get_engagement(engagement_id)
    if not eng or eng["client_user_id"] != user_id:
        raise MarketplaceError("Only the client who hired this provider can review the job", 403)
    if eng["status"] != "completed" or not eng.get("client_confirmed_at"):
        raise MarketplaceError("You can review once the job is closed: confirm the work is done first", 409)
    if not eng["provider_id"]:
        raise MarketplaceError("This job had no provider to review", 409)
    if _payments_on() and eng.get("payment_status") != "paid":
        raise MarketplaceError("Reviews are for jobs paid through Compliance Navigator", 409)
    if eng["review_id"]:
        raise MarketplaceError("You already reviewed this job", 409)
    execute(
        """
        insert into reviews (engagement_id, provider_id, client_user_id, rating, communication,
          fee_honesty, speed, outcome, would_hire_again, comment)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (engagement_id, eng["provider_id"], user_id, data["rating"], data.get("communication"),
         data.get("fee_honesty"), data.get("speed"), data.get("outcome"),
         data.get("would_hire_again"), data.get("comment")),
    )
    recompute(eng["provider_id"])
    _tell(eng, "provider", f"New {data['rating']}-star review for {eng['title']}", (data.get("comment") or "")[:140] or None)
    return get_engagement(engagement_id)


def reply_to_review(review_id: str, *, user_id: str, reply: str) -> dict:
    me = get_for_user(user_id)
    review = fetch_one("select id::text, provider_id::text, reply from reviews where id::text = %s", (review_id,))
    if not me or not review or review["provider_id"] != me["id"]:
        raise MarketplaceError("Review not found", 404)
    if review["reply"]:
        raise MarketplaceError("You already replied to this review", 409)
    execute("update reviews set reply = %s, replied_at = now() where id = %s", (reply, review_id))
    return fetch_one("select id::text, reply, replied_at from reviews where id = %s", (review_id,))


def moderate_review(review_id: str, *, hide: bool, reason: str | None, actor: str) -> dict:
    review = fetch_one("select id::text, provider_id::text from reviews where id::text = %s", (review_id,))
    if not review:
        raise MarketplaceError("Review not found", 404)
    if hide and not reason:
        raise MarketplaceError("A reason is required to hide a review")
    with connection() as conn, conn.transaction():
        conn.execute(
            "update reviews set hidden = %s, hidden_reason = %s, hidden_by = %s, "
            "hidden_at = case when %s then now() end where id = %s",
            (hide, reason if hide else None, actor if hide else None, hide, review_id),
        )
        _log(conn, review["provider_id"], "review_hidden" if hide else "review_restored", actor, reason)
    recompute(review["provider_id"])
    return {"id": review_id, "hidden": hide}


def list_reviews_admin(*, hidden: bool | None = None, max_rating: int | None = None, limit: int = 50, offset: int = 0) -> dict:
    where, params = ["true"], []
    if hidden is not None:
        where.append("r.hidden = %s")
        params.append(hidden)
    if max_rating:
        where.append("r.rating <= %s")
        params.append(max_rating)
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from reviews r where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select r.id::text, r.rating, r.comment, r.reply, r.hidden, r.hidden_reason, r.hidden_by,
          r.created_at, r.would_hire_again, p.display_name as provider_name, p.slug as provider_slug,
          u.email as client_email, e.title as job_title
        from reviews r join providers p on p.id = r.provider_id
        join engagements e on e.id = r.engagement_id left join users u on u.id = r.client_user_id
        where {clause} order by r.created_at desc limit %s offset %s
        """,
        [*params, limit, offset],
    )
    return {"total": total, "items": items}


def admin_update_engagement(
    engagement_id: str, *, provider_id: str | None, status: str | None, note: str | None,
) -> dict:
    eng = get_engagement(engagement_id)
    if not eng:
        raise MarketplaceError("Request not found", 404)
    if provider_id:
        provider = fetch_one(f"select p.id::text from providers p where p.id::text = %s and {LIVE}", (provider_id,))
        if not provider:
            raise MarketplaceError("Only approved providers can be assigned")
        status = status or ("requested" if eng["status"] == "open" else eng["status"])
    if status and status not in ENGAGEMENT_STATUSES:
        raise MarketplaceError(f"Unknown status '{status}'")
    execute(
        """
        update engagements set
          provider_id = coalesce(%(provider)s::uuid, provider_id),
          status = coalesce(%(status)s, status),
          admin_note = coalesce(%(note)s, admin_note),
          completed_at = case when %(status)s = 'completed' then now() else completed_at end,
          accepted_at = case when %(status)s = 'accepted' then now() else accepted_at end,
          updated_at = now()
        where id = %(id)s
        """,
        {"provider": provider_id, "status": status, "note": note, "id": engagement_id},
    )
    for pid in {eng["provider_id"], provider_id} - {None}:
        recompute(pid)
    return get_engagement(engagement_id)


def resolve_dispute(engagement_id: str, decision: str, *, note: str | None, actor: str) -> dict:
    eng = get_engagement(engagement_id)
    if not eng or not eng["disputed"]:
        raise MarketplaceError("No open complaint on this job", 404)
    if decision not in ("upheld", "dismissed"):
        raise MarketplaceError("Decision must be upheld or dismissed")
    execute(
        "update engagements set dispute_status = %s, dispute_note = %s, dispute_resolved_by = %s, "
        "updated_at = now() where id = %s",
        (decision, note, actor, engagement_id),
    )
    if eng["provider_id"]:
        execute(
            "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
            (eng["provider_id"], f"complaint_{decision}", actor, note),
        )
        recompute(eng["provider_id"])
    return get_engagement(engagement_id)


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
        "and license_expires_at between current_date and current_date + 30"
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
