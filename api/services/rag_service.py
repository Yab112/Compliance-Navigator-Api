"""RAG via Supabase pgvector — legal chunk ingest and similarity search."""

from __future__ import annotations

import re
from typing import Any

from services.embeddings import EMBEDDING_DIMENSION, embed_text, embed_texts
from services.supabase_client import get_supabase, is_supabase_configured

MATCH_THRESHOLD = 0.75
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunk = " ".join(words[start:end])
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
        start = max(0, end - overlap)
    return chunks


def ingest_text(
    text: str,
    *,
    document_id: str | None = None,
    service_id: str | None = None,
    proclamation_number: str | None = None,
    article_number: str | None = None,
    issuing_body: str | None = None,
    topic_tags: list[str] | None = None,
    sector_tags: list[str] | None = None,
    source_url: str | None = None,
    language: str = "en",
) -> dict:
    """Chunk, embed, and insert into Supabase legal_chunks."""
    if not is_supabase_configured():
        return {"status": "skipped", "reason": "Supabase not configured"}

    sb = get_supabase()
    parts = chunk_text(text)
    if not parts:
        return {"status": "empty", "chunks_inserted": 0}

    vectors = embed_texts(parts)
    rows = []
    for content, embedding in zip(parts, vectors):
        rows.append({
            "content": content,
            "embedding": embedding,
            "document_id": document_id,
            "service_id": service_id,
            "proclamation_number": proclamation_number,
            "article_number": article_number,
            "issuing_body": issuing_body,
            "topic_tags": topic_tags or [],
            "sector_tags": sector_tags or [],
            "source_url": source_url,
            "language": language,
        })

    sb.table("legal_chunks").insert(rows).execute()
    return {"status": "ok", "chunks_inserted": len(rows)}


def search_legal_chunks(
    query: str,
    *,
    document_id: str | None = None,
    service_id: str | None = None,
    limit: int = 5,
    threshold: float = MATCH_THRESHOLD,
) -> list[dict]:
    if not is_supabase_configured():
        return []

    sb = get_supabase()
    vector = embed_text(query)
    result = sb.rpc(
        "match_legal_chunks",
        {
            "query_embedding": vector,
            "match_threshold": threshold,
            "match_count": limit,
            "filter_document_id": document_id,
            "filter_service_id": service_id,
        },
    ).execute()

    return list(result.data or [])


def ground_step(
    step_title: str,
    sub_city: str,
    industry: str | None = None,
    document_id: str | None = None,
) -> dict | None:
    """
    Retrieve best legal chunk for a roadmap step.
    Returns None if similarity below threshold (caller should show 'cannot confirm').
    """
    query = f"{step_title} requirements Ethiopia {sub_city}"
    if industry:
        query += f" {industry}"
    hits = search_legal_chunks(
        query,
        document_id=document_id,
        limit=1,
        threshold=MATCH_THRESHOLD,
    )
    if not hits:
        return None
    hit = hits[0]
    return {
        "content": hit.get("content"),
        "similarity": hit.get("similarity"),
        "proclamation_number": hit.get("proclamation_number"),
        "issuing_body": hit.get("issuing_body"),
        "source_url": hit.get("source_url"),
        "legal_basis": _format_citation(hit),
    }


def _format_citation(hit: dict) -> str | None:
    proc = hit.get("proclamation_number")
    body = hit.get("issuing_body")
    if proc and body:
        return f"{body} — Proc. {proc}"
    if proc:
        return f"Proc. {proc}"
    if body:
        return body
    return None


def enrich_roadmap_steps(roadmap: dict) -> dict:
    """Attach legal_basis / sourceUrl from RAG when chunks match."""
    if not is_supabase_configured():
        return roadmap

    req = roadmap.get("request", {})
    sub_city = req.get("subCity", "")
    industry = req.get("industry")

    for step in roadmap.get("steps", []):
        doc_id = step.get("id")
        grounding = ground_step(
            step.get("title", ""),
            sub_city,
            industry,
            document_id=doc_id,
        )
        if grounding:
            if grounding.get("legal_basis") and not step.get("legalBasis"):
                step["legalBasis"] = grounding["legal_basis"]
            if grounding.get("source_url") and not step.get("sourceUrl"):
                step["sourceUrl"] = grounding["source_url"]
    return roadmap
