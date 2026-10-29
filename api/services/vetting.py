"""Vetting: who may be listed as a Guday Geday or agency, and the proof staff check before they do.

Clients let a Guday Geday handle their papers, money and sometimes their ID, so a listing needs
more than a sign-up. The requirements depend on who the provider is:

  Individual (Guday Geday, or a one-person agency)
    - national ID verified with Fayda (a staff-checked ID copy when Fayda is switched off)
    - police clearance certificate (የወንጀል ሪከርድ ማስረጃ), no older than the platform setting
      police_clearance_max_age_days (180 by default)
    - education certificate at or above the platform setting vetting_min_education (grade 12 by default)
    - passport-style photo
    - Telegram username, so clients and staff can reach them
    - two references staff phoned, only when the setting vetting_references_required is on

  Company (agency)
    - the representative's national ID verified with Fayda
    - trade licence (with its valid-until date), TIN certificate
    - the representative's police clearance certificate

Every document is checked by a person: staff verify or reject each one (a rejection always has a
reason the provider sees). Approving or renewing a listing is refused until every required item is
verified and in date. Nothing is deleted: a new upload supersedes the old one, which stays on file.
Opening a police clearance is written to the provider's audit log, because it is criminal record data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from services import platform_settings, storage_service
from services.db import connection, fetch_all, fetch_one

log = logging.getLogger(__name__)


class VettingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Kind:
    label: str
    am: str
    help: str  # what to bring, shown to the provider
    how_to_verify: str  # shown to staff
    reference_label: str = "Reference number"
    needs_issued_on: bool = False
    needs_reference: bool = False
    needs_expires_on: bool = False
    needs_level: bool = False
    images_only: bool = False
    sensitive: bool = False  # every staff view is logged


KINDS: dict[str, Kind] = {
    "police_clearance": Kind(
        "Police clearance certificate", "የወንጀል ሪከርድ ማስረጃ",
        "Get it from the Federal Police Commission, Forensic Investigation Department, in Addis Ababa "
        "(they take your fingerprints; it takes about three weeks). "
        "Upload a clear photo or scan of the whole certificate, with the stamp and signature visible.",
        "Check the name matches the Fayda name and the photo matches the person. Check the issuing "
        "office, the stamp and signature, the certificate number and the issue date. If anything looks "
        "off, write to or call the Federal Police Forensic Investigation Department with the certificate "
        "number to confirm it is genuine. There is no public online check.",
        reference_label="Certificate number", needs_issued_on=True, needs_reference=True, sensitive=True,
    ),
    "education": Kind(
        "Education certificate", "የትምህርት ማስረጃ",
        "Your highest certificate: grade 12 national exam (ESSLCE) result or school completion, TVET "
        "certificate or Certificate of Competence (COC), diploma or degree.",
        "Check the name, school or institution, level and year. Grade 12 (ESSLCE): look up the "
        "result with the registration number at result.eaes.et (Educational Assessment and "
        "Examinations Service). Degrees: the Education and Training Authority (ETA, call 9799) "
        "authenticates them with the university; some carry a QR seal you can scan. TVET COCs: call "
        "the assessment and certification agency that issued them. Many fake degrees circulate, and "
        "degrees from unaccredited colleges are not valid.",
        reference_label="Certificate or registration number", needs_level=True,
    ),
    "photo": Kind(
        "Passport-style photo", "ፓስፖርት መጠን ፎቶ",
        "A recent photo of your face on a plain background, like a passport photo. Only staff see it.",
        "Compare the face with the person you meet and with the police clearance photo.",
        images_only=True,
    ),
    "trade_licence": Kind(
        "Trade licence", "የንግድ ፈቃድ",
        "The company's current trade licence (renewed every year), showing the licence number and "
        "the date it is valid until.",
        "Check the business name, licence number, licensed activity and valid-until date. The "
        "licence can be checked on the Ministry of Trade and Regional Integration's e-Trade site "
        "(etrade.gov.et) or with the trade bureau that issued it. Licences are renewed every year.",
        reference_label="Licence number", needs_reference=True, needs_expires_on=True,
    ),
    "tin_certificate": Kind(
        "TIN certificate", "የግብር ከፋይ መለያ ቁጥር ሰርተፍኬት",
        "The company's taxpayer registration certificate from the Ministry of Revenues.",
        "Check the TIN on the certificate matches the TIN on the profile and the company name matches "
        "the trade licence.",
        reference_label="TIN", needs_reference=True,
    ),
    "id_copy": Kind(
        "Copy of national ID", "የብሔራዊ መታወቂያ ቅጂ",
        "Only needed when Fayda verification is switched off: a clear copy of your national ID or kebele ID.",
        "Compare the name and photo with the person and the police clearance. Fayda verification is "
        "stronger; prefer it when available.",
        reference_label="ID number",
    ),
}

# Lowest to highest. Staff confirm the level on the certificate when they verify it.
EDUCATION_LEVELS = ("grade_10", "grade_12", "tvet", "diploma", "degree")
EDUCATION_LABELS = {
    "grade_10": "Grade 10",
    "grade_12": "Grade 12 (ESSLCE or completion)",
    "tvet": "TVET certificate or COC",
    "diploma": "Diploma (TVET level IV-V or college)",
    "degree": "Bachelor's degree or higher",
}
STATUSES = ("pending", "verified", "rejected", "expired", "superseded")
REFERENCES_NEEDED = 2
MAX_REFERENCES = 3

DOC_COLUMNS = """
  d.id::text, d.provider_id::text, d.kind, d.level, d.content_type, d.size_bytes, d.issued_on, d.expires_on,
  d.reference_no, d.issuer, d.status, d.reviewed_by, d.reviewed_at, d.review_note, d.reminded_at,
  d.uploaded_at, d.consent_at
