"""Reading a service from its source: organization, path engine or MESOB catalog."""

from __future__ import annotations

from assistant import entities
from assistant.dialogue.base import _fmt_money
from assistant.texts import t

# ---------------------------------------------------------------- data access per source


def _org_live() -> dict:
    from services import org_service

    return org_service._live_services()


def _service_record(key: str) -> dict | None:
    """Everything we know about a service key, normalized across sources."""
    source, _, ref = key.partition(":")
    if source == "mesob":
        from services import catalog_service

        s = catalog_service.get_service(ref)
        if not s:
            return None
        name = s["name"].strip()
        return {"key": key, "source": "mesob", "ref": ref, "title": name.title() if name.isupper() else name, "raw": s}
    if source == "org":
        snap = _org_live().get(ref)
        if not snap:
            return None
        return {"key": key, "source": "org", "ref": ref, "title": snap.get("name"), "title_am": snap.get("name_am"), "raw": snap}
    if source == "path":
        from services.graph_admin import list_documents

        doc = next((d for d in list_documents() if d["id"] == ref), None)
        if not doc:
            return None
        meta = entities.DOCUMENTS.get(ref, {})
        return {"key": key, "source": "path", "ref": ref, "title": doc.get("name") or ref,
                "title_am": doc.get("name_am") or meta.get("am"), "raw": doc}
    return None


def _title(rec: dict, lang: str) -> str:
    return (rec.get("title_am") if lang == "am" and rec.get("title_am") else rec["title"]) or rec["ref"]


def _source_line(rec: dict, lang: str) -> str:
    if rec["source"] == "org":
        org = (rec["raw"].get("org") or {}).get("name", "")
        return t("source", lang, source=t("src_org", lang, org=org))
    return t("source", lang, source=t("src_path" if rec["source"] == "path" else "src_mesob", lang))


def _service_card(rec: dict, lang: str) -> dict:
    raw = rec["raw"]
    if rec["source"] == "mesob":
        return {"kind": "service", "title": _title(rec, lang), "provider": raw.get("institution_name"),
                "source": "mesob", "fee": raw.get("fee_text"), "time": raw.get("processing_time_text"),
                "documents": raw.get("required_documents") or [], "href": f"/services/{rec['ref']}"}
    if rec["source"] == "org":
        org = raw.get("org") or {}
        return {"kind": "service", "title": _title(rec, lang), "provider": org.get("name"), "source": "organization",
                "fee": _org_fee_text(raw), "time": raw.get("processing_time_text"),
                "documents": [r["name"] for r in raw.get("requirements") or []],
                "href": f"/organizations/{org.get('slug')}/services/{raw.get('slug')}"}
    return {"kind": "service", "title": _title(rec, lang), "provider": raw.get("issuing_authority"), "source": "path",
            "fee": _fmt_money(raw.get("fee_etb")) if raw.get("fee_etb") is not None else None,
            "time": f"{raw['avg_processing_days']} days" if raw.get("avg_processing_days") else None,
            "documents": raw.get("required_input_labels") or [], "href": f"/roadmap/new?goal={rec['ref']}"}


def _org_fee_text(snap: dict, applicant: str | None = None) -> str | None:
    if snap.get("is_free"):
        return "Free"
    rows = snap.get("fee_schedule") or []
    if applicant:
        matching = [r for r in rows if (r.get("category") or "everyone") in (applicant, "everyone")]
        rows = matching or rows
    parts = []
    for r in rows:
        amount = _fmt_money(r.get("amount_min"), r.get("currency") or "ETB")
        if r.get("amount_max") and r.get("amount_max") != r.get("amount_min"):
            amount += f" to {_fmt_money(r['amount_max'], r.get('currency') or 'ETB')}"
        label = ", ".join(x for x in (r.get("category") if r.get("category") != "everyone" else None,
                                      r.get("speed") if r.get("speed") not in (None, "regular") else None) if x)
        covers = f" for {r['covers']}" if r.get("covers") else ""
        parts.append(f"{amount}{f' ({label})' if label else ''}{covers}")
    if parts:
        return "; ".join(parts)
    if snap.get("fee_amount_min") is not None:
        return _fmt_money(snap["fee_amount_min"], snap.get("fee_currency") or "ETB")
    return None
