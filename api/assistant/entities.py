"""Rule-based entity extraction: sub-city, documents already held, applicant type, urgency, variant."""

from __future__ import annotations

import re

from assistant.nlu import normalize

SUB_CITIES: dict[str, dict] = {
    "addis_ketema": {"en": "Addis Ketema", "am": "አዲስ ከተማ", "aliases": ["addis ketema", "addis ketama", "አዲስ ከተማ"]},
    "akaki": {"en": "Akaki Kaliti", "am": "አቃቂ ቃሊቲ", "aliases": ["akaki", "akaki kality", "akaki kaliti", "kality", "kaliti", "አቃቂ", "ቃሊቲ"]},
    "arada": {"en": "Arada", "am": "አራዳ", "aliases": ["arada", "piassa", "piazza", "አራዳ", "ፒያሳ"]},
    "bole": {"en": "Bole", "am": "ቦሌ", "aliases": ["bole", "ቦሌ"]},
    "gulele": {"en": "Gulele", "am": "ጉለሌ", "aliases": ["gulele", "gullele", "ጉለሌ"]},
    "kirkos": {"en": "Kirkos", "am": "ቂርቆስ", "aliases": ["kirkos", "qirqos", "kirkose", "ቂርቆስ"]},
    "kolfe": {"en": "Kolfe Keranio", "am": "ኮልፌ ቀራኒዮ", "aliases": ["kolfe", "kolfe keranio", "keranio", "ኮልፌ", "ቀራኒዮ"]},
    "lideta": {"en": "Lideta", "am": "ልደታ", "aliases": ["lideta", "ledeta", "ልደታ"]},
    "nifas_silk": {"en": "Nifas Silk-Lafto", "am": "ንፋስ ስልክ ላፍቶ", "aliases": ["nifas silk", "nefas silk", "nifas silk lafto", "lafto", "ንፋስ ስልክ", "ላፍቶ"]},
    "yeka": {"en": "Yeka", "am": "የካ", "aliases": ["yeka", "የካ"]},
}

# Documents the roadmap engine knows, with how people refer to them
DOCUMENTS: dict[str, dict] = {
    "birth_certificate": {"en": "Birth certificate", "am": "የልደት ሰርተፍኬት", "aliases": ["birth certificate", "birth cert", "ልደት", "yelidet"]},
    "kebele_id": {"en": "Kebele ID", "am": "የቀበሌ መታወቂያ", "aliases": ["kebele id", "kebele", "resident id", "id card", "መታወቂያ", "metawekiya"]},
    "notarized_lease": {"en": "Notarized lease agreement", "am": "የተረጋገጠ የኪራይ ውል", "aliases": ["lease", "rental agreement", "ኪራይ ውል", "ውል"]},
    "tin": {"en": "TIN certificate", "am": "የግብር ከፋይ መለያ ቁጥር", "aliases": ["tin", "tax id", "tax number", "ቲን", "የግብር ከፋይ"]},
    "commercial_registration": {"en": "Commercial registration", "am": "የንግድ ምዝገባ", "aliases": ["commercial registration", "business registration", "የንግድ ምዝገባ"]},
    "trade_license": {"en": "Trade license", "am": "የንግድ ፈቃድ", "aliases": ["trade license", "business license", "የንግድ ፈቃድ", "nigd fekad"]},
    "passport": {"en": "Passport", "am": "ፓስፖርት", "aliases": ["passport", "ፓስፖርት", "pasport"]},
}

_HELD = re.compile(
    r"(?:i (?:already )?(?:have|got|hold|obtained|finished)|already have|i've got|i have got|"
    r"አለኝ|ያለኝ|አውጥቻለሁ|አግኝቻለሁ|alegn|awtichalehu)",
)
_FOREIGN = re.compile(r"\b(foreign|foreigner|not ethiopian|diaspora|expat|non ethiopian)\b|የውጭ|ውጭ ሀገር|ዲያስፖራ")
_COMPANY = re.compile(r"\b(company|plc|share company|business|enterprise|organization)\b|ድርጅት|ኩባንያ|ማህበር")
_URGENT = re.compile(r"\b(urgent|urgently|fast|quick|quickly|asap|express|same day|tomorrow)\b|አስቸኳይ|ቶሎ|በፍጥነት|asachekay|tolo")

