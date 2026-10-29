import re
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, BeforeValidator, EmailStr, Field

ORG_TYPES = (
    "federal_institution", "regional_bureau", "sub_city_office", "woreda_office", "bank",
    "utility", "health", "education", "embassy", "ngo", "private_provider", "other",
)
OrgType = Literal[
    "federal_institution", "regional_bureau", "sub_city_office", "woreda_office", "bank",
    "utility", "health", "education", "embassy", "ngo", "private_provider", "other",
]
# Landlines and mobiles, local or international format
PHONE = r"^\+?[0-9][0-9 ()\-]{6,19}$"
KEY = r"^[a-z0-9][a-z0-9_\-]{0,39}$"
# A form the organization uploaded to us is stored at a path on our own site
OWN_UPLOAD = re.compile(r"^/uploads/public/[A-Za-z0-9._-]+$")


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _web_link(value: str | None) -> str | None:
    """Only http(s) links (or our own uploads) reach the public pages; 'example.gov.et' becomes https://example.gov.et."""
    if value is None:
        return None
    if OWN_UPLOAD.match(value):
        return value
    if any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("A link can't contain spaces")
    if "://" not in value and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname or "." not in parts.hostname:
        raise ValueError("Links must start with http:// or https:// and name a website")
    if parts.username or parts.password:
        raise ValueError("Links can't contain a user name or password")
    return value


WebLink = Annotated[str | None, BeforeValidator(_blank_to_none), AfterValidator(_web_link)]


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TIME = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"


class HoursDay(BaseModel):
    """One weekday's opening hours. A closed day keeps its row with closed=true."""

    day: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    closed: bool = False
    open: str | None = Field(None, pattern=TIME)
    close: str | None = Field(None, pattern=TIME)
    lunch_start: str | None = Field(None, pattern=TIME)
    lunch_end: str | None = Field(None, pattern=TIME)


class BranchIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    region: str | None = Field(None, max_length=80)
    sub_city: str | None = Field(None, max_length=80)
    woreda: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=300)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    map_url: WebLink = Field(None, max_length=500)
    phone: str | None = Field(None, pattern=PHONE)
    hours: str | None = Field(None, max_length=200)
    landmark: str | None = Field(None, max_length=200)
    email: EmailStr | None = None
    hours_schedule: list[HoursDay] = Field(default_factory=list, max_length=7)


class OrgRegistration(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    name_am: str | None = Field(None, max_length=200)
    org_type: OrgType
    sector: str | None = Field(None, max_length=80)
    parent_org_id: str | None = None
    description: str | None = Field(None, max_length=2000)
    website: WebLink = Field(None, max_length=300)
    phone: str | None = Field(None, pattern=PHONE)
    email: EmailStr | None = None
    hq_address: str | None = Field(None, max_length=300)
    region: str | None = Field(None, max_length=80)
    sub_city: str | None = Field(None, max_length=80)
    # Optional while the registration is a saved draft; required when it's sent for verification
    representative_name: str | None = Field(None, min_length=3, max_length=120)
    representative_title: str | None = Field(None, min_length=2, max_length=120)
    official_email: EmailStr | None = None
    branches: list[BranchIn] = Field(default_factory=list, max_length=50)
    draft: bool = False


class OrgUpdate(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=200)
    name_am: str | None = Field(None, max_length=200)
    org_type: OrgType | None = None
    sector: str | None = Field(None, max_length=80)
    description: str | None = Field(None, max_length=2000)
    website: WebLink = Field(None, max_length=300)
    phone: str | None = Field(None, pattern=PHONE)
    email: EmailStr | None = None
    hq_address: str | None = Field(None, max_length=300)
    region: str | None = Field(None, max_length=80)
    sub_city: str | None = Field(None, max_length=80)
    representative_name: str | None = Field(None, min_length=3, max_length=120)
    representative_title: str | None = Field(None, min_length=2, max_length=120)
    official_email: EmailStr | None = None
    steward_name: str | None = Field(None, min_length=3, max_length=120)
    steward_role: str | None = Field(None, max_length=120)
    steward_phone: str | None = Field(None, pattern=PHONE)
    steward_email: EmailStr | None = None
    data_commitment: bool | None = None
    onboarding_step: int | None = Field(None, ge=0, le=6)


class RegistrationSubmit(BaseModel):
    submit_services: bool = False


class MemberInvite(BaseModel):
    email: EmailStr
    role: Literal["owner", "editor"] = "editor"


class LinkItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    url: Annotated[str, BeforeValidator(_blank_to_none), AfterValidator(_web_link)] = Field(..., min_length=1, max_length=500)


class FaqItem(BaseModel):
    q: str = Field(..., min_length=2, max_length=300)
    a: str = Field(..., min_length=1, max_length=2000)


class OutputDoc(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    document_id: str | None = Field(None, max_length=80)


class RequirementIn(BaseModel):
    key: str = Field(..., pattern=KEY)
    kind: Literal["document", "prerequisite_service"] = "document"
    name: str = Field(..., min_length=2, max_length=200)
    document_id: str | None = Field(None, max_length=80)
    issuing_service_id: str | None = None
    required: Literal["always", "conditional"] = "always"
    notes: str | None = Field(None, max_length=1000)
    original_or_copy: Literal["original", "copy", "both"] | None = None
    copies: int | None = Field(None, ge=1, le=20)
    notarized: bool = False
    translated: bool = False
    max_age_days: int | None = Field(None, ge=1, le=3650)
    photo_specs: str | None = Field(None, max_length=300)
    applies_to: Literal["applicant", "each_party", "each_partner", "company", "representative"] | None = None
    alternatives: list[str] = Field(default_factory=list, max_length=10)


class RuleIn(BaseModel):
    """When the answer matches, add conditional requirements and/or stop with a reason."""

    op: Literal["eq", "gt", "gte", "lt", "lte"] = "eq"
    value: str = Field(..., min_length=1, max_length=120)
    add_requirements: list[str] = Field(default_factory=list, max_length=30)
    ineligible: str | None = Field(None, max_length=300)


class QuestionIn(BaseModel):
    key: str = Field(..., pattern=KEY)
    prompt: str = Field(..., min_length=3, max_length=300)
    prompt_am: str | None = Field(None, max_length=300)
    type: Literal["yes_no", "single_choice", "number", "text"] = "yes_no"
    options: list[str] = Field(default_factory=list, max_length=20)
    rules: list[RuleIn] = Field(default_factory=list, max_length=20)


class StepIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    location: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=1000)
    estimated_minutes: int | None = Field(None, ge=0, le=60 * 24 * 90)


class FeeRow(BaseModel):
    """One line of the fee schedule: who pays what, for which speed."""

    category: Literal["everyone", "ethiopian", "foreign_national", "diaspora", "company", "other"] = "everyone"
    speed: Literal["regular", "urgent"] = "regular"
    amount_min: float = Field(..., ge=0)
    amount_max: float | None = Field(None, ge=0)
    currency: Literal["ETB", "USD"] = "ETB"
    covers: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=300)


