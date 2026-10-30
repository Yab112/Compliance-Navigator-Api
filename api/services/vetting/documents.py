"""Provider side: uploading documents, reading them back, and references."""

from __future__ import annotations

from datetime import date

from services import storage_service
from services.db import connection, fetch_all, fetch_one
from services.vetting.common import _clean_text, _recompute, _uuid_like
from services.vetting.guarantor import current_guarantor
from services.vetting.rules import (
    DOC_COLUMNS,
    EDUCATION_LABELS,
    EDUCATION_LEVELS,
    KINDS,
    MAX_REFERENCES,
    VettingError,
    _public_doc,
    document_kinds,
    max_age_days,
    min_education,
)


def references(provider_id: str) -> list[dict]:
    return fetch_all(
        "select id::text, name, phone, relationship, status, checked_by, checked_at, note, created_at "
        "from provider_references where provider_id = %s and status <> 'removed' order by created_at",
        (provider_id,),
    )


# ---------------------------------------------------------------- provider side



def upload(provider: dict, kind: str, content: bytes, *, actor: str, issued_on: date | None = None,
           expires_on: date | None = None, reference_no: str | None = None, issuer: str | None = None,
           level: str | None = None, strict: bool = True, consent: bool = False) -> dict:
    """Store a new document as pending. strict=False is for files that arrive with the join form,
    without dates: staff fill those in when they verify."""
    if kind not in KINDS or kind not in document_kinds(provider):
        raise VettingError("This document isn't needed for your kind of profile")
    meta = KINDS[kind]
    if meta.sensitive and not consent:
        # Offence data: kept only with the person's explicit agreement (privacy policy, Proclamation 1321/2024)
        raise VettingError("Tick the box to agree that we keep and check your police clearance")
    reference_no, issuer = _clean_text(reference_no, 60), _clean_text(issuer, 120)
    today = date.today()
    if issued_on and issued_on > today:
        raise VettingError("The issue date can't be in the future")
    if expires_on and expires_on < today:
        raise VettingError("This document has already expired. Upload a current one.")
    if issued_on and expires_on and expires_on <= issued_on:
        raise VettingError("The valid-until date must be after the issue date")
    if strict:
        if meta.needs_issued_on and not issued_on:
            raise VettingError("Enter the date printed on the certificate")
        if meta.needs_reference and not reference_no:
            raise VettingError(f"Enter the {meta.reference_label.lower()} printed on the document")
        if meta.needs_expires_on and not expires_on:
            raise VettingError("Enter the date the licence is valid until")
    if kind == "police_clearance" and issued_on:
        age = (today - issued_on).days
        if age > max_age_days():
            raise VettingError(
                f"This clearance was issued {age} days ago. We accept clearances up to {max_age_days()} days "
                "old. Please get a new one from the police."
            )
    if kind == "education":
        if level not in EDUCATION_LEVELS:
            raise VettingError("Choose the level of this certificate")
        need = min_education()
        if EDUCATION_LEVELS.index(level) < EDUCATION_LEVELS.index(need):
            raise VettingError(f"Guday Geday need at least {EDUCATION_LABELS[need]}. Upload that certificate or a higher one.")
    else:
        level = None
    guarantor_id = None
    if meta.guarantor:
        current = current_guarantor(provider["id"])
        if not current:
            raise VettingError("Enter your guarantor's details first, then upload their papers")
        guarantor_id = current["id"]
    try:
        key, content_type = storage_service.save_vetting_file(content, images_only=meta.images_only)
    except ValueError as exc:
        raise VettingError(str(exc)) from exc

    try:
        with connection() as conn, conn.transaction():
            # An unchecked or rejected copy of the same kind is replaced; a verified one stays until
            # the new one is verified.
            conn.execute(
                "update provider_documents set status = 'superseded' "
                "where provider_id = %s and kind = %s and status in ('pending', 'rejected')",
                (provider["id"], kind),
            )
            row = conn.execute(
                """
                insert into provider_documents (provider_id, kind, level, file_key, content_type, size_bytes,
                  issued_on, expires_on, reference_no, issuer, uploaded_by, consent_at, guarantor_id)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, case when %s then now() end, %s) returning id::text
                """,
                (provider["id"], kind, level, key, content_type, len(content), issued_on, expires_on,
                 reference_no, issuer, actor, consent, guarantor_id),
            ).fetchone()
            conn.execute(
                "insert into provider_events (provider_id, action, actor, note) values (%s, 'document_uploaded', %s, %s)",
                (provider["id"], actor, meta.label),
            )
            if provider.get("status") == "rejected":
                # New proof on a rejected application sends it back to the review queue
                conn.execute("update providers set status = 'pending', updated_at = now() where id = %s", (provider["id"],))
                conn.execute(
                    "insert into provider_events (provider_id, action, actor, note) values (%s, 'updated', %s, 'resubmitted')",
                    (provider["id"], actor),
                )
    except Exception:
        storage_service.delete_vetting_file(key)
        raise
    _recompute(provider["id"])
    return get_document(provider["id"], row["id"])