PASSPORT_VARIANTS = {
    "new": re.compile(r"\b(new|first|first time|apply)\b|አዲስ|addis"),
    "renewal": re.compile(r"\b(renew|renewal|re new|expired|expire|extend)\b|እድሳት|ማሳደስ|ለማሳደስ|masadess|lemasades"),
    "lost": re.compile(r"\b(lost|stolen|missing)\b|ጠፋ|ጠፍቶ|የጠፋ|ተሰረቀ|tefa|yetefa"),
    "damaged": re.compile(r"\b(damaged|torn|broken|wet|correction|wrong name)\b|ተበላሸ|የተበላሸ|ጉዳት|ማስተካከያ"),
    "pages": re.compile(r"\b(pages?|full|run ?out)\b|ቅጠሉ ያለቀ|ቅጠል"),
}


def _contains(text: str, alias: str) -> bool:
    alias = normalize(alias)
    if re.search(r"[a-z]", alias):
        return re.search(rf"\b{re.escape(alias)}\b", text) is not None
    return alias in text


def sub_city(text: str) -> str | None:
    norm = normalize(text)
    for key, meta in SUB_CITIES.items():
        if any(_contains(norm, a) for a in meta["aliases"]):
            return key
    return None


def documents_held(text: str) -> list[str]:
    """Documents mentioned after 'I have / already have / አለኝ', not the ones the person wants."""
    norm = normalize(text)
    match = _HELD.search(norm)
    if not match:
        return []
    verb = match.group(0)
    if re.search(r"[\u1200-\u137f]", verb) or verb in ("alegn", "awtichalehu"):
        # Amharic puts the verb last: "የቀበሌ መታወቂያ አለኝ ግን ፓስፖርት እፈልጋለሁ"
        clause = re.split(r"ግን|እና|ነገር ግን|gin", norm[: match.start()])[-1]
    else:
        # English: the held clause runs until a contrast word or the end
        clause = re.split(r"\b(?:but|and i need|i need|i want|now i)\b", norm[match.start():])[0]
    return [doc for doc, meta in DOCUMENTS.items() if any(_contains(clause, a) for a in meta["aliases"])]


def applicant_type(text: str) -> str | None:
    norm = normalize(text)
    if _FOREIGN.search(norm):
        return "foreign"
    if _COMPANY.search(norm):
        return "company"
    return None


def urgent(text: str) -> bool:
    return _URGENT.search(normalize(text)) is not None


def passport_variant(text: str) -> str | None:
    norm = normalize(text)
    for variant, pattern in PASSPORT_VARIANTS.items():
        if variant != "new" and pattern.search(norm):
            return variant
    return "new" if PASSPORT_VARIANTS["new"].search(norm) else None


def redact(text: str) -> str:
    """Mask long digit runs (national IDs, phone numbers, TINs) before anything is stored."""
    return re.sub(r"\+?\d[\d\s-]{5,}\d", lambda m: "#" * 6, text or "")


def want_text(text: str) -> str:
    """The message without its 'I already have ...' part, so held documents don't steer the service match."""
    norm = normalize(text)
    match = _HELD.search(norm)
    if not match:
        return text
    verb = match.group(0)
    if re.search(r"[\u1200-\u137f]", verb) or verb in ("alegn", "awtichalehu"):
        parts = re.split(r"ግን|ነገር ግን|gin", norm[match.end():])
        rest = parts[-1] if len(parts) > 1 else norm[match.end():]
        return rest.strip() or text
    rest = re.split(r"\b(?:but|and i need|i need|i want|now i)\b", norm[match.start():], maxsplit=1)
    before = norm[: match.start()]
    wanted = rest[1] if len(rest) > 1 else ""
    return (before + " " + wanted).strip() or text
