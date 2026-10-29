"""The assistant's agent layer: it acts, not only answers.

A *task* is something the assistant does for the person: hand the case to a person on the right
team, report wrong information, ask staff to find a provider, or look up the person's requests.
Each task declares the facts (slots) it needs. The agent fills what it can from the conversation,
asks for the rest one question at a time, shows a summary, and only acts after the person confirms.

TOOLS describes the same capabilities as JSON-schema tools, so a hosted LLM (Claude tool use)
can drive them later without changing what they do.
"""

from __future__ import annotations

import logging
import re

from assistant.texts import chip

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- triggers

HUMAN = re.compile(
    r"\b(human|real person|a person|customer (service|care|support)|support team|your (team|staff)|operator|"
    r"representative|call me|call me back|contact (you|us)|talk to (someone|somebody)|speak (to|with) (someone|somebody|a)|"
    r"phone number)\b|ሰው ማናገር|ሰው አገናኝ|ባለሙያ አገናኙ|ደውሉልኝ|ደውልልኝ|የደንበኞች አገልግሎት|ሰራተኞቻችሁ|ስልክ ቁጥራችሁ",
    re.I,
)
COMPLAINT = re.compile(
    r"\b(complain|complaint|scam|scammed|cheated|fraud|refund|overcharged|rude|bribe|corruption|never showed up|disappeared)\b"
    r"|ቅሬታ|አቤቱታ|አታለለ|ተታለልኩ|ጉቦ|ገንዘቤ ይመለስ",
    re.I,
)
STATUS = re.compile(
    r"\b(status of my|my (requests?|tickets?|hires?|case|complaint)|any updates?|track my|did (anyone|someone) reply)\b"
    r"|ጥያቄዬ|ጥያቄዎቼ|ቅሬታዬ|የጉዳዬ ሁኔታ",
    re.I,
)
REPORT = re.compile(
    r"\b(is wrong|are wrong|wrong information|incorrect|outdated|out of date|not correct|has changed|have changed|"
    r"moved|report wrong)\b|ስህተት ነው|ትክክል አይደለም|ተቀይሯል|ተዛውሯል",
    re.I,
)
CANCEL = re.compile(r"^\s*(cancel|stop|never ?mind|forget it|no thanks)\s*[.!]?\s*$|^\s*(ተው|ይቅር|ተወው|ሰርዝ)\s*$", re.I)

_MARKET = re.compile(r"\b(agent|provider|guday|hire|hired|agency)\b|ወኪል|ጉዳይ ገዳይ", re.I)
_TECH = re.compile(r"\b(log ?in|sign ?in|password|otp|fayda|account|website|site|app|bug|error|not working|broken|page)\b"
                   r"|መግባት|የይለፍ ቃል|መለያ|ድረ ገጽ", re.I)
_ORG = re.compile(r"\b(organization|organisation|our office|publish|register (our|my) (office|organization))\b|ተቋም", re.I)
_COMPLIANCE = re.compile(r"\b(licen[cs]e|permit|requirement|document|tax|tin|vat|law|legal|regulation|registration|"
                         r"certificate|renew)\b|ፈቃድ|መስፈርት|ሰነድ|ግብር|ሕግ|ምዝገባ", re.I)

MODEL_TASK_CONFIDENCE = 0.5
INTENT_TASKS = {"talk_to_human": "handoff", "complaint": "handoff", "check_status": "check_status",
                "report_problem": "report_problem"}

# ---------------------------------------------------------------- tool definitions (for an LLM brain)

TOOLS = [
    {"name": "handoff_to_team", "side_effect": True,
     "description": "Send the case to a person on the right team. Use when the person asks for a human, complains, "
                    "or when you cannot answer reliably from the data.",
     "input_schema": {"type": "object", "required": ["queue", "details"], "properties": {
         "queue": {"enum": ["customer_support", "compliance", "marketplace", "organizations", "technical"]},
         "details": {"type": "string"}, "priority": {"enum": ["low", "normal", "high", "urgent"]},
         "name": {"type": "string"}, "phone": {"type": "string"}, "email": {"type": "string"}}}},
    {"name": "report_wrong_information", "side_effect": True,
     "description": "Report that a fee, document, office or hours shown for a service is wrong.",
     "input_schema": {"type": "object", "required": ["service", "what"], "properties": {
         "service": {"type": "string"}, "what": {"type": "string"}}}},
    {"name": "request_provider_match", "side_effect": True,
     "description": "Ask staff to match the person with a verified provider for a service.",
     "input_schema": {"type": "object", "required": ["service", "sub_city", "phone"], "properties": {
         "service": {"type": "string"}, "sub_city": {"type": "string"}, "details": {"type": "string"},
         "phone": {"type": "string"}}}},
    {"name": "check_my_requests", "side_effect": False,
     "description": "List the signed-in person's support requests, hires and saved paths with their status.",
     "input_schema": {"type": "object", "properties": {}}},
]

