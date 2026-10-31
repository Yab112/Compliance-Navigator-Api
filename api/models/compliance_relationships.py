"""Compliance graph relationships, Doc/01 §3.2."""

from typing import ClassVar

from models.graph_model import GraphRelationship

from models.compliance_nodes import (
    DocumentNode,
    GovServiceNode,
    InstitutionNode,
    ManualReferenceNode,
    OfficeNode,
    RoadmapNode,
    SectorNode,
    ServiceNode,
    SubCityNode,
)
from models.user import UserNode


class TargetsRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "TARGETS"

    source: ServiceNode
    target: DocumentNode


class RequiresRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "REQUIRES"

    source: DocumentNode
    target: DocumentNode


class IssuedByRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "ISSUED_BY"

    source: DocumentNode
    target: OfficeNode


class LocatedInRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "LOCATED_IN"

    source: OfficeNode
    target: SubCityNode


class SectorExtraRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "SECTOR_EXTRA"

    source: SectorNode
    target: DocumentNode


class AppliesToRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "APPLIES_TO"

    source: DocumentNode
    target: SectorNode


class OfferedByRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "OFFERED_BY"

    source: GovServiceNode
    target: InstitutionNode


class FulfilledByRel(GraphRelationship):
    """Roadmap document can be obtained through this catalog service."""

    __relationshiptype__: ClassVar[str] = "FULFILLED_BY"

    source: DocumentNode
    target: GovServiceNode


class EnrichesDocumentRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "ENRICHES"

    source: ManualReferenceNode
    target: DocumentNode


class EnrichesServiceRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "ENRICHES_SERVICE"

    source: ManualReferenceNode
    target: ServiceNode


class OwnsRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "OWNS"

    source: UserNode
    target: RoadmapNode


class ForServiceRel(GraphRelationship):
    __relationshiptype__: ClassVar[str] = "FOR"

    source: RoadmapNode
    target: ServiceNode
