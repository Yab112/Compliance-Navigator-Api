"""Speech-to-text via faster-whisper (Amharic + English)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from config.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        size = settings.whisper_model_size or "small"
        _model = WhisperModel(size, device="cpu", compute_type="int8")
    return _model


def transcribe_audio(content: bytes, filename: str = "audio.webm") -> dict:
    """
    Transcribe audio bytes. Returns { text, detected_language }.
    """
    suffix = Path(filename).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        model = _get_model()
        segments, info = model.transcribe(
            tmp_path,
            language=None,
            beam_size=5,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        lang = info.language or "unknown"
        return {"text": text, "detected_language": lang}
    except Exception as exc:
        logger.exception("Transcription failed")
        return {"text": "", "detected_language": "unknown", "error": str(exc)}
    finally:
        Path(tmp_path).unlink(missing_ok=True)
