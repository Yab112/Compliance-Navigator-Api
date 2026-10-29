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
    - a guarantor (ተያዥ), when the setting vetting_guarantor_required is on (it is by default): the
      guarantor's details confirmed by staff on the phone, a signed guarantee letter and a copy of the
      guarantor's ID, both verified. Companies need one only when vetting_guarantor_required_company is on.

  Company (agency)
    - the representative's national ID verified with Fayda
    - trade licence (with its valid-until date), TIN certificate
    - the representative's police clearance certificate

Every document is checked by a person: staff verify or reject each one (a rejection always has a
reason the provider sees). Approving or renewing a listing is refused until every required item is
verified and in date. Nothing is deleted: a new upload supersedes the old one, which stays on file.
Opening a police clearance is written to the provider's audit log, because it is criminal record data;
so is opening a guarantor's ID or papers, because they belong to someone who is not our user.

Vetting must hold all the time, not only on the day of approval: provider_service.refresh_readiness()
hides a provider from clients as soon as an item stops being verified or in date.
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
    sensitive: bool = False  # criminal record data: staff need a permission to open it, every view is logged
    log_views: bool = False  # someone else's personal data: every staff view is logged
    guarantor: bool = False  # belongs to the current guarantor, shown inside the guarantor item
    optional: bool = False  # helps staff, never required


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
    # The guarantor's papers. A guarantee (suretyship) falls under the Civil Code; Article 1922 asks
    # for the most the guarantor answers for to be stated, so staff check the letter names an amount.
    "guarantee_letter": Kind(
        "Signed guarantee letter", "የዋስትና ደብዳቤ / ውል",
        "The letter or form in which your guarantor promises to answer for your conduct and for any loss "
        "you cause while working through Compliance Navigator, up to an amount written in the letter. It "
        "must carry the guarantor's full name, signature and date. A letter authenticated at the Documents "
        "Authentication and Registration Service (ሰነዶች ማረጋገጫና ምዝገባ አገልግሎት) is preferred: it has their "
        "stamp and a registration number.",
        "Check the names match the provider and the guarantor details on file, that it is signed and dated, "
        "and that it states the most the guarantor answers for. If it was authenticated, check the "
        "Documents Authentication and Registration Service (DARS) stamp and registration number, and scan "
        "its QR code when it has one, and write in your note whether it was authenticated or not. Then "
        "call the guarantor (see the guarantor details).",
        reference_label="Authentication (DARS) number, if any", log_views=True, guarantor=True,
    ),
    "guarantor_id": Kind(
        "Guarantor's ID copy", "የተያዡ መታወቂያ ቅጂ",
        "A clear copy of your guarantor's national ID, Fayda card or kebele ID, both sides.",
        "Check the name and the last 4 digits match the guarantor details, and that the ID is in date.",
        reference_label="ID number", log_views=True, guarantor=True,
    ),
    "guarantor_employment": Kind(
        "Guarantor's employment or property proof", "የተያዡ የሥራ ወይም የንብረት ማስረጃ",
        "Optional but helps: a letter from the guarantor's employer stating their position and salary, "
        "or proof that they own property (for example a house title deed).",
        "Check it names the guarantor. For an employer letter, call the employer on the number printed on "
        "the letterhead (not one the provider gives you) to confirm the person works there.",
        log_views=True, guarantor=True, optional=True,
    ),
}
GUARANTOR_KINDS = tuple(k for k, m in KINDS.items() if m.guarantor)

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


def guarantor_required(provider: dict) -> bool:
    key = "vetting_guarantor_required_company" if provider.get("entity_type") == "company" else "vetting_guarantor_required"
    return bool(platform_settings.get(key))


def guarantor_applies(provider: dict) -> bool:
    """Individuals can always add a guarantor (it counts toward trust); companies only when required."""
    return provider.get("entity_type") != "company" or guarantor_required(provider)


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
    if guarantor_applies(provider):
        kinds += list(GUARANTOR_KINDS)
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


