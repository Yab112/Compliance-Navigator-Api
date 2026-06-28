"""Local embeddings for Supabase pgvector (384-dim MiniLM)."""

from __future__ import annotations

from functools import lru_cache

EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")


def embed_text(text: str) -> list[float]:
    model = _model()
    vectors = list(model.embed([text]))
    return vectors[0].tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _model()
    return [v.tolist() for v in model.embed(texts)]
