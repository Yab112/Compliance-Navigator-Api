"""The agentic assistant: Claude runs the conversation and calls our tools.

Claude decides what to look up and when: it searches our services, reads a service's fees,
documents, offices and times, builds a person's path, reads the start-up and tax guides, finds
verified providers, and searches the web for general background (markets, news). It writes the
answer to the question actually asked, in the person's language.

What stays in code, not in the prompt's hands:
  * Facts about offices come only from our tools. Every number in a reply must appear in a tool
    result, a web search citation, or the person's own words; a reply that fails this check is
    sent back once to be fixed, and otherwise the deterministic assistant answers instead.
  * Cards (paths, services, providers) and buttons come from the tools, not from Claude's text.
  * No key, an API error, a refusal or a failed check: the template assistant takes the turn.

Enabled with LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY in the environment.
"""

from __future__ import annotations

import json
import logging
import os
import re

from config.config import settings

log = logging.getLogger(__name__)

MODEL = os.environ.get("ASSISTANT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("ASSISTANT_EFFORT", "low")  # chat turns: low is usually enough; raise if quality needs it
MAX_TOOL_ROUNDS = 6
HISTORY_MESSAGES = 12
WEB_SEARCH_USES = 3

SYSTEM = """You are the Compliance Navigator assistant for people in Ethiopia (mostly Addis Ababa). You help \
citizens and businesses get things done with government offices and organizations: which office, in what \
order, what to bring, what it costs, how long it takes, and verified agents who can do it for them.

How to work:
- Use the tools. Before stating anything about a service (fee, document, office, time, online option, \
law), look it up with search_services and get_service. For "I need X" build_path when it is a \
multi-office path. For starting a business or tax questions use business_guide. For hiring help use \
find_providers. For market or general background (prices, demand, competition, news) use web_search.
- Answer the question that was asked, not a topic. Do not repeat what you already said earlier in \
the conversation; build on it.
- Every number, fee, date, law number or office name you state must come from a tool result, a web \
search result, or the person's message. If our data does not have it, say so plainly ("I don't have \
the fee for that yet") and suggest asking the office or a person on our team. Never guess a fee.
- Fees marked unconfirmed must be called "not yet confirmed by the office". Tell people to pay only at \
the official window, never to an individual.
- Web search is for background only. Say it comes from the web, name the source, and never present \
it as an office's official requirement.
- Boundaries: you give general information, not legal or tax advice; for a personal case suggest a \
licensed tax agent, accountant or lawyer (find_providers). Never advise on what to invest in or which \
shares to buy (only ECMA-licensed advisers may). We do not list property or car brokers (delala).
- If the person is upset, reports a problem or wants a person, call offer_person.
- Reply in the person's language: Amharic if they write Amharic (Ge'ez script), otherwise English. \
Keep replies short and plain, for a phone screen: a few sentences or a short list. No em dashes. \
Do not use markdown headings or tables."""

TOOLS = [
    {
        "name": "search_services",
        "description": "Search the services we hold (multi-office paths, organization-published services and the "
                       "MESOB catalog). Returns candidate services with their key. Use it to find the key "
                       "before get_service or build_path. Empty results mean we don't cover it.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["query"],
                         "properties": {"query": {"type": "string", "description": "Short service name, e.g. 'trade license renewal'"}}},
    },
    {
        "name": "get_service",
        "description": "Everything we hold about one service: fee (and whether the office confirmed it), "
                       "documents to bring, processing time, where to go, online option, whether someone "
                       "else can apply, and the source. Shows the service card to the person.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["service_key"],
                         "properties": {"service_key": {"type": "string"},
                                        "sub_city": {"type": "string", "description": "Addis sub-city id if known, e.g. 'bole'"}}},
    },
    {
        "name": "build_path",
        "description": "Build the person's step-by-step path for a path service (key starting 'path:'), skipping "
                       "documents they already have. Saves it and shows the path card.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["service_key", "sub_city"],
                         "properties": {
                             "service_key": {"type": "string"},
                             "sub_city": {"type": "string", "enum": ["addis_ketema", "akaki", "arada", "bole", "gulele",
                                                                     "kirkos", "kolfe", "lideta", "nifas_silk", "yeka"]},
                             "documents_held": {"type": "array", "items": {"type": "string"},
                                                "description": "Document ids they already have, e.g. kebele_id, tin"}}},
    },
    {
        "name": "business_guide",
        "description": "Our reviewed guide for starting and running a business in Ethiopia: 'steps' (order of "
                       "registration), 'costs' (office fees per step), 'taxes' (tax basics), 'forms' (sole "
                       "proprietor vs PLC vs share company). Cite the proclamations it names.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["topics"],
                         "properties": {"topics": {"type": "array", "items": {"type": "string",
                                                                                "enum": ["steps", "costs", "taxes", "forms"]}}}},
    },
    {
        "name": "find_providers",
        "description": "Verified providers the person can hire: 'guday_geday' (errand agents for office work), "
                       "'agency' (customs, travel/visa, employment, legal), 'advisor' (tax agents, accountants, "
                       "auditors, business set-up). Shows provider cards. Empty means none verified yet.",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["provider_type"],
                         "properties": {
                             "provider_type": {"type": "string", "enum": ["guday_geday", "agency", "advisor"]},
                             "specialty": {"type": "string", "description": "e.g. tax_agent, accountant, auditor, business_setup, customs_clearing, travel_visa"},
                             "sub_city": {"type": "string"}}},
    },
    {
        "name": "offer_person",
        "description": "Offer to hand the conversation to a person on our team (a button the person taps to confirm).",
        "input_schema": {"type": "object", "additionalProperties": False, "required": ["reason"],
                         "properties": {"reason": {"type": "string"}}},
    },
]
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": WEB_SEARCH_USES,
              "user_location": {"type": "approximate", "country": "ET", "city": "Addis Ababa", "timezone": "Africa/Addis_Ababa"}}

