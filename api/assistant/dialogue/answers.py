"""Answering questions about a service, and finding providers to hire."""

from __future__ import annotations

import re

from assistant import agent, references
from assistant.dialogue.base import (
    _fmt_money,
    _msg_action,
    _popular_chips,
    _qa_chips,
    _reply,
    log,
)
from assistant.dialogue.data import _org_fee_text, _service_record, _source_line, _title
from assistant.dialogue.present import _mesob_centers, _org_branches
from assistant.texts import chip, t

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
