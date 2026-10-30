"""Ready to work: whether a provider may be listed and take new work."""

from __future__ import annotations

import logging
from datetime import date

from psycopg.types.json import Jsonb

from services import vetting
from services.db import execute, fetch_all

from .common import get

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- ready to work
#
# A provider is listed, offered to staff for assigning, requestable by clients, and may accept or start
# new work only while ALL of these hold (product decision, 2026-10-29):
#   1. listing  approved by staff and the listing (licence) date not passed
#   2. vetting  every required item in vetting.checklist() verified and in date, all the time
#   3. legal    the current version of the Terms, Privacy Policy, Marketplace Rules and Provider Agreement
#   4. profile  every field the join form asks for (PROFILE_REQUIRED below)
# The answer is stored on the provider (ready_to_work, not_ready_reasons, ready_until) so list queries
# stay simple, and refreshed whenever one of the inputs changes: recompute() (documents, references,
# guarantor, profile edits, listing actions), accepting a legal document, the daily run, a vetting
# setting change, and for everyone on startup (a new legal version ships with a new release).

# What a complete profile has. Joining already asks for most of it; About became required with this rule.
BIO_MIN = 40
PROFILE_REQUIRED = {
    "display_name": "Name",
    "phone": "Mobile phone",
    "telegram_username": "Telegram username",
    "service_areas": "Areas you work in",
    "work": "Services (Guday Geday) or specialties (agencies)",
    "bio": f"About you (at least {BIO_MIN} characters)",
    # Companies only
    "legal_name": "Registered legal name",
    "tin": "TIN",
    "trade_license_no": "Trade licence number",
}


def profile_gaps(provider: dict) -> list[str]:
    """Keys of PROFILE_REQUIRED this profile is missing."""
    gaps = [k for k in ("display_name", "phone", "telegram_username", "service_areas") if not provider.get(k)]
    work = provider.get("service_ids") if provider["provider_type"] == "guday_geday" else provider.get("specialties")
    if not work:
        gaps.append("work")
    if len((provider.get("bio") or "").strip()) < BIO_MIN:
        gaps.append("bio")
    if provider["entity_type"] == "company":
        gaps += [k for k in ("legal_name", "tin", "trade_license_no") if not provider.get(k)]
    return gaps


def _listing_reason(provider: dict) -> dict | None:
    status = provider["status"]
    expires = provider.get("license_expires_at")
    if status == "pending":
        return {"key": "listing", "fix": "listing", "label": "Staff have not approved your listing yet"}
    if status == "rejected":
        return {"key": "listing", "fix": "listing",
                "label": "Your application was not accepted" + (f": {provider['review_note']}" if provider.get("review_note") else "")}
    if status == "suspended":
        return {"key": "listing", "fix": "listing",
                "label": "Your listing is paused" + (f": {provider['review_note']}" if provider.get("review_note") else "")}
    if expires and expires < date.today():
        return {"key": "listing", "fix": "listing", "label": f"Your listing expired on {expires:%d %b %Y}. Staff must renew it."}
    return None


def readiness(provider: dict) -> dict:
    """{ready, reasons: [{key, label, fix}], until}. fix tells the page where to send the person:
    listing (wait for or ask staff), vetting, profile, agreement."""
    from services import legal

    reasons: list[dict] = []
    listing = _listing_reason(provider)
    if listing:
        reasons.append(listing)
    words = {"missing": "missing", "pending": "waiting for staff to check", "rejected": "not accepted",
             "expired": "expired", "below_minimum": "below the minimum level"}
    check = vetting.checklist(provider)
    until = provider.get("license_expires_at") if provider["status"] == "approved" else None
    for item in check["items"]:
        if not item["required"]:
            continue
        if item["status"] in ("verified", "expiring"):
            valid = (item.get("current") or {}).get("valid_until")
            if valid and (until is None or valid < until):
                until = valid
            for d in item.get("documents") or []:
                valid = (d.get("current") or {}).get("valid_until")
                if d["required"] and valid and (until is None or valid < until):
                    until = valid
            continue
        reasons.append({"key": f"vetting:{item['key']}", "fix": "vetting",
                        "label": f"{item['label']}: {words.get(item['status'], item['status'])}"})
    for key in profile_gaps(provider):
        reasons.append({"key": f"profile:{key}", "fix": "profile", "label": f"Profile: {PROFILE_REQUIRED[key]} missing"})
    if provider.get("user_id"):
        todo = legal.missing(provider["user_id"], legal.CLIENT_REQUIRED + legal.PROVIDER_REQUIRED)
    else:
        todo = list(legal.CLIENT_REQUIRED + legal.PROVIDER_REQUIRED)
    for key in todo:
        doc = legal.DOCUMENTS[key]
        reasons.append({"key": f"agreement:{key}", "fix": "agreement",
                        "label": f"Accept the current {doc.title} (version {doc.version})"})
    return {"ready": not reasons, "reasons": reasons, "until": until}


def refresh_readiness(provider_id: str) -> dict | None:
    """Work out readiness again and store it. Returns the readiness, or None for an unknown provider."""
    provider = get(provider_id)
    if not provider:
        return None
    r = readiness(provider)
    execute(
        "update providers set ready_to_work = %s, not_ready_reasons = %s, ready_until = %s, "
        "readiness_checked_at = now() where id = %s",
        (r["ready"], Jsonb(r["reasons"]), r["until"], provider_id),
    )
    if provider.get("ready_to_work") != r["ready"]:
        log.info("Provider %s is %s", provider_id, "ready to work" if r["ready"] else "no longer ready to work")
    return r


def refresh_readiness_all(only: list[str] | None = None) -> int:
    """Every provider (or the listed ones). Used on startup, daily, and when a vetting setting changes."""
    rows = fetch_all(
        "select id::text from providers where (%s::uuid[] is null or id = any(%s::uuid[]))", (only, only),
    )
    for r in rows:
        try:
            refresh_readiness(r["id"])
        except Exception:  # one bad row never stops the others
            log.exception("Readiness check failed for provider %s", r["id"])
    return len(rows)


def not_ready_message(provider: dict) -> str:
    reasons = provider.get("not_ready_reasons") or []
    return "; ".join(r["label"] for r in reasons[:6]) or "not ready to work"
