"""One turn of the conversation: route a message or a button press to the right reply."""

from __future__ import annotations

import re

from assistant import agent, entities, nlu, references, resolver
from assistant.dialogue.answers import (
    ASKS_FEE,
    ASKS_TAX,
    BROKER,
    BUSINESS_FORMS,
    START_STEPS,
    TAX_RULE_Q,
    TAX_WORD,
    INVESTMENT_ADVICE,
    LOOKING,
    NAMES_STEP,
    PROPERTY_HUNT,
    START_BUSINESS,
    _answer,
    _hire,
    _provider_want,
    start_business_costs,
)
from assistant.dialogue.base import (
    HIRE,
    LOW_CONFIDENCE,
    QA_INTENTS,
    _msg_action,
    _popular_chips,
    _qa_chips,
    _reply,
    new_state,
)
from assistant.dialogue.data import _service_record, _title
from assistant.dialogue import typed
from assistant.dialogue.slots import _advance, _set_service
from assistant.texts import chip, t

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
        if result.get("family") == "passport":
            question = t("which_passport", lang)
        elif len(result["options"]) == 1:
            question = t("did_you_mean", lang, title=result["options"][0]["label"])
        else:
            question = t("which_service", lang)
        return _reply(state, f"{prefix} {question}" if prefix else question, widget={
            "kind": "choice", "key": "service",
            "options": [{"value": o["key"], "label": _option_label(o, lang)} for o in result["options"]],
        }, quick_replies=[{"label": chip("start_over", lang), "action": {"type": "start_over"}}])
    # Quote a short name back; a whole sentence quoted reads like a parrot
    short = len(text.split()) <= 4 and len(text) <= 40
    return _missed(state, t("not_found", lang, text=text) if short else t("not_found_long", lang))


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


# Small talk the model may guess for text it doesn't understand ("asdkjh", "new"). Ending or
# restarting someone's conversation on a guess loses their place, so these need the words.
SOCIAL_WORDS = {
    "goodbye": re.compile(r"\b(bye|goodbye|good bye|see you|ciao|chao|later|that'?s all|done|nothing else)\b"
                          r"|ደህና|ቻው|በቃ|ይበቃኛል|ደና", re.I),
    "start_over": re.compile(r"\b(start (over|again)|restart|reset|from the (beginning|start)|new (chat|conversation))\b"
                             r"|እንደገና|ከመጀመሪያ", re.I),
    "thanks": re.compile(r"\b(thank\w*|thx|thanx|ty|appreciate\w*|ameseginalehu|amesegnalehu|great|perfect)\b"
                         r"|አመሰግና|እናመሰግና|ግሩም|በጣም ጥሩ", re.I),
    "greeting": re.compile(r"\b(hi|hii+|hello|hey|selam|salam|good (morning|afternoon|evening)|tena yistilign|howdy)\b"
                           r"|ሰላም|ጤና ይስጥልኝ|እንደምን", re.I),
}
SOCIAL_SURE = 0.6


