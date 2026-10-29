"""Deterministic, grounded dialogue manager.

Every fact in a reply (fees, documents, offices, times) is read from our data at the moment
of the turn: organization-published services first, then the path engine, then the MESOB
catalog, and the reply names its source. The trained intent model only decides what the
person is trying to do; it never produces facts.

A turn returns one assistant message:
  {text, quick_replies, widget, cards, actions, source, intent, confidence}
Quick replies and widgets carry an `action` the client sends back as-is.
"""

from __future__ import annotations

import logging
import re
from copy import deepcopy

from assistant import agent, entities, nlu, references, resolver
from assistant.texts import chip, t

log = logging.getLogger(__name__)

POPULAR = [("passport", "passport"), ("trade_license", "trade license"), ("tin", "TIN certificate"), ("kebele_id", "kebele ID")]
QA_INTENTS = {"ask_fee", "ask_documents", "ask_time", "ask_location", "ask_online", "ask_proxy"}
LOW_CONFIDENCE = 0.35
# Explicit marketplace words decide the intent on their own
HIRE = re.compile(r"\b(hire|agent|agents|agency|guday geday|guday|errand|do it for me|handle it for me)\b|ጉዳይ ገዳይ|ወኪል|ኤጀንሲ|ቅጠር|ይቅጠሩ")

EMPTY_STATE = {
    "lang": "en", "lang_locked": False, "lang_offered": False,
    "service": None, "answers": {}, "sub_city": None, "held": [], "held_asked": False,
    "applicant": None, "pending": None, "roadmap_id": None,
    # agent layer: the task in progress, who answers typed messages, the request handed to staff
    "task": None, "channel": "agent", "ticket_id": None, "misses": 0,
    # providers last shown and the one being discussed, for "what did Meron do" / "her reviews"
    "shown_providers": [], "focus_provider": None, "topic": None,
}


def new_state(lang: str = "en") -> dict:
    s = deepcopy(EMPTY_STATE)
    s["lang"] = lang
    return s


def _no_em_dash(text: str) -> str:
    return re.sub(r"\s*\u2014\s*", ", ", text or "")


def _msg_action(text: str) -> dict:
    return {"type": "message", "value": text}


def _reply(state: dict, text: str, **extra) -> dict:
    out = {"text": _no_em_dash(text), "quick_replies": [], "widget": None, "cards": [], "actions": [], "source": None}
    out.update(extra)
    return out


def _popular_chips(lang: str) -> list[dict]:
    chips = [{"label": chip(k, lang), "action": _msg_action(q if lang == "en" else chip(k, "am"))} for k, q in POPULAR]
    chips.append({"label": chip("hire", lang), "action": {"type": "hire"}})
    return chips


def _qa_chips(state: dict) -> list[dict]:
    lang = state["lang"]
    return [{"label": chip(k, lang), "action": {"type": "ask", "value": f"ask_{k}"}}
            for k in ("fee", "documents", "time", "location", "online", "proxy")] + [
        {"label": chip("hire_for", lang), "action": {"type": "hire"}},
        {"label": chip("start_over", lang), "action": {"type": "start_over"}},
    ]


def _fmt_money(amount, currency: str = "ETB") -> str:
    if amount is None:
        return ""
    value = float(amount)
    if value == 0:
        return "Free"
    return f"{int(value) if value.is_integer() else value:,} {currency}"


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


# ---------------------------------------------------------------- slot filling


def _set_service(state: dict, key: str) -> dict | None:
    rec = _service_record(key)
    if not rec:
        return None
    keep = {k: state.get(k) for k in ("lang", "lang_locked", "lang_offered", "sub_city", "applicant",
                                       "ticket_id", "channel", "shown_providers", "focus_provider", "topic")}
    held = state.get("held") or []
    state.clear()
    state.update(new_state(keep["lang"]))
    state.update({k: v for k, v in keep.items() if v is not None})
    state["held"] = held
    state["service"] = {"key": key, "source": rec["source"], "title": rec["title"], "title_am": rec.get("title_am")}
    return rec


