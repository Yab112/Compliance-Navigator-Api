"""Small helpers shared by the vetting modules."""

from __future__ import annotations

import logging

from services.db import fetch_one

log = logging.getLogger(__name__)


def _clean_text(value: str | None, limit: int) -> str | None:
    value = (value or "").strip()
    return value[:limit] or None


def _uuid_like(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _recompute(provider_id: str) -> None:
    from services import provider_service

    provider_service.recompute(provider_id)


def _notify_provider(provider_id: str, title: str, body: str | None) -> None:
    from services import notifications

    row = fetch_one("select user_id::text from providers where id = %s", (provider_id,))
    if not row or not row["user_id"]:
        return
    try:
        notifications.notify([row["user_id"]], kind="vetting", title=title[:140], body=body,
                             link="/me/provider?tab=vetting")
    except Exception:  # a failed notification never blocks the review
        log.exception("Vetting notification failed")