# ---------------------------------------------------------------- texts

T = {
    "ask_queue": {"en": "I'll get you to the right person. What is it about?",
                  "am": "ትክክለኛውን ሰው አገናኝዎታለሁ። ጉዳዩ ስለ ምንድን ነው?"},
    "ask_details": {"en": "In a sentence or two, what do you need help with? The more you tell me, the faster they can act.",
                    "am": "በአንድ ወይም በሁለት ዓረፍተ ነገር ምን እርዳታ እንደሚፈልጉ ይንገሩኝ። ብዙ በነገሩኝ ቁጥር በፍጥነት ይረዱዎታል።"},
    "ask_complaint": {"en": "I'm sorry that happened. Tell me what happened, with the name of the provider or office and the date if you have it.",
                      "am": "ይህ በመከሰቱ አዝናለሁ። ምን እንደተፈጠረ፣ የአገልግሎት ሰጪውን ወይም የቢሮውን ስም እና ቀኑን ካለዎት ይንገሩኝ።"},
    "ask_contact": {"en": "How can the team reach you?", "am": "ቡድኑ እንዴት ሊያገኝዎ ይችላል?"},
    "ask_phone": {"en": "Which phone number should they call you on?", "am": "በየትኛው ስልክ ቁጥር ይደውሉልዎ?"},
    "confirm_handoff": {"en": "Here is what I'll send to the {team} team. Shall I send it?",
                        "am": "ለ{team} ቡድን የምልከው ይህ ነው። ልላከው?"},
    "sent_handoff": {"en": "Done. Your request {ref} is with the {team} team. {expected}. Their reply will appear right here and under the bell. Anything you type now goes to them; tap \"Back to the assistant\" to keep asking me.",
                     "am": "ተልኳል። ጥያቄዎ {ref} ለ{team} ቡድን ደርሷል። ምላሻቸው እዚሁ እና በደወሉ ስር ይታያል። አሁን የሚጽፉት ለእነሱ ይደርሳል፤ እኔን መጠየቅ ለመቀጠል \"ወደ ረዳቱ ተመለስ\" ይጫኑ።"},
    "ask_report_service": {"en": "Which service or office has the wrong information?",
                           "am": "የተሳሳተ መረጃ ያለው የትኛው አገልግሎት ወይም ቢሮ ነው?"},
    "ask_report_what": {"en": "What is wrong, and what is correct now? For example: \"The fee is now 1,200 birr\" or \"They also asked for a bank statement\".",
                        "am": "ምን ተሳስቷል፣ አሁን ትክክለኛው ምንድን ነው? ለምሳሌ፦ \"ክፍያው አሁን 1,200 ብር ነው\" ወይም \"የባንክ ስቴትመንትም ጠየቁ\"።"},
    "confirm_report": {"en": "I'll send this correction to the people who maintain this service's information:",
                       "am": "ይህን እርማት የአገልግሎቱን መረጃ ለሚያስተዳድሩት እልካለሁ፦"},
    "sent_report": {"en": "Thank you. Your report is in. The organization and our data team will check it, and the page will show the corrected information once confirmed.",
                    "am": "እናመሰግናለን። ሪፖርትዎ ደርሷል። ተቋሙ እና የመረጃ ቡድናችን ያረጋግጡታል፤ ሲረጋገጥ ገጹ የተስተካከለውን መረጃ ያሳያል።"},
    "sent_report_ticket": {"en": "Thank you. Your report {ref} is in. The organization and our data team will check it and tell you here what they changed.",
                           "am": "እናመሰግናለን። ሪፖርትዎ {ref} ደርሷል። ተቋሙ እና የመረጃ ቡድናችን አረጋግጠው የቀየሩትን እዚሁ ይነግሩዎታል።"},
    "provider_sign_in": {"en": "To have staff find you a provider, please sign in first, so the provider can reach you safely and you can rate them after.",
                         "am": "ሰራተኞቻችን አገልግሎት ሰጪ እንዲያገኙልዎ መጀመሪያ ይግቡ፤ አገልግሎት ሰጪው በደህና እንዲያገኝዎ እና በኋላ እንዲገመግሙት።"},
    "ask_provider_service": {"en": "Which service should the provider handle?", "am": "አገልግሎት ሰጪው የትኛውን አገልግሎት ያስፈጽም?"},
    "ask_provider_area": {"en": "Which sub-city should the provider work in?", "am": "አገልግሎት ሰጪው በየትኛው ክፍለ ከተማ ይስራ?"},
    "ask_provider_details": {"en": "Anything the provider should know, like a deadline or what you already have?",
                             "am": "አገልግሎት ሰጪው ማወቅ ያለበት ነገር አለ? ለምሳሌ የጊዜ ገደብ ወይም ያለዎት ሰነድ።"},
    "confirm_provider": {"en": "I'll ask our staff to match you with a verified provider:",
                         "am": "ሰራተኞቻችን የተረጋገጠ አገልግሎት ሰጪ እንዲያገናኙዎ እጠይቃለሁ፦"},
    "sent_provider": {"en": "Done. Staff will match you with a verified provider, usually within one working day. The provider calls you once they accept. You can follow it under My hires.",
                      "am": "ተልኳል። ሰራተኞቻችን ብዙውን ጊዜ በአንድ የስራ ቀን ውስጥ የተረጋገጠ አገልግሎት ሰጪ ያገናኙዎታል። አገልግሎት ሰጪው ሲቀበል ይደውልልዎታል። በ\"የቀጠርኳቸው\" ስር መከታተል ይችላሉ።"},
    "status_sign_in": {"en": "Sign in and I'll show you your requests, hires and saved paths with their status.",
                       "am": "ይግቡ፤ ጥያቄዎችዎን፣ ቅጥሮችዎን እና የተቀመጡ መንገዶችዎን ከሁኔታቸው ጋር አሳይዎታለሁ።"},
    "status_none": {"en": "You have no requests, hires or saved paths yet. What can I help you get done?",
                    "am": "እስካሁን ጥያቄ፣ ቅጥር ወይም የተቀመጠ መንገድ የለዎትም። ምን ላስፈጽምልዎ?"},
    "status": {"en": "Here is where everything stands:", "am": "ሁሉም ያለበት ሁኔታ ይህ ነው፦"},
    "cancelled": {"en": "Okay, I've dropped that. What else can I help with?", "am": "እሺ፣ ተውኩት። ሌላ ምን ልርዳዎ?"},
    "failed": {"en": "Sorry, I couldn't complete that just now: {error}. You can try again, or call us on {phone}.",
               "am": "ይቅርታ፣ አሁን ማጠናቀቅ አልቻልኩም፦ {error}። እንደገና ይሞክሩ ወይም በ{phone} ይደውሉልን።"},
    "back_to_agent": {"en": "I'm back. Your request {ref} stays open and the team's reply will still appear here. What else can I help with?",
                      "am": "ተመልሻለሁ። ጥያቄዎ {ref} ክፍት ነው፤ የቡድኑ ምላሽ እዚሁ ይታያል። ሌላ ምን ልርዳዎ?"},
    "to_human": {"en": "You're connected with the {team} team on {ref}. Type your message and they'll see it.",
                 "am": "ከ{team} ቡድን ጋር በ{ref} ተገናኝተዋል። መልዕክትዎን ይጻፉ፤ ያዩታል።"},
    "offer_human": {"en": "I'm not getting this right. A person from our team can look at it for you.",
                    "am": "በትክክል እየረዳሁዎት አይደለም። ከቡድናችን አንድ ሰው ሊያየው ይችላል።"},
}
CHIPS = {
    "handoff": {"en": "Talk to a person", "am": "ሰው ያናግሩኝ"},
    "send": {"en": "Send it", "am": "ላክ"},
    "send_report": {"en": "Send the report", "am": "ሪፖርቱን ላክ"},
    "send_match": {"en": "Find me a provider", "am": "አገልግሎት ሰጪ ፈልጉልኝ"},
    "cancel": {"en": "Cancel", "am": "ተው"},
    "back": {"en": "Back to the assistant", "am": "ወደ ረዳቱ ተመለስ"},
    "sign_in": {"en": "Sign in", "am": "ይግቡ"},
    "my_requests": {"en": "My requests", "am": "ጥያቄዎቼ"},
    "my_hires": {"en": "My hires", "am": "የቀጠርኳቸው"},
    "staff_match": {"en": "Let staff find one for me", "am": "ሰራተኞች ይፈልጉልኝ"},
    "skip": {"en": "Nothing to add", "am": "የምጨምረው የለም"},
}
LABELS = {
    "team": {"en": "Team", "am": "ቡድን"}, "request": {"en": "Request", "am": "ጥያቄ"},
    "about": {"en": "About", "am": "ስለ"}, "contact": {"en": "Contact", "am": "አድራሻ"},
    "priority": {"en": "Priority", "am": "ቅድሚያ"}, "service": {"en": "Service", "am": "አገልግሎት"},
    "correction": {"en": "Correction", "am": "እርማት"}, "area": {"en": "Sub-city", "am": "ክፍለ ከተማ"},
    "details": {"en": "Details", "am": "ዝርዝር"}, "phone": {"en": "Phone", "am": "ስልክ"},
    "name": {"en": "Full name", "am": "ሙሉ ስም"}, "email": {"en": "Email (optional)", "am": "ኢሜይል (ካለ)"},
    "message": {"en": "Your message", "am": "መልዕክትዎ"}, "continue": {"en": "Continue", "am": "ቀጥል"},
    "high": {"en": "High", "am": "ከፍተኛ"}, "normal": {"en": "Normal", "am": "መደበኛ"},
}


