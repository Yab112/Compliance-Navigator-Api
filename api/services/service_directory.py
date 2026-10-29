"""One directory of every service on the platform, whatever the source.

Sources, in the order we trust them:
  organization  services an organization published itself (org_services.published_snapshot)
  path          documents our roadmap engine builds a full multi-office path for (Neo4j)
  mesob         the public MESOB catalog, shown as a partner source
"""

from __future__ import annotations

import logging
import re

from services import catalog_service
from services.db import fetch_all

log = logging.getLogger(__name__)

SOURCES = ("organization", "path", "mesob")
_TOKEN = re.compile(r"[\wሀ-፿]+")


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 1]


def _score(terms: list[str], title: str, context: str, docs: str) -> int:
    score = 0
    for t in terms:
        if t in title:
            score += 3
        elif t in context:
            score += 2
        elif t in docs:
            score += 1
        else:
            return 0  # every term must match somewhere
    return score


def _organization_items() -> list[dict]:
    rows = fetch_all(
        """
        select s.id::text, s.slug, s.published_snapshot as snap, s.published_at,
               o.slug as org_slug, o.name as org_name, o.name_am as org_name_am, o.logo_url,
               o.org_type, o.status = 'verified' as org_verified
        from org_services s join organizations o on o.id = s.org_id
        where s.published_snapshot is not null and s.status <> 'archived' and o.status = 'verified'
        """
    )
    items = []
    for r in rows:
        snap = r["snap"] or {}
        reqs = snap.get("requirements") or []
        items.append({
            "id": f"org:{r['id']}",
            "source": "organization",
            "title": snap.get("name") or r["slug"],
            "titleAm": snap.get("name_am"),
            "summary": snap.get("summary"),
            "provider": r["org_name"],
            "providerAm": r["org_name_am"],
            "providerLogo": r["logo_url"],
            "verified": r["org_verified"],
            "feeMin": snap.get("fee_amount_min"),
            "feeMax": snap.get("fee_amount_max"),
            "feeCurrency": snap.get("fee_currency") or "ETB",
            "time": snap.get("processing_time_text"),
            "documentCount": len(reqs),
            "href": f"/organizations/{r['org_slug']}/services/{snap.get('slug') or r['slug']}",
            "updatedAt": r["published_at"].isoformat() if r["published_at"] else None,
            "_docs": " ".join((q.get("name") or "") for q in reqs).lower(),
        })
    return items


def _path_items() -> list[dict]:
    try:
        from services.graph_admin import list_documents

        docs = list_documents()
    except Exception:  # graph down: the directory still works from the other sources
        log.exception("Graph unavailable for the service directory")
        return []
    items = []
    for d in docs:
        if not d.get("target_of"):
            continue  # only documents the roadmap engine can build a path to
        items.append({
            "id": f"path:{d['id']}",
            "source": "path",
            "title": d.get("name") or d["id"],
            "titleAm": d.get("name_am"),
            "summary": "Step-by-step path across every office involved, starting from what you already have.",
            "provider": d.get("issuing_authority"),
            "providerAm": None,
            "providerLogo": None,
            "verified": False,
            "feeMin": d.get("fee_etb"),
            "feeMax": d.get("fee_etb"),
            "feeCurrency": "ETB",
            "time": f"About {d['avg_processing_days']} days" if d.get("avg_processing_days") else None,
            "documentCount": len(d.get("prerequisites") or []),
            "href": f"/roadmap/new?goal={d['id']}",
            "updatedAt": d.get("last_verified"),
            "_docs": " ".join(d.get("required_input_labels") or []).lower(),
        })
    return items


def _mesob_items(language: str) -> list[dict]:
    items = []
    for s in catalog_service.load_catalog()["services"]:
        if s["language"] != language:
            continue
        docs = s.get("required_documents") or []
        items.append({
            "id": f"mesob:{s['id']}",
            "source": "mesob",
            "title": s["name"],
            "titleAm": None,
            "summary": None,
            "provider": s.get("institution_name") or s.get("institution_short_name"),
            "providerAm": None,
            "providerLogo": (s.get("institution") or {}).get("logo_url"),
            "providerShort": s.get("institution_short_name"),
            "verified": False,
            "feeMin": s.get("fee_etb_min"),
            "feeMax": s.get("fee_etb_max"),
            "feeCurrency": "ETB",
            "feeText": s.get("fee_text"),
            "time": s.get("processing_time_text"),
            "documentCount": len(docs),
            "href": f"/services/{s['id']}",
            "updatedAt": None,
            "_docs": " ".join(docs).lower(),
        })
    return items


def search(q: str | None = None, source: str | None = None, language: str = "en",
           limit: int = 20, offset: int = 0) -> dict:
    groups = {
        "organization": _organization_items(),
        "path": _path_items(),
        "mesob": _mesob_items(language),
    }
    terms = _tokens(q) if q else []

    def matches(items: list[dict]) -> list[tuple[int, dict]]:
        if not terms:
            return [(0, i) for i in items]
        out = []
        for i in items:
            context = f"{(i.get('provider') or '')} {(i.get('providerShort') or '')} {(i.get('summary') or '')}".lower()
            score = _score(terms, f"{i['title']} {i.get('titleAm') or ''}".lower(), context, i["_docs"])
            if score:
                out.append((score, i))
        return out

    matched = {k: matches(v) for k, v in groups.items()}
    counts = {k: len(v) for k, v in matched.items()}
    chosen = [source] if source in SOURCES else list(SOURCES)
    # Organization-published data first, then guided paths, then the partner catalog
    ordered = []
    for k in chosen:
        ordered += [i for _, i in sorted(matched[k], key=lambda si: -si[0])] if terms else [i for _, i in matched[k]]
    page = [{k: v for k, v in i.items() if not k.startswith("_")} for i in ordered[offset: offset + limit]]
    return {"total": len(ordered), "counts": counts, "items": page}