def _held_options(rec: dict, state: dict) -> list[dict]:
    lang = state["lang"]
    if rec["source"] == "path":
        from services.roadmap_service import generate_roadmap

        roadmap = generate_roadmap(rec["ref"], state.get("sub_city") or "bole", [])
        return [{"value": s["id"], "label": (s.get("titleAm") if lang == "am" and s.get("titleAm") else s["title"])}
                for s in roadmap["steps"] if s["id"] != rec["ref"]]
    if rec["source"] == "org":
        from services import org_service

        result = org_service.check_eligibility(rec["ref"], state.get("answers") or {})
        return [{"value": r["key"], "label": r["name"]} for r in result["checklist"]]
    return [{"value": d, "label": d} for d in rec["raw"].get("required_documents") or []]


def _next_question(rec: dict, state: dict) -> dict | None:
    """The next thing we must ask before showing the path, as a reply; None when ready."""
    lang = state["lang"]
    if rec["source"] == "org":
        for q in rec["raw"].get("questions") or []:
            if q["key"] in state["answers"]:
                continue
            prompt = q.get("prompt_am") if lang == "am" and q.get("prompt_am") else q["prompt"]
            state["pending"] = {"kind": "question", "key": q["key"], "type": q["type"]}
            if q["type"] == "yes_no":
                options = [{"value": "yes", "label": chip("yes", lang)}, {"value": "no", "label": chip("no", lang)}]
            elif q["type"] == "single_choice":
                options = [{"value": o.get("value", o.get("label")), "label": o.get("label_am") if lang == "am" and o.get("label_am") else o.get("label", o.get("value"))}
                           for o in q.get("options") or []]
            else:
                return _reply(state, f"{prompt} {t('answer_free_text', lang)}")
            return _reply(state, prompt, widget={"kind": "choice", "key": q["key"], "options": options})
        categories = {r.get("category") for r in rec["raw"].get("fee_schedule") or [] if r.get("category") not in (None, "everyone")}
        if len(categories) > 1 and not state.get("applicant"):
            state["pending"] = {"kind": "applicant"}
            options = [{"value": c, "label": chip(f"applicant_{c}", lang) if f"applicant_{c}" in _APPLICANT_CHIPS else c}
                       for c in sorted(categories)]
            return _reply(state, t("ask_applicant", lang), widget={"kind": "choice", "key": "applicant", "options": options})
    needs_city = rec["source"] in ("path", "mesob") or len(rec["raw"].get("branch_ids") or []) > 1
    if needs_city and not state.get("sub_city"):
        from assistant.entities import SUB_CITIES

        state["pending"] = {"kind": "sub_city"}
        options = [{"value": k, "label": v["am"] if lang == "am" else v["en"]} for k, v in SUB_CITIES.items()]
        return _reply(state, t("ask_sub_city", lang), widget={"kind": "sub_city", "key": "sub_city", "options": options})
    if not state.get("held_asked"):
        options = _held_options(rec, state)
        state["held_asked"] = True
        if options:
            state["pending"] = {"kind": "held"}
            return _reply(state, t("ask_held", lang), widget={
                "kind": "checklist", "key": "held", "options": options,
                "submit_label": chip("continue", lang), "none_label": chip("none_held", lang),
                "selected": [o["value"] for o in options if o["value"] in (state.get("held") or [])],
            })
    state["pending"] = None
    return None


_APPLICANT_CHIPS = {"applicant_ethiopian", "applicant_foreign", "applicant_company"}