def _t(key: str, lang: str, **kw) -> str:
    text = T[key].get(lang) or T[key]["en"]
    return text.format(**kw) if kw else text


def _c(key: str, lang: str) -> str:
    return CHIPS[key].get(lang) or CHIPS[key]["en"]


def _l(key: str, lang: str) -> str:
    return LABELS[key].get(lang) or LABELS[key]["en"]


def handoff_chip(lang: str) -> dict:
    return {"label": _c("handoff", lang), "action": {"type": "handoff"}}


# ---------------------------------------------------------------- detection


def detect(text: str, intent: str | None, state: dict, confidence: float | None = None) -> str | None:
    """Which task a typed message starts, if any. Explicit wording wins; the model's guess needs confidence."""
    if COMPLAINT.search(text):
        return "complaint"
    if HUMAN.search(text):
        return "handoff"
    if STATUS.search(text):
        return "check_status"
    if REPORT.search(text) and (state.get("service") or len(text.split()) > 3):
        return "report_problem"
    if confidence is None or confidence < MODEL_TASK_CONFIDENCE:
        return None
    if intent == "complaint":
        return "complaint"
    return INTENT_TASKS.get(intent or "")


def classify_queue(text: str, state: dict, *, complaint: bool = False) -> str | None:
    if _MARKET.search(text) or (complaint and state.get("last_hire")):
        return "marketplace"
    if _TECH.search(text):
        return "technical"
    if _ORG.search(text) or REPORT.search(text):
        return "organizations"
    if _COMPLIANCE.search(text) or state.get("service"):
        return "compliance"
    return None