_NUM = re.compile(r"\d[\d,.]*\d|\d")


def enabled() -> bool:
    return settings.llm_provider == "anthropic" and bool(settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"))


_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None, timeout=60.0, max_retries=2)
    return _client


# ---------------------------------------------------------------- tools


class _Turn:
    """What the tools found this turn: the text the reply may draw facts from, and what to show."""

    def __init__(self, state: dict, user) -> None:
        self.state, self.user = state, user
        self.evidence: list[str] = []
        self.cards: list[dict] = []
        self.actions: list[dict] = []
        self.quick_replies: list[dict] = []
        self.tools_used: list[str] = []

    def run(self, name: str, args: dict) -> str:
        self.tools_used.append(name)
        handler = getattr(self, f"_{name}", None)
        if not handler:
            return json.dumps({"error": f"unknown tool {name}"})
        out = handler(**args)
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
        self.evidence.append(text)
        return text

    def _search_services(self, query: str) -> dict:
        from assistant import resolver

        matches = resolver.get_index().search(query, limit=6)
        found = [{"key": m.candidate.key, "title": m.candidate.title, "title_am": m.candidate.title_am,
                  "source": m.candidate.source, "match": round(m.score, 2)}
                 for m in matches if m.score >= resolver.SUGGEST - 0.07]
        return {"services": found, "note": None if found else "We don't hold this service yet."}

    def _get_service(self, service_key: str, sub_city: str | None = None) -> dict:
        from assistant.dialogue.answers import _answer
        from assistant.dialogue.data import _service_card, _service_record, _source_line, _title

        rec = _service_record(service_key)
        if not rec:
            return {"error": "No such service key. Use search_services first."}
        if sub_city:
            self.state["sub_city"] = sub_city
        lang = self.state["lang"]
        facts = {"title": _title(rec, lang), "source": _source_line(rec, lang)}
        for intent in ("ask_fee", "ask_documents", "ask_time", "ask_location", "ask_online", "ask_proxy"):
            reply = _answer(intent, rec, self.state)
            facts[intent.removeprefix("ask_")] = reply["text"]
        card = _service_card(rec, lang)
        facts["card"] = {k: v for k, v in card.items() if k in ("provider", "fee", "time", "documents")}
        self.cards.append(card)
        from assistant.dialogue.slots import _set_service

        _set_service(self.state, service_key)
        return facts

    def _build_path(self, service_key: str, sub_city: str, documents_held: list[str] | None = None) -> dict:
        from assistant.dialogue.data import _service_record
        from assistant.dialogue.present import _present
        from assistant.dialogue.slots import _set_service

        rec = _service_record(service_key)
        if not rec:
            return {"error": "No such service key. Use search_services first."}
        _set_service(self.state, service_key)
        self.state["sub_city"] = sub_city
        self.state["held"] = sorted(set(self.state.get("held") or []) | set(documents_held or []))
        self.state["held_asked"] = True
        reply = _present(rec, self.state, self.user)
        self.cards.extend(reply.get("cards") or [])
        self.actions.extend(reply.get("actions") or [])
        steps = [{k: c.get(k) for k in ("title", "steps", "summary") if c.get(k)} for c in reply.get("cards") or []]
        return {"summary": reply["text"], "cards": steps}

    def _business_guide(self, topics: list[str]) -> dict:
        from assistant.dialogue.answers import start_business_costs
        from assistant.texts import t

        lang = self.state["lang"]
        self.state["subject"] = "start_business"
        out = {}
        for topic in topics:
            out[topic] = (start_business_costs(self.state) if topic == "costs" else
                          t({"steps": "start_business", "taxes": "business_taxes", "forms": "business_forms"}[topic], lang))
        return out

    def _find_providers(self, provider_type: str, specialty: str | None = None, sub_city: str | None = None) -> dict:
        from assistant.dialogue.answers import _hire

        self.state["hire_filter"] = {"type": provider_type, "specialty": specialty}
        if sub_city:
            self.state["sub_city"] = sub_city
        reply = _hire(self.state)
        self.cards.extend(reply.get("cards") or [])
        self.actions.extend(reply.get("actions") or [])
        items = next((c["items"] for c in reply.get("cards") or [] if c.get("kind") == "providers"), [])
        return {"providers": [{k: p.get(k) for k in ("name", "headline", "type", "score", "rating", "reviews", "verified")}
                              for p in items], "note": reply["text"]}

    def _offer_person(self, reason: str) -> dict:
        from assistant import agent

        self.quick_replies.append(agent.handoff_chip(self.state["lang"]))
        return {"offered": True, "note": "A 'Talk to a person' button is shown under your reply."}


