"""Actions the assistant can offer, carried out only after the person taps Confirm.

The AI (or a button) can only *propose* an action: it is stored in the conversation state and shown as a
card with Confirm and Cancel. Our own code carries it out when the person confirms, never the model.

  remind  - a reminder on their notification bell on a date ("remind me before my licence renewal")
  hire    - open a verified provider's page to hire them (payment is always on the hire page itself)
"""

from __future__ import annotations

import secrets
from datetime import date, timedelta

KINDS = ("remind", "hire")
LABELS = {
    "en": {"remind": "Set reminder", "hire": "Open hire page", "cancel": "Cancel", "when": "When", "what": "What",
           "provider": "Provider", "sign_in": "Sign in to set reminders"},
    "am": {"remind": "አስታዋሽ አስቀምጥ", "hire": "የቅጥር ገጹን ክፈት", "cancel": "ተወው", "when": "መቼ", "what": "ምን",
           "provider": "አገልግሎት ሰጪ", "sign_in": "አስታዋሽ ለማስቀመጥ ይግቡ"},
}
TEXT = {
    "en": {"confirm_remind": "Shall I set this reminder? It will appear under your bell on that day.",
           "confirm_hire": "Shall I open {name}'s page so you can hire them? You review the price and pay there, "
                           "never in the chat.",
           "sign_in": "Reminders are saved to your account. Sign in and ask me again.",
           "done_remind": "Done. I'll remind you on {when} under your bell. You can see or cancel it on your "
                          "account page.",
           "done_hire": "Here is {name}'s page. Check the price and reviews, then hire them there.",
           "cancelled": "Okay, I didn't do it.", "expired": "That offer has expired. Ask me again.",
           "bad": "I couldn't do that: {why}"},
    "am": {"confirm_remind": "ይህን አስታዋሽ ላስቀምጥ? በዚያ ቀን በደወሉ ስር ይታያል።",
           "confirm_hire": "{name}ን ለመቅጠር ገጻቸውን ልክፈትልዎ? ዋጋውን የሚያዩትና የሚከፍሉት እዚያ ነው፤ በውይይቱ ውስጥ አይደለም።",
           "sign_in": "አስታዋሾች በመለያዎ ይቀመጣሉ። ይግቡና እንደገና ይጠይቁኝ።",
           "done_remind": "ተቀምጧል። {when} በደወሉ ስር አስታውስዎታለሁ። በመለያ ገጽዎ ላይ ማየት ወይም መሰረዝ ይችላሉ።",
           "done_hire": "የ{name} ገጽ ይኸው። ዋጋውንና ግምገማዎቹን አይተው እዚያ ይቅጠሩ።",
           "cancelled": "እሺ፣ አላደረግሁትም።", "expired": "ያ ጥያቄ ጊዜው አልፏል። እንደገና ይጠይቁኝ።",
           "bad": "ያንን ማድረግ አልቻልኩም፦ {why}"},
}


class ActionError(Exception):
    pass


def _lang(state: dict) -> str:
    return "am" if state.get("lang") == "am" else "en"


def _parse_day(value: str | None) -> date:
    try:
        day = date.fromisoformat((value or "").strip())
    except ValueError as exc:
        raise ActionError("the date must look like 2026-12-01") from exc
    if day < date.today() or day > date.today() + timedelta(days=730):
        raise ActionError("pick a date between today and two years from now")
    return day


def propose(state: dict, user, kind: str, *, title: str | None = None, due_on: str | None = None,
            link: str | None = None, provider_slug: str | None = None) -> dict:
    """Check and store a proposal; returns what to show: {text, cards, actions} or raises ActionError."""
    lang = _lang(state)
    L, T = LABELS[lang], TEXT[lang]
    if kind not in KINDS:
        raise ActionError("unknown action")
    if kind == "remind":
        if not user:
            return {"text": T["sign_in"], "cards": [], "actions": [
                {"kind": "link", "label": L["sign_in"], "href": "/login?next=/chat"}], "needs_sign_in": True}
        day = _parse_day(due_on)
        title = (title or "").strip()
        if not 3 <= len(title) <= 200:
            raise ActionError("the reminder needs a short title")
        params = {"title": title, "due_on": day.isoformat(), "link": link if (link or "").startswith("/") else None}
        rows = [{"label": L["what"], "value": title}, {"label": L["when"], "value": day.strftime("%d %b %Y")}]
        text = T["confirm_remind"]
    else:
        from services import provider_service

        slug = (provider_slug or "").strip()
        provider = provider_service.public_profile(slug) if slug else None
        if not provider:
            raise ActionError("that provider isn't listed")
        name = provider.get("display_name") or provider.get("name") or slug
        params = {"slug": provider.get("slug") or slug, "name": name}
        rows = [{"label": L["provider"], "value": name}]
        text = T["confirm_hire"].format(name=name)
    proposal_id = secrets.token_urlsafe(8)
    state["proposal"] = {"id": proposal_id, "kind": kind, "params": params}
    return {"text": text, "cards": [{"kind": "summary", "title": L[kind], "rows": rows}], "actions": [
        {"kind": "action", "label": L[kind], "action": {"type": "confirm_proposal", "value": proposal_id}},
        {"kind": "action", "label": L["cancel"], "action": {"type": "cancel_proposal", "value": proposal_id}},
    ]}


def confirm(state: dict, user, proposal_id: str, conversation_id: str | None = None) -> dict:
    """Carry out the stored proposal the person just confirmed. Returns {text, cards, actions}."""
    lang = _lang(state)
    T, L = TEXT[lang], LABELS[lang]
    proposal = state.get("proposal") or {}
    if not proposal or proposal.get("id") != proposal_id:
        return {"text": T["expired"], "cards": [], "actions": []}
    state["proposal"] = None
    p = proposal["params"]
    if proposal["kind"] == "remind":
        if not user:
            return {"text": T["sign_in"], "cards": [], "actions": [
                {"kind": "link", "label": L["sign_in"], "href": "/login?next=/chat"}]}
        from services import reminders

        try:
            reminders.create(user.id, title=p["title"], due_on=date.fromisoformat(p["due_on"]), link=p.get("link"),
                             source="assistant", conversation_id=conversation_id)
        except reminders.ReminderError as exc:
            return {"text": T["bad"].format(why=str(exc)), "cards": [], "actions": []}
        when = date.fromisoformat(p["due_on"]).strftime("%d %b %Y")
        return {"text": T["done_remind"].format(when=when), "cards": [],
                "actions": [{"kind": "link", "label": "My reminders" if lang == "en" else "አስታዋሾቼ",
                             "href": "/account/reminders"}]}
    return {"text": T["done_hire"].format(name=p["name"]), "cards": [],
            "actions": [{"kind": "link", "label": L["hire"], "href": f"/providers/{p['slug']}"}]}


def cancel(state: dict) -> str:
    state["proposal"] = None
    return TEXT[_lang(state)]["cancelled"]