def _substantive(text: str) -> bool:
    """Does the triggering message already describe the problem, beyond 'talk to a person'?"""
    stripped = HUMAN.sub(" ", text or "")
    stripped = re.sub(r"\b(i|want|need|to|please|can|could|a|the|me|with|you|your|is|there|get|let)\b", " ", stripped, flags=re.I)
    return len([w for w in stripped.split() if len(w) > 1]) >= 4


# ---------------------------------------------------------------- task engine


def active(state: dict) -> bool:
    return bool(state.get("task"))


def start(name: str, state: dict, user, text: str = "", reply_fn=None) -> dict:
    lang = state["lang"]
    complaint = name == "complaint"
    if complaint:
        name = "handoff"
    task = {"name": name, "slots": {}, "awaiting": None}
    if name == "handoff":
        queue = classify_queue(text, state, complaint=complaint) if text else None
        if queue:
            task["slots"]["queue"] = queue
        if complaint:
            task["slots"]["priority"] = "high"
            task["complaint"] = True
        if text and _substantive(text):
            task["slots"]["details"] = text.strip()
    elif name == "report_problem":
        if state.get("service"):
            task["slots"]["service"] = state["service"]["title"]
            task["slots"]["service_key"] = state["service"]["key"]
        if text and len(text.split()) > 4:
            task["slots"]["what"] = text.strip()
    elif name == "request_provider":
        if state.get("service"):
            task["slots"]["service"] = state["service"]["title"]
            task["slots"]["service_key"] = state["service"]["key"]
        if state.get("sub_city"):
            task["slots"]["sub_city"] = state["sub_city"]
    state["task"] = task
    state["pending"] = None
    return _next(state, user, reply_fn)


