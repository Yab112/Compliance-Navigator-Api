"""
Our legal documents and who agreed to which version.

The text of each document lives in the web app (web/src/content/legal/*.ts). This registry holds the
version and effective date that are currently in force, and which ones a person must accept:
  everyone       Terms of Service, Privacy Policy, Marketplace Rules (the Refund and Dispute Policy is
                 part of the Terms, so it has no separate tick box)
  providers      the Guday Geday Provider Agreement as well

When a document changes in a way people must agree to again, bump its version here AND in the matching
web content file (tests/test_legal.py checks they agree). Everyone is then asked to accept the new
version the next time they open the site. Agreement rows are never updated or deleted. Providers who
have not accepted the current version are hidden from clients until they do: the API checks everyone
on startup (provider_service.refresh_readiness_all), so a new version takes effect with the release.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException

from services.db import connection, fetch_all, fetch_one

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LegalDocument:
    key: str
    title: str
    title_am: str
    version: str
    effective: str  # ISO date the version took effect
    path: str  # page on the public site

    def public(self) -> dict:
        return {"key": self.key, "title": self.title, "titleAm": self.title_am, "version": self.version,
                "effective": self.effective, "path": self.path}


DOCUMENTS: dict[str, LegalDocument] = {
    d.key: d
    for d in (
        LegalDocument("terms", "Terms of Service", "የአገልግሎት ውል", "1.0", "2026-10-29", "/legal/terms"),
        LegalDocument("privacy", "Privacy Policy", "የግላዊነት ፖሊሲ", "1.0", "2026-10-29", "/legal/privacy"),
        LegalDocument("marketplace_rules", "Marketplace Rules and Off-platform Payment Policy",
                      "የገበያ ደንቦች እና ከመድረኩ ውጭ ክፍያ ፖሊሲ", "1.0", "2026-10-29", "/legal/marketplace-rules"),
        LegalDocument("provider_agreement", "Guday Geday Provider Agreement", "የጉዳይ ገዳይ አገልግሎት ሰጪ ስምምነት",
                      "1.0", "2026-10-29", "/legal/provider-agreement"),
        LegalDocument("refund_policy", "Refund and Dispute Policy", "የገንዘብ ተመላሽ እና የክርክር ፖሊሲ",
                      "1.0", "2026-10-29", "/legal/refunds"),
    )
}

# Ticked at sign-up by everyone
CLIENT_REQUIRED: tuple[str, ...] = ("terms", "privacy", "marketplace_rules")
# Also required from anyone who offers services (Guday Geday agents and agencies)
PROVIDER_REQUIRED: tuple[str, ...] = ("provider_agreement",)


class LegalError(HTTPException):
    """A 400 the web app shows as is. It is an HTTPException so routes can let it bubble up."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(status_code=status_code, detail=detail)


def _names(keys) -> str:
    titles = [DOCUMENTS[k].title for k in keys]
    return titles[0] if len(titles) == 1 else ", ".join(titles[:-1]) + " and " + titles[-1]


def current_versions(keys=None) -> dict[str, str]:
    return {k: DOCUMENTS[k].version for k in (keys or DOCUMENTS)}


def client_acceptance() -> dict[str, str]:
    """What the sign-up form sends when every box is ticked (handy for tests and scripts)."""
    return current_versions(CLIENT_REQUIRED)


def validate_acceptance(accept: dict[str, str] | None, required=CLIENT_REQUIRED) -> dict[str, str]:
    """Checks the person accepted the current version of every required document.
    Extra documents may be accepted too, but only known ones at their current version."""
    accept = {k: (v or "").strip() for k, v in (accept or {}).items()}
    unknown = [k for k in accept if k not in DOCUMENTS]
    if unknown:
        raise LegalError(f"Unknown document: {', '.join(sorted(unknown))}")
    missing = [k for k in required if not accept.get(k)]
    if missing:
        raise LegalError(f"Please read and accept the {_names(missing)} to continue.")
    stale = [k for k, v in accept.items() if v != DOCUMENTS[k].version]
    if stale:
        raise LegalError(
            f"The {_names(stale)} changed since you opened this page. Reload it and accept the current version."
        )
    return accept


