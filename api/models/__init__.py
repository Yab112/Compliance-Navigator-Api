"""Import all models so neontology registers node/relationship types at startup."""

from models.user import UserNode
from models.compliance_nodes import (
    CompanyProfileNode,
    DocumentNode,
    EntityTypeNode,
    InstitutionNode,
    ManualReferenceNode,
    OfficeNode,
    RoadmapNode,
    SectorNode,
    ServiceNode,
    SubCityNode,
)
from models.compliance_relationships import (
    AppliesToRel,
    EnrichesDocumentRel,
    EnrichesServiceRel,
    ForServiceRel,
    IssuedByRel,
    LocatedInRel,
    OwnsRel,
    RequiresRel,
    SectorExtraRel,
    TargetsRel,
)

__all__ = [
    "UserNode",
    "ServiceNode",
    "SubCityNode",
    "SectorNode",
    "EntityTypeNode",
    "InstitutionNode",
    "DocumentNode",
    "OfficeNode",
    "ManualReferenceNode",
    "CompanyProfileNode",
    "RoadmapNode",
    "TargetsRel",
    "RequiresRel",
    "IssuedByRel",
    "LocatedInRel",
    "SectorExtraRel",
    "AppliesToRel",
    "EnrichesDocumentRel",
    "EnrichesServiceRel",
    "OwnsRel",
    "ForServiceRel",
]