def cancel(state: dict, reply_fn, quick_replies: list) -> dict:
    state["task"] = None
    return reply_fn(state, _t("cancelled", state["lang"]), quick_replies=quick_replies)


def _contact_known(user) -> dict | None:
    if not user:
        return None
    from services.db import fetch_one

    row = fetch_one("select fullname, phone, email from users where id = %s", (user.id,)) or {}
    return {"name": row.get("fullname") or None, "phone": row.get("phone"), "email": row.get("email")}


def _form(key: str, fields: list[dict], lang: str, submit: str | None = None) -> dict:
    return {"kind": "form", "key": key, "fields": fields, "submit_label": submit or _l("continue", lang)}


def _field(key: str, lang: str, ftype: str = "text", required: bool = True, value: str | None = None,
           placeholder: str | None = None, label: str | None = None) -> dict:
    out = {"key": key, "label": label or _l(key, lang), "type": ftype, "required": required}
    if value:
        out["value"] = value
    if placeholder:
        out["placeholder"] = placeholder
    return out


def _ask(state: dict, reply_fn, slot: str, text: str, **extra) -> dict:
    state["task"]["awaiting"] = slot
    cancel_chip = {"label": _c("cancel", state["lang"]), "action": {"type": "cancel_task"}}
    return reply_fn(state, text, quick_replies=extra.pop("quick_replies", []) + [cancel_chip], **extra)


def _next(state: dict, user, reply_fn) -> dict:
    task = state["task"]
    name, slots, lang = task["name"], task["slots"], state["lang"]

    if name == "check_status":
        state["task"] = None
        return _status(state, user, reply_fn)

    if name == "handoff":
        from services.support_service import QUEUES

        if not slots.get("queue"):
            options = [{"value": k, "label": v[1] if lang == "am" else v[0]} for k, v in QUEUES.items()]
            return _ask(state, reply_fn, "queue", _t("ask_queue", lang),
                        widget={"kind": "choice", "key": "queue", "options": options})
        if not slots.get("details"):
            question = _t("ask_complaint" if task.get("complaint") else "ask_details", lang)
            return _ask(state, reply_fn, "details", question, widget=_form("details", [
                _field("details", lang, "textarea", label=_l("message", lang))], lang))
        if "contact" not in slots:
            known = _contact_known(user)
            if known and known["phone"]:
                slots["contact"] = known
            else:
                fields = [] if known else [_field("name", lang)]
                fields.append(_field("phone", lang, "tel", value=(known or {}).get("phone"), placeholder="09XXXXXXXX"))
                if not known:
                    fields.append(_field("email", lang, "email", required=False))
                return _ask(state, reply_fn, "contact", _t("ask_contact" if not known else "ask_phone", lang),
                            widget=_form("contact", fields, lang))
        return _confirm(state, reply_fn)

    if name == "report_problem":
        if not slots.get("service"):
            return _ask(state, reply_fn, "service", _t("ask_report_service", lang), widget=_form("service", [
                _field("service", lang, placeholder="Passport renewal, Bole MESOB" if lang == "en" else None)], lang))
        if not slots.get("what"):
            return _ask(state, reply_fn, "what", _t("ask_report_what", lang), widget=_form("what", [
                _field("what", lang, "textarea", label=_l("correction", lang))], lang))
        return _confirm(state, reply_fn)

    if name == "request_provider":
        if not user:
            state["task"] = None
            return reply_fn(state, _t("provider_sign_in", lang),
                             actions=[{"kind": "link", "label": _c("sign_in", lang), "href": "/login?returnTo=/chat"}],
                             quick_replies=[handoff_chip(lang)])
        if not slots.get("service"):
            return _ask(state, reply_fn, "service", _t("ask_provider_service", lang), widget=_form("service", [
                _field("service", lang)], lang))
        if not slots.get("sub_city"):
            from assistant.entities import SUB_CITIES

            options = [{"value": k, "label": v["am"] if lang == "am" else v["en"]} for k, v in SUB_CITIES.items()]
            return _ask(state, reply_fn, "sub_city", _t("ask_provider_area", lang),
                        widget={"kind": "sub_city", "key": "task_sub_city", "options": options})
        if "details" not in slots:
            return _ask(state, reply_fn, "details", _t("ask_provider_details", lang),
                        widget=_form("details", [_field("details", lang, "textarea", required=False)], lang),
                        quick_replies=[{"label": _c("skip", lang), "action": {"type": "form", "key": "details", "value": {"details": ""}}}])
        if "contact" not in slots:
            known = _contact_known(user) or {}
            if known.get("phone"):
                slots["contact"] = known
            else:
                return _ask(state, reply_fn, "contact", _t("ask_phone", lang), widget=_form("contact", [
                    _field("phone", lang, "tel", placeholder="09XXXXXXXX")], lang))
        return _confirm(state, reply_fn)

    state["task"] = None
    return reply_fn(state, _t("cancelled", lang))