def _advance(state: dict, user, prefix: str | None = None) -> dict:
    if not state.get("service"):
        return _reply(state, t("need_service_first", state["lang"]), quick_replies=_popular_chips(state["lang"]))
    rec = _service_record(state["service"]["key"])
    if not rec:
        state["service"] = None
        return _reply(state, t("not_found", state["lang"], text=""), quick_replies=_popular_chips(state["lang"]))
    question = _next_question(rec, state)
    if question:
        if prefix:
            question["text"] = f"{prefix} {question['text']}"
        question["quick_replies"] = [{"label": chip("start_over", state["lang"]), "action": {"type": "start_over"}}]
        return question
    reply = _present(rec, state, user)
    if prefix:
        reply["text"] = f"{prefix} {reply['text']}"
    return reply


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


# ---------------------------------------------------------------- questions about a service


def _answer(intent: str, rec: dict, state: dict) -> dict:
    lang = state["lang"]
    title = _title(rec, lang)
    raw = rec["raw"]
    src = rec["source"]
    cards: list[dict] = []
    if intent == "ask_fee":
        fee = raw.get("fee_text") if src == "mesob" else _org_fee_text(raw, state.get("applicant")) if src == "org" else (
            _fmt_money(raw.get("fee_etb")) if raw.get("fee_etb") is not None else None)
        text = t("fee", lang, title=title, fee=fee) if fee else t("fee_unknown", lang, title=title)
        if src == "org" and raw.get("payment_methods"):
            text += " " + ("Payment: " if lang == "en" else "የክፍያ መንገድ፦ ") + ", ".join(raw["payment_methods"]) + "."
        if src == "path" and state.get("roadmap_id"):
            text += " " + ("Fees for the other steps are on each step of your path." if lang == "en" else "የሌሎቹ ደረጃዎች ክፍያ በመንገድዎ ላይ ይገኛል።")
    elif intent == "ask_documents":
        if src == "org":
            from services import org_service

            items = org_service.check_eligibility(rec["ref"], state.get("answers") or {})["checklist"]
            docs = [r["name"] + (f" ({r['original_or_copy']})" if r.get("original_or_copy") else "") for r in items]
        else:
            docs = raw.get("required_documents") if src == "mesob" else raw.get("required_input_labels")
        docs = docs or []
        text = t("documents", lang, title=title) if docs else t("documents_none", lang, title=title)
        if docs:
            cards.append({"kind": "checklist", "title": title, "items": [{"label": d, "done": False} for d in docs]})
    elif intent == "ask_time":
        time = raw.get("processing_time_text") if src in ("mesob", "org") else (
            f"about {raw['avg_processing_days']} days" if raw.get("avg_processing_days") else None)
        text = t("time", lang, title=title, time=time) if time else t("time_unknown", lang, title=title)
    elif intent == "ask_location":
        items = _org_branches(rec, state) if src == "org" else _mesob_centers(state.get("sub_city")) if src == "mesob" else []
        if src == "path" and raw.get("issuing_authority"):
            items = [{"name": raw["issuing_authority"]}]
        text = t("location", lang, title=title) if items else t("location_unknown", lang, title=title)
        if items:
            cards.append({"kind": "branches", "items": items})
    elif intent == "ask_online":
        url = raw.get("online_url") or raw.get("sourceUrl")
        if src == "org" and raw.get("online_parts"):
            url = raw.get("online_url") or ", ".join(raw["online_parts"]) if isinstance(raw["online_parts"], list) else raw["online_parts"]
        text = t("online_yes", lang, title=title, url=url) if raw.get("online_url") or (src == "org" and raw.get("online_parts")) else t("online_no", lang, title=title)
    else:  # ask_proxy
        notes = f" ({raw['proxy_notes']})" if src == "org" and raw.get("proxy_notes") else ""
        proxy = raw.get("proxy_allowed") if src == "org" else None
        if proxy in ("yes", True):
            text = t("proxy_yes", lang, notes=notes)
        elif proxy == "with_poa":
            text = t("proxy_poa", lang, notes=notes)
        elif proxy in ("no", False):
            text = t("proxy_no", lang, title=title, notes=notes)
        else:
            text = t("proxy_unknown", lang, title=title)
    return _reply(state, text, cards=cards, quick_replies=_qa_chips(state), source=_source_line(rec, lang))