def _doc_item(provider: dict, kind: str, docs: list[dict], max_age: int, *, for_staff: bool) -> dict:
    """One document requirement: its status from the copies on file, and what the provider must do."""
    remind = platform_settings.get_int("police_clearance_remind_days")
    min_level = min_education()
    today = date.today()
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
    item = {
        "key": kind, "type": "document", "kind": kind, "label": meta.label, "label_am": meta.am,
        "required": not meta.optional and (kind != "id_copy" or not _fayda_on()),
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
    return item


def checklist(provider: dict, *, for_staff: bool = False) -> dict:
    """Every requirement with its status, plus whether the provider can be approved now."""
    max_age = max_age_days()
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
        if KINDS[kind].guarantor or (kind == "photo" and _is_company(provider)):
            continue  # guarantor papers are listed inside the guarantor item below
        items.append(_doc_item(provider, kind, docs, max_age, for_staff=for_staff))

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
            "key": "references", "type": "references", "label": "Two references", "label_am": "ሁለት ምስክሮች",
            "required": required, "status": ref_status,
            "message": None if ref_status == "verified" else (
                f"{confirmed} of {REFERENCES_NEEDED} confirmed by phone." if refs else
                "Add two people who know your work (not family), with their phone numbers."),
            "references": [r if for_staff else {k: v for k, v in r.items() if k not in ("checked_by", "note")}
                           for r in refs],
        }
        items.append(ref_item)

    if guarantor_applies(provider):
        items.append(_guarantor_item(provider, docs, max_age, for_staff=for_staff))

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
        if meta.guarantor:
            continue  # one guarantor item below
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
    if guarantor_applies({"entity_type": entity_type}):
        items.append({
            "key": "guarantor", "type": "guarantor", "label": "Guarantor", "label_am": "ተያዥ",
            "required": guarantor_required({"entity_type": entity_type}), "status": "missing",
            "help": GUARANTOR_HELP, "documents": [
                {"kind": k, "label": KINDS[k].label, "label_am": KINDS[k].am, "help": KINDS[k].help,
                 "required": not KINDS[k].optional} for k in GUARANTOR_KINDS],
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
    _recompute(provider["id"])
    return references(provider["id"])


# ---------------------------------------------------------------- guarantor (ተያዥ)

# In Ethiopia a guarantor (ተያዥ) signs that they will answer for a worker's conduct and losses, as
# employers ask of cashiers, drivers and domestic workers. Usually an employed person (with an employer
# letter stating their salary) or a property owner; the letter is often authenticated at the Documents
# Authentication and Registration Service; and the employer phones the guarantor to confirm.
GUARANTOR_HELP = (
    "A guarantor (ተያዥ) is someone who signs that they will answer for your conduct and for losses you cause "
    "a client, as employers in Ethiopia often ask. Choose an adult who knows you well and has a steady job "
    "or owns property. They sign a guarantee letter (better if it is authenticated at the Documents "
    "Authentication and Registration Service), and our staff will phone them to confirm they signed it "
    "knowingly. Ask them first: you share their name, phone and ID number with us."
)
GUARANTOR_STAFF_HELP = (
    "Call the guarantor on the phone number given (not one the provider passes you on the day). Confirm "
    "their full name and the last 4 digits of their ID, that they know the provider and how, that they "
    "signed the guarantee letter themselves and understand they answer for losses up to the amount in it, "
    "and where they work. Check the letter's Documents Authentication and Registration Service stamp and "
    "number when it has one. Confirm only when the call and the papers agree; write what you checked."
)
GUARANTOR_COLUMNS = ("id::text, provider_id::text, full_name, phone, relationship, sub_city, woreda, address, "
                     "occupation, employer, id_last4, status, checked_by, checked_at, note, created_by, created_at, "
                     "superseded_at")


def current_guarantor(provider_id: str) -> dict | None:
    return fetch_one(
        f"select {GUARANTOR_COLUMNS} from provider_guarantors where provider_id = %s and status <> 'superseded'",
        (provider_id,),
    )


def guarantor_history(provider_id: str) -> list[dict]:
    """Replaced guarantors, kept on file, newest first (staff only)."""
    return fetch_all(
        f"select {GUARANTOR_COLUMNS} from provider_guarantors where provider_id = %s and status = 'superseded' "
        "order by created_at desc limit 20",
        (provider_id,),
    )


def _guarantor_item(provider: dict, docs: list[dict], max_age: int, *, for_staff: bool) -> dict:
    """Verified only when staff confirmed the guarantor by phone AND the letter and ID copy are verified."""
    g = current_guarantor(provider["id"])
    papers = [_doc_item(provider, k, docs, max_age, for_staff=for_staff) for k in GUARANTOR_KINDS]
    needed = [d for d in papers if d["required"]]
    papers_ok = all(d["status"] in ("verified", "expiring") for d in needed)
    if not g:
        status, message = "missing", "Add your guarantor's details, then upload the signed letter and their ID."
    elif g["status"] == "failed":
        status = "rejected"
        message = "We could not confirm your guarantor" + (f": {g['note']}" if g.get("note") else ".") + \
            " Add another guarantor or correct the details."
    elif any(d["status"] in ("rejected", "expired") for d in needed):
        status, message = "rejected", "A guarantor paper was not accepted. Upload a new copy."
    elif g["status"] == "confirmed" and papers_ok:
        status, message = "verified", None
    elif any(d["status"] == "missing" for d in needed):
        status, message = "missing", "Upload the signed guarantee letter and your guarantor's ID."
    else:
        status = "pending"
        message = "Staff will phone your guarantor and check the papers." if g["status"] == "pending" \
            else "Guarantor confirmed. Staff will check the papers."
    if g:
        g = dict(g)
        if not for_staff:
            # The provider sees what they entered; staff's call notes stay internal unless it failed
            g.pop("checked_by", None)
            if g["status"] != "failed":
                g.pop("note", None)
    item = {
        "key": "guarantor", "type": "guarantor", "label": "Guarantor", "label_am": "ተያዥ",
        "required": guarantor_required(provider), "status": status, "message": message,
        "help": GUARANTOR_HELP, "guarantor": g, "documents": papers,
    }
    if for_staff:
        item["how_to_verify"] = GUARANTOR_STAFF_HELP
        item["history"] = guarantor_history(provider["id"])
    return item


def _clean_id_number(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isalnum())
    if not 6 <= len(digits) <= 32:
        raise VettingError("Enter the guarantor's national ID or Fayda number (6 to 32 letters and digits)")
    return digits


def set_guarantor(provider: dict, data: dict, *, actor: str, consent: bool) -> dict:
    """Add or change the guarantor. The same person (same ID number) is updated in place and keeps their
    papers; a different person replaces the old one, whose record and papers stay on file as superseded.
    Either way a change goes back to staff to confirm."""
    from core.crypto import decrypt, encrypt

    if not guarantor_applies(provider):
        raise VettingError("A guarantor isn't needed for your kind of profile")
    if not consent:
        raise VettingError("Tick the box to confirm your guarantor agreed that you share their details with us")
    fields = {k: _clean_text(data.get(k), limit) for k, limit in (
        ("full_name", 120), ("phone", 20), ("relationship", 80), ("sub_city", 80), ("woreda", 40),
        ("address", 200), ("occupation", 120), ("employer", 160))}
    for k, label in (("full_name", "full name"), ("phone", "phone number"), ("relationship", "relationship to you"),
                     ("occupation", "occupation"), ("sub_city", "sub-city or town")):
        if not fields[k]:
            raise VettingError(f"Enter your guarantor's {label}")
    if provider.get("phone") and fields["phone"] == provider["phone"]:
        raise VettingError("Your guarantor needs their own phone number, not yours")
    if (fields["full_name"] or "").lower() == (provider.get("display_name") or "").lower() or \
            (provider.get("verified_name") and fields["full_name"].lower() == provider["verified_name"].lower()):
        raise VettingError("You can't be your own guarantor")
    id_number = _clean_id_number(data.get("id_number") or "")
    current = fetch_one(
        "select id::text, id_number_enc, status, full_name, phone, relationship, sub_city, woreda, address, "
        "occupation, employer from provider_guarantors where provider_id = %s and status <> 'superseded'",
        (provider["id"],),
    )
    same_person = bool(current and decrypt(current["id_number_enc"]) == id_number)
    with connection() as conn, conn.transaction():
        if same_person:
            changed = [k for k, v in fields.items() if v != current[k]]
            if not changed:
                return current_guarantor(provider["id"])
            assignments = ", ".join(f"{k} = %({k})s" for k in fields)
            # Different details need a new call; a failed check can be retried with corrected details
            conn.execute(
                f"update provider_guarantors set {assignments}, status = 'pending', checked_by = null, "
                "checked_at = null, note = null where id = %(id)s",
                {**fields, "id": current["id"]},
            )
            note = f"{fields['full_name']}: changed {', '.join(changed)}"
            action = "guarantor_updated"
        else:
            if current:
                conn.execute("update provider_guarantors set status = 'superseded', superseded_at = now() where id = %s",
                             (current["id"],))
                # The old guarantor's papers stay on file but no longer count
                conn.execute(
                    "update provider_documents set status = 'superseded' where provider_id = %s "
                    "and kind = any(%s) and status <> 'superseded'",
                    (provider["id"], list(GUARANTOR_KINDS)),
                )
            conn.execute(
                """
                insert into provider_guarantors (provider_id, full_name, phone, relationship, sub_city, woreda, address,
                  occupation, employer, id_number_enc, id_last4, created_by)
                values (%(pid)s, %(full_name)s, %(phone)s, %(relationship)s, %(sub_city)s, %(woreda)s, %(address)s,
                  %(occupation)s, %(employer)s, %(enc)s, %(last4)s, %(actor)s)
                """,
                {**fields, "pid": provider["id"], "enc": encrypt(id_number), "last4": id_number[-4:], "actor": actor},
            )
            note = f"{fields['full_name']}, ID ending {id_number[-4:]}" + (" (replaced the previous guarantor)" if current else "")
            action = "guarantor_replaced" if current else "guarantor_added"
        conn.execute(
            "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
            (provider["id"], action, actor, note),
        )
    _recompute(provider["id"])
    return current_guarantor(provider["id"])


def check_guarantor(provider_id: str, guarantor_id: str, decision: str, *, actor: str, note: str | None) -> dict:
    """Staff phoned the guarantor: confirmed (they knowingly signed) or failed (with what happened)."""
    if decision not in ("confirmed", "failed"):
        raise VettingError("Choose confirmed or failed")
    note = (note or "").strip()
    if decision == "confirmed" and len(note) < 10:
        raise VettingError("Write what you confirmed on the call (at least 10 characters)")
    if decision == "failed" and len(note) < 5:
        raise VettingError("Write what happened on the call. The provider sees this.")
    if not (_uuid_like(guarantor_id) and _uuid_like(provider_id)):
        raise VettingError("Guarantor not found", 404)
    with connection() as conn, conn.transaction():
        row = conn.execute(
            "update provider_guarantors set status = %s, checked_by = %s, checked_at = now(), note = %s "
            "where id = %s and provider_id = %s and status <> 'superseded' returning full_name",
            (decision, actor, note, guarantor_id, provider_id),
        ).fetchone()
        if not row:
            raise VettingError("Guarantor not found, or replaced by a newer one", 404)
        conn.execute(
            "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
            (provider_id, f"guarantor_{decision}", actor, f"{row['full_name']}: {note}"),
        )
    _notify_provider(provider_id, "Your guarantor was confirmed" if decision == "confirmed"
                     else "We could not confirm your guarantor", None if decision == "confirmed" else note)
    _recompute(provider_id)
    return current_guarantor(provider_id)


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
    # Everyone is checked again every day: dates pass, settings and legal documents change
    from services import provider_service

    provider_service.refresh_readiness_all(only=only)
    return {"documents_expired": len(expired), "listings_suspended": len(suspended), "reminders_sent": len(due)}