def _sub_city_label(key: str | None, lang: str) -> str | None:
    from assistant.entities import SUB_CITIES

    if not key:
        return None
    entry = SUB_CITIES.get(key)
    return (entry["am"] if lang == "am" else entry["en"]) if entry else key


def _contact_line(contact: dict) -> str:
    return " · ".join(x for x in (contact.get("name"), contact.get("phone"), contact.get("email")) if x)


def _confirm(state: dict, reply_fn) -> dict:
    from services.support_service import QUEUES, queue_label

    task, lang = state["task"], state["lang"]
    slots, name = task["slots"], task["name"]
    task["awaiting"] = "confirm"
    rows: list[dict] = []
    if name == "handoff":
        team = QUEUES[slots["queue"]][1] if lang == "am" else queue_label(slots["queue"])
        text, send = _t("confirm_handoff", lang, team=team), _c("send", lang)
        rows.append({"label": _l("team", lang), "value": team})
        if state.get("service"):
            rows.append({"label": _l("about", lang), "value": state["service"]["title"]})
        rows.append({"label": _l("request", lang), "value": slots["details"][:400]})
        rows.append({"label": _l("contact", lang), "value": _contact_line(slots["contact"])})
        if slots.get("priority") == "high":
            rows.append({"label": _l("priority", lang), "value": _l("high", lang)})
        title = _l("request", lang)
    elif name == "report_problem":
        text, send, title = _t("confirm_report", lang), _c("send_report", lang), _c("send_report", lang)
        rows += [{"label": _l("service", lang), "value": slots["service"]},
                 {"label": _l("correction", lang), "value": slots["what"][:400]}]
    else:
        text, send, title = _t("confirm_provider", lang), _c("send_match", lang), _c("send_match", lang)
        rows += [{"label": _l("service", lang), "value": slots["service"]},
                 {"label": _l("area", lang), "value": _sub_city_label(slots["sub_city"], lang)}]
        if slots.get("details"):
            rows.append({"label": _l("details", lang), "value": slots["details"][:400]})
        rows.append({"label": _l("phone", lang), "value": slots["contact"].get("phone")})
    return reply_fn(state, text, cards=[{"kind": "summary", "title": title, "rows": rows}], actions=[
        {"kind": "action", "label": send, "action": {"type": "confirm", "value": name}},
        {"kind": "action", "label": _c("cancel", lang), "action": {"type": "cancel_task"}},
    ])


def fill(state: dict, user, reply_fn, *, value) -> dict:
    """The person answered the question the task is waiting on (typed text, a form or a choice)."""
    task = state["task"]
    slot = task.get("awaiting")
    slots = task["slots"]
    if slot == "contact":
        data = value if isinstance(value, dict) else {"phone": str(value)}
        known = _contact_known(user) or {}
        phone = re.sub(r"[^\d+]", "", data.get("phone") or "")
        if not re.fullmatch(r"\+?\d{9,13}", phone):
            return _ask(state, reply_fn, "contact", _t("ask_phone", state["lang"]), widget=_form("contact", [
                *([] if user else [_field("name", state["lang"], value=data.get("name"))]),
                _field("phone", state["lang"], "tel", placeholder="09XXXXXXXX"),
            ], state["lang"]))
        if not user and not (data.get("name") or "").strip():
            return _ask(state, reply_fn, "contact", _t("ask_contact", state["lang"]), widget=_form("contact", [
                _field("name", state["lang"]), _field("phone", state["lang"], "tel", value=phone),
                _field("email", state["lang"], "email", required=False)], state["lang"]))
        slots["contact"] = {"name": (data.get("name") or known.get("name") or "").strip() or None,
                            "phone": phone, "email": (data.get("email") or known.get("email") or "").strip() or None}
    elif slot == "queue":
        from services.support_service import QUEUES

        text = value if isinstance(value, str) else ""
        if text in QUEUES:
            slots["queue"] = text
        else:  # typed instead of tapped: classify it, and keep it as the description too
            slots["queue"] = classify_queue(text, state) or "customer_support"
            if text and not slots.get("details") and _substantive(text):
                slots["details"] = text
    elif slot == "sub_city":
        slots["sub_city"] = value if isinstance(value, str) else (value or {}).get("sub_city")
    elif slot:
        text = value.get(slot, "") if isinstance(value, dict) else str(value or "")
        text = text.strip()
        if slot == "details" and task["name"] == "request_provider":
            slots["details"] = text
        elif text:
            slots[slot] = text
            if slot == "service":
                slots.pop("service_key", None)
    task["awaiting"] = None
    return _next(state, user, reply_fn)