# What kind of provider the person asked for: (pattern, provider_type, specialty)
PROVIDER_WANTS = [
    (re.compile(r"\b(customs|clearing|forwarding|import|export)\b|ጉምሩክ", re.I), "agency", "customs_clearing"),
    (re.compile(r"\b(visa|travel)\b|ቪዛ", re.I), "agency", "travel_visa"),
    (re.compile(r"\b(employment|recruit|recruitment|job abroad)\b|ቅጥር ኤጀንሲ", re.I), "agency", "employment"),
    (re.compile(r"\b(lawyer|legal|accountant|accounting|audit)\b|ጠበቃ|ሂሳብ", re.I), "agency", "legal_accounting"),
    (re.compile(r"\b(agency|agencies)\b|ኤጀንሲ", re.I), "agency", None),
    (re.compile(r"\b(guday|errand|runner)\b|ጉዳይ ገዳይ", re.I), "guday_geday", None),
]
# Property and car brokerage is out of scope. Office work about property (title deed, lease
# certificate, car ownership transfer) is a service and still goes to the normal flow.
BROKER = re.compile(r"\b(broker|brokers|delala|dalala|real estate agent)\b|ደላላ|ደላሎች", re.I)
PROPERTY_HUNT = re.compile(
    r"\b(for rent|to rent|rent an?|apartment|condo|condominium|studio)\b|\b(buy|sell|find)\b.*\b(house|home|villa|plot|land|car|vehicle)\b"
    r"|ኪራይ ቤት|የሚከራይ|ቤት (መግዛት|መሸጥ|መከራየት)|መኪና (መግዛት|መሸጥ)", re.I)
LOOKING = re.compile(r"\b(need|looking|look for|find|want|searching|search|show me)\b|እፈልጋለሁ|ፈልግ|ፈልጉ", re.I)
PROVIDER_PLURAL = {
    "agency": ("agencies", "ኤጀንሲዎች"),
    "guday_geday": ("errand agents (Guday Geday)", "ጉዳይ ገዳዮች"),
}


def _provider_want(text: str) -> tuple[str | None, str | None]:
    for pattern, ptype, specialty in PROVIDER_WANTS:
        if pattern.search(text or ""):
            return ptype, specialty
    return None, None


