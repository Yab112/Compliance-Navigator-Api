"""Vetting: who may be listed as a Guday Geday or agency, and the proof staff check before they do.

Clients let a Guday Geday handle their papers, money and sometimes their ID, so a listing needs
more than a sign-up. The requirements depend on who the provider is:

  Individual (Guday Geday, or a one-person agency)
    - national ID verified with Fayda (a staff-checked ID copy when Fayda is switched off)
    - police clearance certificate (የወንጀል ሪከርድ ማስረጃ), no older than the platform setting
      police_clearance_max_age_days (180 by default)
    - education certificate at or above the platform setting vetting_min_education (grade 12 by default)
    - passport-style photo
    - Telegram username, so clients and staff can reach them
    - two references staff phoned, only when the setting vetting_references_required is on
    - a guarantor (ተያዥ), when the setting vetting_guarantor_required is on (it is by default): the
      guarantor's details confirmed by staff on the phone, a signed guarantee letter and a copy of the
      guarantor's ID, both verified. Companies need one only when vetting_guarantor_required_company is on.

  Company (agency)
    - the representative's national ID verified with Fayda
    - trade licence (with its valid-until date), TIN certificate
    - the representative's police clearance certificate

Every document is checked by a person: staff verify or reject each one (a rejection always has a
reason the provider sees). Approving or renewing a listing is refused until every required item is
verified and in date. Nothing is deleted: a new upload supersedes the old one, which stays on file.
Opening a police clearance is written to the provider's audit log, because it is criminal record data;
so is opening a guarantor's ID or papers, because they belong to someone who is not our user.

Vetting must hold all the time, not only on the day of approval: provider_service.refresh_readiness()
hides a provider from clients as soon as an item stops being verified or in date.
"""

from __future__ import annotations

from services.vetting.requirements import (
    _blocker_text,
    blocker,
    checklist,
    expired_blocker,
    template,
)
from services.vetting.common import (
    _clean_text,
    _notify_provider,
    _recompute,
    _uuid_like,
)
from services.vetting.daily import run_daily
from services.vetting.documents import (
    get_document,
    history,
    read_file,
    references,
    set_references,
    upload,
)
from services.vetting.guarantor import (
    GUARANTOR_COLUMNS,
    GUARANTOR_HELP,
    GUARANTOR_STAFF_HELP,
    _clean_id_number,
    _guarantor_item,
    check_guarantor,
    current_guarantor,
    guarantor_history,
    set_guarantor,
)
from services.vetting.rules import (
    DOC_COLUMNS,
    EDUCATION_LABELS,
    EDUCATION_LEVELS,
    EXPIRY_SQL,
    GUARANTOR_KINDS,
    KINDS,
    MAX_REFERENCES,
    REFERENCES_NEEDED,
    STATUSES,
    Kind,
    VettingError,
    _doc_item,
    _docs,
    _fayda_on,
    _is_company,
    _public_doc,
    document_kinds,
    effective_expiry,
    guarantor_applies,
    guarantor_required,
    max_age_days,
    min_education,
    references_required,
)
from services.vetting.staff import check_reference, review_document, verified_kinds

__all__ = [
    "VettingError",
    "Kind",
    "KINDS",
    "GUARANTOR_KINDS",
    "EDUCATION_LEVELS",
    "EDUCATION_LABELS",
    "STATUSES",
    "REFERENCES_NEEDED",
    "MAX_REFERENCES",
    "DOC_COLUMNS",
    "max_age_days",
    "min_education",
    "references_required",
    "guarantor_required",
    "guarantor_applies",
    "_fayda_on",
    "EXPIRY_SQL",
    "effective_expiry",
    "_is_company",
    "document_kinds",
    "_public_doc",
    "_docs",
    "references",
    "_doc_item",
    "checklist",
    "template",
    "_blocker_text",
    "blocker",
    "expired_blocker",
    "_clean_text",
    "upload",
    "get_document",
    "history",
    "read_file",
    "_uuid_like",
    "set_references",
    "GUARANTOR_HELP",
    "GUARANTOR_STAFF_HELP",
    "GUARANTOR_COLUMNS",
    "current_guarantor",
    "guarantor_history",
    "_guarantor_item",
    "_clean_id_number",
    "set_guarantor",
    "check_guarantor",
    "review_document",
    "check_reference",
    "_recompute",
    "_notify_provider",
    "verified_kinds",
    "run_daily",
]
