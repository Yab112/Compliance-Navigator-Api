"""Conversational compliance assistant, Ollama / Anthropic / keyword + RAG."""

from __future__ import annotations

from services.llm_service import EXTRACT_TOOL_SCHEMA, extract_slots
from services.rag_service import search_legal_chunks
from services.catalog_service import get_service, search_services, services_for_document
from services.roadmap_service import generate_roadmap

VALID_GOALS = [
    "passport",
    "kebele_id",
    "tin",
    "trade_license",
    "commercial_registration",
    "fintech_license",
]

VALID_SUB_CITIES = [
    "addis_ketema",
    "akaki",
    "arada",
    "bole",
    "gulele",
    "kirkos",
    "kolfe",
    "lideta",
    "nifas_silk",
    "yeka",
]

VALID_DOCUMENTS = [
    "kebele_id",
    "passport",
    "tin",
    "notarized_lease",
    "commercial_registration",
    "trade_license",
    "birth_certificate",
]

SYSTEM_PROMPT_BASE = """You are a helpful compliance guide for Ethiopian government services
in Addis Ababa. Users may write in English or Amharic (አማርኛ).

INTENTS:
- new_roadmap: user wants a step-by-step path for a goal
- resume_progress: user already started (e.g. "I was halfway through TIN")
- multi_entity: two or more linked companies / holding structure questions
- general_advice: general compliance questions without needing a full roadmap yet

Collect when building a roadmap:
1. GOAL: passport, kebele_id, tin, trade_license, commercial_registration, fintech_license
2. SUB-CITY: addis_ketema, akaki, arada, bole, gulele, kirkos, kolfe, lideta, nifas_silk, yeka
3. DOCUMENTS already held (empty list is fine)

Amharic aliases: ፓስፖርት→passport, ቦሌ→bole, ንግድ ፈቃድ→trade_license, ቲን→tin, ከቤል→kebele_id

Context:
- Compliance Navigator is an independent platform that connects the requirements of many
  organizations into one path. MESOB one-stop centers (mesobcenter.et) are a partner: where a
  step can be done at a MESOB center, mention it.
- The platform has a marketplace of verified providers: Guday Geday (ጉዳይ ገዳይ) errand agents,
  and agencies (customs clearing, legal and accounting, consultancy), all ID verified, scored and
  reviewed by real clients. We do not list property or car brokers (delala).
  Suggest the "Hire" page when the user wants someone to do it for them. Never recommend
  unverified intermediaries.

Rules:
- Reply in the SAME language the user used (en or am).
- For resume_progress: infer documents_held from what they say they completed.
- For multi_entity: explain holding/subsidiary basics in reply_message; still set goal if clear.
- For general_advice: answer helpfully; set needs_more_info true unless goal+sub_city known.
- Once goal AND sub_city are known and intent is new_roadmap or resume_progress, set needs_more_info false.
- Write plain sentences. Never use the long dash character (U+2014); use commas, periods or colons instead.
- Always return valid JSON per the tool schema.
"""

EXTRACT_SLOTS_TOOL = {
    "name": "extract_compliance_slots",
    "description": "Extract structured compliance information and reply to user.",
    "input_schema": EXTRACT_TOOL_SCHEMA,
}


def _build_rag_context(message: str) -> str:
    try:
        hits = search_legal_chunks(message, limit=4, threshold=0.5)
    except Exception:
        return ""
    if not hits:
        return ""
    lines = ["Relevant references (cite these, never invent fees or offices):"]
    for h in hits:
        content = (h.get("content") or "")[:400]
        body = h.get("issuing_body") or ""
        lines.append(f"- [{body}] {content}")
    return "\n".join(lines)


_STOPWORDS = {
    "i", "a", "an", "the", "to", "for", "of", "my", "me", "how", "do", "can", "what",
    "is", "in", "and", "need", "want", "get", "where", "please", "help", "with", "at",
}


def _catalog_matches(message: str, goal: str | None = None, limit: int = 3) -> list[dict]:
    """MESOB services the user is probably asking about (shown as cards in chat)."""
    # The service that fulfils the recognised goal is the most useful card
    services = services_for_document(goal)[:1] if goal else []
    try:
        hits = search_legal_chunks(message, limit=limit, threshold=0.35, service_id_prefix="mesob-")
        seen = {s["id"] for s in services}
        services += [
            s for s in (get_service(h["service_id"]) for h in hits if h["service_id"] not in seen) if s
        ]
    except Exception:
        pass
    if not services:
        terms = [t for t in message.lower().split() if t.strip("?.,!") not in _STOPWORDS]
        for size in range(min(len(terms), 3), 0, -1):
            services = search_services(q=" ".join(terms[:size]), limit=limit)["items"]
            if services:
                break
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "institution": s["institution"]["short_name"] or s["institution"]["name"],
            "feeText": s.get("fee_text"),
            "processingTimeText": s.get("processing_time_text"),
            "requiredDocuments": (s.get("required_documents") or [])[:6],
        }
        for s in services[:limit]
    ]


def process_chat(
    message: str,
    documents_held: list[str] | None = None,
    sub_city: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    conversation_history: list[dict] | None = None,
    goal: str | None = None,
) -> dict:
    rag_context = _build_rag_context(message)
    system = SYSTEM_PROMPT_BASE
    if rag_context:
        system += f"\n\n{rag_context}"

    tool_input, updated_history = extract_slots(
        message,
        system_prompt=system,
        conversation_history=conversation_history,
        documents_held=documents_held,
        sub_city=sub_city,
        goal=goal,
        tool_def=EXTRACT_SLOTS_TOOL,
    )

    extracted_goal: str | None = tool_input.get("goal")
    extracted_sub_city: str | None = tool_input.get("sub_city")
    extracted_docs: list[str] = tool_input.get("documents_held", [])
    needs_more_info: bool = tool_input.get("needs_more_info", True)
    reply: str = tool_input.get("reply_message", "How can I help you today?")
    intent: str = tool_input.get("intent", "new_roadmap")
    language: str = tool_input.get("language", "en")

    final_goal = extracted_goal or goal or None
    final_sub_city = extracted_sub_city or sub_city or None
    final_docs = list(dict.fromkeys((documents_held or []) + extracted_docs))
    final_industry = industry or sector or (
        "fintech" if final_goal == "fintech_license" else None
    )

    missing: list[str] = []
    if not final_goal:
        missing.append("goal")
    if not final_sub_city:
        missing.append("sub_city")

    roadmap: dict | None = None
    build_roadmap = (
        intent in ("new_roadmap", "resume_progress")
        and not missing
        and not needs_more_info
    )
    if build_roadmap and final_goal and final_sub_city:
        roadmap = generate_roadmap(
            goal=final_goal,
            sub_city=final_sub_city,
            documents_held=final_docs,
            industry=final_industry,
        )

    return {
        "catalog_matches": _catalog_matches(message, final_goal),
        "reply": reply,
        "needs_more_info": needs_more_info or bool(missing),
        "missing_slots": missing,
        "suggested_goal": final_goal,
        "suggested_sub_city": final_sub_city,
        "suggested_documents_held": final_docs,
        "intent": intent,
        "language": language,
        "roadmap": roadmap,
        "updated_history": updated_history,
    }
