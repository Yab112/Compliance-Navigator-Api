"""The assistant agent's fixed parts: trigger patterns, tool definitions and texts."""

from __future__ import annotations

import re

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