"""


def max_age_days() -> int:
    return platform_settings.get_int("police_clearance_max_age_days")


def min_education() -> str:
    value = platform_settings.get("vetting_min_education")
    return value if value in EDUCATION_LEVELS else "grade_12"


def references_required() -> bool:
    return bool(platform_settings.get("vetting_references_required"))


def _fayda_on() -> bool:
    from services import id_verification

    return id_verification.is_required()


# Effective expiry in SQL: the printed valid-until date, and for a police clearance also its
# issue date plus the accepted age (the owner can shorten or lengthen it in Platform settings).
EXPIRY_SQL = ("least(d.expires_on, case when d.kind = 'police_clearance' and d.issued_on is not null "
              "then d.issued_on + %(max_age)s::int end)")


def effective_expiry(doc: dict, max_age: int | None = None) -> date | None:
    dates = [doc.get("expires_on")]
    if doc["kind"] == "police_clearance" and doc.get("issued_on"):
        dates.append(doc["issued_on"] + timedelta(days=max_age if max_age is not None else max_age_days()))
    dates = [d for d in dates if d]
    return min(dates) if dates else None


def _is_company(provider: dict) -> bool:
    return provider["entity_type"] == "company"


def document_kinds(provider: dict) -> list[str]:
    """Kinds this provider may upload, required ones first."""
    kinds = ["trade_licence", "tin_certificate", "police_clearance"] if _is_company(provider) \
        else ["police_clearance", "education", "photo"]
    if not _fayda_on():
        kinds.append("id_copy")
    return kinds


def _public_doc(doc: dict | None, max_age: int) -> dict | None:
    if not doc:
        return None
    out = dict(doc)
    expiry = effective_expiry(doc, max_age)
    out["valid_until"] = expiry
    out["days_left"] = (expiry - date.today()).days if expiry else None
    out["label"] = KINDS[doc["kind"]].label
    if doc.get("level"):
        out["level_label"] = EDUCATION_LABELS.get(doc["level"], doc["level"])
    return out


def _docs(provider_id: str) -> list[dict]:
    """Every document that isn't superseded, newest first."""
    return fetch_all(
        f"select {DOC_COLUMNS} from provider_documents d "
        "where d.provider_id = %s and d.status <> 'superseded' order by d.uploaded_at desc",
        (provider_id,),
    )