# ---------------------------------------------------------------- grounding check


def _numbers(text: str) -> set[str]:
    out = set()
    for n in _NUM.findall(text or ""):
        n = n.replace(",", "").rstrip(".")
        if n.isdigit() and int(n) <= 12:
            continue  # list numbering and small counts
        out.add(n)
    return out


def unsupported_numbers(reply: str, evidence: list[str]) -> set[str]:
    seen = set()
    for e in evidence:
        seen |= {n.replace(",", "").rstrip(".") for n in _NUM.findall(e or "")}
    return {n for n in _numbers(reply) if n not in seen}


def _web_evidence(content) -> list[str]:
    """Citations and result titles from server-side web search count as evidence."""
    out = []
    for block in content:
        btype = getattr(block, "type", None)
        if btype == "text":
            for c in getattr(block, "citations", None) or []:
                out.append(getattr(c, "cited_text", "") or "")
                out.append(getattr(c, "title", "") or "")
        elif btype == "web_search_tool_result":
            results = getattr(block, "content", None)
            if isinstance(results, list):
                out.extend(f"{getattr(r, 'title', '')} {getattr(r, 'page_age', '') or ''}" for r in results)
    return out


# ---------------------------------------------------------------- the turn


def _history(conversation_id: str | None, text: str) -> list[dict]:
    """Earlier messages as plain text (tool calls of past turns are not replayed)."""
    from assistant import store

    rows = store.history(conversation_id, limit=HISTORY_MESSAGES + 1) if conversation_id else []
    messages: list[dict] = []
    for m in rows:
        role = "user" if m["role"] == "user" else "assistant" if m["role"] in ("assistant", "staff") else None
        if not role or not (m["content"] or "").strip():
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + m["content"]
        else:
            messages.append({"role": role, "content": m["content"]})
    # The current message is already stored as the last user message; make sure it is there exactly once
    if not messages or messages[-1]["role"] != "user" or not messages[-1]["content"].endswith(text):
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += "\n\n" + text
        else:
            messages.append({"role": "user", "content": text})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def _create(messages: list[dict]):
    client = _get_client()
    return client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[*TOOLS, WEB_SEARCH],
        messages=messages,
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"output_config": {"effort": EFFORT}, "fallbacks": "default"},
    )


def run(state: dict, text: str, user, ctx: dict | None, reply_fn) -> dict | None:
    """One agentic turn. Returns a reply, or None to let the template assistant answer."""
    ctx = ctx or {}
    turn = _Turn(state, user)
    messages = _history(ctx.get("conversation_id"), text)
    evidence_user = [m["content"] for m in messages if m["role"] == "user"]
    try:
        response = None
        fixed = False
        for _ in range(MAX_TOOL_ROUNDS + 2):
            response = _create(messages)
            if response.stop_reason == "refusal":
                log.info("Assistant model refused; template answers")
                return None
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            uses = [b for b in response.content if b.type == "tool_use"]
            if uses:
                messages.append({"role": "assistant", "content": response.content})
                results = []
                for b in uses:
                    try:
                        out = turn.run(b.name, dict(b.input or {}))
                        results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
                    except Exception as exc:  # a tool failing is told to the model, not raised
                        log.exception("Assistant tool %s failed", b.name)
                        results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                                        "content": f"Tool failed: {type(exc).__name__}"})
                messages.append({"role": "user", "content": results})
                continue
            reply_text = "".join(b.text for b in response.content if b.type == "text").strip()
            evidence = turn.evidence + evidence_user + _web_evidence(response.content) + [
                e for m in messages if m["role"] == "assistant" and not isinstance(m["content"], str)
                for e in _web_evidence(m["content"])]
            bad = unsupported_numbers(reply_text, evidence)
            if bad and not fixed:
                fixed = True
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": (
                    "[system check] These numbers in your reply are not in any tool result or search result: "
                    f"{', '.join(sorted(bad))}. Look them up with a tool, or rewrite the reply without them. "
                    "Reply with the corrected message only.")})
                continue
            if bad or not reply_text:
                log.warning("Assistant reply failed the grounding check (%s); template answers", sorted(bad))
                return None
            break
        else:
            return None
    except Exception:
        log.exception("Agentic assistant failed; template answers")
        return None

    from assistant.dialogue.base import _popular_chips, _qa_chips

    quick = turn.quick_replies or (_qa_chips(state) if state.get("service") else _popular_chips(state["lang"])[:4])
    reply = reply_fn(state, re.sub(r"\s*—\s*", ", ", reply_text), cards=turn.cards[:4],
                     actions=turn.actions[:4], quick_replies=quick)
    reply["agentic"] = {"model": getattr(response, "model", MODEL), "tools": turn.tools_used}
    return reply
