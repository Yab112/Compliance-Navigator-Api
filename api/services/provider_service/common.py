"""Marketplace constants, the marketplace error, the provider audit log and provider lookups."""

from __future__ import annotations

from services.db import fetch_one

PROVIDER_TYPES = ("guday_geday", "agency", "advisor")
ENTITY_TYPES = ("individual", "company")
SPECIALTIES = {
    "guday_geday": (), # Guday Geday list MESOB / organisation services instead
    "agency": ("customs_clearing", "travel_visa", "employment",
               "legal_accounting", "consultancy", "other"),
    # Tax and business advisors, people or firms. tax_agent, auditor and accountant need a verified
    # licence or qualification first (vetting LICENCE_FOR_SPECIALTY). Investment advice is not offered:
    # it needs a licence from the Ethiopian Capital Market Authority (Proclamation No. 1248/2021).
    "advisor": ("tax_agent", "accountant", "auditor", "business_setup"),
}
# Where the work happens. client_office: the advisor visits the client.
DELIVERY_MODES = ("client_office", "provider_office", "online")
SUB_CITIES = ("addis_ketema", "akaki", "arada", "bole", "gulele", "kirkos", "kolfe",
              "lideta", "nifas_silk", "yeka")
REGIONS = ("adama", "bahir_dar", "dire_dawa", "hawassa", "mekelle", "gondar", "jimma",
           "dessie", "harar", "bishoftu", "nationwide")
AREAS = SUB_CITIES + REGIONS
REG_PREFIX = {"guday_geday": "GG", "agency": "AG", "advisor": "AD"}

# Status transitions an admin may apply, and the resulting status
ADMIN_ACTIONS = {
    "approve": ({"pending", "rejected"}, "approved"),
    "reject": ({"pending"}, "rejected"),
    "suspend": ({"approved"}, "suspended"),
    "reinstate": ({"suspended"}, "approved"),
    "renew": ({"approved", "suspended"}, None), # extends the licence, keeps status
}

ENGAGEMENT_STATUSES = ("open", "requested", "accepted", "in_progress", "completed", "declined", "cancelled")
ACTIVE_ENGAGEMENT = ("requested", "accepted", "in_progress")

# What anyone may see: never contact details, national ID, TIN, licence documents or staff notes.
# Phone and email reach a client only through an accepted hire, so the marketplace can't be scraped or bypassed.
PUBLIC_COLUMNS = """
  p.id::text, p.slug, p.provider_type, p.entity_type, p.registration_no, p.display_name,
  p.display_name_am, p.legal_name, p.headline, p.bio, p.photo_url, p.website,
  p.sub_city, p.service_areas, p.specialties, p.service_ids, p.institution_ids, p.languages,
  p.experience_years, p.fee_from::float, p.fee_to::float, p.fee_unit, p.pricing_notes,
  p.highlights, p.external_license_type, p.external_license_status, p.accepting_work,
  p.completed_count, p.response_hours::float, p.trust_score, p.score_breakdown,
  p.rating_avg::float, p.rating_count, p.national_id_verified as id_verified, p.job_success, p.closed_jobs,
  (p.national_id_verified and p.id_verification_method = 'fayda_sandbox') as id_test,
  -- Badge only once staff have approved the profile (that is when the TIN and trade licence are checked)
  (p.tin is not null and (p.entity_type = 'individual' or p.trade_license_no is not null)
    and p.approved_at is not null) as registered_business,
  p.license_expires_at, p.approved_at, p.created_at, p.is_sample, p.delivery_modes, p.visit_fee::float
"""

PRIVATE_COLUMNS = PUBLIC_COLUMNS + """,
  p.phone, p.telegram_username, p.email, p.vat_registered, p.vat_number, p.user_id::text, p.status, p.national_id_last4, p.tin, p.trade_license_no, p.license_document_url,
  p.id_document_url, p.representative_title, p.address, p.external_license_no,
  p.external_license_verified_by, p.external_license_verified_at, p.reviewed_by,
  p.reviewed_at, p.review_note, p.updated_at, p.id_verification_method, p.verified_name,
  (p.payout_account_enc is not null) as payout_ready, p.payout_bank_code, p.payout_bank_name, p.payout_account_name, p.payout_account_last4,
  p.payout_set_at, p.ready_to_work, p.not_ready_reasons, p.ready_until, p.readiness_checked_at
"""

# The staff providers list shows only these: no national ID, TIN, documents, address or payout details
ADMIN_LIST_COLUMNS = """
  p.id::text, p.slug, p.provider_type, p.entity_type, p.registration_no, p.display_name, p.photo_url,
  p.phone, p.status, p.sub_city, p.service_areas, p.specialties, p.accepting_work,
  p.national_id_verified as id_verified, p.id_verification_method,
  (p.tin is not null and (p.entity_type = 'individual' or p.trade_license_no is not null)) as registered_business,
  (p.external_license_no is not null) as has_external_license, p.external_license_status,
  p.trust_score, p.rating_avg::float, p.rating_count, p.completed_count, p.license_expires_at,
  p.approved_at, p.created_at, p.is_sample, p.ready_to_work, p.not_ready_reasons
"""

# Dates follow the Addis Ababa calendar day, not the database's UTC day
TODAY = "(now() at time zone 'Africa/Addis_Ababa')::date"

PROFILE_FIELDS = (
    "display_name", "display_name_am", "headline", "bio", "phone", "telegram_username", "email", "website",
    "vat_registered", "vat_number",
    "sub_city", "address", "service_areas", "specialties", "service_ids", "languages",
    "experience_years", "fee_from", "fee_to", "fee_unit", "pricing_notes", "highlights",
    "accepting_work", "legal_name", "tin", "trade_license_no", "representative_title",
    "external_license_type", "external_license_no", "photo_url", "license_document_url",
    "delivery_modes", "visit_fee",
)
NULLABLE_FIELDS = {
    "display_name_am", "headline", "bio", "telegram_username", "email", "website", "sub_city", "address",
    "vat_number",
    "fee_from", "fee_to", "pricing_notes", "legal_name", "tin", "trade_license_no",
    "representative_title", "external_license_type", "external_license_no", "photo_url",
    "license_document_url", "visit_fee",
}


class MarketplaceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _log(conn, provider_id: str, action: str, actor: str | None, note: str | None = None) -> None:
    conn.execute(
        "insert into provider_events (provider_id, action, actor, note) values (%s, %s, %s, %s)",
        (provider_id, action, actor, note),
    )


def get(provider_id: str) -> dict | None:
    return fetch_one(f"select {PRIVATE_COLUMNS} from providers p where p.id::text = %s", (provider_id,))


def get_for_user(user_id: str) -> dict | None:
    return fetch_one(f"select {PRIVATE_COLUMNS} from providers p where p.user_id = %s", (user_id,))


# Listed: approved, listing in date, and ready to work (see readiness.py). ready_until makes a document
# that runs out today count at once, even before the daily run refreshes the flag.
READY = f"p.ready_to_work and (p.ready_until is null or p.ready_until >= {TODAY})"
LIVE = (f"p.status = 'approved' and (p.license_expires_at is null or p.license_expires_at >= {TODAY}) "
        f"and {READY}")
