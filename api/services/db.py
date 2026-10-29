"""Postgres access (self-hosted pgvector)."""

from __future__ import annotations

import atexit
import logging
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from config.config import settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"

__all__ = ["Jsonb", "connection", "execute", "fetch_all", "fetch_one", "run_migrations"]


@lru_cache(maxsize=1)
def _pool() -> ConnectionPool:
    pool = ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row, "autocommit": True},
        open=True,
    )
    atexit.register(pool.close)
    return pool


@contextmanager
def connection() -> Iterator[Any]:
    with _pool().connection() as conn:
        yield conn


def fetch_all(sql: str, params: dict | tuple | None = None) -> list[dict]:
    with connection() as conn:
        return list(conn.execute(sql, params).fetchall())


def fetch_one(sql: str, params: dict | tuple | None = None) -> dict | None:
    with connection() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: dict | tuple | None = None) -> int:
    with connection() as conn:
        return conn.execute(sql, params).rowcount


def run_migrations() -> list[str]:
    """Apply db/migrations/*.sql in name order; each file runs once."""
    applied: list[str] = []
    try:
        with connection() as conn:
            conn.execute(
                "create table if not exists schema_migrations ("
                " name text primary key, applied_at timestamptz not null default now())"
            )
            done = {r["name"] for r in conn.execute("select name from schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.name in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute(
                        "insert into schema_migrations (name) values (%s)", (path.name,)
                    )
                applied.append(path.name)
                logger.info("Applied migration %s", path.name)
    except Exception:
        logger.exception("Database migrations failed, is Postgres running?")
        raise
    return applied