def _hire(state: dict, text: str = "") -> dict:
    from services import provider_service

    lang = state["lang"]
    ptype, specialty = _provider_want(text)
    if ptype:
        state["hire_filter"] = {"type": ptype, "specialty": specialty}
    elif text:
        state["hire_filter"] = None
    want = state.get("hire_filter") or {}
    rec = _service_record(state["service"]["key"]) if state.get("service") and not want else None
    params = {"limit": 3, "sort": "score"}
    if want:
        params["provider_type"] = want["type"]
        if want.get("specialty"):
            params["specialty"] = want["specialty"]
    elif rec and rec["source"] == "mesob":
        params["service_id"] = rec["ref"]
    elif rec:
        params["provider_type"] = "guday_geday"  # office errands; brokers and agencies are browsed on /hire
    if state.get("sub_city"):
        params["area"] = state["sub_city"]
    try:
        result = provider_service.public_list(**params)
        for loosen in ("area", "specialty", "service_id"):
            if result["items"] or loosen not in params:
                continue
            params.pop(loosen)
            if loosen == "service_id":
                params["provider_type"] = "guday_geday"
            result = provider_service.public_list(**params)
    except Exception:
        log.exception("Provider lookup failed")
        result = {"items": []}
    items = result.get("items") or []
    providers = [{
        "name": p.get("display_name") or p.get("full_name") or p.get("name"),
        "slug": p.get("slug"), "headline": p.get("headline"), "type": p.get("provider_type"),
        "score": p.get("trust_score"), "rating": p.get("rating_avg"), "reviews": p.get("rating_count") or p.get("reviews_count"),
        "photo": p.get("photo_url"), "verified": bool(p.get("national_id_verified") or p.get("id_verified")),
    } for p in items]
    references.remember(state, providers)
    title = _title(rec, lang) if rec else None
    if not providers:
        text_out = t("hire_none", lang)
    elif want:
        plural = PROVIDER_PLURAL[want["type"]][1 if lang == "am" else 0]
        text_out = f"Verified {plural} you can hire, best trust score first:" if lang == "en" else f"ሊቀጥሯቸው የሚችሉ የተረጋገጡ {plural}፦"
    else:
        text_out = t("hire", lang, title=title) if title else t("hire_any", lang)
    query = {}
    if want:
        query["type"] = want["type"]
        if want.get("specialty"):
            query["specialty"] = want["specialty"]
    elif rec and rec["source"] == "mesob":
        query["service_id"] = rec["ref"]
    href = "/hire" + ("?" + "&".join(f"{k}={v}" for k, v in query.items()) if query else "")
    # Follow-ups are about these providers now
    about = [{"label": (f"About {p['name'].split()[0]}" if lang == "en" else f"ስለ {p['name'].split()[0]}"),
              "action": _msg_action(f"tell me about {p['name'].split()[0]}")} for p in providers[:3]]
    return _reply(state, text_out, cards=[{"kind": "providers", "items": providers, "href": href}] if providers else [],
                  actions=[{"kind": "link", "label": chip("hire", lang), "href": href},
                           {"kind": "action", "label": agent.staff_match_chip(lang)["label"], "action": agent.staff_match_chip(lang)["action"]}],
                  quick_replies=about or (_qa_chips(state) if rec else _popular_chips(lang)))


# ---------------------------------------------------------------- the turn


def _resolve_and_start(text: str, state: dict, user, prefix: str | None = None) -> dict:
    lang = state["lang"]
    result = resolver.resolve(entities.want_text(text), lang)
    if result["status"] == "resolved":
        state["misses"] = 0
        rec = _set_service(state, result["candidate"].key)
        intro = t("got_service", lang, title=_title(rec, lang)) if rec else None
        return _advance(state, user, " ".join(x for x in (prefix, intro) if x) or None)
    if result["status"] == "ambiguous":
        state["pending"] = {"kind": "service_choice"}
        question = t("which_passport" if result.get("family") == "passport" else "which_service", lang)
        return _reply(state, f"{prefix} {question}" if prefix else question, widget={
            "kind": "choice", "key": "service",
            "options": [{"value": o["key"], "label": _option_label(o, lang)} for o in result["options"]],
        }, quick_replies=[{"label": chip("start_over", lang), "action": {"type": "start_over"}}])
    return _missed(state, t("not_found", lang, text=text[:60]))


def _missed(state: dict, text: str) -> dict:
    """The assistant could not help. After two misses in a row it offers a person first."""
    lang = state["lang"]
    state["misses"] = (state.get("misses") or 0) + 1
    if state["misses"] >= 2:
        return _reply(state, f"{agent.offer_human_text(lang)} {text}",
                      quick_replies=[agent.handoff_chip(lang), *_popular_chips(lang)])
    return _reply(state, text, quick_replies=[*_popular_chips(lang), agent.handoff_chip(lang)])


def _option_label(option: dict, lang: str) -> str:
    """Say where each choice comes from, so 'Trade license' and 'New trade license' are tellable apart."""
    if option.get("variant"):
        return option["label"]
    rec = _service_record(option["key"])
    if not rec:
        return option["label"]
    if rec["source"] == "org":
        where = (rec["raw"].get("org") or {}).get("name")
    elif rec["source"] == "path":
        where = "full path across offices" if lang == "en" else "ሙሉ መንገድ"
    else:
        where = rec["raw"].get("institution_short_name") or "MESOB"
    return f"{option['label']} · {where}" if where else option["label"]


