"""Optional: let an LLM reword a grounded reply so it reads naturally. It may not add facts.

Only used when the AI provider is anthropic or ollama. The rewrite is rejected (and the
template kept) if it times out, changes the language, drops or invents any number, or is
much longer than the original.
"""

from __future__ import annotations

import logging
import re

import httpx

from config.config import settings

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 8.0
_NUM = re.compile(r"\d[\d,.]*")

PROMPT = (
    "Rewrite this message from a government-services assistant so it sounds natural and friendly. "
    "Keep the same language ({lang}). Keep every number, name and fact exactly; do not add any information. "
    "Do not use the long dash character. Reply with the rewritten message only.\n\nMessage:\n{text}"
)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in _NUM.findall(text)}


def _acceptable(original: str, rewritten: str) -> bool:
    if not rewritten or len(rewritten) > len(original) * 1.6 + 40:
        return False
    if _numbers(rewritten) != _numbers(original):
        return False
    ethiopic = lambda s: bool(re.search(r"[ሀ-፿]", s))  # noqa: E731
    return ethiopic(original) == ethiopic(rewritten)


def _call(prompt: str) -> str | None:
    provider = settings.llm_provider
    if provider == "anthropic" and settings.anthropic_api_key:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=TIMEOUT_SECONDS)
        msg = client.messages.create(model="claude-opus-5-5", max_tokens=400,
                                     messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    if provider == "ollama":
        r = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False, "think": False,
                  "options": {"num_predict": 220}},
            timeout=TIMEOUT_SECONDS,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip()
    return None


def maybe_rephrase(text: str, lang: str) -> str:
    if settings.llm_provider not in ("anthropic", "ollama") or not text:
        return text
    try:
        rewritten = _call(PROMPT.format(lang="Amharic" if lang == "am" else "English", text=text))
    except Exception:
        log.info("Rephrase skipped (provider unavailable or slow)")
        return text
    rewritten = re.sub(r"\s*\u2014\s*", ", ", rewritten or "")
    return rewritten if _acceptable(text, rewritten) else text
