"""One imported row (a dict of template column to cell text) checked and turned into a service.

Every file format reads into the same rows, so this part doesn't know where a row came from.
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from schemas.organizations import ServiceIn

COLUMNS = [
    ("name", "Service name in English (required)", "New trade license"),
    ("name_am", "Service name in Amharic", "አዲስ የንግድ ፈቃድ"),
    ("summary", "One or two sentences people see first (required)", "First trade license for a business in Bole."),
    ("who_can_apply", "Who can apply", "Sole proprietors and companies with premises in the sub-city"),
    ("audience", "citizen; resident; company; foreigner; investor; diaspora; ngo", "company; investor"),
    ("delivery", "in_person, online or both", "in_person"),
    ("online_url", "Link to apply online", ""),
    ("fee_etb", "Fee in birr for everyone, or the word free", "302"),
    ("fee_foreign_etb", "Different fee for foreign nationals, if any", ""),
    ("fee_urgent_etb", "Fee for urgent service, if offered", ""),
    ("fee_notes", "What the fee covers or extra charges", ""),
    ("payment_methods", "Semicolon separated", "Cash; Telebirr; CBE Birr"),
    ("where_to_pay", "Where people pay", "Cashier window at the branch"),
    ("processing_time_text", "How long it takes, as people should read it (required)", "About 15 minutes"),
    ("processing_minutes", "The same in minutes, used to add up full paths", "15"),
    ("required_documents", "Semicolon separated; add (original), (copy), (both), (x2) or (notarized) after a name",
     "TIN certificate (copy); Resident ID card (both); Notarized lease agreement (original) (notarized)"),
    ("no_documents_required", "yes if nothing needs to be brought", ""),
    ("steps", "Steps at the office, semicolon separated", "Check documents; Pay the fee; Receive the license"),
    ("branches", "Branch names exactly as registered, semicolon separated", "Bole branch"),
    ("appointment_required", "yes or no", "no"),
    ("proxy_allowed", "yes, with_poa (with a power of attorney) or no", "with_poa"),
    ("languages", "Languages served, semicolon separated", "Amharic; English"),
    ("output_document", "What the applicant receives", "Trade license certificate"),
    ("output_validity_months", "How long it is valid, in months", "12"),
    ("legal_basis", "Proclamation or directive", "Commercial Registration and Business Licensing Proclamation"),
    ("legal_reference_number", "Its number", "1150/2019"),
    ("contact_phone", "Phone for questions about this service", "0116 000 000"),
    ("common_rejection_reasons", "Semicolon separated", "Lease not notarized; TIN name differs"),
]
HEADERS = [c[0] for c in COLUMNS]
_DOC_FLAGS = re.compile(r"\((original|copy|both|notarized|translated|x\d+)\)", re.I)


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def _yes(value: str | None) -> bool | None:
    v = (value or "").strip().lower()
    if v in ("yes", "y", "true", "1", "አዎ"):
        return True
    if v in ("no", "n", "false", "0", "አይ"):
        return False
    return None


def _money(value: str | None, field: str, errors: list[str]) -> float | None:
    v = (value or "").strip().replace(",", "")
    if not v:
        return None
    try:
        amount = float(re.sub(r"(?i)\s*(etb|birr)$", "", v))
    except ValueError:
        errors.append(f"The {field} column should be a number, like 302, but it has '{value}'")
        return None
    if amount < 0:
        errors.append(f"The {field} column can't be a negative amount")
    return amount


def _document(text: str, used: set[str]) -> dict:
    flags = [f.lower() for f in _DOC_FLAGS.findall(text)]
    name = _DOC_FLAGS.sub("", text).strip(" ,") or text.strip()
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:30] or "doc"
    base, n = key, 2
    while key in used:
        key, n = f"{base}_{n}", n + 1
    used.add(key)
    copies = next((int(f[1:]) for f in flags if f.startswith("x")), None)
    kind = next((f for f in flags if f in ("original", "copy", "both")), None)
    return {
        "key": key, "kind": "document", "name": name, "required": "always", "original_or_copy": kind,
        "copies": copies, "notarized": "notarized" in flags, "translated": "translated" in flags,
    }


# Service fields whose template column has a different name
_FIELD_COLUMN = {
    "fee_schedule": "fee_etb", "is_free": "fee_etb", "requirements": "required_documents",
    "branch_ids": "branches", "outputs": "output_document",
}


def _plain_error(error: dict, row: dict) -> str:
    """A validation error as a sentence that names the spreadsheet column, not the field path."""
    field = str(error["loc"][0]) if error.get("loc") else ""
    column = _FIELD_COLUMN.get(field, field)
    value = (row.get(column) or "").strip()
    has = f" It has '{value}'." if value else ""
    ctx = error.get("ctx") or {}
    kind = error.get("type", "")
    if kind in ("literal_error", "enum"):
        allowed = str(ctx.get("expected", "")).replace("'", "")
        return f"The {column} column can only be {allowed}.{has}"
    if kind == "string_too_short":
        return f"The {column} column is too short: write at least {ctx.get('min_length')} characters.{has}"
    if kind in ("string_too_long", "too_long"):
        limit = ctx.get("max_length")
        unit = "characters" if kind == "string_too_long" else "items"
        return f"The {column} column is too long: at most {limit} {unit}."
    if kind == "string_pattern_mismatch" and "phone" in column:
        return f"The {column} column should be a phone number, like 0116 000 000.{has}"
    if kind == "string_pattern_mismatch":
        return f"The {column} column isn't in the expected format.{has}"
    if kind.startswith(("url_", "value_error")) and "url" in column:
        return f"The {column} column should be a full web link starting with https://.{has}"
    if kind in ("greater_than_equal", "greater_than", "less_than_equal", "less_than"):
        return f"The {column} column is out of range.{has}"
    msg = str(error.get("msg", "is not valid")).removeprefix("Value error, ")
    return f"The {column} column has a problem: {msg[:1].lower()}{msg[1:]}.{has}".replace("..", ".")


def _row_to_service(row: dict, branches: dict[str, str]) -> tuple[dict | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    get = lambda k: (row.get(k) or "").strip()  # noqa: E731

    fee_text = get("fee_etb").lower()
    is_free = fee_text in ("free", "0", "no fee", "ነጻ")
    fee_rows = []
    if not is_free:
        base = _money(get("fee_etb"), "fee_etb", errors)
        if base is not None:
            fee_rows.append({"category": "everyone", "speed": "regular", "amount_min": base, "currency": "ETB"})
        foreign = _money(get("fee_foreign_etb"), "fee_foreign_etb", errors)
        if foreign is not None:
            if fee_rows:
                fee_rows[0]["category"] = "ethiopian"
            fee_rows.append({"category": "foreign_national", "speed": "regular", "amount_min": foreign, "currency": "ETB"})
        urgent = _money(get("fee_urgent_etb"), "fee_urgent_etb", errors)
        if urgent is not None:
            fee_rows.append({"category": "everyone", "speed": "urgent", "amount_min": urgent, "currency": "ETB"})

    minutes = None
    if get("processing_minutes"):
        try:
            minutes = int(float(get("processing_minutes")))
        except ValueError:
            errors.append(f"The processing_minutes column should be a number, like 15, but it has '{get('processing_minutes')}'")

    branch_ids = []
    for name in _split(get("branches")):
        bid = branches.get(name.lower())
        if bid:
            branch_ids.append(bid)
        else:
            errors.append(f"Branch '{name}' isn't registered. Add it under Branches first or fix the spelling")

    used: set[str] = set()
    requirements = [_document(d, used) for d in _split(get("required_documents"))]
    validity = None
    if get("output_validity_months"):
        try:
            validity = int(get("output_validity_months"))
        except ValueError:
            errors.append(f"The output_validity_months column should be a whole number of months, like 12, "
                          f"but it has '{get('output_validity_months')}'")

    delivery = get("delivery").lower() or "in_person"
    proxy = get("proxy_allowed").lower() or None
    body = {
        "name": get("name"),
        "name_am": get("name_am") or None,
        "summary": get("summary") or None,
        "who_can_apply": get("who_can_apply") or None,
        "audience": [a.lower() for a in _split(get("audience"))],
        "delivery": delivery,
        "online_url": get("online_url") or None,
        "is_free": is_free,
        "fee_schedule": fee_rows,
        "fee_notes": get("fee_notes") or None,
        "payment_methods": _split(get("payment_methods")),
        "where_to_pay": get("where_to_pay") or None,
        "processing_time_text": get("processing_time_text") or None,
        "processing_minutes": minutes,
        "requirements": requirements,
        "no_documents_required": bool(_yes(get("no_documents_required"))),
        "steps": [{"title": t} for t in _split(get("steps"))],
        "branch_ids": branch_ids,
        "appointment_required": bool(_yes(get("appointment_required"))),
        "proxy_allowed": proxy,
        "languages": _split(get("languages")),
        "outputs": [{"name": get("output_document")}] if get("output_document") else [],
        "output_validity_months": validity,
        "legal_basis": get("legal_basis") or None,
        "legal_reference_number": get("legal_reference_number") or None,
        "contact_phone": get("contact_phone") or None,
        "common_rejection_reasons": _split(get("common_rejection_reasons")),
    }
    if not body["summary"]:
        errors.append("The summary column is empty. Write one or two sentences about the service")
    if not body["processing_time_text"] and minutes is None:
        errors.append("The processing_time_text column is empty. Say how long the service takes, like 'About 15 minutes'")
    if not fee_text and not errors:
        warnings.append("No fee given; add one or write free")
    if not requirements and not body["no_documents_required"]:
        warnings.append("No documents listed; list them or write yes under no_documents_required")
    if not branch_ids and delivery != "online":
        warnings.append("No branch chosen; people won't know where to go")
    try:
        parsed = ServiceIn(**body).model_dump()
    except ValidationError as exc:
        for e in exc.errors():
            errors.append(_plain_error(e, row))
        return None, errors, warnings
    return (None if errors else parsed), errors, warnings