def _apply_entities(text: str, state: dict) -> None:
    city = entities.sub_city(text)
    if city:
        state["sub_city"] = city
    held = entities.documents_held(text)
    if held:
        state["held"] = sorted(set(state.get("held") or []) | set(held))
    applicant = entities.applicant_type(text)
    if applicant:
        state["applicant"] = applicant


YES = re.compile(r"^\s*(yes|yeah|yep|ok|okay|sure|send|send it|go ahead|confirm)\b|^\s*(አዎ|እሺ|ላክ|ይላክ)", re.I)


def handle(state: dict, *, message: str | None, action: dict | None, user, ctx: dict | None = None) -> tuple[dict, dict]:
    """Returns (reply, nlu_info). Mutates state. ctx: {conversation_id, ip} for actions that create records."""
    info = {"intent": None, "confidence": None, "ranked": None, "version": None, "service": None}
    ctx = ctx or {}
    for key, default in (("task", None), ("channel", "agent"), ("ticket_id", None), ("misses", 0)):
        state.setdefault(key, default)

    if action:
        reply = _handle_action(state, action, user, ctx)
        info["service"] = (state.get("service") or {}).get("key")
        return reply, info

    text = (message or "").strip()
    prev_topic, state["topic"] = state.get("topic"), None
    lang_detected = nlu.detect_language(text)
    # Reply in the language the person is typing, even after they pressed the other language button
    if lang_detected == "am":
        state["lang"] = "am"
    elif lang_detected == "en" and state["lang"] == "am" and len(re.findall(r"[a-zA-Z]{2,}", text)) >= 3:
        state["lang"] = "en"
    offer_language = lang_detected == "tr" and not state.get("lang_locked") and not state.get("lang_offered")

    # A task in progress takes the answer to its question
    if agent.active(state):
        awaiting = state["task"].get("awaiting")
        if agent.CANCEL.search(text):
            return agent.cancel(state, _reply, _popular_chips(state["lang"])), info
        if awaiting == "confirm" and YES.search(text):
            return agent.execute(state, user, _reply, conversation_id=ctx.get("conversation_id"), ip=ctx.get("ip")), info
        if awaiting and awaiting != "confirm":
            return agent.fill(state, user, _reply, value=text), info
        state["task"] = None  # they moved on to something else

    pending = state.get("pending") or {}
    # A typed answer to an open question
    if pending.get("kind") == "question" and pending.get("type") in ("number", "text"):
        state["answers"][pending["key"]] = text
        state["pending"] = None
        return _advance(state, user), info
    _apply_entities(text, state)
    if pending.get("kind") == "sub_city" and state.get("sub_city"):
        state["pending"] = None
        return _advance(state, user), info

    # "What did Meron do", "the first one", "her reviews": a provider we just showed
    slug, candidates = references.resolve(text, state, prev_topic)
    if slug or candidates:
        kind = references.aspect(text)
        info.update(routed_intent="provider_info", service=(state.get("service") or {}).get("key"))
        if slug:
            return references.answer(slug, kind, state, _reply), info
        return references.ask_which(candidates, state, _reply, kind), info

    model = nlu.get_model()
    if model:
        pred = model.predict(text)
        intent, confidence = pred.intent, pred.confidence
        info.update(intent=intent, confidence=confidence, ranked=pred.ranked, version=pred.version)
    else:
        intent, confidence = ("service_request", 0.0)

    # Short "hi"/"thanks" are reliable; anything that names a service is a request even if the
    # model leans to small talk.
    names_service = resolver.PASSPORT.search(nlu.normalize(text)) is not None
    if intent in ("greeting", "smalltalk_other", "out_of_scope") and len(text.split()) > 2:
        probe = resolver.resolve(text, state["lang"])
        if probe["status"] == "resolved" or names_service:
            intent = "service_request"
    if confidence is not None and confidence < LOW_CONFIDENCE and intent in QA_INTENTS and not state.get("service"):
        intent = "service_request"  # an unsure "question" with nothing in context is almost always a request
    elif confidence is not None and confidence < LOW_CONFIDENCE and not (intent in QA_INTENTS and state.get("service")):
        # Unsure what the message is: if it clearly names a service, treat it as a request
        probe = resolver.resolve(entities.want_text(text), state["lang"])
        if probe["status"] == "resolved" or names_service:
            intent = "service_request"

    task = agent.detect(text, intent, state, confidence)
    if not task and HIRE.search(nlu.normalize(text)) and intent not in ("thanks", "goodbye", "start_over"):
        intent = "hire_agent"
    # Brokers and house or car hunting: say plainly that we don't do it, and what we do instead
    if not task and (BROKER.search(text) or (PROPERTY_HUNT.search(text) and LOOKING.search(text))):
        intent = "no_brokers"

    lang = state["lang"]
    if task:
        reply = agent.start(task, state, user, text, _reply)
    elif intent == "no_brokers":
        reply = _reply(state, t("no_brokers", lang), quick_replies=[
            {"label": chip("hire", lang), "action": {"type": "hire"}}, *_popular_chips(lang)[:4]])
    elif intent in agent.INTENT_TASKS:  # the model's guess without explicit wording: treat as unclear
        reply = _resolve_and_start(text, state, user)
    elif intent == "greeting":
        reply = _reply(state, t("welcome", lang), quick_replies=_popular_chips(lang))
    elif intent == "thanks":
        reply = _reply(state, t("thanks", lang), quick_replies=_qa_chips(state) if state.get("service") else _popular_chips(lang))
    elif intent == "goodbye":
        reply = _reply(state, t("goodbye", lang))
    elif intent == "start_over":
        state.clear()
        state.update(new_state(lang))
        state["lang_locked"] = True
        reply = _reply(state, t("start_over", lang), quick_replies=_popular_chips(lang))
    elif intent == "out_of_scope":
        reply = _missed(state, t("out_of_scope", lang))
    elif intent == "smalltalk_other":
        reply = _reply(state, t("smalltalk", lang), quick_replies=_popular_chips(lang))
    elif intent == "multi_entity":
        reply = _reply(state, t("multi_entity", lang), quick_replies=[
            {"label": "Commercial registration" if lang == "en" else "የንግድ ምዝገባ", "action": _msg_action("commercial registration")},
            {"label": chip("hire", lang), "action": {"type": "hire"}},
        ])
    elif intent == "hire_agent":
        probe = resolver.resolve(entities.want_text(text), lang)
        if probe["status"] == "resolved":
            _set_service(state, probe["candidate"].key)
        reply = _hire(state, text)
    elif intent in QA_INTENTS:
        probe = resolver.resolve(text, lang)
        if probe["status"] == "resolved" and probe["candidate"].key != (state.get("service") or {}).get("key"):
            _set_service(state, probe["candidate"].key)
        if state.get("service"):
            rec = _service_record(state["service"]["key"])
            reply = _answer(intent, rec, state) if rec else _reply(state, t("need_service_first", lang), quick_replies=_popular_chips(lang))
        elif probe["status"] == "ambiguous":
            state["pending_question"] = intent
            reply = _resolve_and_start(text, state, user)
        else:
            state["pending_question"] = intent
            reply = _reply(state, t("need_service_first", lang), quick_replies=_popular_chips(lang))
    elif intent == "resume_progress" and state.get("service"):
        state["held_asked"] = False
        reply = _advance(state, user, t("resume", lang))
    else:  # service_request, resume_progress without a service, low-confidence fallbacks
        prefix = t("resume", lang) if intent == "resume_progress" else None
        reply = _resolve_and_start(text, state, user, prefix)

    if offer_language:
        state["lang_offered"] = True
        reply["text"] += " " + t("language_choice", "en")
        reply["quick_replies"] = [
            {"label": chip("english", lang), "action": {"type": "language", "value": "en"}},
            {"label": chip("amharic", lang), "action": {"type": "language", "value": "am"}},
            *reply["quick_replies"],
        ]
    info["service"] = (state.get("service") or {}).get("key")
    info["routed_intent"] = intent
    return reply, info