def get_document(provider_id: str, document_id: str) -> dict | None:
    """A document, only when it belongs to this provider (callers pass the provider they checked)."""
    try:
        row = fetch_one(
            f"select {DOC_COLUMNS} from provider_documents d where d.id::text = %s and d.provider_id::text = %s",
            (document_id, provider_id),
        )
    except Exception:
        return None
    return _public_doc(row, max_age_days()) if row else None


def history(provider_id: str, *, limit: int = 20, offset: int = 0) -> dict:
    total = fetch_one("select count(*) as n from provider_documents where provider_id = %s", (provider_id,))["n"]
    rows = fetch_all(
        f"select {DOC_COLUMNS} from provider_documents d where d.provider_id = %s "
        "order by d.uploaded_at desc limit %s offset %s",
        (provider_id, limit, offset),
    )
    max_age = max_age_days()
    return {"total": total, "items": [_public_doc(r, max_age) for r in rows]}


def read_file(provider_id: str, document_id: str, *, actor: str, by_staff: bool,
              may_see_sensitive: bool = True) -> tuple[bytes, str, dict]:
    """The document's bytes. Staff opening a police clearance is written to the audit log."""
    row = fetch_one(
        "select id::text, kind, file_key, reference_no from provider_documents "
        "where id::text = %s and provider_id::text = %s",
        (document_id, provider_id),
    ) if _uuid_like(document_id) and _uuid_like(provider_id) else None
    if not row:
        raise VettingError("Document not found", 404)
    if by_staff and KINDS[row["kind"]].sensitive and not may_see_sensitive:
        raise VettingError("Opening criminal record documents needs the 'See criminal record checks' permission", 403)
    found = storage_service.read_private_file(row["file_key"])
    if not found:
        raise VettingError("The file is missing from storage", 404)
    if by_staff and (KINDS[row["kind"]].sensitive or KINDS[row["kind"]].log_views):
        with connection() as conn, conn.transaction():
            conn.execute(
                "insert into provider_events (provider_id, action, actor, note) values (%s, 'document_viewed', %s, %s)",
                (provider_id, actor, f"Opened {KINDS[row['kind']].label.lower()}"
                 + (f" no. {row['reference_no']}" if row["reference_no"] else "")),
            )
    content, content_type = found
    return content, content_type, row


def set_references(provider: dict, refs: list[dict], *, actor: str) -> list[dict]:
    """Replace the provider's references. People already on file (same phone) keep their check."""
    if len(refs) > MAX_REFERENCES:
        raise VettingError(f"Add at most {MAX_REFERENCES} references")
    phones = [r["phone"] for r in refs]
    if len(set(phones)) != len(phones):
        raise VettingError("Each reference needs a different phone number")
    if provider.get("phone") and provider["phone"] in phones:
        raise VettingError("A reference can't be your own phone number")
    current = {r["phone"]: r for r in references(provider["id"])}
    with connection() as conn, conn.transaction():
        for phone, r in current.items():
            if phone not in phones:
                conn.execute("update provider_references set status = 'removed' where id = %s", (r["id"],))
        for r in refs:
            old = current.get(r["phone"])
            if old and (old["name"], old["relationship"]) == (r["name"], r["relationship"]):
                continue
            if old:
                conn.execute("update provider_references set status = 'removed' where id = %s", (old["id"],))
            conn.execute(
                "insert into provider_references (provider_id, name, phone, relationship) values (%s, %s, %s, %s)",
                (provider["id"], r["name"].strip(), r["phone"], r["relationship"].strip()),
            )
        conn.execute(
            "insert into provider_events (provider_id, action, actor, note) values (%s, 'references_updated', %s, %s)",
            (provider["id"], actor, f"{len(refs)} reference(s)"),
        )
    _recompute(provider["id"])
    return references(provider["id"])