# ---------------------------------------------------------------- actions


def _summary(state: dict, conversation_id: str | None) -> str:
    if not conversation_id:
        return ""
    from services.db import fetch_all

    rows = fetch_all(
        "select content from assistant_messages where conversation_id = %s and role = 'user' and payload is null "
        "order by id desc limit 6",
        (conversation_id,),
    )
    return " / ".join(r["content"] for r in rows[::-1] if "#" * 4 not in r["content"])[:600]


def execute(state: dict, user, reply_fn, *, conversation_id: str | None, ip: str | None) -> dict:
    from services import support_service

    task, lang = state["task"], state["lang"]
    slots, name = task["slots"], task["name"]
    try:
        if name == "handoff":
            contact = slots["contact"]
            details = slots["details"]
            subject = re.split(r"(?<=[.!?።])\s", details, maxsplit=1)[0][:90]
            ticket = support_service.create_ticket(
                subject=subject, body=details, queue=slots["queue"], priority=slots.get("priority"),
                source="assistant", category="complaint" if task.get("complaint") else None,
                user_id=user.id if user else None, name=contact.get("name"), phone=contact.get("phone"),
                email=contact.get("email"), conversation_id=conversation_id,
                service_key=(state.get("service") or {}).get("key"), service_title=(state.get("service") or {}).get("title"),
                context={"sub_city": state.get("sub_city"), "held": state.get("held") or [],
                         "answers": state.get("answers") or {}, "language": lang,
                         "service": (state.get("service") or {}).get("title"),
                         "summary": _summary(state, conversation_id)},
                ip=ip,
            )
            state["task"] = None
            state["ticket_id"] = ticket["id"]
            state["channel"] = "human"
            team = support_service.QUEUES[ticket["queue"]][1] if lang == "am" else ticket["queue_label"]
            return reply_fn(state, _t("sent_handoff", lang, ref=ticket["ref"], team=team,
                                      expected=support_service.expected_text(ticket["priority"])),
                            cards=[ticket_card(ticket, user)],
                            actions=[{"kind": "action", "label": _c("back", lang), "action": {"type": "channel", "value": "agent"}}])

        if name == "report_problem":
            from services import feedback_service

            key = slots.get("service_key") or ""
            source, _, ref = key.partition(":")
            target_type = {"org": "org_service", "mesob": "gov_service", "path": "document"}.get(source, "other")
            message = f"{slots['service']}: {slots['what']}" if target_type == "other" else slots["what"]
            feedback_service.create_flag(target_type, ref or None, message[:2000], user.id if user else None)
            state["task"] = None
            if not user:
                return reply_fn(state, _t("sent_report", lang))
            ticket = support_service.create_ticket(
                subject=f"Wrong information: {slots['service']}"[:120], body=slots["what"], queue="organizations",
                priority="normal", source="report", category="wrong_info", user_id=user.id,
                conversation_id=conversation_id, service_key=key or None, service_title=slots["service"],
                context={"language": lang, "service": slots["service"]}, ip=ip,
            )
            state["ticket_id"] = ticket["id"]
            return reply_fn(state, _t("sent_report_ticket", lang, ref=ticket["ref"]), cards=[ticket_card(ticket, user)])

        if name == "request_provider":
            key = slots.get("service_key") or ""
            source, _, ref = key.partition(":")
            contact = slots["contact"]
            if source == "mesob":
                from services import provider_service

                hire = provider_service.create_hire({
                    "service_id": ref, "client_name": contact.get("name") or user.fullname or user.email,
                    "client_phone": contact["phone"], "sub_city": slots["sub_city"], "details": slots.get("details") or None,
                }, user_id=user.id)
                state["task"] = None
                state["last_hire"] = hire["id"]
                return reply_fn(state, _t("sent_provider", lang), actions=[
                    {"kind": "link", "label": _c("my_hires", lang), "href": "/account/requests"}])
            # Services outside the MESOB catalog: the marketplace team matches by hand
            area = _sub_city_label(slots["sub_city"], "en")
            ticket = support_service.create_ticket(
                subject=f"Find a provider: {slots['service']}"[:120],
                body=f"Service: {slots['service']}\nSub-city: {area}\n{slots.get('details') or ''}".strip(),
                queue="marketplace", source="assistant", category="provider_match", user_id=user.id,
                name=contact.get("name"), phone=contact["phone"], conversation_id=conversation_id,
                service_key=key or None, service_title=slots["service"],
                context={"sub_city": slots["sub_city"], "language": lang, "service": slots["service"]}, ip=ip,
            )
            state["task"] = None
            state["ticket_id"] = ticket["id"]
            return reply_fn(state, _t("sent_provider", lang), cards=[ticket_card(ticket, user)])
    except Exception as exc:  # noqa: BLE001 - every failure is reported to the person, never swallowed
        from services.support_service import CONTACT

        log.exception("Agent task %s failed", name)
        message = str(exc) if exc.__class__.__name__ in ("SupportError", "MarketplaceError") else "something went wrong on our side"
        return reply_fn(state, _t("failed", lang, error=message, phone=CONTACT["phone"]), actions=[
            {"kind": "action", "label": _c("send", lang), "action": {"type": "confirm", "value": name}},
            {"kind": "action", "label": _c("cancel", lang), "action": {"type": "cancel_task"}},
        ])
    state["task"] = None
    return reply_fn(state, _t("cancelled", lang))