def references(provider_id: str) -> list[dict]:
    return fetch_all(
        "select id::text, name, phone, relationship, status, checked_by, checked_at, note, created_at "
        "from provider_references where provider_id = %s and status <> 'removed' order by created_at",
        (provider_id,),
    )


def checklist(provider: dict, *, for_staff: bool = False) -> dict:
    """Every requirement with its status, plus whether the provider can be approved now."""
    max_age, remind = max_age_days(), platform_settings.get_int("police_clearance_remind_days")
    min_level = min_education()
    today = date.today()
    docs = _docs(provider["id"])
    items: list[dict] = []

    # Identity: Fayda, or a checked ID copy when Fayda is off
    fayda = bool(provider.get("id_verified") or provider.get("national_id_verified"))
    who = "The representative's national ID" if _is_company(provider) else "National ID"
    if _fayda_on() or fayda:
        items.append({
            "key": "identity", "type": "identity", "label": f"{who} verified with Fayda", "label_am": "ፋይዳ መታወቂያ",
            "required": True, "status": "verified" if fayda else "missing",
            "message": None if fayda else "Verify your national ID with Fayda from your account.",
        })

    for kind in document_kinds(provider):
        if kind == "id_copy" and fayda:
            continue
        meta = KINDS[kind]
        mine = [d for d in docs if d["kind"] == kind]
        verified = next((d for d in mine if d["status"] == "verified"), None)
        waiting = next((d for d in mine if d["status"] in ("pending", "rejected")), None)
        if waiting and verified and waiting["uploaded_at"] < verified["uploaded_at"]:
            waiting = None  # an older rejected copy that the verified one already replaced
        expired = next((d for d in mine if d["status"] == "expired"), None)
        expiry = effective_expiry(verified, max_age) if verified else None
        message = None
        if verified and expiry and expiry < today:
            status, message = "expired", f"Expired on {expiry:%d %b %Y}. Upload a new one."
        elif verified and kind == "education" and verified.get("level") and \
                EDUCATION_LEVELS.index(verified["level"]) < EDUCATION_LEVELS.index(min_level):
            status = "below_minimum"
            message = f"We now need at least {EDUCATION_LABELS[min_level]}. Upload a higher certificate."
        elif verified:
            status = "expiring" if expiry and (expiry - today).days <= remind else "verified"
            if status == "expiring":
                message = f"Valid until {expiry:%d %b %Y}. Upload a new one before then to stay listed."
        elif waiting and waiting["status"] == "pending":
            status, message = "pending", "Uploaded. Staff will check it."
        elif waiting:
            status = "rejected"
            message = f"Not accepted: {waiting['review_note']}" if waiting.get("review_note") else "Not accepted. Upload a new copy."
        elif expired:
            status, message = "expired", "Expired. Upload a new one."
        else:
            status = "missing"
        if kind == "photo" and _is_company(provider):
            continue
        item = {
            "key": kind, "type": "document", "kind": kind, "label": meta.label, "label_am": meta.am,
            "required": kind != "id_copy" or not _fayda_on(),
            "status": status, "message": message, "help": meta.help,
            "needs": {"issued_on": meta.needs_issued_on, "expires_on": meta.needs_expires_on,
                      "reference_no": meta.needs_reference, "level": meta.needs_level,
                      "images_only": meta.images_only},
            "reference_label": meta.reference_label,
            "current": _public_doc(verified, max_age), "waiting": _public_doc(waiting, max_age),
        }
        if kind == "police_clearance":
            item["label"] = "Representative's police clearance" if _is_company(provider) else meta.label
            item["max_age_days"] = max_age
        if kind == "education":
            item["min_level"] = min_level
            item["min_level_label"] = EDUCATION_LABELS[min_level]
        if for_staff:
            item["how_to_verify"] = meta.how_to_verify
            item["sensitive"] = meta.sensitive
        items.append(item)

    if not _is_company(provider):
        has_tg = bool(provider.get("telegram_username"))
        items.append({
            "key": "telegram", "type": "telegram", "label": "Telegram username", "label_am": "የቴሌግራም ስም",
            "required": True, "status": "verified" if has_tg else "missing",
            "message": None if has_tg else "Add your Telegram username on the Profile tab.",
        })
        refs = references(provider["id"])
        confirmed = sum(1 for r in refs if r["status"] == "confirmed")
        required = references_required()
        if confirmed >= REFERENCES_NEEDED:
            ref_status = "verified"
        elif any(r["status"] == "pending" for r in refs):
            ref_status = "pending"
        else:
            ref_status = "missing"
        ref_item = {
            "key": "references", "type": "references", "label": "Two references", "label_am": "ሁለት ዋስ/ምስክሮች",
            "required": required, "status": ref_status,
            "message": None if ref_status == "verified" else (
                f"{confirmed} of {REFERENCES_NEEDED} confirmed by phone." if refs else
                "Add two people who know your work (not family), with their phone numbers."),
            "references": [r if for_staff else {k: v for k, v in r.items() if k not in ("checked_by", "note")}
                           for r in refs],
        }
        items.append(ref_item)

    missing = [i for i in items if i["required"] and i["status"] not in ("verified", "expiring")]
    return {
        "complete": not missing,
        "blocker": _blocker_text(missing),
        "items": items,
        "max_upload_mb": storage_service.VETTING_MAX_BYTES // (1024 * 1024),
        "education_levels": [{"key": k, "label": EDUCATION_LABELS[k]} for k in EDUCATION_LEVELS],
    }


