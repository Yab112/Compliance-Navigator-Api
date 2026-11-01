"""Typed answers to what the last reply offered.

On a phone people type "new", "2" or "bole" instead of tapping, and over SMS or Telegram there
is nothing to tap. This turns such a reply into the action the matching button carries. It only
picks when exactly one option fits; anything else goes on to the normal understanding.
"""

from __future__ import annotations

import re

from assistant import nlu

ORDINALS = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5,
    "last": -1, "የመጀመሪያው": 1, "አንደኛው": 1, "ሁለተኛው": 2, "ሶስተኛው": 3, "ሦስተኛው": 3, "አራተኛው": 4, "አምስተኛው": 5,
    "የመጨረሻው": -1,
}
ORDINALS = {nlu.normalize(k): v for k, v in ORDINALS.items()}
FILLER = {"the", "one", "a", "an", "please", "option", "number", "no.", "it", "is", "its", "it's", "i", "want", "need",
          "choose", "pick", "take", "go", "with", "for", "me", "my", "እሱ", "ነው", "እፈልጋለሁ", "እባክዎ", "ቁጥር"}
YES = re.compile(r"^(yes|yeah|yep|y|ok|okay|sure|correct|right|አዎ|አዎን|እሺ|ትክክል)$")
NO = re.compile(r"^(no|nope|n|not really|አይ|አይደለም|የለም|የለኝም)$")
NONE_HELD = re.compile(r"^(none|nothing|no|i have none|i don ?t have any|ምንም|የለኝም|ምንም የለኝም)$")
ADDRESSED_LIMIT = 6  # a longer message is a new request, not an answer to the buttons


def _words(text: str) -> list[str]:
    return [w for w in nlu.normalize(text).split() if w not in FILLER]


def _label(option: dict) -> str:
    # "New trade license · Bole Sub-city Trade Office" is told apart by both halves
    return nlu.normalize(option["label"].replace("·", " "))


def _by_position(words: list[str], options: list[dict]) -> dict | None:
    if len(words) != 1:
        return None
    w = words[0].rstrip(".)")
    index = int(w) if w.isdigit() else ORDINALS.get(w)
    if index is None:
        return None
    if index == -1:
        index = len(options)
    return options[index - 1] if 1 <= index <= len(options) else None


def _fits(words: list[str], label: str) -> bool:
    label_words = label.split()
    if not words:
        return False
    text = " ".join(words)
    if text == label or (len(text) >= 3 and re.search(rf"(^| ){re.escape(text)}", label)):
        return True
    # every typed word is (the start of) a word of the label: "lost" -> "Lost or stolen", "renew" -> "Renewal"
    return all(any(lw == w or (len(w) >= 3 and lw.startswith(w)) for lw in label_words) for w in words)


def pick(text: str, offered: dict | None) -> dict | None:
    """The action of the one offered option the text points at, or None."""
    if not offered or not text:
        return None
    raw = nlu.normalize(text)
    words = _words(text)
    if not raw or len(raw.split()) > ADDRESSED_LIMIT:
        return None
    options, chips = offered.get("options") or [], offered.get("chips") or []

    if offered.get("widget") == "checklist" and NONE_HELD.match(raw):
        return {"type": "documents", "value": []}
    if options:
        values = {str(o["action"].get("value")) for o in options}
        if values == {"yes", "no"}:
            if YES.match(raw):
                return next(o["action"] for o in options if o["action"]["value"] == "yes")
            if NO.match(raw):
                return next(o["action"] for o in options if o["action"]["value"] == "no")
        if len(options) == 1 and YES.match(raw):  # "Did you mean ...?" "yes"
            return options[0]["action"]
        hit = _by_position(words, options)
        if hit:
            return hit["action"]
        fits = [o for o in options if _fits(words, _label(o))]
        if len(fits) == 1:
            return fits[0]["action"]
        exact = [o for o in fits if _label(o) == " ".join(words)]
        if len(exact) == 1:
            return exact[0]["action"]
        return None
    # Buttons under a message: a number, or the button's own words (not a longer request that contains them)
    hit = _by_position(words, chips)
    if hit:
        return hit["action"]
    exact = [c for c in chips if _label(c) == " ".join(words)]
    return exact[0]["action"] if len(exact) == 1 else None
