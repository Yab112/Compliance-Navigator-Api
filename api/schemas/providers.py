from pydantic import BaseModel, EmailStr, Field

from schemas.telegram import TelegramUsername

SUB_CITY_PATTERN = (
    "^(addis_ketema|akaki|arada|bole|gulele|kirkos|kolfe|lideta|nifas_silk|yeka)$"
)
# Ethiopian mobile numbers: 09XXXXXXXX / 07XXXXXXXX or +2519... / +2517...
PHONE_PATTERN = r"^(\+251|0)[79]\d{8}$"
TIN_PATTERN = r"^(\d{10})?$"  # empty clears it


class ProviderProfile(BaseModel):
    """Fields a provider edits on their own profile (all optional for PATCH)."""

    display_name: str | None = Field(None, min_length=3, max_length=120)
    display_name_am: str | None = Field(None, max_length=120)
    headline: str | None = Field(None, max_length=140)
    bio: str | None = Field(None, max_length=3000)
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    # Shown to a client only after the provider accepts their request
    telegram_username: TelegramUsername = None
    # VAT-registered providers (over ETB 2 million a year, or voluntarily) charge 15% VAT on their price
    vat_registered: bool | None = None
    vat_number: str | None = Field(None, max_length=30, pattern=r"^[0-9A-Za-z/-]{4,30}$")
    email: EmailStr | None = None
    website: str | None = Field(None, max_length=200, pattern=r"^https?://")
    sub_city: str | None = Field(None, pattern=SUB_CITY_PATTERN)
    address: str | None = Field(None, max_length=200)
    service_areas: list[str] | None = Field(None, min_length=1, max_length=25)
    specialties: list[str] | None = Field(None, max_length=10)
    service_ids: list[str] | None = Field(None, max_length=40)
    languages: list[str] | None = Field(None, max_length=8)
    experience_years: int | None = Field(None, ge=0, le=60)
    fee_from: float | None = Field(None, ge=0, le=100_000_000)
    fee_to: float | None = Field(None, ge=0, le=100_000_000)
    fee_unit: str | None = Field(None, pattern="^(per_job|percent|per_hour|negotiable)$")
    pricing_notes: str | None = Field(None, max_length=500)
    highlights: list[str] | None = Field(None, max_length=10)
    accepting_work: bool | None = None
    legal_name: str | None = Field(None, max_length=160)
    tin: str | None = Field(None, pattern=TIN_PATTERN)
    trade_license_no: str | None = Field(None, max_length=40)
    representative_title: str | None = Field(None, max_length=80)
    external_license_type: str | None = Field(None, max_length=80)
    external_license_no: str | None = Field(None, max_length=60)


class ProviderJoin(ProviderProfile):
    provider_type: str = Field(..., pattern="^(guday_geday|agency)$")
    entity_type: str = Field(..., pattern="^(individual|company)$")
    display_name: str = Field(..., min_length=3, max_length=120)
    phone: str = Field(..., pattern=PHONE_PATTERN)
    service_areas: list[str] = Field(..., min_length=1, max_length=25)
    # Only used when Fayda verification is switched off
    national_id: str | None = Field(None, min_length=6, max_length=32)


class ProviderReview(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|suspend|reinstate|renew)$")
    note: str | None = Field(None, max_length=500)


class LicenseDecision(BaseModel):
    decision: str = Field(..., pattern="^(verified|rejected)$")
    note: str | None = Field(None, max_length=500)


class HireCreate(BaseModel):
    provider_id: str | None = Field(None, max_length=80, description="Provider id or slug; empty = staff assign")
    service_id: str | None = None
    specialty: str | None = Field(None, max_length=40)
    title: str | None = Field(None, max_length=200)
    client_name: str = Field(..., min_length=2, max_length=120)
    client_phone: str = Field(..., pattern=PHONE_PATTERN)
    client_telegram: TelegramUsername = None
    sub_city: str | None = Field(None, pattern=SUB_CITY_PATTERN)
    details: str | None = Field(None, max_length=2000)
    budget: str | None = Field(None, max_length=120)


class JobAction(BaseModel):
    action: str = Field(..., pattern="^(accept|decline|start|complete|set_price)$")
    reason: str | None = Field(None, max_length=500)
    # The provider's price in birr, when accepting or later; the client can then pay online
    price: float | None = Field(None, gt=0, le=10_000_000)
    price_note: str | None = Field(None, max_length=300)
    # What the provider delivered, required when marking a job complete
    note: str | None = Field(None, max_length=2000)


class ClientAction(BaseModel):
    reason: str | None = Field(None, max_length=1000)


class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    communication: int | None = Field(None, ge=1, le=5)
    fee_honesty: int | None = Field(None, ge=1, le=5)
    speed: int | None = Field(None, ge=1, le=5)
    outcome: int | None = Field(None, ge=1, le=5)
    would_hire_again: bool | None = None
    comment: str | None = Field(None, max_length=2000)


class ReviewReply(BaseModel):
    reply: str = Field(..., min_length=2, max_length=1000)


class ReviewModeration(BaseModel):
    hidden: bool
    reason: str | None = Field(None, max_length=500)


class EngagementAdminUpdate(BaseModel):
    """A staff change to a hire. Staff never move a job forward (only the provider does); see
    provider_service.STAFF_HIRE_ACTIONS for what is allowed from which status."""

    action: str = Field(..., pattern="^(assign|cancel|reopen|note)$")
    provider_id: str | None = Field(None, max_length=80)
    # Required: the history must say why
    note: str = Field(..., min_length=5, max_length=1000)


class DisputeDecision(BaseModel):
    decision: str = Field(..., pattern="^(upheld|dismissed)$")
    # The finding both sides are told
    note: str = Field(..., min_length=5, max_length=1000)


class TeamInvite(BaseModel):
    member: str = Field(..., min_length=3, max_length=80, description="Member's profile slug or id")
    role_title: str | None = Field(None, max_length=80)


class JoinAgency(BaseModel):
    agency: str = Field(..., min_length=3, max_length=80, description="Agency slug or id")


class MembershipAction(BaseModel):
    action: str = Field(..., pattern="^(accept|decline|remove)$")