def _handle_action(state: dict, action: dict, user, ctx: dict | None = None) -> dict:
    kind = action.get("type")
    value = action.get("value")
    lang = state["lang"]
    ctx = ctx or {}
    if kind == "handoff":
        return agent.start("handoff", state, user, "", _reply)
    if kind == "choice" and str(action.get("key", "")).startswith("provider:"):
        return references.answer(str(value), action["key"].split(":", 1)[1], state, _reply)
    if kind == "task" and value in ("handoff", "report_problem", "request_provider", "check_status"):
        return agent.start(value, state, user, "", _reply)
    if kind == "cancel_task":
        return agent.cancel(state, _reply, _popular_chips(lang))
    if kind == "channel":
        return agent.switch_channel(state, value, _reply)
    if agent.active(state):
        if kind == "confirm":
            return agent.execute(state, user, _reply, conversation_id=ctx.get("conversation_id"), ip=ctx.get("ip"))
        if kind == "form" or (kind == "choice" and action.get("key") in ("queue", "task_sub_city")):
            return agent.fill(state, user, _reply, value=value)
        state["task"] = None  # an older button: drop the task and do what it says
    if kind in ("confirm", "form"):
        return _reply(state, agent._t("cancelled", lang), quick_replies=_popular_chips(lang))
    if kind == "start_over":
        locked = state.get("lang_locked")
        state.clear()
        state.update(new_state(lang))
        state["lang_locked"] = locked
        return _reply(state, t("start_over", lang), quick_replies=_popular_chips(lang))
    if kind == "language" and value in ("en", "am"):
        state["lang"] = value
        state["lang_locked"] = True
        if state.get("service"):
            return _advance(state, user)
        return _reply(state, t("welcome", value), quick_replies=_popular_chips(value))
    if kind == "select_service" or (kind == "choice" and action.get("key") == "service"):
        if not _set_service(state, value):
            return _reply(state, t("not_found", lang, text=""), quick_replies=_popular_chips(lang))
        pending_q = state.pop("pending_question", None)
        if pending_q:
            return _answer(pending_q, _service_record(value), state)
        return _advance(state, user, t("got_service", lang, title=_title(_service_record(value), lang)))
    if kind == "choice" and action.get("key") == "applicant":
        state["applicant"] = value
        return _advance(state, user)
    if kind == "choice" and action.get("key") == "sub_city" or kind == "sub_city":
        state["sub_city"] = value
        return _advance(state, user)
    if kind == "choice":
        state["answers"][action.get("key")] = value
        return _advance(state, user)
    if kind == "documents":
        state["held"] = list(value or [])
        state["held_asked"] = True
        return _advance(state, user)
    if kind == "ask" and state.get("service"):
        rec = _service_record(state["service"]["key"])
        if rec:
            return _answer(value, rec, state)
    if kind == "hire":
        return _hire(state)
    if kind == "message":
        return handle(state, message=str(value or ""), action=None, user=user, ctx=ctx)[0]
    return _reply(state, t("welcome", lang), quick_replies=_popular_chips(lang))


def adopt_context(state: dict, key: str) -> None:
    """Take the page's service as the topic without asking its questions yet."""
    _set_service(state, key)


def welcome(state: dict) -> dict:
    return _reply(state, t("welcome", state["lang"]), quick_replies=_popular_chips(state["lang"]))
