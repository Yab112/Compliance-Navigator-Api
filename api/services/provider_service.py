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

from services import catalog_service, platform_settings, trust_score, vetting
from services.db import connection, execute, fetch_all, fetch_one

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
  (p.national_id_verified and p.id_verification_method = 'fayda_sandbox') as id_test,
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

# The staff providers list shows only these: no national ID, TIN, documents, address or payout details
ADMIN_LIST_COLUMNS = """
  p.id::text, p.slug, p.provider_type, p.entity_type, p.registration_no, p.display_name, p.photo_url,
  p.phone, p.status, p.sub_city, p.service_areas, p.specialties, p.accepting_work,
  p.national_id_verified as id_verified, p.id_verification_method,
  (p.tin is not null and (p.entity_type = 'individual' or p.trade_license_no is not null)) as registered_business,
  (p.external_license_no is not null) as has_external_license, p.external_license_status,
  p.trust_score, p.rating_avg::float, p.rating_count, p.completed_count, p.license_expires_at,
  p.approved_at, p.created_at, p.is_sample
"""

# Dates follow the Addis Ababa calendar day, not the database's UTC day
TODAY = "(now() at time zone 'Africa/Addis_Ababa')::date"

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
    if by_owner and provider["status"] == "approved":
        # Who they are and how clients are taxed only change after staff check (old values stay live)
        held = {k: fields.pop(k) for k in REVIEWED_FIELDS if k in fields}
        held = {k: v for k, v in held.items() if v != provider.get(k)}
        if held:
            _request_change(provider, held, actor)
            notes.append("name, registration or VAT change sent for staff review")
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


# Fields an approved provider can't change on their own: staff check the proof first
REVIEWED_FIELDS = ("display_name", "legal_name", "tin", "trade_license_no", "vat_registered", "vat_number")
CHANGE_COLUMNS = ("id::text, provider_id::text, changes, old_values, status, requested_by, requested_at, "
                  "decided_by, decided_at, note")


def _request_change(provider: dict, held: dict, actor: str) -> None:
    """Save (or add to) the provider's one pending change request."""
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "select id, changes, old_values from provider_change_requests "
            "where provider_id = %s and status = 'pending' for update",
            (provider["id"],),
        ).fetchone()
        changes = {**(row["changes"] if row else {}), **held}
        old = {**{k: provider.get(k) for k in held}, **(row["old_values"] if row else {})}
        # A field set back to its live value needs no review
        changes = {k: v for k, v in changes.items() if v != provider.get(k)}
        old = {k: old[k] for k in changes}
        if row and not changes:
            conn.execute("delete from provider_change_requests where id = %s", (row["id"],))
        elif row:
            conn.execute(
                "update provider_change_requests set changes = %s, old_values = %s, requested_by = %s, "
                "requested_at = now() where id = %s",
                (Jsonb(changes), Jsonb(old), actor, row["id"]),
            )
        elif changes:
            conn.execute(
                "insert into provider_change_requests (provider_id, changes, old_values, requested_by) "
                "values (%s, %s, %s, %s)",
                (provider["id"], Jsonb(changes), Jsonb(old), actor),
            )
        if changes:
            _log(conn, provider["id"], "change_requested", actor, ", ".join(sorted(changes)))


def pending_change(provider_id: str) -> dict | None:
    return fetch_one(
        f"select {CHANGE_COLUMNS} from provider_change_requests where provider_id = %s and status = 'pending'",
        (provider_id,),
    )


def decide_change(provider_id: str, change_id: str, decision: str, *, actor: str, note: str | None) -> dict:
    """Staff approve (the new values go live) or reject (the provider sees why) a held change."""
    if decision not in ("approve", "reject"):
        raise MarketplaceError("Choose approve or reject")
    if decision == "reject" and len((note or "").strip()) < 5:
        raise MarketplaceError("Write why the change is refused. The provider sees this.")
    if decision == "approve" and len((note or "").strip()) < 10:
        raise MarketplaceError("Write what you checked (for example: VAT certificate matches the number)")
    change = pending_change(provider_id)
    if not change or change["id"] != change_id:
        raise MarketplaceError("No such pending change", 404)
    provider = get(provider_id)
    if decision == "approve":
        _update(provider, change["changes"], actor, by_owner=False)
    with connection() as conn, conn.transaction():
        conn.execute(
            "update provider_change_requests set status = %s, decided_by = %s, decided_at = now(), note = %s "
            "where id = %s and status = 'pending'",
            ("approved" if decision == "approve" else "rejected", actor, (note or "").strip(), change_id),
        )
        _log(conn, provider_id, f"change_{decision}d", actor, f"{', '.join(sorted(change['changes']))}: {note}")
    if provider.get("user_id"):
        from services import notifications

        try:
            notifications.notify(
                [provider["user_id"]], kind="vetting",
                title="Your profile change was approved" if decision == "approve" else "Your profile change was not accepted",
                body=None if decision == "approve" else note, link="/me/provider?tab=profile",
            )
        except Exception:
            log.exception("Change notification failed")
    return get(provider_id)


