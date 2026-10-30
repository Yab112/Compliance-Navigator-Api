"""Government service catalog (MESOB snapshot), search and roadmap linking."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "mesob" / "catalog.json"

# Roadmap document id -> catalog services that fulfil it, matched on
# (institution short name, case-insensitive name prefix). Prefix matching keeps
# links stable across re-scrapes even if MESOB renumbers rows.
DOCUMENT_SERVICE_RULES: dict[str, list[tuple[str, str]]] = {
    "passport": [("ICS", "RENEWAL PASSPORT")],
    "notarized_lease": [
        ("DARS", "Authentication of Contract of Lease"),
        ("EPSE", "Lease / House Rental Agreement Drafting"),
    ],
    "tin": [("MOR", "Taxpayer Identification Number")],
    "commercial_registration": [
        ("MOTRI", "Commercial Registration Certificate for Partnerships and Private Limited"),
        ("MOTRI", "Commercial Registration Certificate for One-Member"),
        ("MOTRI", "Commercial Registration Certificate for Sole Proprietors"),
        ("MOTRI", "Trade Name Registration for Business Associations"),
    ],
    "trade_license": [("MOTRI", "Business License Certificate")],
}


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    if not SNAPSHOT_PATH.exists():
        return {"institutions": [], "centers": [], "services": [], "fetched_at": None}
    # House style: no em dashes in anything we show, including scraped catalog text
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8").replace(" \u2014 ", ", ").replace("\u2014", ", "))


def reload_catalog() -> dict:
    load_catalog.cache_clear()
    return load_catalog()


def _institutions_by_id() -> dict[str, dict]:
    return {i["id"]: i for i in load_catalog()["institutions"]}


def _short_name(service: dict) -> str:
    inst = _institutions_by_id().get(service["institution_id"], {})
    return (inst.get("short_name") or service.get("institution_short_name") or "").upper()


# Kept in capitals when an all-caps catalog name is put in sentence case
_ACRONYMS = {"EOID", "ID", "TIN", "VAT", "USD", "ETB", "NID", "ICS", "DARS", "MOTRI", "MOR", "CBE", "EIC", "PPPA"}


def display_name(name: str) -> str:
    """Some catalog names arrive in all caps ("RENEWAL PASSPORT"); show them in sentence case.

    Display only: the snapshot and the matching rules keep the original text.
    """
    letters = [c for c in name if c.isalpha()]
    if not letters or not all(c.isupper() for c in letters if c.isascii()):
        return name
    lowered = re.sub(r"[A-Za-z]+", lambda m: m.group(0) if m.group(0) in _ACRONYMS else m.group(0).lower(), name)
    return lowered[:1].upper() + lowered[1:]


_DAY_TIER = re.compile(r"^\s*(?:for\s+)?(\d+)\s*days?\s+(?:[a-z]+\s+)?service\s+(.+)$", re.I)


def _fee_label(fee: str) -> str:
    plain = re.fullmatch(r"(\d+)\s*(ETB|Birr)", fee.strip(), re.I)
    return f"{int(plain.group(1)):,} ETB" if plain else fee.strip()


def service_summary(service: dict, institution: str | None = None) -> str:
    """One readable line for a catalog service: "At ICS: official fee 21,000 ETB, about 5 days"."""
    fee = (service.get("fee_text") or "").strip()
    if fee.lower() in ("-", "none", "n/a"):
        fee = ""
    days = None
    tier = _DAY_TIER.match(fee)
    if tier:  # ICS lists the delivery speed inside the fee: "5 days service 21000 ETB"
        days, fee = tier.group(1), tier.group(2)
    parts = []
    if fee:
        parts.append(f"official fee {_fee_label(fee)}")
    if days:
        parts.append(f"about {days} days")
    elif service.get("processing_time_text"):
        parts.append(f"processing time {service['processing_time_text'].strip().lower()}")
    line = ", ".join(parts)
    if institution:
        return f"At {institution}: {line}" if line else f"At {institution}"
    return line[:1].upper() + line[1:]


def _with_institution(service: dict) -> dict:
    inst = _institutions_by_id().get(service["institution_id"], {})
    return {
        **service,
        "name": display_name(service["name"]),
        "summary": service_summary(service, inst.get("short_name") or service.get("institution_short_name")),
        "institution": {
            "id": inst.get("id", service["institution_id"]),
            "name": inst.get("name") or service.get("institution_name"),
            "name_am": inst.get("name_am"),
            "short_name": inst.get("short_name") or service.get("institution_short_name"),
            "logo_url": inst.get("logo_url"),
        },
    }


def list_institutions() -> list[dict]:
    return load_catalog()["institutions"]


def list_centers() -> list[dict]:
    return load_catalog()["centers"]


def get_service(service_id: str) -> dict | None:
    for s in load_catalog()["services"]:
        if s["id"] == service_id:
            return _with_institution(s)
    return None


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", text.lower()) if t]


def search_services(
    q: str | None = None,
    institution_id: str | None = None,
    language: str | None = "en",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    services = load_catalog()["services"]
    if language:
        services = [s for s in services if s["language"] == language]
    if institution_id:
        services = [s for s in services if s["institution_id"] == institution_id]

    if q:
        terms = _tokens(q)
        scored = []
        for s in services:
            name = s["name"].lower()
            haystack = " ".join(
                [name, (s.get("institution_short_name") or "").lower(), (s.get("institution_name") or "").lower()]
            )
            docs = " ".join(s.get("required_documents") or []).lower()
            score = 0
            for t in terms:
                if t in name:
                    score += 3
                elif t in haystack:
                    score += 2
                elif t in docs:
                    score += 1
                else:
                    score = 0
                    break
            if score:
                scored.append((score, s))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["name"]))
        services = [s for _, s in scored]

    total = len(services)
    page = services[offset : offset + limit]
    return {"total": total, "items": [_with_institution(s) for s in page]}


def services_for_document(doc_id: str, language: str = "en") -> list[dict]:
    rules = DOCUMENT_SERVICE_RULES.get(doc_id, [])
    if not rules:
        return []
    matches = []
    for short, prefix in rules:
        for s in load_catalog()["services"]:
            if s["language"] != language:
                continue
            if _short_name(s) == short and s["name"].lower().startswith(prefix.lower()):
                if s not in matches:
                    matches.append(s)
    return [_with_institution(s) for s in matches]


def mesob_summary_for_step(doc_id: str) -> dict | None:
    """Compact MESOB info attached to a roadmap step for the UI."""
    matches = services_for_document(doc_id)
    if not matches:
        return None
    primary = matches[0]
    return {
        "available": True,
        "serviceId": primary["id"],
        "serviceName": primary["name"],
        "institution": primary["institution"]["short_name"] or primary["institution"]["name"],
        "feeText": primary.get("fee_text"),
        "feeEtbMin": primary.get("fee_etb_min"),
        "processingTimeText": primary.get("processing_time_text"),
        "processingMinutes": primary.get("processing_minutes"),
        "requiredDocuments": primary.get("required_documents") or [],
        "onlineUrl": primary.get("online_url"),
        "sourceUrl": primary.get("source_url"),
        "alternatives": [
            {"serviceId": m["id"], "serviceName": m["name"]} for m in matches[1:]
        ],
    }


def catalog_stats() -> dict:
    c = load_catalog()
    return {
        "fetchedAt": c.get("fetched_at"),
        "institutions": len(c["institutions"]),
        "centers": len(c["centers"]),
        "services": sum(1 for s in c["services"] if s["language"] == "en"),
        "servicesAm": sum(1 for s in c["services"] if s["language"] == "am"),
    }


def service_as_text(service: dict) -> str:
    """Flat description of a catalog service for embedding and LLM context."""
    inst = service.get("institution_short_name") or service.get("institution_name") or ""
    parts = [f"{service['name']} ({inst}), available at MESOB one-stop service centers."]
    if service.get("required_documents"):
        parts.append("Required documents: " + "; ".join(service["required_documents"]) + ".")
    if service.get("fee_text"):
        parts.append(f"Fee: {service['fee_text']}.")
    if service.get("processing_time_text"):
        parts.append(f"Processing time: {service['processing_time_text']}.")
    if service.get("online_url"):
        parts.append(f"Online: {service['online_url']}.")
    return " ".join(parts)


def services_by_ids(ids: list[str]) -> list[dict]:
    wanted = set(ids)
    return [_with_institution(s) for s in load_catalog()["services"] if s["id"] in wanted]
