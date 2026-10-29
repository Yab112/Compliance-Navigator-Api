"""RAG via Postgres pgvector, legal chunk ingest and similarity search."""

from __future__ import annotations

import re
from typing import Any

from services.embeddings import EMBEDDING_DIMENSION, embed_text, embed_texts
from services.db import connection, execute, fetch_all, fetch_one

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
    """Chunk, embed, and insert into legal_chunks."""
    parts = chunk_text(text)
    if not parts:
        return {"status": "empty", "chunks_inserted": 0}

    vectors = embed_texts(parts)
    rows = [
        (
            content, _vector_literal(embedding), document_id, service_id,
            proclamation_number, article_number, issuing_body,
            topic_tags or [], sector_tags or [], source_url, language,
        )
        for content, embedding in zip(parts, vectors)
    ]
    with connection() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            insert into legal_chunks (content, embedding, document_id, service_id,
              proclamation_number, article_number, issuing_body, topic_tags,
              sector_tags, source_url, language)
            values (%s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            rows,
        )
    return {"status": "ok", "chunks_inserted": len(rows)}


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


def delete_chunks(*, service_id: str | None = None, service_id_prefix: str | None = None) -> int:
    """Remove previously ingested chunks for a source before re-ingesting it."""
    if service_id:
        return execute("delete from legal_chunks where service_id = %s", (service_id,))
    if service_id_prefix:
        return execute(
            "delete from legal_chunks where service_id like %s", (f"{service_id_prefix}%",)
        )
    raise ValueError("delete_chunks needs service_id or service_id_prefix")


def chunk_stats() -> dict:
    row = fetch_one(
        """
        select count(*) as total,
               count(*) filter (where service_id like 'mesob-%') as mesob,
               count(distinct coalesce(issuing_body, '')) as sources,
               max(created_at) as last_ingested_at
        from legal_chunks
        """
    )
    return dict(row)


def search_legal_chunks(
    query: str,
    *,
    document_id: str | None = None,
    service_id: str | None = None,
    limit: int = 5,
    threshold: float = MATCH_THRESHOLD,
    service_id_prefix: str | None = None,
) -> list[dict]:
    vector = _vector_literal(embed_text(query))
    rows = fetch_all(
        """
        select id::text, content, service_id, document_id, proclamation_number,
               article_number, issuing_body, source_url,
               1 - (embedding <=> %(v)s::vector) as similarity
        from legal_chunks
        where embedding is not null
          and (%(doc)s::text is null or document_id = %(doc)s)
          and (%(svc)s::text is null or service_id = %(svc)s)
          and (%(prefix)s::text is null or service_id like %(prefix)s || '%%')
          and 1 - (embedding <=> %(v)s::vector) > %(threshold)s
        order by embedding <=> %(v)s::vector
        limit %(limit)s
        """,
        {"v": vector, "doc": document_id, "svc": service_id, "prefix": service_id_prefix,
         "threshold": threshold, "limit": limit},
    )
    return [{**r, "similarity": float(r["similarity"])} for r in rows]


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
        return f"{body}, Proc. {proc}"
    if proc:
        return f"Proc. {proc}"
    if body:
        return body
    return None


def enrich_roadmap_steps(roadmap: dict) -> dict:
    """Attach legal_basis / sourceUrl from RAG when chunks match."""
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
