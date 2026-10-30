"""The checklist a provider and staff see, the join-form template and the approval blockers."""

from __future__ import annotations

from services import storage_service
from services.vetting.documents import references
from services.vetting.guarantor import GUARANTOR_HELP, _guarantor_item
from services.vetting.rules import (
    EDUCATION_LABELS,
    EDUCATION_LEVELS,
    GUARANTOR_KINDS,
    KINDS,
    REFERENCES_NEEDED,
    _doc_item,
    _docs,
    _fayda_on,
    _is_company,
    document_kinds,
    guarantor_applies,
    guarantor_required,
    max_age_days,
    min_education,
    references_required,
)


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
            "message": None if has_tg else "Add your Telegram username on the Edit profile tab.",
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
