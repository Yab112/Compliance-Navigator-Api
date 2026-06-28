"""Supabase client — Postgres + pgvector + optional Storage."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from config.config import settings

_client: Any = None


def is_supabase_configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_role_key)


@lru_cache(maxsize=1)
def get_supabase():
    global _client
    if not is_supabase_configured():
        return None
    if _client is None:
        from supabase import create_client

        _client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
    return _client


def reset_client() -> None:
    global _client
    _client = None
    get_supabase.cache_clear()
