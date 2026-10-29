"""Local embeddings for pgvector (384-dim MiniLM)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

EMBEDDING_DIMENSION = 384
# fastembed defaults to /tmp, which is wiped on reboot and then fails half-downloaded
MODEL_CACHE = os.environ.get("FASTEMBED_CACHE_PATH", str(Path(__file__).resolve().parent.parent / ".cache" / "fastembed"))


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2", cache_dir=MODEL_CACHE)


def embed_text(text: str) -> list[float]:
    model = _model()
    vectors = list(model.embed([text]))
    return vectors[0].tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _model()
    return [v.tolist() for v in model.embed(texts)]
