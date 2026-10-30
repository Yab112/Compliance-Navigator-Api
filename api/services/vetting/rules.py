"""What vetting asks for: the document kinds, the policy settings and how a requirement's status is read."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from services import platform_settings
from services.db import fetch_all


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
