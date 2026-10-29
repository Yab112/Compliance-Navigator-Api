"""Compliance graph nodes, aligned with Doc/02 Government Data Dictionary."""

from datetime import date, datetime
from typing import ClassVar, Optional
from uuid import uuid4

from pydantic import Field
from neontology import BaseNode


class ServiceNode(BaseNode):
    __primarylabel__: ClassVar[str] = "Service"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    name: str
    name_am: Optional[str] = None
    category: str = "business"
    description: str = ""
    is_active: bool = True
    sort_order: int = 0


class SubCityNode(BaseNode):
    __primarylabel__: ClassVar[str] = "SubCity"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    label: str
    label_am: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)


class SectorNode(BaseNode):
    __primarylabel__: ClassVar[str] = "Sector"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    name: str
    regulatory_body: str = ""


class EntityTypeNode(BaseNode):
    __primarylabel__: ClassVar[str] = "EntityType"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    label: str


class InstitutionNode(BaseNode):
    __primarylabel__: ClassVar[str] = "Institution"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    name: str
    name_am: Optional[str] = None
    short_name: Optional[str] = None
    logo_url: Optional[str] = None
    portal_url: Optional[str] = None
    scrape_method: Optional[str] = None
    refresh_frequency: Optional[str] = None
    at_mesob: bool = False


class DocumentNode(BaseNode):
    __primarylabel__: ClassVar[str] = "Document"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    name: str
    name_am: Optional[str] = None
    issuing_authority: str = ""
    form_code: Optional[str] = None
    fee_etb: Optional[int] = None
    avg_processing_days: Optional[int] = None
    legal_basis: Optional[str] = None
    required_input_labels: list[str] = Field(default_factory=list)
    sector_specific: bool = False
    applicable_sectors: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    last_verified: Optional[date] = None
    source_url: Optional[str] = None
    stale: bool = False


class OfficeNode(BaseNode):
    __primarylabel__: ClassVar[str] = "Office"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    name: str
    parent_institution: str = ""
    address_detail: str = ""
    landmark: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phones: list[str] = Field(default_factory=list)
    working_hours: str = "Mon–Fri 08:30–17:00 (EAT)"
    documents_issued: list[str] = Field(default_factory=list)
    last_verified: Optional[date] = None


class GovServiceNode(BaseNode):
    """A single government service from a public catalog (e.g. MESOB)."""

    __primarylabel__: ClassVar[str] = "GovService"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    source: str = "mesob"
    source_id: Optional[int] = None
    language: str = "en"
    name: str
    institution_id: str
    required_documents: list[str] = Field(default_factory=list)
    processing_time_text: Optional[str] = None
    processing_minutes: Optional[int] = None
    fee_text: Optional[str] = None
    fee_etb_min: Optional[int] = None
    fee_etb_max: Optional[int] = None
    fee_has_usd: bool = False
    online_url: Optional[str] = None
    source_url: Optional[str] = None
    last_verified: Optional[date] = None


class MesobCenterNode(BaseNode):
    __primarylabel__: ClassVar[str] = "MesobCenter"
    __primaryproperty__: ClassVar[str] = "id"

    id: str
    name: str
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    map_url: Optional[str] = None


class ManualReferenceNode(BaseNode):
    __primarylabel__: ClassVar[str] = "ManualReference"
    __primaryproperty__: ClassVar[str] = "id"

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    file_url: Optional[str] = None
    mime_type: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    extraction_status: str = "pending"
    raw_text: Optional[str] = None
    verified: bool = False
    service_id: Optional[str] = None
    company_name: Optional[str] = None


class CompanyProfileNode(BaseNode):
    __primarylabel__: ClassVar[str] = "CompanyProfile"
    __primaryproperty__: ClassVar[str] = "id"

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    sector_id: Optional[str] = None
    notes: Optional[str] = None


class RoadmapNode(BaseNode):
    __primarylabel__: ClassVar[str] = "Roadmap"
    __primaryproperty__: ClassVar[str] = "id"

    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str
    goal: str
    sub_city: str
    industry: Optional[str] = None
    entity_type: Optional[str] = None
    documents_held: list[str] = Field(default_factory=list)
    tracked_completed: list[str] = Field(default_factory=list)
    snapshot_json: str = ""