class BranchDetail(BaseModel):
    """How a specific branch handles this service; overrides the branch defaults."""

    branch_id: str
    window: str | None = Field(None, max_length=80)
    phone: str | None = Field(None, pattern=PHONE)
    hours_note: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=500)


AUDIENCE = Literal["citizen", "resident", "company", "foreigner", "investor", "diaspora", "ngo"]


class ServiceIn(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    name_am: str | None = Field(None, max_length=200)
    summary: str | None = Field(None, max_length=2000)
    who_can_apply: str | None = Field(None, max_length=1000)
    delivery: Literal["in_person", "online", "both"] = "in_person"
    online_url: WebLink = Field(None, max_length=500)
    fee_amount_min: float | None = Field(None, ge=0)
    fee_amount_max: float | None = Field(None, ge=0)
    fee_currency: str = Field("ETB", min_length=3, max_length=3)
    fee_notes: str | None = Field(None, max_length=1000)
    payment_methods: list[str] = Field(default_factory=list, max_length=12)
    processing_time_text: str | None = Field(None, max_length=200)
    processing_minutes: int | None = Field(None, ge=0, le=60 * 24 * 365)
    legal_basis: str | None = Field(None, max_length=500)
    forms: list[LinkItem] = Field(default_factory=list, max_length=20)
    common_rejection_reasons: list[str] = Field(default_factory=list, max_length=20)
    faq: list[FaqItem] = Field(default_factory=list, max_length=30)
    branch_ids: list[str] = Field(default_factory=list, max_length=100)
    outputs: list[OutputDoc] = Field(default_factory=list, max_length=10)
    requirements: list[RequirementIn] = Field(default_factory=list, max_length=60)
    questions: list[QuestionIn] = Field(default_factory=list, max_length=30)
    steps: list[StepIn] = Field(default_factory=list, max_length=40)
    fee_schedule: list[FeeRow] = Field(default_factory=list, max_length=20)
    is_free: bool = False
    where_to_pay: str | None = Field(None, max_length=300)
    no_documents_required: bool = False
    appointment_required: bool = False
    appointment_how: str | None = Field(None, max_length=300)
    appointment_url: WebLink = Field(None, max_length=500)
    appointment_phone: str | None = Field(None, pattern=PHONE)
    proxy_allowed: Literal["yes", "with_poa", "no"] | None = None
    proxy_notes: str | None = Field(None, max_length=500)
    online_parts: str | None = Field(None, max_length=500)
    languages: list[str] = Field(default_factory=list, max_length=10)
    accessibility_notes: str | None = Field(None, max_length=500)
    audience: list[AUDIENCE] = Field(default_factory=list, max_length=7)
    legal_reference_number: str | None = Field(None, max_length=120)
    legal_effective_date: date | None = None
    contact_name: str | None = Field(None, max_length=120)
    contact_phone: str | None = Field(None, pattern=PHONE)
    contact_email: EmailStr | None = None
    output_validity_months: int | None = Field(None, ge=1, le=600)
    renewal_service_id: str | None = None
    late_renewal_penalty: str | None = Field(None, max_length=300)
    branch_details: list[BranchDetail] = Field(default_factory=list, max_length=100)


class ServiceSubmit(BaseModel):
    """Required when the service is already live: what changes, why, and from when."""

    change_summary: str | None = Field(None, min_length=5, max_length=500)
    change_reason: str | None = Field(None, max_length=500)
    effective_at: date | None = None


class ReportResponse(BaseModel):
    """The organization's answer to a report. Only staff close reports."""

    verdict: Literal["fixed", "correct"]
    response: str = Field(..., min_length=2, max_length=1000)


class OrgReview(BaseModel):
    action: Literal["verify", "reject", "suspend", "reinstate"]
    note: str | None = Field(None, max_length=1000)
    catalog_institution_id: str | None = Field(None, max_length=80)


class SubmissionReview(BaseModel):
    action: Literal["publish", "request_changes"]
    note: str | None = Field(None, max_length=1000)


class EligibilityIn(BaseModel):
    answers: dict[str, str | float | bool | None] = Field(default_factory=dict)
