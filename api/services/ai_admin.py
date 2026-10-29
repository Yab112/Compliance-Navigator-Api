"""LLM provider status and runtime switching for the admin dashboard."""

from __future__ import annotations

import time

import httpx

from config.config import settings
from services.db import Jsonb, fetch_one

PROVIDERS = ("ollama", "anthropic", "keyword")


def load_overrides() -> None:
    """Apply provider/model chosen in the dashboard on top of .env defaults."""
    try:
        row = fetch_one("select value from app_settings where key = 'ai'")
    except Exception:
        return
    if row:
        value = row["value"]
        settings.llm_provider = value.get("provider", settings.llm_provider)
        settings.ollama_model = value.get("ollama_model", settings.ollama_model)


def save_settings(provider: str, ollama_model: str | None, actor: str) -> dict:
    if provider not in PROVIDERS:
        raise ValueError(f"provider must be one of {PROVIDERS}")
    value = {"provider": provider, "ollama_model": ollama_model or settings.ollama_model}
    fetch_one(
        """
        insert into app_settings (key, value, updated_by) values ('ai', %s, %s)
        on conflict (key) do update set value = excluded.value,
          updated_by = excluded.updated_by, updated_at = now()
        returning key
        """,
        (Jsonb(value), actor),
    )
    settings.llm_provider = value["provider"]
    settings.ollama_model = value["ollama_model"]
    return value


def _ollama_models() -> tuple[bool, list[str]]:
    try:
        r = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3.0)
        r.raise_for_status()
        return True, [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return False, []


def status() -> dict:
    from services.rag_service import chunk_stats

    reachable, models = _ollama_models()
    try:
        rag = chunk_stats()
    except Exception as exc:
        rag = {"error": str(exc)}
    return {
        "provider": settings.llm_provider,
        "providers": list(PROVIDERS),
        "ollama": {
            "baseUrl": settings.ollama_base_url,
            "reachable": reachable,
            "model": settings.ollama_model,
            "models": models,
            "modelInstalled": any(
                m == settings.ollama_model or m.split(":")[0] == settings.ollama_model for m in models
            ),
        },
        "anthropic": {"configured": bool(settings.anthropic_api_key)},
        "embeddings": {"model": "sentence-transformers/all-MiniLM-L6-v2", "dimension": 384},
        "speechToText": {"engine": "faster-whisper", "model": settings.whisper_model_size},
        "knowledgeBase": rag,
    }


def test_prompt(message: str) -> dict:
    from services.chat_service import process_chat

    started = time.perf_counter()
    result = process_chat(message=message)
    result.pop("updated_history", None)
    return {
        "provider": settings.llm_provider,
        "latencyMs": int((time.perf_counter() - started) * 1000),
        "reply": result.get("reply"),
        "intent": result.get("intent"),
        "language": result.get("language"),
        "suggestedGoal": result.get("suggested_goal"),
        "suggestedSubCity": result.get("suggested_sub_city"),
        "catalogMatches": result.get("catalog_matches", []),
        "roadmapBuilt": bool(result.get("roadmap")),
    }
