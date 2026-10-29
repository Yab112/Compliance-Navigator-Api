"""LLM provider abstraction: Ollama (default), Anthropic, keyword fallback."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config.config import settings
from services.keyword_chat import extract_slots_keyword

logger = logging.getLogger(__name__)

EXTRACT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {
            "type": "string",
            "enum": [
                "passport",
                "kebele_id",
                "tin",
                "trade_license",
                "commercial_registration",
                "fintech_license",
            ],
        },
        "sub_city": {
            "type": "string",
            "enum": [
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
            ],
        },
        "documents_held": {
            "type": "array",
            "items": {"type": "string"},
        },
        "needs_more_info": {"type": "boolean"},
        "reply_message": {"type": "string"},
        "intent": {
            "type": "string",
            "enum": [
                "new_roadmap",
                "resume_progress",
                "multi_entity",
                "general_advice",
            ],
        },
        "language": {"type": "string", "enum": ["en", "am"]},
        "progress_notes": {"type": "string"},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["PLC", "sole_prop"]},
                    "relationship": {"type": "string"},
                },
            },
        },
    },
    "required": ["needs_more_info", "reply_message", "intent", "language"],
}


def _ollama_available() -> bool:
    base = settings.ollama_base_url
    if not base:
        return False
    try:
        r = httpx.get(f"{base.rstrip('/')}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def _call_ollama(
    system: str,
    messages: list[dict],
) -> dict | None:
    base = (settings.ollama_base_url or "http://localhost:11434").rstrip("/")
    model = settings.ollama_model or "llama3.2"

    prompt = (
        f"{system}\n\n"
        "Respond with ONLY valid JSON matching this schema:\n"
        f"{json.dumps(EXTRACT_TOOL_SCHEMA)}\n\n"
        "Conversation:\n"
    )
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, list):
            content = json.dumps(content)
        prompt += f"{role}: {content}\n"

    try:
        r = httpx.post(
            f"{base}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                # A schema (not just "json") makes Ollama emit exactly our keys
                "format": EXTRACT_TOOL_SCHEMA,
                "options": {"num_predict": 400},
                # Reasoning models (qwen3, deepseek-r1) otherwise think for minutes
                "think": False,
            },
            timeout=120.0,
        )
        r.raise_for_status()
        raw = r.json().get("response", "{}")
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Ollama call failed: %s", exc)
        return None


def _call_anthropic(
    system: str,
    messages: list[dict],
    tool_def: dict,
) -> dict | None:
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        # Forced tool_choice is rejected on current models, steer with the prompt instead
        response = client.beta.messages.create(
            model="claude-opus-5-5",
            max_tokens=4096,
            system=system + "\n\nAlways answer by calling the extract_compliance_slots tool.",
            tools=[tool_def],
            tool_choice={"type": "auto"},
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=messages,
        )
        if response.stop_reason == "refusal":
            return None
        for block in response.content:
            if block.type == "tool_use" and block.name == "extract_compliance_slots":
                return block.input
        return None
    except Exception as exc:
        logger.warning("Anthropic call failed: %s", exc)
        return None


def extract_slots(
    message: str,
    *,
    system_prompt: str,
    conversation_history: list[dict] | None = None,
    documents_held: list[str] | None = None,
    sub_city: str | None = None,
    goal: str | None = None,
    tool_def: dict | None = None,
) -> tuple[dict, list[dict]]:
    """
    Returns (tool_input dict, updated_history).
    Falls back to keyword extraction when LLM unavailable.
    """
    history: list[dict] = list(conversation_history or [])
    history.append({"role": "user", "content": message})

    provider = (settings.llm_provider or "ollama").lower()
    tool_input: dict | None = None
    assistant_content: Any = None

    if provider == "anthropic" and settings.anthropic_api_key:
        tool_input = _call_anthropic(
            system_prompt, history, tool_def or {}
        )
        if tool_input:
            assistant_content = [
                {
                    "type": "tool_use",
                    "name": "extract_compliance_slots",
                    "input": tool_input,
                }
            ]

    if tool_input is None and provider in ("ollama", "anthropic"):
        if provider == "ollama" or _ollama_available():
            tool_input = _call_ollama(system_prompt, history)
            if tool_input:
                assistant_content = tool_input

    if tool_input is None and provider == "anthropic" and _ollama_available():
        tool_input = _call_ollama(system_prompt, history)
        if tool_input:
            assistant_content = tool_input

    if tool_input is None:
        tool_input = extract_slots_keyword(
            message,
            documents_held=documents_held,
            sub_city=sub_city,
            goal=goal,
        )
        assistant_content = tool_input

    updated_history = history + [
        {"role": "assistant", "content": assistant_content or tool_input}
    ]
    return tool_input, updated_history
