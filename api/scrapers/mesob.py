"""
MESOB one-stop service catalog scraper.

Pulls the public catalog behind mesobcenter.et (institutions, services with
required documents / fees / processing times, and center locations), normalizes
it, and writes a snapshot to data/mesob/catalog.json.

Run from api/:  uv run python -m scrapers.mesob
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_URL = "https://mesobcenter.et/api/api"
ASSET_BASE_URL = "https://mesobcenter.et/api"
SOURCE_URL = "https://mesobcenter.et/service-catalogue"
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "mesob" / "catalog.json"

_MONEY_RE = re.compile(
    r"(?:(?P<pre>ETB|Birr|birr|ብር)\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<post>ETB|Birr|birr|BIRR|ብር|USD|\$)?"
)
_DURATION_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>minutes?|mins?|hours?|hrs?|days?|weeks?|months?|ደቂቃ|ሰዓት|ቀን|ሳምንት|ወር)",
    re.IGNORECASE,
)
_UNIT_MINUTES = {
    "min": 1,
    "hou": 60,
    "hr": 60,
    "day": 60 * 8, # working day
    "wee": 60 * 8 * 5,
    "mon": 60 * 8 * 22,
    "ደቂቃ": 1,
    "ሰዓት": 60,
    "ቀን": 60 * 8,
    "ሳምንት": 60 * 8 * 5,
    "ወር": 60 * 8 * 22,
}


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def parse_required_documents(raw: str | None) -> list[str]:
    """MESOB stores requirements as one comma/newline separated string."""
    if not raw:
        return []
    items = []
    for line in re.split(r",?\s*\n|,\s*$", raw):
        item = _clean(line).strip(",").strip()
        if item and item.lower() not in {"none", "n/a"}:
            items.append(item)
    return items


def parse_fee_etb(raw: str | None) -> dict:
    """
    Extract ETB amounts from free-text fees. Returns min/max ETB, whether any
    amount is quoted in USD, and whether the service is free.
    """
    text = raw or ""
    etb: list[float] = []
    usd = False
    for m in _MONEY_RE.finditer(text):
        unit = m.group("pre") or m.group("post")
        if not unit:
            continue
        value = float(m.group("num").replace(",", ""))
        if unit in ("USD", "$"):
            usd = True
        elif text[: m.start()].rstrip().endswith("+"):
            # Add-ons like "+ 5 Birr (custom duty)" are not the headline fee
            continue
        else:
            etb.append(value)
    lowered = text.lower()
    free = not etb and not usd and ("free" in lowered or "ነጻ" in text or "ነፃ" in text)
    return {
        "fee_etb_min": int(min(etb)) if etb else (0 if free else None),
        "fee_etb_max": int(max(etb)) if etb else (0 if free else None),
        "fee_has_usd": usd,
    }


def parse_duration_minutes(raw: str | None) -> int | None:
    """
    Best-effort processing time in minutes. Uses the 'Total ...' clause when
    present (e.g. 'Universal Service 5 minutes, DARS Office 15 Minute, Total 20 Minute').
    """
    text = raw or ""
    total_idx = text.lower().rfind("total")
    if total_idx >= 0:
        text = text[total_idx:]
    minutes = 0.0
    found = False
    for m in _DURATION_RE.finditer(text):
        unit = m.group("unit").lower()
        factor = next((v for k, v in _UNIT_MINUTES.items() if unit.startswith(k)), None)
        if factor is None:
            continue
        found = True
        minutes += float(m.group("num")) * factor
        if total_idx < 0:
            # Without a total, the first duration is the headline time
            break
    return int(minutes) if found else None


def normalize_service(row: dict) -> dict:
    short = _clean(row.get("organizationShortName"))
    org_name = _clean(row.get("organizationName"))
    fee_raw, time_raw = row.get("ServiceFee"), row.get("processingTime")
    fee = parse_fee_etb(fee_raw)
    if fee["fee_etb_min"] is None and not fee["fee_has_usd"]:
        # Some MESOB rows have fee and processing time entered in swapped fields
        swapped = parse_fee_etb(time_raw)
        if (swapped["fee_etb_min"] is not None or swapped["fee_has_usd"]) and parse_duration_minutes(fee_raw):
            fee_raw, time_raw, fee = time_raw, fee_raw, swapped
    return {
        "id": f"mesob-{row['id']}",
        "source_id": row["id"],
        "language": row.get("languageCode") or ("am" if row.get("languageId") == 2 else "en"),
        "name": _clean(row.get("name")),
        "institution_id": f"mesob-org-{row.get('organizationId')}",
        "institution_short_name": short or None,
        "institution_name": org_name,
        "required_documents": parse_required_documents(row.get("requiredDoucment")),
        "processing_time_text": _clean(time_raw) or None,
        "processing_minutes": parse_duration_minutes(time_raw),
        "fee_text": _clean(fee_raw) or None,
        **fee,
        "online_url": _clean(row.get("link")) or None,
        "source_url": SOURCE_URL,
        "updated_at": row.get("updatedAt"),
    }


def normalize_institutions(translated: list[dict], services: list[dict]) -> list[dict]:
    by_org: dict[int, dict] = {}
    for row in translated:
        org = by_org.setdefault(
            row["organizationId"],
            {"id": f"mesob-org-{row['organizationId']}", "source_id": row["organizationId"]},
        )
        lang = row.get("languageCode") or "en"
        name = _clean(row.get("name"))
        short = _clean(row.get("shortName")).strip("_ ").strip()
        if lang == "am":
            org["name_am"] = name
        else:
            org["name"] = name
            if short:
                org["short_name"] = short
        if row.get("logo"):
            org["logo_url"] = f"{ASSET_BASE_URL}{row['logo']}"

    counts: dict[str, int] = {}
    for s in services:
        if s["language"] == "en":
            counts[s["institution_id"]] = counts.get(s["institution_id"], 0) + 1
        # Fill gaps for orgs missing from the translation table
        org_id = int(s["institution_id"].rsplit("-", 1)[1]) if s["institution_id"][-1].isdigit() else None
        if org_id is not None and org_id not in by_org:
            by_org[org_id] = {"id": s["institution_id"], "source_id": org_id}
        if org_id is not None:
            org = by_org[org_id]
            org.setdefault("name", s["institution_name"])
            if s["institution_short_name"]:
                org.setdefault("short_name", s["institution_short_name"])

    out = []
    for org in by_org.values():
        org.setdefault("name", org.get("name_am") or org["id"])
        org["service_count"] = counts.get(org["id"], 0)
        out.append(org)
    return sorted(out, key=lambda o: (-o["service_count"], o["name"]))


def normalize_centers(locations: list[dict]) -> list[dict]:
    centers = []
    for loc in locations:
        if not loc.get("isActive", 1):
            continue
        label = _clean(loc.get("label"))
        centers.append(
            {
                "id": f"mesob-center-{loc['id']}",
                "name": label,
                "latitude": float(loc["lat"]) if loc.get("lat") else None,
                "longitude": float(loc["lng"]) if loc.get("lng") else None,
                "map_url": loc.get("link"),
                "city": "Addis Ababa" if label.lower().startswith("addis ababa") else None,
            }
        )
    return centers


def _get(client: httpx.Client, path: str) -> list[dict]:
    resp = client.get(f"{BASE_URL}{path}")
    resp.raise_for_status()
    body = resp.json()
    return body.get("data", body) if isinstance(body, dict) else body


def fetch_catalog() -> dict:
    headers = {"User-Agent": "ComplianceNavigator/0.1 (+catalog sync)"}
    with httpx.Client(timeout=60, headers=headers) as client:
        raw_services = _get(client, "/Services/with-language-and-organization")
        translated = _get(client, "/TranslatedOrganizations")
        locations = _get(client, "/Locations")

    services = [normalize_service(r) for r in raw_services if r.get("name")]
    return {
        "source": "mesob",
        "source_url": SOURCE_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "institutions": normalize_institutions(translated, services),
        "centers": normalize_centers(locations),
        "services": sorted(services, key=lambda s: (s["institution_id"], s["source_id"])),
    }


def write_snapshot(catalog: dict, path: Path = SNAPSHOT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def sync() -> dict:
    catalog = fetch_catalog()
    write_snapshot(catalog)
    return {
        "source": "mesob",
        "institutions": len(catalog["institutions"]),
        "centers": len(catalog["centers"]),
        "services": len(catalog["services"]),
        "services_en": sum(1 for s in catalog["services"] if s["language"] == "en"),
    }


def main() -> None:
    stats = sync()
    print(json.dumps(stats, indent=2))
    print(f"Snapshot written to {SNAPSHOT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