def last_rejected_change(provider_id: str) -> dict | None:
    return fetch_one(
        f"select {CHANGE_COLUMNS} from provider_change_requests where provider_id = %s and status = 'rejected' "
        "and decided_at > now() - interval '30 days' order by decided_at desc limit 1",
        (provider_id,),
    )


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
    provider["vetting"] = vetting.checklist(provider)
    provider["pending_change"] = pending_change(provider["id"])
    provider["rejected_change"] = None if provider["pending_change"] else last_rejected_change(provider["id"])
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
    return result


# ---------------------------------------------------------------- public marketplace


SORTS = {
    "score": "p.trust_score desc, p.rating_count desc",
    "rating": "p.rating_avg desc, p.rating_count desc",
    "reviews": "p.rating_count desc, p.trust_score desc",
    "newest": "p.approved_at desc nulls last",
}
LIVE = f"p.status = 'approved' and (p.license_expires_at is null or p.license_expires_at >= {TODAY})"


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


# ---------------------------------------------------------------- agency teams


def team(agency_id: str, include_pending: bool = False) -> list[dict]:
    statuses = ("active", "pending") if include_pending else ("active",)
    return fetch_all(
        """
        select m.id::text as membership_id, m.status, m.initiated_by, m.role_title,
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
    if agency["status"] != "approved":
        raise MarketplaceError("Your agency can invite members once it is approved", 409)
    # Only listed agents: a pending or suspended profile can't be tied up by an invitation
    member = fetch_one(f"select p.id::text, p.entity_type, p.provider_type, p.display_name from providers p "
                       f"where (p.slug = %s or p.id::text = %s) and {LIVE}", (member_slug, member_slug))
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


ADMIN_SORTS = {
    # The vetting queue first: pending applications and licences, oldest waiting first
    "queue": "case p.status when 'pending' then 0 else 1 end, "
             "case p.external_license_status when 'pending' then 0 else 1 end, p.created_at",
    "newest": "p.created_at desc",
    "score": "p.trust_score desc nulls last, p.created_at desc",
    "complaints": "open_disputes desc, p.created_at desc",
    "expiry": "p.license_expires_at nulls last, p.created_at",
}


def admin_list(
    *, provider_type: str | None = None, status: str | None = None, q: str | None = None,
    license_status: str | None = None, expiring_days: int | None = None, area: str | None = None,
    id_verified: bool | None = None, accepting_work: bool | None = None, sort: str = "queue",
    limit: int = 50, offset: int = 0,
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
    if expiring_days is not None:
        where.append(f"p.status = 'approved' and p.license_expires_at between {TODAY} and {TODAY} + %(days)s::int")
        params["days"] = expiring_days
    if area:
        where.append("(p.sub_city = %(area)s or %(area)s = any(p.service_areas))")
        params["area"] = area
    if id_verified is not None:
        where.append("p.national_id_verified = %(idv)s")
        params["idv"] = id_verified
    if accepting_work is not None:
        where.append("p.accepting_work = %(acc)s")
        params["acc"] = accepting_work
    if q:
        # Staff may search by national ID or TIN, but the list never sends them back
        where.append(
            "(p.display_name ilike %(q)s or p.legal_name ilike %(q)s or p.phone ilike %(q)s "
            "or p.registration_no ilike %(q)s or p.national_id ilike %(q)s or p.tin ilike %(q)s)"
        )
        params["q"] = f"%{q}%"
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from providers p where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select * from (
          select {ADMIN_LIST_COLUMNS},
            (select count(*) from engagements e where e.provider_id = p.id
               and e.status = any(array['requested','accepted','in_progress'])) as open_jobs,
            (select count(*) from engagements e where e.provider_id = p.id and e.disputed
               and e.dispute_status = 'open') as open_disputes
          from providers p where {clause}
        ) p
        order by {ADMIN_SORTS.get(sort, ADMIN_SORTS["queue"])}
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
    provider["renewal"] = {"opens_on": renewal_opens_on(provider), "blocker": renewal_blocker(provider)}
    provider["vetting"] = vetting.checklist(provider, for_staff=True)
    provider["pending_change"] = pending_change(provider_id)
    # What Fayda returned when this person verified their national ID: the proof of identity
    provider["identity"] = fetch_one(
        """
        select method, id_type, id_last4, verified_name, birthdate, gender, phone, verified_at
        from id_verifications where user_id = %s and status = 'verified' order by verified_at desc limit 1
        """,
        (provider["user_id"],),
    ) if provider.get("user_id") else None
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
    if action in ("approve", "renew") and len((note or "").strip()) < 10:
        # The audit log is the proof: say what was checked (ID, licence, references)
        raise MarketplaceError(f"Write what you checked before you {action} (at least 10 characters)")
    old_expiry = provider.get("license_expires_at")
    if action == "renew":
        blocker = renewal_blocker(provider)
        if blocker:
            raise MarketplaceError(blocker, 409)
    if action == "approve":
        # Every required document checked and in date before anyone is listed (services/vetting.py)
        blocker = vetting.blocker(provider)
        if blocker:
            raise MarketplaceError(blocker, 409)
    if action == "reinstate":
        blocker = vetting.expired_blocker(provider)
        if blocker:
            raise MarketplaceError(blocker, 409)

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
            # A suspended provider can't keep client work: send it back to staff, with a line in each hire's history
            moved = conn.execute(
                "update engagements set provider_id = null, status = 'open', updated_at = now(), "
                "admin_note = coalesce(admin_note || E'\\n', '') || 'Provider suspended. Reassign.' "
                "where provider_id = %s and status = any(%s) returning id::text, status",
                (provider_id, list(ACTIVE_ENGAGEMENT)),
            ).fetchall()
            for hire in moved:
                _event(conn, hire["id"], "provider_suspended", who="staff", actor=actor, to_status="open",
                       provider_id=provider_id, note="Provider suspended; job sent back to staff to reassign")
        if action in ("approve", "renew", "reinstate"):
            # Keep the before and after in the log so a renewal can be traced
            note = f"{note or ''} (valid until {old_expiry or 'not set'} -> {updates['license_expires_at']})".strip()
        _log(conn, provider_id, action, actor, note)
    recompute(provider_id)
    return get(provider_id)


def renewal_opens_on(provider: dict) -> date | None:
    """A listing can be renewed from this many days before it expires (platform setting license_renew_window_days)."""
    expires = provider.get("license_expires_at")
    if not expires:
        return None
    return expires - timedelta(days=platform_settings.get_int("license_renew_window_days"))


def renewal_blocker(provider: dict) -> str | None:
    """Why a listing can't be renewed now, or None. Renewing early or twice proves nothing, so it isn't allowed."""
    opens = renewal_opens_on(provider)
    if opens and date.today() < opens:
        return (f"The listing is valid until {provider['license_expires_at']:%d %b %Y}. "
                f"Renewal opens on {opens:%d %b %Y}.")
    if provider["entity_type"] == "individual" and not provider.get("id_verified"):
        return "Verify the provider's national ID with Fayda before renewing."
    if provider["entity_type"] != "individual" and not provider.get("trade_license_no"):
        return "Add the company's trade licence number before renewing."
    return vetting.blocker(provider)


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
        f"updated_at = now() where status = 'approved' and license_expires_at < {TODAY}"
    )


def _purge_blockers(conn) -> list[str]:
    """Why the sample data can't be deleted: never take real money records or a real client's hire with it."""
    row = conn.execute(
        """
        select
          (select count(*) from payments pay join engagements e on e.id = pay.engagement_id
             where e.is_sample or e.provider_id in (select id from providers where is_sample)) as payments,
          (select count(*) from provider_ledger l where l.provider_id in (select id from providers where is_sample)) as ledger,
          (select count(*) from payouts po where po.provider_id in (select id from providers where is_sample)) as payouts,
          (select count(*) from engagements e where not e.is_sample
             and e.provider_id in (select id from providers where is_sample)) as real_hires
        """
    ).fetchone()
    reasons = []
    if row["payments"]:
        reasons.append(f"{row['payments']} payment(s)")
    if row["ledger"]:
        reasons.append(f"{row['ledger']} earnings record(s)")
    if row["payouts"]:
        reasons.append(f"{row['payouts']} payout(s)")
    if row["real_hires"]:
        reasons.append(f"{row['real_hires']} hire(s) from real clients")
    return reasons


def sample_status() -> dict:
    """What the "Remove sample data" button may do here."""
    from config.config import settings

    count = fetch_one("select count(*) as c from providers where is_sample")["c"]
    if settings.environment.lower() in ("production", "prod"):
        return {"providers": count, "can_purge": False, "reason": "Sample data can't be removed on the live site."}
    with connection() as conn:
        blockers = _purge_blockers(conn)
    reason = ("Sample providers are linked to " + ", ".join(blockers) + ". Remove those links first."
              if blockers else None if count else "There is no sample data.")
    return {"providers": count, "can_purge": bool(count) and not blockers, "reason": reason}


def purge_samples(*, actor: str) -> dict:
    """Delete the demo providers, hires and reviews from scripts/seed_providers.py. Only outside production,
    and never when a sample provider has money records or a real client's hire."""
    from config.config import settings

    if settings.environment.lower() in ("production", "prod"):
        raise MarketplaceError("Sample data can't be removed on the live site", 403)
    with connection() as conn, conn.transaction():
        # Lock the sample providers so no hire or payment attaches to them while we check
        conn.execute("select id from providers where is_sample for update").fetchall()
        blockers = _purge_blockers(conn)
        if blockers:
            raise MarketplaceError("Not removed: sample providers are linked to " + ", ".join(blockers), 409)
        users = conn.execute(
            "select user_id::text from providers where is_sample and user_id is not null"
        ).fetchall()
        hires = conn.execute("delete from engagements where is_sample returning id").fetchall()
        n = conn.execute("delete from providers where is_sample returning id").fetchall()
        conn.execute(
            "delete from users where id = any(%s::uuid[]) "
            "and (email like '%%@sample.invalid' or email like '%%.sample@example.com')",
            ([u["user_id"] for u in users],),
        )
        conn.execute("delete from users where email like 'sample-client-%%@sample.invalid'")
    log.warning("Sample data removed by %s: %s providers, %s hires", actor, len(n), len(hires))
    return {"providers_removed": len(n), "hires_removed": len(hires)}


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
    as review_change_status,
  e.refund_needed, e.refund_flagged_at, e.refund_flagged_by, e.dispute_resolved_by, e.dispute_resolved_at
"""
# Staff-only fields, removed from what the client and the provider see
STAFF_ONLY = ("admin_note", "refund_needed", "refund_flagged_at", "refund_flagged_by", "dispute_resolved_by")
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

    view = {k: v for k, v in engagement.items() if k not in STAFF_ONLY}
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

    view = {k: v for k, v in engagement.items() if k not in STAFF_ONLY}
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


# A client can't flood providers' bells or the staff queue with requests
MAX_WAITING_REQUESTS = 10   # open or requested at once
MAX_REQUESTS_PER_HOUR = 10


def _hire_limit(user_id: str) -> None:
    row = fetch_one(
        "select count(*) filter (where status in ('open', 'requested')) as waiting, "
        "count(*) filter (where created_at > now() - interval '1 hour') as last_hour "
        "from engagements where client_user_id = %s",
        (user_id,),
    )
    if row["waiting"] >= MAX_WAITING_REQUESTS:
        raise MarketplaceError(f"You have {row['waiting']} requests waiting for an answer. Cancel some, or wait for "
                               "providers to reply, before sending more.", 429)
    if row["last_hour"] >= MAX_REQUESTS_PER_HOUR:
        raise MarketplaceError("You sent many requests in the last hour. Please try again later.", 429)


def create_hire(data: dict, *, user_id: str) -> dict:
    _hire_limit(user_id)
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
    _event(None, row["id"], "created", who="client", to_status="requested" if provider_id else "open",
           provider_id=provider_id)
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
        _event(None, r["id"], "auto_confirmed", who="system", from_status="completed", to_status="completed",
               note=f"Closed after {AUTO_CONFIRM_DAYS} days with no problem reported")
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
    payment_status: str | None = None, refund_needed: bool | None = None,
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
    if payment_status:
        where.append("e.payment_status = %(pay)s")
        params["pay"] = payment_status
    if refund_needed is not None:
        where.append("e.refund_needed = %(refund)s")
        params["refund"] = refund_needed
    if q:
        # Title, client, provider, or a reference: the start of the hire id or a payment's tx_ref
        where.append("(e.client_name ilike %(q)s or e.client_phone ilike %(q)s or e.title ilike %(q)s "
                     "or p.display_name ilike %(q)s or p.registration_no ilike %(q)s or e.id::text like %(ref)s "
                     "or exists (select 1 from payments pq where pq.engagement_id = e.id and pq.tx_ref ilike %(q)s))")
        params["q"] = f"%{q}%"
        params["ref"] = f"{q.lower()}%"
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from {ENGAGEMENT_FROM} where {clause}", params)["c"]
    items = fetch_all(
        f"select {ENGAGEMENT_COLUMNS} from {ENGAGEMENT_FROM} where {clause} "
        f"order by e.created_at desc limit %(limit)s offset %(offset)s",
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": items}


CHANGED_MEANWHILE = "This job changed in the meantime. Refresh the page and try again."


def _event(conn, engagement_id: str, action: str, *, who: str, actor: str | None = None,
           from_status: str | None = None, to_status: str | None = None, note: str | None = None,
           provider_id: str | None = None) -> None:
    """One line in the hire's history (engagement_events). who: client | provider | staff | system."""
    (conn.execute if conn else execute)(
        "insert into engagement_events (engagement_id, action, actor_kind, actor, from_status, to_status, provider_id, note) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s)",
        (engagement_id, action, who, actor, from_status, to_status, provider_id, (note or "").strip()[:2000] or None),
    )


def _set_status(engagement_id: str, status: str, extra: str = "", params: tuple = (), *,
                allowed: tuple[str, ...] | set[str], guard: str = "", guard_params: tuple = (),
                who: str, action: str, actor: str | None = None, note: str | None = None) -> str:
    """Move a hire only if it is still in an allowed status (and passes the guard), in one statement, so two
    people acting at once can't both win (cancel against pay, start against decline). Records the change in
    the hire's history. Returns the status it moved from; raises 409 when the hire had already moved on."""
    with connection() as conn, conn.transaction():
        row = conn.execute(
            f"update engagements e set status = %s, updated_at = now() {extra} "
            f"from engagements o where o.id = e.id and e.id = %s and e.status = any(%s) {guard} "
            f"returning o.status as old_status, e.provider_id::text",
            (status, *params, engagement_id, list(allowed), *guard_params),
        ).fetchone()
        if not row:
            raise MarketplaceError(CHANGED_MEANWHILE, 409)
        _event(conn, engagement_id, action, who=who, actor=actor, from_status=row["old_status"], to_status=status,
               note=note, provider_id=row["provider_id"])
    return row["old_status"]


def _payments_on() -> bool:
    from services import payment_service

    return payment_service.enabled()


def _save_price(engagement_id: str, price: float, note: str | None) -> None:
    # Never once the client is paying or has paid, even if a checkout started a moment ago
    changed = execute(
        "update engagements set agreed_price = %s, price_note = %s, updated_at = now() where id = %s "
        "and status in ('accepted', 'in_progress') and payment_status not in ('paid', 'pending')",
        (price, (note or "").strip() or None, engagement_id),
    )
    if not changed:
        raise MarketplaceError("The price can't change now: the client already paid or is paying", 409)


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
    # Still this provider's job (staff may have reassigned it a moment ago) and still in the expected status
    _set_status(engagement_id, new_status, extra, params, allowed=tuple(allowed), guard="and e.provider_id = %s",
                guard_params=(me["id"],), who="provider", action=action, actor=me["display_name"],
                note=reason if action == "decline" else note if action == "complete" else None)
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
        # The payment guard is in the statement itself: a checkout that started a moment ago wins
        _set_status(engagement_id, "cancelled", allowed=("open", "requested", "accepted", "in_progress"),
                    guard="and e.payment_status not in ('paid', 'pending')", who="client", action="cancel")
    elif action == "complete":
        # Without online payment the client confirms delivery; with it, paying is the confirmation
        if _payments_on():
            raise MarketplaceError("Pay for the delivered work to close the job", 409)
        if eng["status"] != "completed":
            who = eng.get("provider_name") or "The provider"
            raise MarketplaceError(f"You can confirm once {who} marks the work as delivered", 409)
        if eng.get("client_confirmed_at"):
            raise MarketplaceError("You already confirmed this job", 409)
        with connection() as conn, conn.transaction():
            done = conn.execute("update engagements set client_confirmed_at = now(), updated_at = now() "
                                "where id = %s and status = 'completed' and client_confirmed_at is null returning id",
                                (engagement_id,)).fetchone()
            if not done:
                raise MarketplaceError(CHANGED_MEANWHILE, 409)
            _event(conn, engagement_id, "confirmed", who="client", from_status="completed", to_status="completed",
                   provider_id=eng["provider_id"])
    elif action == "dispute":
        if eng["status"] not in ("accepted", "in_progress", "completed"):
            raise MarketplaceError("You can report a problem once a provider has taken the job", 409)
        if eng["disputed"]:
            raise MarketplaceError("You already reported a problem with this job", 409)
        if not reason:
            raise MarketplaceError("Tell us what went wrong")
        with connection() as conn, conn.transaction():
            done = conn.execute(
                "update engagements set disputed = true, dispute_status = 'open', dispute_reason = %s, updated_at = now() "
                "where id = %s and not coalesce(disputed, false) "
                "and status in ('accepted', 'in_progress', 'completed') returning status",
                (reason, engagement_id),
            ).fetchone()
            if not done:
                raise MarketplaceError(CHANGED_MEANWHILE, 409)
            _event(conn, engagement_id, "complaint", who="client", from_status=done["status"], to_status=done["status"],
                   note=reason, provider_id=eng["provider_id"])
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
    reason = (reason or "").strip() or None
    if hide and len(reason or "") < 5:
        raise MarketplaceError("Write why the review is hidden (at least 5 characters)")
    with connection() as conn, conn.transaction():
        conn.execute(
            "update reviews set hidden = %s, hidden_reason = %s, hidden_by = %s, "
            "hidden_at = case when %s then now() end where id = %s",
            (hide, reason if hide else None, actor if hide else None, hide, review_id),
        )
        _log(conn, review["provider_id"], "review_hidden" if hide else "review_restored", actor, reason)
    recompute(review["provider_id"])
    return {"id": review_id, "hidden": hide}


def list_reviews_admin(*, hidden: bool | None = None, max_rating: int | None = None, q: str | None = None,
                       limit: int = 50, offset: int = 0) -> dict:
    where, params = ["true"], []
    if q:
        where.append("(p.display_name ilike %s or u.email ilike %s or e.client_name ilike %s or r.comment ilike %s)")
        params += [f"%{q}%"] * 4
    if hidden is not None:
        where.append("r.hidden = %s")
        params.append(hidden)
    if max_rating:
        where.append("r.rating <= %s")
        params.append(max_rating)
    clause = " and ".join(where)
    joins = ("from reviews r join providers p on p.id = r.provider_id "
             "join engagements e on e.id = r.engagement_id left join users u on u.id = r.client_user_id")
    total = fetch_one(f"select count(*) as c {joins} where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select r.id::text, r.rating, r.comment, r.reply, r.hidden, r.hidden_reason, r.hidden_by,
          r.created_at, r.would_hire_again, p.display_name as provider_name, p.slug as provider_slug,
          u.email as client_email, e.title as job_title, e.id::text as engagement_id
        {joins}
        where {clause} order by r.created_at desc limit %s offset %s
        """,
        [*params, limit, offset],
    )
    return {"total": total, "items": items}


# What staff may do to a hire, from which statuses. Staff never set accepted, in progress or delivered:
# only the provider moves a job forward. Paid (or paying) jobs can't be cancelled or reopened here; the
# money goes back through a refund. Once a provider accepts, the job can't be moved to someone else.
STAFF_HIRE_ACTIONS = {
    "assign": ("open", "requested"),
    "cancel": ("open", "requested", "accepted", "in_progress", "completed"),
    "reopen": ("declined", "cancelled"),
    "note": ENGAGEMENT_STATUSES,
}
NOT_PAID = "and e.payment_status not in ('paid', 'pending')"


def admin_update_engagement(
    engagement_id: str, *, action: str, provider_id: str | None = None, note: str, actor: str,
) -> dict:
    eng = get_engagement(engagement_id)
    if not eng:
        raise MarketplaceError("Request not found", 404)
    if action not in STAFF_HIRE_ACTIONS:
        raise MarketplaceError("Unknown action")
    note = (note or "").strip()
    if len(note) < 5:
        raise MarketplaceError("Write a note saying why (at least 5 characters)")
    allowed = STAFF_HIRE_ACTIONS[action]
    if eng["status"] not in allowed:
        reason = {
            "assign": "A provider can only be assigned before anyone accepts the job",
            "cancel": "This job is already closed",
            "reopen": "Only declined or cancelled requests can be reopened",
        }.get(action, "Not possible now")
        raise MarketplaceError(reason, 409)
    if action in ("cancel", "reopen") and eng.get("payment_status") in ("paid", "pending"):
        raise MarketplaceError("This job is paid or being paid. Money goes back through a refund, not by "
                               "cancelling or reopening the job.", 409)
    if action == "cancel" and eng["status"] == "completed" and eng.get("client_confirmed_at"):
        raise MarketplaceError("This job is closed", 409)
    old_provider = eng["provider_id"]
    title = eng["title"]

    if action == "note":
        with connection() as conn, conn.transaction():
            conn.execute("update engagements set admin_note = %s, updated_at = now() where id = %s", (note, engagement_id))
            _event(conn, engagement_id, "staff_note", who="staff", actor=actor, note=note, provider_id=old_provider)
        return get_engagement(engagement_id)

    if action == "assign":
        if not provider_id:
            raise MarketplaceError("Choose a provider")
        provider = fetch_one(
            f"select p.id::text, p.user_id::text, p.display_name, p.accepting_work from providers p "
            f"where p.id::text = %s and {LIVE}", (provider_id,))
        if not provider:
            raise MarketplaceError("Only approved providers with a valid licence can be assigned")
        if not provider["accepting_work"]:
            raise MarketplaceError("This provider isn't taking new work right now", 409)
        if provider["id"] == old_provider:
            raise MarketplaceError("This provider already has the request", 409)
        if provider["user_id"] and provider["user_id"] == eng["client_user_id"]:
            raise MarketplaceError("A provider can't be assigned their own request", 409)
        # Never accepted_at: the new provider sees the client's phone only after they accept
        _set_status(engagement_id, "requested", ", provider_id = %s::uuid, admin_note = %s, accepted_at = null",
                    (provider["id"], note), allowed=allowed, who="staff", actor=actor, note=note,
                    action="reassigned" if old_provider else "assigned")
    elif action == "cancel":
        _set_status(engagement_id, "cancelled", ", admin_note = %s", (note,), allowed=allowed, guard=NOT_PAID,
                    who="staff", actor=actor, note=note, action="staff_cancelled")
    elif action == "reopen":
        # Back to the staff queue with no provider, ready to be assigned again
        _set_status(engagement_id, "open", ", provider_id = null, admin_note = %s, accepted_at = null, "
                    "declined_reason = null", (note,), allowed=allowed, guard=NOT_PAID, who="staff", actor=actor,
                    note=note, action="reopened")

    hire = get_engagement(engagement_id)
    for pid in {old_provider, hire["provider_id"]} - {None}:
        recompute(pid)
    # Everyone involved hears about it; the staff note itself stays internal
    if action == "assign":
        _tell(hire, "provider", f"New request: {title}",
              "Our team matched you with this client. Accept to see their phone number.")
        if old_provider:
            _tell({**eng, "provider_id": old_provider}, "provider", f"Request moved to another provider: {title}",
                  "Our team reassigned this request. You don't need to do anything.")
        _tell(hire, "client", f"We found a provider for {title}",
              f"{hire['provider_name']} has your request. You will get their phone number once they accept.")
    elif action == "cancel":
        _tell(eng, "client", f"Request cancelled by our team: {title}",
              "If you have questions, contact support from the Help page.")
        _tell(eng, "provider", f"Request cancelled by our team: {title}", "You don't need to do anything more on it.")
    elif action == "reopen":
        _tell(eng, "client", f"We are finding a provider for {title}",
              "Our team reopened your request and will match you with a provider.")
        if old_provider:
            _tell(eng, "provider", f"Request closed for you: {title}", "Our team moved this request back to the queue.")
    return hire


def resolve_dispute(engagement_id: str, decision: str, *, note: str | None, actor: str) -> dict:
    eng = get_engagement(engagement_id)
    if not eng or not eng["disputed"]:
        raise MarketplaceError("No complaint on this job", 404)
    if decision not in ("upheld", "dismissed"):
        raise MarketplaceError("Decision must be upheld or dismissed")
    note = (note or "").strip()
    if len(note) < 5:
        raise MarketplaceError("Write the finding (at least 5 characters). The client and provider see it.")
    with connection() as conn, conn.transaction():
        # Decided once: a second click, or a second staff member, gets a 409 instead of flipping it
        row = conn.execute(
            """
            update engagements set dispute_status = %(d)s, dispute_note = %(note)s, dispute_resolved_by = %(actor)s,
              dispute_resolved_at = now(), updated_at = now(),
              -- An upheld complaint on a paid job: the client is owed money back
              refund_needed = refund_needed or (%(d)s = 'upheld' and payment_status = 'paid'),
              refund_flagged_at = case when %(d)s = 'upheld' and payment_status = 'paid' then now() else refund_flagged_at end,
              refund_flagged_by = case when %(d)s = 'upheld' and payment_status = 'paid' then %(actor)s else refund_flagged_by end
            where id = %(id)s and disputed and dispute_status = 'open'
            returning status, refund_needed
            """,
            {"d": decision, "note": note, "actor": actor, "id": engagement_id},
        ).fetchone()
        if not row:
            raise MarketplaceError("This complaint was already decided", 409)
        _event(conn, engagement_id, f"complaint_{decision}", who="staff", actor=actor, from_status=row["status"],
               to_status=row["status"], note=note, provider_id=eng["provider_id"])
        if row["refund_needed"] and decision == "upheld":
            _event(conn, engagement_id, "refund_needed", who="staff", actor=actor,
                   note="Paid job with an upheld complaint", provider_id=eng["provider_id"])
        if eng["provider_id"]:
            _log(conn, eng["provider_id"], f"complaint_{decision}", actor, note)
    if eng["provider_id"]:
        recompute(eng["provider_id"])
    word = "upheld" if decision == "upheld" else "not upheld"
    _tell(eng, "client", f"Your complaint about {eng['title']} was {word}", note[:300])
    _tell(eng, "provider", f"A complaint about {eng['title']} was {word}", note[:300])
    return get_engagement(engagement_id)


# ---------------------------------------------------------------- staff hire tools


def admin_hire_detail(engagement_id: str, *, can_see_payments: bool, can_see_support: bool) -> dict | None:
    """One hire for staff: the hire, its full history, payments and the people's support requests."""
    hire = get_engagement(engagement_id)
    if not hire:
        return None
    events = fetch_all(
        "select ev.id, ev.action, ev.actor_kind, ev.actor, ev.from_status, ev.to_status, ev.note, ev.created_at, "
        "ev.provider_id::text, p.display_name as provider_name "
        "from engagement_events ev left join providers p on p.id = ev.provider_id "
        "where ev.engagement_id = %s order by ev.id",
        (engagement_id,),
    )
    # Hires from before the history existed: show what the hire itself records
    if not any(e["action"] == "created" for e in events):
        events.insert(0, {"id": None, "action": "created", "actor_kind": "client", "actor": None, "from_status": None,
                          "to_status": None, "note": None, "created_at": hire["created_at"],
                          "provider_id": None, "provider_name": None})
    payments = fetch_all(
        """
        select tx_ref, gateway, amount::float, status, payment_method, gateway_reference, created_at, verified_at,
          commission_amount::float, provider_amount::float
        from payments where engagement_id = %s order by created_at desc
        """,
        (engagement_id,),
    ) if can_see_payments else None
    tickets = None
    if can_see_support:
        people = [u for u in (hire["client_user_id"], _provider_user(hire["provider_id"])) if u]
        tickets = fetch_all(
            """
            select t.id::text, t.ref, t.subject, t.status, t.queue, t.created_at, t.updated_at,
              case when t.user_id = %s then 'client' else 'provider' end as from_side
            from support_tickets t where t.user_id = any(%s::uuid[])
            order by t.created_at desc limit 20
            """,
            (hire["client_user_id"], people),
        ) if people else []
    return {"hire": hire, "events": events, "payments": payments, "tickets": tickets,
            "actions": staff_actions(hire)}


def staff_actions(hire: dict) -> list[str]:
    """What staff may do to this hire now, so the page only offers what the server will accept."""
    paid = hire.get("payment_status") in ("paid", "pending")
    out = []
    for action, allowed in STAFF_HIRE_ACTIONS.items():
        if hire["status"] not in allowed:
            continue
        if action in ("cancel", "reopen") and paid:
            continue
        if action == "cancel" and hire["status"] == "completed" and hire.get("client_confirmed_at"):
            continue
        out.append(action)
    return out


def assign_candidates(engagement_id: str, *, q: str | None = None, area: str | None = None,
                      specialty: str | None = None, limit: int = 20, offset: int = 0) -> dict | None:
    """Providers staff can assign to an open request: listed (approved, licence in date) and taking work.
    Ranked by fit (the requested service, then specialty, then area), then trust score."""
    hire = get_engagement(engagement_id)
    if not hire:
        return None
    where = [LIVE, "p.accepting_work"]
    params: dict = {"service": hire.get("service_id"), "h_specialty": hire.get("specialty"),
                    "h_area": hire.get("sub_city")}
    if hire.get("provider_id"):
        where.append("p.id <> %(current)s::uuid")
        params["current"] = hire["provider_id"]
    if hire.get("client_user_id"):
        where.append("p.user_id is distinct from %(client)s::uuid")
        params["client"] = hire["client_user_id"]
    if area:
        where.append("(p.sub_city = %(area)s or %(area)s = any(p.service_areas) or 'nationwide' = any(p.service_areas))")
        params["area"] = area
    if specialty:
        where.append("%(specialty)s = any(p.specialties)")
        params["specialty"] = specialty
    if q:
        where.append("(p.display_name ilike %(q)s or p.registration_no ilike %(q)s or p.phone ilike %(q)s)")
        params["q"] = f"%{q}%"
    clause = " and ".join(where)
    total = fetch_one(f"select count(*) as c from providers p where {clause}", params)["c"]
    items = fetch_all(
        f"""
        select p.id::text, p.display_name, p.registration_no, p.provider_type, p.entity_type, p.sub_city,
          p.service_areas, p.specialties, p.trust_score, p.rating_avg::float, p.rating_count, p.completed_count,
          p.license_expires_at,
          coalesce(%(service)s::text = any(p.service_ids), false) as offers_service,
          coalesce(%(h_specialty)s::text = any(p.specialties), false) as same_specialty,
          coalesce(p.sub_city = %(h_area)s::text or %(h_area)s::text = any(p.service_areas), false) as covers_area,
          (select count(*) from engagements e where e.provider_id = p.id
             and e.status = any(array['requested','accepted','in_progress'])) as open_jobs
        from providers p where {clause}
        order by offers_service desc, same_specialty desc, covers_area desc, p.trust_score desc nulls last,
          p.display_name
        limit %(limit)s offset %(offset)s
        """,
        {**params, "limit": limit, "offset": offset},
    )
    return {"total": total, "items": items}


HIRE_CSV_COLUMNS = (
    ("id", "Hire id"), ("created_at", "Created"), ("title", "Title"), ("status", "Status"),
    ("client_name", "Client"), ("client_phone", "Client phone"), ("provider_name", "Provider"),
    ("provider_registration_no", "Provider registration no."), ("service_name", "Service"),
    ("sub_city", "Sub-city"), ("agreed_price", "Price (ETB)"), ("payment_status", "Payment"),
    ("paid_at", "Paid at"), ("paid_tx_ref", "Payment reference"), ("disputed", "Complaint"),
    ("dispute_status", "Complaint status"), ("refund_needed", "Refund needed"), ("completed_at", "Delivered"),
    ("client_confirmed_at", "Closed"),
)
HIRE_CSV_MAX = 10_000


def _csv_cell(value) -> str:
    """Spreadsheet-safe text: a cell starting with = + - @ (or a tab or return) is a formula to Excel."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_engagements_csv(**filters) -> tuple[str, int]:
    """The hires list as CSV with the same filters, up to HIRE_CSV_MAX rows. Returns (text, row count)."""
    import csv
    import io

    rows = list_engagements(**filters, limit=HIRE_CSV_MAX, offset=0)["items"]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([label for _, label in HIRE_CSV_COLUMNS])
    for r in rows:
        writer.writerow([_csv_cell(r.get(key)) for key, _ in HIRE_CSV_COLUMNS])
    return out.getvalue(), len(rows)


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