def _social_unsupported(intent: str, confidence: float | None, text: str) -> bool:
    words = SOCIAL_WORDS.get(intent)
    return bool(words) and (confidence or 0) < SOCIAL_SURE and not words.search(text)


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
    # "new", "2", "bole": a typed pick of one of the buttons we just showed
    picked = typed.pick(text, state.get("offered"))
    if picked:
        info["routed_intent"] = "typed_choice"
        return _handle_action(state, picked, user, ctx), info
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

    if _social_unsupported(intent, confidence, text):
        intent = "service_request"  # look it up; if nothing fits, say so and offer help

    task = agent.detect(text, intent, state, confidence)
    if not task and HIRE.search(nlu.normalize(text)) and intent not in ("thanks", "goodbye", "start_over"):
        intent = "hire_agent"
    # Brokers and house or car hunting: say plainly that we don't do it, and what we do instead
    if not task and (BROKER.search(text) or (PROPERTY_HUNT.search(text) and LOOKING.search(text))):
        intent = "no_brokers"
    elif not task and INVESTMENT_ADVICE.search(text):
        intent = "no_investment_advice"
    elif not task and intent not in ("thanks", "goodbye", "start_over", "hire_agent") and BUSINESS_FORMS.search(text):
        intent = "business_forms"
    elif not task and intent not in ("thanks", "goodbye", "start_over") and (ASKS_FEE.search(text) or ASKS_TAX.search(text)) \
            and (START_BUSINESS.search(text) or (state.get("subject") == "start_business" and _about_starting(text, state))):
        # "How much will the government charge me", "what taxes will I pay": about the whole start-up
        intent = "start_business_more"
    elif not task and intent not in ("thanks", "goodbye", "start_over") and START_BUSINESS.search(text) \
            and not NAMES_STEP.search(text):
        intent = "start_business"
    elif not task and intent not in ("thanks", "goodbye", "start_over", "hire_agent") and TAX_WORD.search(text) \
            and TAX_RULE_Q.search(text) and not _provider_want(text)[0]:
        intent = "tax_rules"

    lang = state["lang"]
    if task:
        reply = agent.start(task, state, user, text, _reply)
    elif intent == "no_brokers":
        reply = _reply(state, t("no_brokers", lang), quick_replies=[
            {"label": chip("hire", lang), "action": {"type": "hire"}}, *_popular_chips(lang)[:4]])
    elif intent in ("start_business", "start_business_more"):
        fresh = state.get("subject") != "start_business"
        intent = "start_business" if fresh else "start_business_more"
        state["subject"] = "start_business"
        wants_cost, wants_tax = bool(ASKS_FEE.search(text)), bool(ASKS_TAX.search(text))
        parts = [t("start_business", lang)] if fresh else []
        if wants_cost:
            parts.append(start_business_costs(state))
        if wants_tax:
            parts.append(t("business_taxes", lang))
        chips = []
        if not wants_cost:
            chips.append({"label": chip("start_costs", lang), "action": _msg_action(
                "how much will starting a business cost" if lang == "en" else "ንግድ ለመጀመር ስንት ያስከፍላል")})
        if not wants_tax:
            chips.append({"label": chip("business_taxes", lang), "action": _msg_action(
                "what taxes will my business pay" if lang == "en" else "ንግዴ ምን ግብሮች ይከፍላል")})
        chips += [
            {"label": chip("tin", lang), "action": _msg_action("TIN certificate")},
            {"label": chip("commercial_registration", lang), "action": _msg_action("commercial registration")},
            {"label": chip("trade_license", lang), "action": _msg_action("trade license")},
            {"label": chip("advisor", lang), "action": _msg_action("find me a business advisor")},
        ]
        reply = _reply(state, "\n\n".join(parts), quick_replies=chips)
    elif intent == "business_forms":
        state["subject"] = "start_business"
        reply = _reply(state, t("business_forms", lang), quick_replies=[
            {"label": chip("advisor", lang), "action": _msg_action("find me a business advisor")},
            {"label": chip("business_taxes", lang), "action": _msg_action(
                "what taxes will my business pay" if lang == "en" else "ንግዴ ምን ግብሮች ይከፍላል")},
            {"label": chip("commercial_registration", lang), "action": _msg_action("commercial registration")},
            {"label": chip("trade_license", lang), "action": _msg_action("trade license")},
        ])
    elif intent == "tax_rules":
        reply = _reply(state, t("business_taxes", lang), quick_replies=[
            {"label": chip("vat_registration", lang), "action": _msg_action("VAT registration")},
            {"label": chip("tin", lang), "action": _msg_action("TIN certificate")},
            {"label": chip("advisor", lang), "action": _msg_action("find me a tax agent")},
            {"label": chip("business_forms", lang), "action": _msg_action("should I be a PLC or sole proprietor")},
        ])
    elif intent == "no_investment_advice":
        reply = _reply(state, t("no_investment_advice", lang), quick_replies=[
            {"label": chip("advisor", lang), "action": _msg_action("find me a tax agent")},
            *_popular_chips(lang)[:3]])
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
        # "I need an accountant" asks for a kind of person, not a service ("Account Opening")
        probe = None if _provider_want(text)[0] else resolver.resolve(entities.want_text(text), lang)
        if probe and probe["status"] == "resolved":
            _set_service(state, probe["candidate"].key)
        reply = _hire(state, text)
    elif intent in QA_INTENTS:
        probe = resolver.resolve(text, lang)
        if probe["status"] == "resolved" and probe["candidate"].key != (state.get("service") or {}).get("key"):
            _set_service(state, probe["candidate"].key)
        if state.get("service"):
            rec = _service_record(state["service"]["key"])
            reply = _answer(intent, rec, state, text) if rec else _reply(state, t("need_service_first", lang), quick_replies=_popular_chips(lang))
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
        sure = confidence is not None and confidence >= LOW_CONFIDENCE
        prefix = t("resume", lang) if intent == "resume_progress" and sure else None
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


def _about_starting(text: str, state: dict) -> bool:
    """While we talk about starting a business, a cost or tax question is about the start-up unless it
    clearly names some other service (a passport, say)."""
    probe = resolver.resolve(entities.want_text(text), state["lang"])
    if probe["status"] == "resolved":
        return probe["candidate"].key in START_STEPS
    if probe["status"] == "ambiguous":
        return any(o["key"] in START_STEPS for o in probe.get("options") or [])
    return True  # names no service: "how much will it all cost", "what taxes will I pay"


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
