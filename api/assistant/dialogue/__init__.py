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

from assistant import agent, entities, nlu, references, resolver
from assistant.dialogue.answers import (
    BROKER,
    LOOKING,
    PROPERTY_HUNT,
    PROVIDER_PLURAL,
    PROVIDER_WANTS,
    _answer,
    _hire,
    _provider_want,
)
from assistant.dialogue.base import (
    EMPTY_STATE,
    HIRE,
    LOW_CONFIDENCE,
    POPULAR,
    QA_INTENTS,
    _fmt_money,
    _msg_action,
    _no_em_dash,
    _popular_chips,
    _qa_chips,
    _reply,
    log,
    new_state,
)
from assistant.dialogue.data import (
    _org_fee_text,
    _org_live,
    _service_card,
    _service_record,
    _source_line,
    _title,
)
from assistant.dialogue.present import (
    _mesob_centers,
    _org_branches,
    _present,
    _report_href,
)
from assistant.dialogue.slots import (
    _APPLICANT_CHIPS,
    _advance,
    _held_options,
    _next_question,
    _set_service,
)
from assistant.dialogue.turn import (
    YES,
    _apply_entities,
    _handle_action,
    _missed,
    _option_label,
    _resolve_and_start,
    adopt_context,
    handle,
    welcome,
)
from assistant.texts import chip, t

__all__ = [
    "agent",
    "chip",
    "entities",
    "nlu",
    "references",
    "resolver",
    "t",
    "log",
    "POPULAR",
    "QA_INTENTS",
    "LOW_CONFIDENCE",
    "HIRE",
    "EMPTY_STATE",
    "new_state",
    "_no_em_dash",
    "_msg_action",
    "_reply",
    "_popular_chips",
    "_qa_chips",
    "_fmt_money",
    "_org_live",
    "_service_record",
    "_title",
    "_source_line",
    "_service_card",
    "_org_fee_text",
    "_set_service",
    "_held_options",
    "_next_question",
    "_APPLICANT_CHIPS",
    "_advance",
    "_present",
    "_report_href",
    "_org_branches",
    "_mesob_centers",
    "_answer",
    "PROVIDER_WANTS",
    "BROKER",
    "PROPERTY_HUNT",
    "LOOKING",
    "PROVIDER_PLURAL",
    "_provider_want",
    "_hire",
    "_resolve_and_start",
    "_missed",
    "_option_label",
    "_apply_entities",
    "YES",
    "handle",
    "_handle_action",
    "adopt_context",
    "welcome",
]
