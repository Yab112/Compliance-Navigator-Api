"""Joining, editing a profile, reviewed changes and the provider's own view."""

from __future__ import annotations

import logging
import re
from datetime import date
from difflib import SequenceMatcher

from psycopg.types.json import Jsonb

from services import catalog_service, id_verification, trust_score, vetting
from services.db import connection, fetch_one

from .common import (
    AREAS,
    DELIVERY_MODES,
    ENTITY_TYPES,
    NULLABLE_FIELDS,
    PROFILE_FIELDS,
    PROVIDER_TYPES,
    SPECIALTIES,
    SUB_CITIES,
    MarketplaceError,
    _log,
    get,
    get_for_user,
)
from .readiness import PROFILE_REQUIRED
from .teams import agency_of, team
from .trust import recompute

log = logging.getLogger(__name__)


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
    if "delivery_modes" in out and out["delivery_modes"] is not None:
        bad = [m for m in out["delivery_modes"] if m not in DELIVERY_MODES]
        if bad:
            raise MarketplaceError(f"Unknown ways of working: {', '.join(bad)}")
        out["delivery_modes"] = [m for m in DELIVERY_MODES if m in out["delivery_modes"]]
    if out.get("visit_fee") is not None and out["visit_fee"] < 0:
        raise MarketplaceError("The visit fee can't be negative")
    if out.get("fee_from") is not None and out.get("fee_to") is not None and out["fee_to"] < out["fee_from"]:
        raise MarketplaceError("The highest fee can't be lower than the lowest fee")
    return out


def _requirements(provider: dict) -> None:
    """What a complete application needs, by type and entity."""
    t, e = provider["provider_type"], provider["entity_type"]
    if t == "guday_geday" and not provider.get("service_ids"):
        raise MarketplaceError("Pick at least one service you handle")
    if t in ("agency", "advisor") and not provider.get("specialties"):
        raise MarketplaceError("Pick at least one specialty")
    if t == "advisor" and not provider.get("delivery_modes"):
        raise MarketplaceError("Say where you work with clients: at their office, at yours, or online")
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
    if not data.get("telegram_username"):
        # Clients message providers on Telegram once a job is accepted (the website form asks for it too)
        raise MarketplaceError("Add your Telegram username so clients can message you")
    fields = _validate({k: data[k] for k in PROFILE_FIELDS if data.get(k) not in (None, "")}, t, e)
    _requirements({**fields, "provider_type": t, "entity_type": e})
    if not fields.get("sub_city"):
        fields["sub_city"] = next((a for a in fields.get("service_areas") or [] if a in SUB_CITIES), None)
    if fields.get("external_license_no"):
        fields["external_license_status"] = "pending"

    id_hash, id_last4 = data.get("national_id_hash"), data.get("national_id_last4")
    if not id_hash and data.get("national_id"):
        id_hash, typed_last4 = id_verification.id_hash_and_last4(data["national_id"])
        id_last4 = id_last4 or typed_last4

    fields |= {
        "user_id": user_id, "provider_type": t, "entity_type": e,
        "slug": _slugify(fields.get("legal_name") if e == "company" and fields.get("legal_name") else data["display_name"]),
        # Never the number itself: a keyed hash (staff search) and the last four characters
        "national_id_hash": id_hash,
        "national_id_last4": id_last4,
        "national_id_verified": bool(data.get("national_id_verified")),
        "id_verification_method": data.get("id_verification_method"),
        "verified_name": data.get("verified_name"),
        "id_document_url": data.get("id_document_url"),
        "is_sample": bool(data.get("is_sample")),
    }
    for arr in ("service_ids", "institution_ids", "service_areas", "specialties", "languages", "highlights",
                "delivery_modes"):
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


def _services(service_ids: list[str]) -> list[dict]:
    return [
        {"id": s["id"], "name": s["name"], "institution": s["institution"]["short_name"],
         "fee_text": s.get("fee_text"), "processing_time_text": s.get("processing_time_text"),
         "summary": s["summary"]}
        for s in catalog_service.services_by_ids(service_ids or [])
    ]


def owner_view(user_id: str) -> dict | None:
    provider = get_for_user(user_id)
    if not provider:
        return None
    provider.pop("national_id_last4", None)
    from services import payment_service

    provider["payout"] = payment_service.payout_view(provider)
    provider["services"] = _services(provider["service_ids"])
    provider["team"] = team(provider["id"], include_pending=True)
    provider["agency"] = agency_of(provider["id"], include_pending=True)
    provider["vetting"] = vetting.checklist(provider)
    doc_status = {i["kind"]: i["status"] for i in provider["vetting"]["items"] if i.get("type") == "document"}
    provider["tips"] = trust_score.tips(
        {"parts": provider["score_breakdown"] or [], "is_new": provider["rating_count"] < trust_score.NEW_UNTIL_REVIEWS},
        provider, doc_status,
    ) if provider["score_breakdown"] else []
    provider["completeness"] = completeness(provider)
    provider["readiness"] = _readiness_view(provider)
    provider["pending_change"] = pending_change(provider["id"])
    provider["rejected_change"] = None if provider["pending_change"] else last_rejected_change(provider["id"])
    if provider["status"] not in ("rejected", "suspended"):
        provider.pop("review_note", None)
    return provider


def _readiness_view(provider: dict) -> dict:
    """What the dashboard banner and the staff page show: listed or not, and why."""
    live = provider["status"] == "approved" and provider.get("ready_to_work") and (
        not provider.get("ready_until") or provider["ready_until"] >= date.today())
    return {"listed": bool(live), "reasons": provider.get("not_ready_reasons") or [],
            "checked_at": provider.get("readiness_checked_at"), "profile_required": PROFILE_REQUIRED}


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