def template(entity_type: str) -> dict:
    """The documents someone joining will be asked for, before they have a profile (the join form)."""
    company = entity_type == "company"
    items = []
    for kind in document_kinds({"entity_type": entity_type}):
        meta = KINDS[kind]
        items.append({
            "key": kind, "type": "document", "kind": kind,
            "label": "Representative's police clearance" if kind == "police_clearance" and company else meta.label,
            "label_am": meta.am, "required": True, "status": "missing", "help": meta.help,
            "needs": {"issued_on": meta.needs_issued_on, "expires_on": meta.needs_expires_on,
                      "reference_no": meta.needs_reference, "level": meta.needs_level, "images_only": meta.images_only},
            "reference_label": meta.reference_label,
            "max_age_days": max_age_days() if kind == "police_clearance" else None,
            "min_level": min_education() if kind == "education" else None,
            "min_level_label": EDUCATION_LABELS[min_education()] if kind == "education" else None,
        })
    return {
        "complete": False, "blocker": None, "items": items,
        "max_upload_mb": storage_service.VETTING_MAX_BYTES // (1024 * 1024),
        "education_levels": [{"key": k, "label": EDUCATION_LABELS[k]} for k in EDUCATION_LEVELS],
        "references_required": references_required(),
    }


def _blocker_text(missing: list[dict]) -> str | None:
    if not missing:
        return None
    words = {"missing": "missing", "pending": "not checked yet", "rejected": "rejected", "expired": "expired",
             "below_minimum": "below the minimum level"}
    parts = [f"{i['label']} ({words.get(i['status'], i['status'])})" for i in missing]
    return "Vetting is not complete: " + "; ".join(parts) + "."


def blocker(provider: dict) -> str | None:
    """Why this provider can't be approved or renewed yet, or None."""
    return checklist(provider)["blocker"]


def expired_blocker(provider: dict) -> str | None:
    """Reinstating needs at least every expiring document back in date."""
    items = [i for i in checklist(provider)["items"] if i["required"] and i["status"] == "expired"]
    return _blocker_text(items)


# ---------------------------------------------------------------- provider side


