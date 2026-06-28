"""Rule-based slot extraction fallback when no LLM is available."""

from __future__ import annotations

import re

SERVICE_KEYWORDS: dict[str, list[str]] = {
    "passport": ["passport", "travel document", "ፓስፖርት"],
    "kebele_id": ["kebele", "resident id", "national id", "ከቤል"],
    "tin": ["tin", "tax id", "tax identification", "ቲን"],
    "trade_license": ["trade license", "business license", "trade licence", "ንግድ ፈቃድ"],
    "commercial_registration": [
        "commercial registration",
        "company registration",
        "motri",
    ],
    "fintech_license": ["fintech", "nbe permit", "payment service"],
}

SUB_CITY_KEYWORDS: dict[str, list[str]] = {
    "bole": ["bole", "ቦሌ"],
    "kirkos": ["kirkos", "kerkos", "ኪርኮስ"],
    "arada": ["arada", "piassa", "piazza", "አራዳ"],
    "yeka": ["yeka", "የካ"],
    "addis_ketema": ["addis ketema", "merkato", "አዲስ ከተማ"],
    "akaki": ["akaki", "kaliti", "አቃቂ"],
    "gulele": ["gulele", "ጉለሌ"],
    "kolfe": ["kolfe", "ኮልፌ"],
    "lideta": ["lideta", "ልደታ"],
    "nifas_silk": ["nifas silk", "lafto", "ንፋስ ስልክ"],
}

DOCUMENT_KEYWORDS: dict[str, list[str]] = {
    "kebele_id": ["kebele id", "kebele"],
    "passport": ["passport", "ፓስፖርት"],
    "tin": ["tin", "ቲን"],
    "notarized_lease": ["lease", "notarized"],
    "commercial_registration": ["commercial registration"],
    "trade_license": ["trade license", "ንግድ ፈቃድ"],
    "birth_certificate": ["birth certificate"],
}


def _detect_goal(text: str) -> str | None:
    lower = text.lower()
    for goal, keys in SERVICE_KEYWORDS.items():
        if any(k in lower for k in keys):
            return goal
    return None


def _detect_sub_city(text: str) -> str | None:
    lower = text.lower()
    for sc_id, keys in SUB_CITY_KEYWORDS.items():
        if any(k in lower for k in keys):
            return sc_id
    return None


def _detect_held(text: str) -> list[str]:
    lower = text.lower()
    if re.search(r"\b(nothing|none|don't have|do not have|no documents)\b", lower):
        return []
    held: list[str] = []
    for doc_id, keys in DOCUMENT_KEYWORDS.items():
        if any(k in lower for k in keys):
            held.append(doc_id)
    return held


def _detect_language(text: str) -> str:
    if re.search(r"[\u1200-\u137F]", text):
        return "am"
    return "en"


def _detect_intent(text: str) -> str:
    lower = text.lower()
    if re.search(
        r"(halfway|in the middle|already started|resume|partially|midway|በመንገድ|ጀምሬ)",
        lower,
    ):
        return "resume_progress"
    if re.search(
        r"(two compan|multiple compan|holding|subsidiary|parent company|ሁለት ኩባንያ|ኩባንያዎች)",
        lower,
    ):
        return "multi_entity"
    if re.search(
        r"(advice|recommend|what should|help me understand|ምክር|እንዴት)",
        lower,
    ):
        return "general_advice"
    return "new_roadmap"


def extract_slots_keyword(
    message: str,
    *,
    documents_held: list[str] | None = None,
    sub_city: str | None = None,
    goal: str | None = None,
) -> dict:
    held = list(documents_held or [])
    held.extend(_detect_held(message))
    held = list(dict.fromkeys(held))

    detected_goal = _detect_goal(message) or goal
    detected_sub = _detect_sub_city(message) or sub_city
    language = _detect_language(message)
    intent = _detect_intent(message)

    missing: list[str] = []
    if not detected_goal:
        missing.append("goal")
    if not detected_sub:
        missing.append("sub_city")

    needs_more = bool(missing) and intent != "general_advice"

    if language == "am":
        if needs_more:
            prompts = []
            if "goal" in missing:
                prompts.append("ምን ዓይነት ሰነድ ወይም ፈቃድ ይፈልጋሉ?")
            if "sub_city" in missing:
                prompts.append("በአዲስ አበባ የት ክፍለ ከተማ ይገኛሉ?")
            reply = " ".join(prompts)
        else:
            reply = "መረጃዎን ተረድቻለሁ። የእርስዎን መንገድ እያዘጋጀሁ ነው።"
    else:
        if intent == "general_advice" and missing:
            reply = (
                "I can share general compliance guidance. "
                "For a step-by-step roadmap, tell me your goal and sub-city."
            )
            needs_more = True
        elif needs_more:
            prompts = []
            if "goal" in missing:
                prompts.append("What document or license do you need?")
            if "sub_city" in missing:
                prompts.append("Which Addis Ababa sub-city are you in?")
            reply = " ".join(prompts)
        else:
            reply = "Got it — I'm putting together your compliance path."

    return {
        "goal": detected_goal,
        "sub_city": detected_sub,
        "documents_held": held,
        "needs_more_info": needs_more,
        "reply_message": reply,
        "intent": intent,
        "language": language,
        "progress_notes": message if intent == "resume_progress" else None,
        "entities": [],
    }
