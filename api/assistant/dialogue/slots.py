"""Filling the facts a service needs before its path can be shown."""

from __future__ import annotations

from assistant.dialogue.base import _popular_chips, _reply, new_state
from assistant.dialogue.data import _service_record
from assistant.dialogue.present import _present
from assistant.texts import chip, t

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