def _clean_text(value: str | None, limit: int) -> str | None:
    value = (value or "").strip()
    return value[:limit] or None


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
                  issued_on, expires_on, reference_no, issuer, uploaded_by, consent_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, case when %s then now() end) returning id::text
                """,
                (provider["id"], kind, level, key, content_type, len(content), issued_on, expires_on,
                 reference_no, issuer, actor, consent),
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
    if by_staff and KINDS[row["kind"]].sensitive:
        with connection() as conn, conn.transaction():
            conn.execute(
                "insert into provider_events (provider_id, action, actor, note) values (%s, 'document_viewed', %s, %s)",
                (provider_id, actor, f"Opened {KINDS[row['kind']].label.lower()}"
                 + (f" no. {row['reference_no']}" if row["reference_no"] else "")),
            )
    content, content_type = found
    return content, content_type, row


def _uuid_like(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


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
    return references(provider["id"])


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
    return {"references": references(provider_id)}


def _recompute(provider_id: str) -> None:
    from services import provider_service

    provider_service.recompute(provider_id)


def _notify_provider(provider_id: str, title: str, body: str | None) -> None:
    from services import notifications

    row = fetch_one("select user_id::text from providers where id = %s", (provider_id,))
    if not row or not row["user_id"]:
        return
    try:
        notifications.notify([row["user_id"]], kind="vetting", title=title[:140], body=body,
                             link="/me/provider?tab=vetting")
    except Exception:  # a failed notification never blocks the review
        log.exception("Vetting notification failed")


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


# ---------------------------------------------------------------- daily maintenance


def run_daily(only: list[str] | None = None) -> dict:
    """Mark out-of-date documents expired, suspend listings left without a required document, and
    remind providers before their clearance gets too old. Runs inside the daily maintenance.
    `only` limits the run to some providers (tests)."""
    params = {"max_age": max_age_days(), "remind": platform_settings.get_int("police_clearance_remind_days"),
              "only": only}
    scope = "and (%(only)s::uuid[] is null or d.provider_id = any(%(only)s::uuid[]))"
    with connection() as conn, conn.transaction():
        expired = conn.execute(
            f"""
            update provider_documents d set status = 'expired'
            where d.status = 'verified' and {EXPIRY_SQL} < current_date {scope}
            returning d.provider_id::text, d.kind
            """,
            params,
        ).fetchall()
        # Approved listings whose required document ran out and has no verified replacement
        suspended = conn.execute(
            """
            update providers p set status = 'suspended', updated_at = now(),
              review_note = 'A required document expired. Upload a new one to be listed again.'
            where p.status = 'approved'
              and (%(only)s::uuid[] is null or p.id = any(%(only)s::uuid[])) and exists (
              select 1 from provider_documents d
              where d.provider_id = p.id and d.status = 'expired'
                and d.kind in ('police_clearance', 'trade_licence')
                and not exists (select 1 from provider_documents v where v.provider_id = p.id
                                and v.kind = d.kind and v.status = 'verified')
            )
            returning p.id::text, p.user_id::text
            """,
            params,
        ).fetchall()
        for s in suspended:
            conn.execute(
                "insert into provider_events (provider_id, action, actor, note) values "
                "(%s, 'vetting_suspended', 'daily maintenance', 'Listing paused: a required document expired')",
                (s["id"],),
            )
        due = conn.execute(
            f"""
            update provider_documents d set reminded_at = now()
            where d.status = 'verified' and d.reminded_at is null
              and {EXPIRY_SQL} between current_date and current_date + %(remind)s::int {scope}
            returning d.provider_id::text, d.kind, ({EXPIRY_SQL}) as valid_until
            """,
            params,
        ).fetchall()
    for s in suspended:
        _notify_provider(s["id"], "Your listing is paused",
                         "A required document expired. Upload a new one and staff will check it.")
    for d in due:
        _notify_provider(d["provider_id"], f"Your {KINDS[d['kind']].label.lower()} is getting old",
                         f"It counts until {d['valid_until']:%d %b %Y}. Upload a new one before then to stay listed.")
    for pid in {e["provider_id"] for e in expired}:
        _recompute(pid)
    return {"documents_expired": len(expired), "listings_suspended": len(suspended), "reminders_sent": len(due)}
