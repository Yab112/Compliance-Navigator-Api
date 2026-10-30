"""Presenting a service: the path, checklist, branches and links."""

from __future__ import annotations

from assistant import entities
from assistant.dialogue.base import _fmt_money, _qa_chips, _reply, log
from assistant.dialogue.data import _service_card, _source_line, _title
from assistant.texts import chip, t

# ---------------------------------------------------------------- presenting the result


def _present(rec: dict, state: dict, user) -> dict:
    lang = state["lang"]
    title = _title(rec, lang)
    actions = []
    cards = []
    if rec["source"] == "path":
        from services.roadmap_service import generate_roadmap, save_roadmap

        sub_city = state.get("sub_city") or "bole"
        roadmap = generate_roadmap(rec["ref"], sub_city, state.get("held") or [])
        try:
            saved = save_roadmap(roadmap, user=user)
            state["roadmap_id"] = (saved or roadmap).get("id", roadmap["id"])
        except Exception:
            log.exception("Could not save roadmap from assistant")
            state["roadmap_id"] = None
        steps = roadmap.get("steps") or []
        offices = len({(s.get("office") or {}).get("name") or s.get("issuingAuthority") for s in steps})
        where = f" ({entities.SUB_CITIES[sub_city]['am' if lang == 'am' else 'en']})" if sub_city in entities.SUB_CITIES else ""
        days = f", about {roadmap['totalEstimatedDays']} days" if roadmap.get("totalEstimatedDays") and lang == "en" else (
            f"፣ በግምት {roadmap['totalEstimatedDays']} ቀናት" if roadmap.get("totalEstimatedDays") else "")
        text = t("path_intro", lang, title=title, where=where, steps=len(steps), offices=offices, days=days) if steps else t("path_done", lang)
        cards.append({
            "kind": "path", "title": title, "href": f"/roadmap/{state['roadmap_id']}" if state.get("roadmap_id") else None,
            "steps": [{
                "title": s.get("titleAm") if lang == "am" and s.get("titleAm") else s["title"],
                "office": (s.get("office") or {}).get("name") or s.get("issuingAuthority"),
                "fee": _fmt_money(s.get("feeEtb")) if s.get("feeEtb") is not None else None,
                "time": f"{s['estimatedDays']} days" if s.get("estimatedDays") else None,
                "documents": s.get("requiredInputs") or [],
                "mesob": (s.get("mesob") or {}).get("feeText") and {
                    "service": s["mesob"].get("serviceName"), "fee": s["mesob"].get("feeText"),
                    "time": s["mesob"].get("processingTimeText")},
                "organization": (s.get("orgData") or s.get("org") or {}).get("orgName") if isinstance(s.get("orgData") or s.get("org"), dict) else None,
            } for s in steps],
        })
        if state.get("roadmap_id"):
            actions.append({"kind": "link", "label": chip("open_path", lang), "href": f"/roadmap/{state['roadmap_id']}"})
    elif rec["source"] == "org":
        from services import org_service

        result = org_service.check_eligibility(rec["ref"], state.get("answers") or {})
        if not result["eligible"]:
            return _reply(state, t("ineligible", lang, reasons="; ".join(result["ineligible_reasons"])),
                          quick_replies=_qa_chips(state), source=_source_line(rec, lang))
        held = set(state.get("held") or [])
        keys = {r["key"] for r in result["checklist"]} - held
        path = org_service.service_path(rec["ref"], keys)
        missing = [r["name"] for r in result["checklist"] if r["key"] not in held]
        text = t("service_intro", lang, title=title) + " " + (
            t("missing_docs", lang, docs=", ".join(missing)) if missing else t("all_docs", lang))
        cards.append({"kind": "checklist", "title": title, "items": [
            {"label": r["name"], "done": r["key"] in held,
             "detail": ", ".join(x for x in (
                 r.get("original_or_copy") and f"{r['original_or_copy']}",
                 r.get("copies") and f"{r['copies']} copies",
                 "notarized" if r.get("notarized") else None,
                 (r.get("issued_by") or {}).get("org_name") and f"from {(r['issued_by'] or {})['org_name']}") if x) or None}
            for r in result["checklist"]]})
        cards.append({"kind": "path", "title": title,
                      "href": f"/organizations/{rec['raw']['org']['slug']}/services/{rec['raw']['slug']}",
                      "steps": [{"title": s["name"], "office": s["org"]["name"],
                                 "fee": _fmt_money(s.get("fee_amount_min"), s.get("fee_currency") or "ETB") if s.get("fee_amount_min") is not None else None,
                                 "time": s.get("processing_time_text"), "documents": s.get("provides") or []}
                                for s in path["steps"]]})
        branches = _org_branches(rec, state)
        if branches:
            cards.append({"kind": "branches", "items": branches})
        actions.append({"kind": "link", "label": chip("view_service", lang), "href": cards[-2]["href"] if branches else cards[-1]["href"]})
    else:
        raw = rec["raw"]
        held = set(state.get("held") or [])
        docs = raw.get("required_documents") or []
        missing = [d for d in docs if d not in held]
        text = t("service_intro", lang, title=title) + " " + (
            t("missing_docs", lang, docs=", ".join(missing)) if missing else t("all_docs", lang))
        card = _service_card(rec, lang)
        card["documents"] = [{"label": d, "done": d in held} for d in docs]
        cards.append(card)
        centers = _mesob_centers(state.get("sub_city"))
        if centers:
            cards.append({"kind": "branches", "items": centers})
        if raw.get("online_url"):
            actions.append({"kind": "link", "label": chip("online", lang), "href": raw["online_url"]})
        actions.append({"kind": "link", "label": chip("view_service", lang), "href": f"/services/{rec['ref']}"})
    actions.append({"kind": "action", "label": chip("hire_for", lang), "action": {"type": "hire"}})
    actions.append({"kind": "link", "label": chip("report", lang), "href": _report_href(rec)})
    return _reply(state, text, cards=cards, actions=actions, quick_replies=_qa_chips(state), source=_source_line(rec, lang))


def _report_href(rec: dict) -> str:
    if rec["source"] == "mesob":
        return f"/services/{rec['ref']}#report"
    if rec["source"] == "org":
        return f"/organizations/{rec['raw']['org']['slug']}/services/{rec['raw']['slug']}#report"
    return f"/roadmap/new?goal={rec['ref']}"


def _org_branches(rec: dict, state: dict) -> list[dict]:
    from services import org_service

    try:
        branches = org_service._service_branches(rec["raw"])
    except Exception:
        return []
    sub_city = state.get("sub_city")
    if sub_city:
        local = [b for b in branches if (b.get("sub_city") or "").lower().replace(" ", "_").startswith(sub_city[:4])]
        branches = local or branches
    return [{"name": b.get("name"), "address": b.get("address"), "hours": b.get("hours_text"), "window": b.get("window"),
             "phone": b.get("service_phone") or b.get("phone"), "map_url": b.get("map_url")} for b in branches[:3]]


def _mesob_centers(sub_city: str | None) -> list[dict]:
    from services import catalog_service

    centers = catalog_service.list_centers()
    label = entities.SUB_CITIES.get(sub_city or "", {}).get("en", "")
    first_word = label.split()[0].lower() if label else ""
    local = [c for c in centers if first_word and first_word in c["name"].lower()]
    chosen = local or [c for c in centers if "head quarter" in c["name"].lower()] or centers[:1]
    return [{"name": c["name"], "address": c.get("city"), "map_url": c.get("map_url")} for c in chosen[:2]]