def ticket_card(ticket: dict, user) -> dict:
    from services.support_service import expected_text

    return {"kind": "ticket", "id": ticket["id"], "ref": ticket["ref"], "subject": ticket["subject"],
            "queue_label": ticket["queue_label"], "status": ticket["status"], "status_label": ticket["status_label"],
            "priority": ticket["priority"], "expected": expected_text(ticket["priority"]),
            "href": f"/account/support/{ticket['id']}" if user else None}


HIRE_STATUS = {"open": "Waiting for a match", "requested": "Waiting for the provider", "accepted": "Accepted",
               "in_progress": "In progress", "completed": "Completed", "declined": "Declined", "cancelled": "Cancelled"}


def _status(state: dict, user, reply_fn) -> dict:
    lang = state["lang"]
    if not user:
        return reply_fn(state, _t("status_sign_in", lang),
                        actions=[{"kind": "link", "label": _c("sign_in", lang), "href": "/login?returnTo=/chat"}])
    from services import provider_service, support_service
    from services.db import fetch_all

    items = []
    for tk in support_service.list_for_user(user.id)[:5]:
        items.append({"kind": "ticket", "title": f"{tk['ref']} · {tk['subject']}", "status_label": tk["status_label"],
                      "href": f"/account/support/{tk['id']}", "updated_at": tk["updated_at"].isoformat()})
    for h in provider_service.list_engagements(client_user_id=user.id).get("items", [])[:5]:
        who = f" · {h['provider_name']}" if h.get("provider_name") else ""
        items.append({"kind": "hire", "title": f"{h['title']}{who}", "status_label": HIRE_STATUS.get(h["status"], h["status"]),
                      "href": "/account/requests", "updated_at": h["updated_at"].isoformat() if h.get("updated_at") else None})
    for r in fetch_all("select id::text, goal, updated_at from roadmaps where user_id = %s order by updated_at desc limit 3", (user.id,)):
        items.append({"kind": "path", "title": r["goal"].replace("_", " ").capitalize(), "status_label": "Saved path",
                      "href": f"/roadmap/{r['id']}", "updated_at": r["updated_at"].isoformat()})
    if not items:
        return reply_fn(state, _t("status_none", lang))
    return reply_fn(state, _t("status", lang), cards=[{"kind": "status", "items": items}])


def switch_channel(state: dict, value: str, reply_fn) -> dict:
    from services import support_service

    lang = state["lang"]
    ticket = support_service.get(state["ticket_id"]) if state.get("ticket_id") else None
    if value == "human" and ticket and ticket["status"] not in ("resolved", "closed"):
        state["channel"] = "human"
        return reply_fn(state, _t("to_human", lang, team=ticket["queue_label"], ref=ticket["ref"]))
    state["channel"] = "agent"
    if ticket:
        return reply_fn(state, _t("back_to_agent", lang, ref=ticket["ref"]))
    return reply_fn(state, _t("cancelled", lang))


def offer_human_text(lang: str) -> str:
    return _t("offer_human", lang)


def staff_match_chip(lang: str) -> dict:
    return {"label": _c("staff_match", lang), "action": {"type": "task", "value": "request_provider"}}