def record_consents(conn, user_id: str, accepted: dict[str, str], ip: str | None, user_agent: str | None) -> None:
    """Inserts agreement rows on an open connection, so it can share the caller's transaction."""
    for document, version in accepted.items():
        conn.execute(
            """
            insert into user_consents (user_id, document, version, ip, user_agent)
            values (%s, %s, %s, %s, %s)
            on conflict (user_id, document, version) do nothing
            """,
            (user_id, document, version, ip, (user_agent or "")[:300] or None),
        )


def accept(user_id: str, accept_: dict[str, str] | None, ip: str | None, user_agent: str | None) -> None:
    """A signed-in person accepts one or more documents (updated terms, or the provider agreement)."""
    accepted = validate_acceptance(accept_, required=())
    if not accepted:
        raise LegalError("Nothing to accept.")
    with connection() as conn, conn.transaction():
        record_consents(conn, user_id, accepted, ip, user_agent)
    log.info("user %s accepted %s", user_id, accepted)
    # A provider who was hidden for an out-of-date agreement is listed again at once
    provider = fetch_one("select id::text from providers where user_id = %s", (user_id,))
    if provider:
        from services import provider_service

        provider_service.refresh_readiness(provider["id"])


def _is_provider(user_id: str) -> bool:
    return fetch_one("select exists (select 1 from providers where user_id = %s) as yes", (user_id,))["yes"]


def required_for(user_id: str) -> tuple[str, ...]:
    return CLIENT_REQUIRED + (PROVIDER_REQUIRED if _is_provider(user_id) else ())


def _accepted_current(user_id: str, keys) -> dict[str, dict]:
    rows = fetch_all(
        """
        select document, version, accepted_at from user_consents
        where user_id = %s and document = any(%s)
        """,
        (user_id, list(keys)),
    )
    return {r["document"]: r for r in rows if r["version"] == DOCUMENTS[r["document"]].version}


def missing(user_id: str, keys) -> list[str]:
    done = _accepted_current(user_id, keys)
    return [k for k in keys if k not in done]


def require_accepted(user_id: str, keys) -> None:
    """Call from a route before an action that needs agreement, e.g. joining as a provider:
    `legal.require_accepted(user.id, ["provider_agreement"])`. Raises a 400 naming what is missing."""
    todo = missing(user_id, list(keys))
    if todo:
        raise LegalError(f"Please read and accept the {_names(todo)} first.")


def status(user_id: str) -> dict:
    keys = required_for(user_id)
    done = _accepted_current(user_id, keys)
    documents = [
        {**DOCUMENTS[k].public(), "accepted": k in done, "acceptedAt": done[k]["accepted_at"] if k in done else None}
        for k in keys
    ]
    pending = [d["key"] for d in documents if not d["accepted"]]
    return {"documents": documents, "pending": pending, "upToDate": not pending}


def list_consents(user_id: str, limit: int = 20, offset: int = 0) -> dict:
    total = fetch_one("select count(*) as n from user_consents where user_id = %s", (user_id,))["n"]
    rows = fetch_all(
        """
        select document, version, accepted_at from user_consents where user_id = %s
        order by accepted_at desc, id desc limit %s offset %s
        """,
        (user_id, limit, offset),
    )
    items = []
    for r in rows:
        doc = DOCUMENTS.get(r["document"])
        items.append({
            "document": r["document"],
            "title": doc.title if doc else r["document"],
            "titleAm": doc.title_am if doc else None,
            "version": r["version"],
            "current": bool(doc and doc.version == r["version"]),
            "path": doc.path if doc else None,
            "acceptedAt": r["accepted_at"],
        })
    return {"items": items, "total": total}
