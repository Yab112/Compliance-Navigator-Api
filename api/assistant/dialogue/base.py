"""Conversation state and the reply helpers every part of the dialogue uses."""

from __future__ import annotations

import logging
import re
from copy import deepcopy

from assistant.texts import chip

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
