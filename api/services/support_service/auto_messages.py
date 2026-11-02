"""Messages the desk writes for itself: the acknowledgement on every new request, the note when a request
moves to another team, and the suggested first reply for each team.

The acknowledgement and the move note are written as the platform (author_kind 'assistant'), so they never
count as the team's first response: reply-time targets still measure when a person answered.
"""

from __future__ import annotations

from services.support_service.common import SLA_HOURS, queue_label

# What each team does first, said in the suggested opening (English, Amharic)
TEAM_FIRST_STEP = {
    "customer_support": ("look at what you need and find the right answer or the right person for it",
                         "የሚፈልጉትን አይቼ ትክክለኛውን መልስ ወይም ትክክለኛውን ሰው አገኝልዎታለሁ"),
    "compliance": ("check the requirements and the offices involved, and confirm anything unclear with the office",
                   "መስፈርቶቹን እና የሚመለከታቸውን ቢሮዎች አጣርቼ ግልጽ ያልሆነውን ከቢሮው ጋር አረጋግጣለሁ"),
    "marketplace": ("review the hire, the payments and what the provider did, and talk to the provider if needed",
                    "ቅጥሩን፣ ክፍያዎቹን እና አገልግሎት ሰጪው የሰራውን አይቼ አስፈላጊ ከሆነ አገልግሎት ሰጪውን አነጋግራለሁ"),
    "organizations": ("check the organization's service data and its sources",
                      "የተቋሙን የአገልግሎት መረጃ እና ምንጮቹን አጣራለሁ"),
    "technical": ("look into your account and what happened on the website",
                  "መለያዎን እና በድረ ገጹ ላይ የሆነውን አጣራለሁ"),
}


def _expected(priority: str, lang: str) -> str:
    hours = SLA_HOURS.get(priority, 24)
    if lang == "am":
        return f"በ{hours} ሰዓት ውስጥ" if hours < 24 else f"በ{hours // 24} የሥራ ቀን ውስጥ"
    return f"within {hours} hours" if hours < 24 else f"within {hours // 24} working day{'s' if hours > 24 else ''}"


def _lang(ticket: dict) -> str:
    return "am" if ((ticket.get("context") or {}).get("language") == "am") else "en"


def _first_name(ticket: dict) -> str:
    return ((ticket.get("contact_name") or "").strip().split(" ") or [""])[0]


def acknowledgement(ticket: dict) -> str:
    team, ref, lang = queue_label(ticket["queue"]), ticket["ref"], _lang(ticket)
    name = _first_name(ticket)
    if lang == "am":
        return (f"ሰላም{(' ' + name) if name else ''}፣ ጥያቄዎ {ref} ደርሶናል። የ{team} ቡድን እያየው ነው፤ "
                f"የመጀመሪያ መልስ {_expected(ticket['priority'], lang)} ይጠብቁ። ተጨማሪ ዝርዝር ካለዎት እዚህ መጻፍ ይችላሉ።")
    return (f"Hello{(' ' + name) if name else ''}, we received your request {ref}. The {team} team has it and is "
            f"looking at it. You can expect a first answer {_expected(ticket['priority'], lang)}. "
            "If you have more details, add them here at any time.")


def moved(ticket: dict, new_queue: str) -> str:
    team = queue_label(new_queue)
    if _lang(ticket) == "am":
        return (f"ጥያቄዎ {ticket['ref']} እንደዚህ አይነት ጉዳይ ወደሚይዘው የ{team} ቡድን ተዛውሯል። "
                "እስካሁን የነገሩንን ሁሉ ማየት ይችላሉ፤ መድገም አያስፈልግዎትም።")
    return (f"Your request {ticket['ref']} has moved to the {team} team, who handle this kind of question. "
            "They can see everything you've told us so far, so you don't need to repeat it.")


def suggested_first_reply(ticket: dict, agent_name: str | None) -> str:
    lang, name = _lang(ticket), _first_name(ticket)
    team = queue_label(ticket["queue"])
    step_en, step_am = TEAM_FIRST_STEP.get(ticket["queue"], TEAM_FIRST_STEP["customer_support"])
    agent = (agent_name or "").strip() or ("ከድጋፍ ቡድኑ" if lang == "am" else "from the support team")
    if lang == "am":
        return (f"ሰላም{(' ' + name) if name else ''}፣ እኔ {agent} ነኝ ከ{team} ቡድን፤ ጥያቄዎን {ticket['ref']} እኔ እከታተላለሁ። "
                f"ዝርዝሩን ለመገምገም ትንሽ ጊዜ ይስጡኝ፤ {step_am}። "
                f"{_expected(ticket['priority'], lang)} እመለስልዎታለሁ። እስከዚያ ማንኛውም ተጨማሪ መረጃ ካለዎት እዚህ ይላኩ።")
    return (f"Hello{(' ' + name) if name else ''}, I'm {agent} from the {team} team, and I'll be handling your request "
            f"{ticket['ref']}. Please give me a little time to review the details: I'll {step_en}. "
            f"I'll get back to you {_expected(ticket['priority'], lang)}. In the meantime, send anything else "
            "that might help right here.")
