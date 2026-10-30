"""Staff side: reviewing documents and references, and the verified kinds for the trust score."""

from __future__ import annotations

from datetime import date

from services.db import connection
from services.vetting.common import (
    _clean_text,
    _notify_provider,
    _recompute,
    _uuid_like,
)
from services.vetting.documents import get_document, references
from services.vetting.rules import (
    EDUCATION_LABELS,
    EDUCATION_LEVELS,
    EXPIRY_SQL,
    KINDS,
    VettingError,
    effective_expiry,
    max_age_days,
    min_education,
)

# ---------------------------------------------------------------- staff side


def review_document(provider_id: str, document_id: str, decision: str, *, actor: str, note: str | None = None,
                    issued_on: date | None = None, expires_on: date | None = None,
                    reference_no: str | None = None, level: str | None = None) -> dict:
    """Verify or reject one document. Staff may correct the dates, number and level to what is printed."""
    if decision not in ("verified", "rejected"):
        raise VettingError("Choose verify or reject")
    doc = get_document(provider_id, document_id)
    if not doc:
        raise VettingError("Document not found", 404)
    note = (note or "").strip() or None
    if decision == "rejected":
        if not note or len(note) < 5:
            raise VettingError("Write why the document is rejected. The provider sees this.")
        if doc["status"] not in ("pending", "verified"):
            raise VettingError(f"This document is {doc['status']} and can't be rejected", 409)
    else:
        if doc["status"] != "pending":
            raise VettingError(f"This document is {doc['status']}, only pending documents can be verified", 409)

    meta = KINDS[doc["kind"]]
    fields = {
        "issued_on": issued_on or doc["issued_on"],
        "expires_on": expires_on or doc["expires_on"],
        "reference_no": _clean_text(reference_no, 60) or doc["reference_no"],
        "level": (level or doc["level"]) if doc["kind"] == "education" else None,
    }
    if decision == "verified":
        today = date.today()
        if meta.needs_issued_on and not fields["issued_on"]:
            raise VettingError("Enter the issue date printed on the certificate before verifying")
        if meta.needs_expires_on and not fields["expires_on"]:
            raise VettingError("Enter the valid-until date printed on the licence before verifying")
        if meta.needs_reference and not fields["reference_no"]:
            raise VettingError(f"Enter the {meta.reference_label.lower()} before verifying")
        if fields["issued_on"] and fields["issued_on"] > today:
            raise VettingError("The issue date can't be in the future")
        if doc["kind"] == "education":
            if fields["level"] not in EDUCATION_LEVELS:
                raise VettingError("Choose the level shown on the certificate")
            need = min_education()
            if EDUCATION_LEVELS.index(fields["level"]) < EDUCATION_LEVELS.index(need):
                raise VettingError(f"Below the minimum ({EDUCATION_LABELS[need]}). Reject it instead.")
        expiry = effective_expiry({"kind": doc["kind"], **fields})
        if expiry and expiry < today:
            raise VettingError(f"This document is out of date (valid until {expiry:%d %b %Y}). Reject it and ask for a new one.")

    with connection() as conn, conn.transaction():
        if decision == "verified":
            # The previous verified (or expired) copy steps aside for this one
            conn.execute(
                "update provider_documents set status = 'superseded' "
                "where provider_id = %s and kind = %s and status in ('verified', 'expired') and id <> %s",
                (provider_id, doc["kind"], document_id),
            )
        conn.execute(
            """
            update provider_documents set status = %s, reviewed_by = %s, reviewed_at = now(), review_note = %s,
              issued_on = %s, expires_on = %s, reference_no = %s, level = %s, reminded_at = null
            where id = %s
            """,
            (decision, actor, note, fields["issued_on"], fields["expires_on"], fields["reference_no"], fields["level"],
             document_id),
        )
        conn.execute(
            "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
            (provider_id, f"document_{decision}", actor, f"{meta.label}" + (f": {note}" if note else "")),
        )
    _notify_provider(provider_id, f"{meta.label} {'verified' if decision == 'verified' else 'not accepted'}",
                     note if decision == "rejected" else "Thank you. It counts toward your listing.")
    _recompute(provider_id)
    return get_document(provider_id, document_id)


def check_reference(provider_id: str, reference_id: str, decision: str, *, actor: str, note: str | None) -> dict:
    if decision not in ("confirmed", "failed"):
        raise VettingError("Choose confirmed or failed")
    if decision == "failed" and not (note or "").strip():
        raise VettingError("Write what happened on the call")
    if not (_uuid_like(reference_id) and _uuid_like(provider_id)):
        raise VettingError("Reference not found", 404)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "update provider_references set status = %s, checked_by = %s, checked_at = now(), note = %s "
            "where id = %s and provider_id = %s and status <> 'removed' returning name",
            (decision, actor, (note or "").strip() or None, reference_id, provider_id),
        ).fetchone()
        if not row:
            raise VettingError("Reference not found", 404)
        conn.execute(
            "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
            (provider_id, f"reference_{decision}", actor, f"{row['name']}" + (f": {note}" if note else "")),
        )
    _recompute(provider_id)
    return {"references": references(provider_id)}


def verified_kinds(conn, provider_id: str) -> set[str]:
    """Kinds with a verified, in-date document, for the trust score."""
    rows = conn.execute(
        f"""
        select d.kind, d.level from provider_documents d
        where d.provider_id = %(id)s and d.status = 'verified'
          and coalesce({EXPIRY_SQL}, current_date) >= current_date
        """,
        {"id": provider_id, "max_age": max_age_days()},
    ).fetchall()
    need = EDUCATION_LEVELS.index(min_education())
    return {r["kind"] for r in rows
            if r["kind"] != "education" or (r["level"] in EDUCATION_LEVELS and EDUCATION_LEVELS.index(r["level"]) >= need)}
