"""Shared constants, errors and small helpers for organization onboarding."""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from services import catalog_service

log = logging.getLogger(__name__)


ORG_ACTIONS = {  # draft registrations aren't reviewable until the organization sends them
    "verify": ({"pending", "rejected"}, "verified"),
    "reject": ({"pending"}, "rejected"),
    "suspend": ({"verified"}, "suspended"),
    "reinstate": ({"suspended"}, "verified"),
}
NOTE_REQUIRED = {"reject", "suspend", "request_changes"}
# Changing these on a verified organization sends it back for review
IDENTITY_FIELDS = {"name", "org_type"}
# Who speaks for the organization: only an owner may change these (or the identity fields)
OWNER_ONLY_FIELDS = IDENTITY_FIELDS | {"representative_name", "representative_title", "official_email"}
ORG_EDITABLE = (
    "name", "name_am", "org_type", "sector", "description", "website", "phone", "email",
    "hq_address", "region", "sub_city", "representative_name", "representative_title", "official_email",
    "steward_name", "steward_role", "steward_phone", "steward_email", "onboarding_step",
)
SERVICE_FIELDS = (
    "name", "name_am", "summary", "who_can_apply", "delivery", "online_url", "fee_amount_min",
    "fee_amount_max", "fee_currency", "fee_notes", "payment_methods", "processing_time_text",
    "processing_minutes", "legal_basis", "forms", "common_rejection_reasons", "faq", "branch_ids",
    "outputs", "fee_schedule", "is_free", "where_to_pay", "no_documents_required",
    "appointment_required", "appointment_how", "appointment_url", "appointment_phone", "proxy_allowed",
    "proxy_notes", "online_parts", "languages", "accessibility_notes", "audience", "legal_reference_number",
    "legal_effective_date", "contact_name", "contact_phone", "contact_email", "output_validity_months",
    "renewal_service_id", "late_renewal_penalty", "branch_details",
)
JSON_FIELDS = {"forms", "faq", "outputs", "fee_schedule", "branch_details"}
REQUIREMENT_FIELDS = (
    "key", "kind", "name", "document_id", "issuing_service_id", "required", "notes", "original_or_copy",
    "copies", "notarized", "translated", "max_age_days", "photo_specs", "applies_to", "alternatives",
)
# An organization confirms each live service is still accurate at least this often

PUBLIC_ORG_COLUMNS = """
  o.id::text, o.slug, o.name, o.name_am, o.org_type, o.sector, o.description, o.logo_url,
  o.website, o.phone, o.email, o.hq_address, o.region, o.sub_city, o.catalog_institution_id,
  o.status, o.created_at
"""
MEMBER_ORG_COLUMNS = PUBLIC_ORG_COLUMNS + """,
  o.representative_name, o.representative_title, o.official_email,
  (o.authorization_letter_key is not null) as has_authorization_letter,
  o.verification_note, o.reviewed_at, o.updated_at, o.onboarding_step, o.submitted_at,
  o.steward_name, o.steward_role, o.steward_phone, o.steward_email, o.data_commitment_at
"""
ADMIN_ORG_COLUMNS = MEMBER_ORG_COLUMNS + """,
  o.authorization_letter_key, o.reviewed_by,
  (select email from users u where u.id = o.created_by) as created_by_email
"""


class OrgError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------- helpers


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:60] or "org"


def _unique_slug(conn, table: str, base: str, scope_sql: str = "", scope_params: tuple = ()) -> str:
    slug, n = base, 2
    while conn.execute(
        f"select 1 from {table} where slug = %s {scope_sql}", (slug, *scope_params)
    ).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _plain(value: Any) -> Any:
    """JSON-safe copy of DB values (Decimal, datetime, UUID)."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is not None and type(value).__name__ == "UUID":
        return str(value)
    return value


def _log(conn, action: str, *, org_id: str | None, service_id: str | None = None,
         actor: str | None = None, note: str | None = None) -> None:
    conn.execute(
        "insert into org_events (org_id, service_id, action, actor, note) values (%s, %s, %s, %s, %s)",
        (org_id, service_id, action, actor, note),
    )


def _match_catalog_institution(name: str) -> str | None:
    wanted = name.strip().lower()
    try:
        for inst in catalog_service.list_institutions():
            if wanted in {(inst.get("name") or "").lower(), (inst.get("short_name") or "").lower()}:
                return inst["id"]
    except Exception:
        log.exception("Catalog lookup failed")
    return None
