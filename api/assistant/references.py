"""Follow-up questions about providers the assistant just showed.

After a list of providers, people say "what did Meron do", "the first one", "can I see her last
jobs". The assistant remembers who it showed (state["shown_providers"]) and who was last discussed
(state["focus_provider"]), resolves names, ordinals and pronouns to one of them, and answers from
the provider's public record. Replies use the provider's name, never a guessed pronoun.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

PRONOUN = re.compile(r"\b(her|him|his|hers|she|he|them|they|their|this (one|agent|broker|provider|person)|"
                     r"that (one|agent|broker|provider|person))\b|እሷ|እሱ|የሷ|የሱ|እሳቸው|የእሳቸው", re.I)
ORDINALS = [
    (re.compile(r"\b(first|1st|top)\b|የመጀመሪያው|አንደኛው", re.I), 0),
    (re.compile(r"\b(second|2nd)\b|ሁለተኛው", re.I), 1),
    (re.compile(r"\b(third|3rd)\b|ሶስተኛው|ሦስተኛው", re.I), 2),
    (re.compile(r"\b(last one|last provider|last agent)\b|የመጨረሻው", re.I), -1),
]
ASPECTS = [
    ("jobs", re.compile(r"\b(jobs?|work|worked|did|done|completed|closed|finished|history|experience|portfolio|"
                        r"track record|previous|past|before)\b|የሰራ|ስራዎ|የሰራቸው|ልምድ", re.I)),
    ("reviews", re.compile(r"\b(reviews?|ratings?|rated|feedback|stars?|comments?|trust(ed|worthy)?|reliable|"
                           r"recommend|good|honest|scam|say|says|said|think|opinion|clients|customers)\b|ግምገማ|አስተያየት|ታማኝ|ምን አሉ|ደንበኞች", re.I)),
    ("fees", re.compile(r"\b(price|prices|fee|fees|cost|costs|charge|charges|how much|commission|rate)\b|ዋጋ|ክፍያ|ስንት", re.I)),
    ("contact", re.compile(r"\b(phone|number|call|contact|reach|whatsapp|telegram)\b|ስልክ|ደውል|ላግኘ", re.I)),
    ("hire", re.compile(r"\b(hire|book|choose|pick|take|go with|want (her|him|this|that))\b|ቅጠር|ልቅጠር|ይቅጠሩ", re.I)),
]

TYPES = {
    "guday_geday": ("errand agent (Guday Geday)", "ጉዳይ ገዳይ"),
    "agency": ("agency", "ኤጀንሲ"),
}
T = {
    "overview": {
        "en": "{name} is a verified {type}{areas}. Trust score {score}/100{rating}, {jobs} job{s} completed on the platform{exp}.",
        "am": "{name} የተረጋገጠ {type} ነው{areas}። የእምነት ነጥብ {score}/100{rating}፣ በመድረኩ {jobs} ስራ ተጠናቋል{exp}።",
    },
    "jobs": {"en": "Recent jobs {name} completed through the platform:", "am": "{name} በመድረኩ በቅርቡ ያጠናቀቃቸው ስራዎች፦"},
    "no_jobs": {"en": "{name} has no completed jobs on the platform yet, so there is no track record to show. New providers are marked \"New\" until they have reviews.",
                "am": "{name} እስካሁን በመድረኩ ያጠናቀቀው ስራ የለም። አዳዲስ አገልግሎት ሰጪዎች ግምገማ እስኪያገኙ \"አዲስ\" ተብለው ይታያሉ።"},
    "reviews": {"en": "What clients who hired {name} said. Only people who actually hired a provider can review them.",
                "am": "{name}ን የቀጠሩ ደንበኞች ያሉት። ግምገማ መስጠት የሚችሉት በእርግጥ የቀጠሩ ብቻ ናቸው።"},
    "no_reviews": {"en": "{name} has no reviews yet. Only clients who hired a provider can leave one.",
                   "am": "{name} እስካሁን ግምገማ የለውም። ግምገማ መስጠት የሚችሉት የቀጠሩ ደንበኞች ብቻ ናቸው።"},
    "fees": {"en": "{name} charges {fee}.{notes}", "am": "{name} የሚያስከፍለው {fee}።{notes}"},
    "no_fees": {"en": "{name} has not published a fee. Ask when you send the request; the price is agreed before work starts.",
                "am": "{name} ክፍያ አላሳወቀም። ጥያቄ ሲልኩ ይጠይቁ፤ ዋጋው ስራ ከመጀመሩ በፊት ይስማማሉ።"},
    "contact": {"en": "To protect both sides, {name}'s phone number is shared once {name} accepts your request. Send a request from the profile and you'll get the number as soon as it's accepted.",
                "am": "ሁለቱንም ወገን ለመጠበቅ የ{name} ስልክ ቁጥር የሚታየው ጥያቄዎን ሲቀበል ነው። ከፕሮፋይሉ ጥያቄ ይላኩ፤ ሲቀበል ቁጥሩ ይደርስዎታል።"},
    "hire": {"en": "Good choice. Send {name} a request from the profile: say what you need and by when. {name} accepts or declines, and you can follow it under My hires.",
             "am": "ጥሩ ምርጫ። ከፕሮፋይሉ ለ{name} ጥያቄ ይላኩ፤ ምን እና መቼ እንደሚፈልጉ ይግለጹ። ይቀበላል ወይም አይቀበልም፤ በ\"የቀጠርኳቸው\" ስር ይከታተላሉ።"},
    "which": {"en": "Which provider do you mean?", "am": "የትኛውን አገልግሎት ሰጪ ማለትዎ ነው?"},
    "gone": {"en": "I can't find that provider any more. They may have paused their profile.", "am": "ያንን አገልግሎት ሰጪ ማግኘት አልቻልኩም።"},
}
CHIPS = {
    "jobs": {"en": "Completed jobs", "am": "የተጠናቀቁ ስራዎች"},
    "reviews": {"en": "Reviews", "am": "ግምገማዎች"},
    "fees": {"en": "Fees", "am": "ክፍያ"},
    "profile": {"en": "View full profile", "am": "ሙሉ ፕሮፋይል"},
    "hire": {"en": "Hire {first}", "am": "{first}ን ቅጠር"},
    "others": {"en": "See other providers", "am": "ሌሎች አገልግሎት ሰጪዎች"},
}


def _t(key: str, lang: str, **kw) -> str:
    return (T[key].get(lang) or T[key]["en"]).format(**kw)


def _chip(key: str, lang: str, **kw) -> str:
    return (CHIPS[key].get(lang) or CHIPS[key]["en"]).format(**kw)


def remember(state: dict, providers: list[dict]) -> None:
    """Called whenever a list of providers is shown."""
    state["shown_providers"] = [{"slug": p["slug"], "name": p["name"]} for p in providers if p.get("slug")]
    state["topic"] = "providers"
    if len(state["shown_providers"]) == 1:
        state["focus_provider"] = state["shown_providers"][0]["slug"]


# Words in company names that people also use for the service itself ("customs clearing")
GENERIC = {"clearing", "forwarding", "agency", "agent", "plc", "services", "service", "trading", "real", "estate",
           "broker", "brokers", "consult", "consultancy", "consulting", "the", "and", "group", "ethiopia", "addis"}


def _name_tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[^\wሀ-፿]+", (name or "").lower()) if len(t) >= 3 and t not in GENERIC]


def resolve(text: str, state: dict, prev_topic: str | None) -> tuple[str | None, list[dict]]:
    """(slug, candidates). A slug when one provider is clearly meant; candidates when several match."""
    shown = state.get("shown_providers") or []
    if not shown:
        return None, []
    words = set(re.split(r"[^\wሀ-፿]+", (text or "").lower()))
    by_name = [p for p in shown if words & set(_name_tokens(p["name"]))]
    if len(by_name) == 1:
        return by_name[0]["slug"], []
    if len(by_name) > 1:
        full = [p for p in by_name if all(t in words for t in _name_tokens(p["name"]))]
        return (full[0]["slug"], []) if len(full) == 1 else (None, by_name)
    for pattern, index in ORDINALS:
        if pattern.search(text) and (index < len(shown)):
            return shown[index]["slug"], []
    if PRONOUN.search(text) and prev_topic == "providers":
        if state.get("focus_provider"):
            return state["focus_provider"], []
        return None, shown
    return None, []


def aspect(text: str) -> str:
    if re.search(r"\b(tell me about|who is|more about)\b", text or "", re.I):
        return "overview"
    for name, pattern in ASPECTS:
        if pattern.search(text or ""):
            return name
    return "overview"


def _fee_text(p: dict, lang: str) -> str | None:
    lo, hi, unit = p.get("fee_from"), p.get("fee_to"), p.get("fee_unit")
    if lo is None:
        return None
    if unit == "percent":
        return f"{lo:g}%" + (f" to {hi:g}%" if hi and hi != lo else "") + (" commission" if lang == "en" else " ኮሚሽን")
    amount = f"{lo:,.0f}" + (f" to {hi:,.0f}" if hi and hi != lo else "")
    per = {"per_job": "per job", "per_hour": "per hour", "per_day": "per day"}.get(unit or "", "")
    return f"{amount} birr {per}".strip() if lang == "en" else f"{amount} ብር"


def answer(slug: str, kind: str, state: dict, reply_fn) -> dict:
    from services import provider_service

    lang = state["lang"]
    p = provider_service.public_profile(slug)
    if not p:
        return reply_fn(state, _t("gone", lang))
    state["focus_provider"] = p["slug"]
    state["topic"] = "providers"
    name = p["display_name"]
    first = name.split()[0]
    card = {"kind": "providers", "href": f"/providers/{p['slug']}", "items": [{
        "name": name, "slug": p["slug"], "headline": p.get("headline"), "type": p.get("provider_type"),
        "score": p.get("trust_score"), "rating": p.get("rating_avg"), "reviews": p.get("rating_count"),
        "photo": p.get("photo_url"), "verified": bool(p.get("id_verified")),
    }]}
    cards: list[dict] = []
    if kind == "jobs":
        jobs = provider_service.recent_jobs(p["id"])
        if jobs:
            text = _t("jobs", lang, name=name)
            cards.append({"kind": "checklist", "style": "list", "title": CHIPS["jobs"][lang] if lang in CHIPS["jobs"] else "Completed jobs",
                          "items": [{"label": " · ".join(x for x in (j["title"], (j["sub_city"] or "").replace("_", " ").title() or None) if x),
                                     "done": True,
                                     "detail": " · ".join(x for x in (
                                         j["completed_at"].strftime("%d %b %Y") if j["completed_at"] else None,
                                         f"rated {j['rating']}/5" if j["rating"] else None) if x) or None}
                                    for j in jobs]})
        else:
            text = _t("no_jobs", lang, name=name)
    elif kind == "reviews":
        reviews = (p.get("reviews") or {}).get("items") or []
        if reviews:
            text = _t("reviews", lang, name=name)
            cards.append({"kind": "checklist", "style": "list", "title": CHIPS["reviews"][lang],
                          "items": [{"label": f"{'★' * int(r['rating'])}{'☆' * (5 - int(r['rating']))} {r.get('comment') or ''}".strip(),
                                     "done": r["rating"] >= 4,
                                     "detail": " · ".join(x for x in (r.get("client_name"), r.get("job_title")) if x) or None}
                                    for r in reviews[:4]]})
        else:
            text = _t("no_reviews", lang, name=name)
    elif kind == "fees":
        fee = _fee_text(p, lang)
        notes = f" {p['pricing_notes']}" if p.get("pricing_notes") else ""
        text = _t("fees", lang, name=name, fee=fee, notes=notes) if fee else _t("no_fees", lang, name=name)
    elif kind == "contact":
        text = _t("contact", lang, name=first)
    elif kind == "hire":
        text = _t("hire", lang, name=first)
    else:
        type_label = TYPES.get(p.get("provider_type"), ("provider", "አገልግሎት ሰጪ"))[1 if lang == "am" else 0]
        areas = ", ".join(a.replace("_", " ").title() for a in (p.get("service_areas") or [])[:3])
        rating = (f", {p['rating_avg']:.1f} from {p['rating_count']} review{'s' if p['rating_count'] != 1 else ''}"
                  if p.get("rating_count") else "") if lang == "en" else (
                  f"፣ ከ{p['rating_count']} ግምገማ {p['rating_avg']:.1f}" if p.get("rating_count") else "")
        exp = (f", {p['experience_years']} years of experience" if lang == "en" else f"፣ የ{p['experience_years']} ዓመት ልምድ") \
            if p.get("experience_years") else ""
        text = _t("overview", lang, name=name, type=type_label,
                  areas=(f" working in {areas}" if lang == "en" else f"፤ በ{areas} ይሰራል") if areas else "",
                  score=p.get("trust_score") or 0, rating=rating, jobs=p.get("completed_count") or 0,
                  s="" if (p.get("completed_count") or 0) == 1 else "s", exp=exp)
        if p.get("headline"):
            text += f" {p['headline']}."
    chips = [{"label": _chip(k, lang), "action": {"type": "message", "value": f"{first} {k}" if lang == "en" else f"{first} {_chip(k, lang)}"}}
             for k in ("jobs", "reviews", "fees") if k != kind]
    if len(state.get("shown_providers") or []) > 1:
        chips.append({"label": _chip("others", lang), "action": {"type": "hire"}})
    return reply_fn(state, text, cards=[card, *cards], actions=[
        {"kind": "link", "label": _chip("hire", lang, first=first), "href": f"/providers/{p['slug']}#hire"},
        {"kind": "link", "label": _chip("profile", lang), "href": f"/providers/{p['slug']}"},
    ], quick_replies=chips)


def ask_which(candidates: list[dict], state: dict, reply_fn, kind: str) -> dict:
    lang = state["lang"]
    state["topic"] = "providers"
    return reply_fn(state, _t("which", lang), widget={
        "kind": "choice", "key": f"provider:{kind}",
        "options": [{"value": c["slug"], "label": c["name"]} for c in candidates],
    })
