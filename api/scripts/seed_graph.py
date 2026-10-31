"""
Seed the compliance graph (graph tables in Postgres).

Run from api/:  uv run python -m scripts.seed_graph
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure api/ is on path when run as module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.db import run_migrations
from models.compliance_nodes import (
    DocumentNode,
    EntityTypeNode,
    InstitutionNode,
    OfficeNode,
    SectorNode,
    ServiceNode,
    SubCityNode,
)
from models.compliance_relationships import (
    AppliesToRel,
    IssuedByRel,
    LocatedInRel,
    RequiresRel,
    SectorExtraRel,
    TargetsRel,
)
from scripts.seed_data import (
    DOC_OFFICE_TEMPLATE,
    DOCUMENTS,
    ENTITY_TYPES,
    INSTITUTIONS,
    OFFICE_TEMPLATES,
    REQUIRES_EDGES,
    SECTOR_EXTRAS,
    SEED_DATE,
    SERVICE_TARGETS,
    SECTORS,
    SERVICES,
    SUB_CITIES,
)


def _merge_nodes() -> None:
    for row in SUB_CITIES:
        SubCityNode(**row).merge()

    for row in SERVICES:
        ServiceNode(**row).merge()

    for row in SECTORS:
        SectorNode(**row).merge()

    for row in ENTITY_TYPES:
        EntityTypeNode(**row).merge()

    for row in INSTITUTIONS:
        InstitutionNode(**row).merge()

    for row in DOCUMENTS:
        DocumentNode(last_verified=SEED_DATE, stale=False, **row).merge()


def _merge_offices() -> None:
    subcity_by_id = {sc["id"]: sc for sc in SUB_CITIES}

    for sc_id, sc in subcity_by_id.items():
        label = sc["label"]
        for template_key, tmpl in OFFICE_TEMPLATES.items():
            if template_key.endswith("_main"):
                office_id = template_key
                sub_city_for_loc = None
            else:
                office_id = f"{template_key}_{sc_id}"
                sub_city_for_loc = sc_id

            office = OfficeNode(
                id=office_id,
                name=tmpl["name"].format(label=label),
                parent_institution=tmpl["parent_institution"],
                address_detail=tmpl["address_detail"].format(label=label),
                landmark=tmpl.get("landmark"),
                latitude=tmpl.get("latitude"),
                longitude=tmpl.get("longitude"),
                phones=tmpl.get("phones", []),
                documents_issued=tmpl.get("documents_issued", []),
                last_verified=SEED_DATE,
            )
            office.merge()

            if sub_city_for_loc:
                sc_node = SubCityNode.match(sc_id)
                if sc_node:
                    LocatedInRel(source=office, target=sc_node).merge()


def _merge_document_offices() -> None:
    subcity_ids = [sc["id"] for sc in SUB_CITIES]

    for doc_id, template_key in DOC_OFFICE_TEMPLATE.items():
        doc = DocumentNode.match(doc_id)
        if not doc:
            continue

        if template_key.endswith("_main"):
            office = OfficeNode.match(template_key)
            if office:
                IssuedByRel(source=doc, target=office).merge()
        else:
            for sc_id in subcity_ids:
                office = OfficeNode.match(f"{template_key}_{sc_id}")
                if office:
                    IssuedByRel(source=doc, target=office).merge()


def _merge_relationships() -> None:
    for prereq, dependent in REQUIRES_EDGES:
        a = DocumentNode.match(prereq)
        b = DocumentNode.match(dependent)
        if a and b:
            RequiresRel(source=a, target=b).merge()

    for service_id, doc_id in SERVICE_TARGETS.items():
        s = ServiceNode.match(service_id)
        d = DocumentNode.match(doc_id)
        if s and d:
            TargetsRel(source=s, target=d).merge()

    for sector_id, doc_id in SECTOR_EXTRAS:
        sec = SectorNode.match(sector_id)
        d = DocumentNode.match(doc_id)
        if sec and d:
            SectorExtraRel(source=sec, target=d).merge()
            d.sector_specific = True
            d.applicable_sectors = [sector_id]
            d.merge()
            AppliesToRel(source=d, target=sec).merge()


def main() -> None:
    run_migrations()
    print("Merging catalog nodes...")
    _merge_nodes()
    print("Merging offices...")
    _merge_offices()
    print("Linking documents to offices...")
    _merge_document_offices()
    print("Merging REQUIRES / TARGETS / SECTOR_EXTRA...")
    _merge_relationships()
    print("Seed complete.")


if __name__ == "__main__":
    main()
