"""Roadmap generation, from the compliance graph with an in-memory/stub fallback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from models.compliance_nodes import RoadmapNode
from models.compliance_relationships import ForServiceRel
from schemas.auth_user import AuthUser
from services import graph_service
from services.rag_service import enrich_roadmap_steps
from services import roadmap_store
from services.catalog_service import mesob_summary_for_step

PROCESS_CATALOG = [
    {"id": "passport", "label": "Passport", "description": "New or renewal passport through Immigration and Citizenship Service."},
    {"id": "kebele_id", "label": "Kebele ID", "description": "Local resident identification at your Kebele office."},
    {"id": "tin", "label": "TIN", "description": "Tax identification number from ERCA."},
    {"id": "trade_license", "label": "Trade license", "description": "Sub-city trade bureau license for operating a business."},
    {"id": "commercial_registration", "label": "Commercial registration", "description": "Register your company with MoTRI."},
    {"id": "fintech_license", "label": "Fintech license", "description": "Full path including NBE fintech permit."},
]

_SUB_CITY_LABELS = {
    "addis_ketema": "Addis Ketema",
    "akaki": "Akaki Kaliti",
    "arada": "Arada",
    "bole": "Bole",
    "gulele": "Gulele",
    "kirkos": "Kirkos",
    "kolfe": "Kolfe Keranio",
    "lideta": "Lideta",
    "nifas_silk": "Nifas Silk-Lafto",
    "yeka": "Yeka",
}


def list_processes() -> list[dict]:
    if graph_service.graph_is_seeded():
        rows = graph_service.list_services_from_graph()
        return [
            {
                "id": r["id"],
                "label": r["name"],
                "description": r.get("description") or "",
            }
            for r in rows
        ]
    return [
        {"id": p["id"], "label": p["label"], "description": p["description"]}
        for p in PROCESS_CATALOG
    ]


def _goal_meta(goal_id: str) -> dict:
    for item in PROCESS_CATALOG:
        if item["id"] == goal_id:
            return item
    return PROCESS_CATALOG[0]


def _generate_roadmap_stub(
    goal: str,
    sub_city: str,
    documents_held: list[str],
    industry: str | None = None,
) -> dict:
    """Fallback when graph is empty or query fails."""
    meta = _goal_meta(goal)
    sub_label = _SUB_CITY_LABELS.get(sub_city, sub_city.replace("_", " ").title())
    held = set(documents_held)

    steps = [
        {
            "id": "kebele_id",
            "order": 1,
            "title": "Kebele ID",
            "issuingAuthority": f"Kebele office, {sub_label}",
            "feeEtb": 0,
            "paymentMethods": ["cash"],
            "estimatedDays": "3-7",
            "status": "completed" if "kebele_id" in held else "active",
            "requiredInputs": ["Birth certificate", "Passport photos"],
            "prerequisiteIds": [],
            "rejectionReasons": ["Missing prior document"],
        },
        {
            "id": "passport",
            "order": 2,
            "title": "Passport application",
            "issuingAuthority": "Immigration and Citizenship Service",
            "feeEtb": 2500,
            "paymentMethods": ["cash", "CBE Birr"],
            "estimatedDays": "14-30",
            "status": "completed"
            if "passport" in held
            else ("blocked" if "kebele_id" not in held else "active"),
            "requiredInputs": ["Kebele ID", "Application form"],
            "prerequisiteIds": ["kebele_id"],
            "rejectionReasons": ["Invalid Kebele stamp"],
        },
    ]

    if goal != "passport":
        steps = [
            {
                "id": goal,
                "order": 1,
                "title": meta["label"],
                "issuingAuthority": "Relevant government office",
                "feeEtb": None,
                "paymentMethods": ["cash"],
                "estimatedDays": "5-15",
                "status": "active",
                "requiredInputs": ["See office checklist"],
                "prerequisiteIds": [],
                "rejectionReasons": [],
            }
        ]

    remaining = [s for s in steps if s["status"] != "completed"]
    total_min = sum(int(str(s["estimatedDays"]).split("-")[0]) for s in remaining) or 0

    return {
        "id": str(uuid4()),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "request": {
            "goal": goal,
            "goalLabel": meta["label"],
            "category": "personal" if goal in ("passport", "kebele_id") else "business",
            "subCity": sub_city,
            "subCityLabel": sub_label,
            "industry": industry,
            "documentsHeld": documents_held,
        },
        "steps": steps,
        "totalEstimatedDays": (
            f"~{total_min}+ business days remaining"
            if total_min
            else "All steps complete"
        ),
        "trackedCompleted": list(documents_held),
    }


def generate_roadmap(
    goal: str,
    sub_city: str,
    documents_held: list[str],
    industry: str | None = None,
) -> dict:
    ind = industry or ("fintech" if goal == "fintech_license" else None)
    built = None
    if graph_service.graph_is_seeded():
        try:
            built = graph_service.build_roadmap_from_graph(
                goal, sub_city, documents_held, ind
            )
        except Exception:
            built = None

    if built:
        roadmap_id = str(uuid4())
        roadmap = {
            "id": roadmap_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            **built,
        }
        return _attach_org_data(_attach_mesob(enrich_roadmap_steps(roadmap)))

    stub = _generate_roadmap_stub(goal, sub_city, documents_held, industry)
    return _attach_org_data(_attach_mesob(enrich_roadmap_steps(stub)))


def _attach_mesob(roadmap: dict) -> dict:
    """Show where a step can be done at a MESOB one-stop center, with its fee and time."""
    for step in roadmap.get("steps", []):
        summary = mesob_summary_for_step(step["id"])
        if summary:
            step["mesob"] = summary
    return roadmap


# Step fields the issuing organization's published data replaces, kept so they can be restored
_ORG_OVERRIDES = ("issuingAuthority", "feeEtb", "paymentMethods", "requiredInputs", "rejectionReasons",
                  "legalBasis", "lastVerified")


def _clean_offices(steps: list[dict]) -> None:
    """Saved paths may hold stand-in phone numbers from older seeds; never show them."""
    for step in steps:
        office = step.get("office")
        if office:
            office["phones"] = graph_service.real_phones(office.get("phones"))


def _attach_org_data(roadmap: dict) -> dict:
    """Where the issuing organization published the service itself, its data leads the step.

    Runs on every read too, so saved paths always show the organization's current version.
    """
    steps = roadmap.get("steps", [])
    _clean_offices(steps)
    try:
        from services.org_service import org_data_for_steps

        found = org_data_for_steps([s["id"] for s in steps], roadmap.get("request", {}).get("subCity"))
    except Exception:
        return roadmap
    for step in steps:
        org = found.get(step["id"])
        if not org:
            old = step.pop("orgService", None)
            base = step.pop("graphDefaults", None)
            if base:
                for k, v in base.items():
                    if v is None:
                        step.pop(k, None)
                    else:
                        step[k] = v
            elif old and step.get("issuingAuthority") == old.get("orgName"):
                # Saved before graphDefaults existed: at least stop naming an office that no longer applies
                step["issuingAuthority"] = (step.get("office") or {}).get("name") or step["title"]
            continue
        step.setdefault("graphDefaults", {k: step.get(k) for k in _ORG_OVERRIDES})
        step["orgService"] = org
        step["issuingAuthority"] = org["orgName"]
        if org["isFree"]:
            step["feeEtb"] = 0
        elif org["feeAmountMin"] is not None and org["feeCurrency"] == "ETB":
            step["feeEtb"] = org["feeAmountMin"]
        if org["paymentMethods"]:
            step["paymentMethods"] = org["paymentMethods"]
        if org["requirements"]:
            step["requiredInputs"] = [r["name"] for r in org["requirements"] if r.get("required") == "always"] or step["requiredInputs"]
        if org["rejectionReasons"]:
            step["rejectionReasons"] = org["rejectionReasons"]
        if org["legalBasis"]:
            step["legalBasis"] = org["legalBasis"]
        if org["confirmedAt"]:
            step["lastVerified"] = org["confirmedAt"]
    return roadmap


def save_roadmap(roadmap: dict, user: AuthUser | None = None) -> dict:
    node = RoadmapNode(
        id=roadmap["id"],
        created_at=roadmap.get("createdAt", datetime.now(timezone.utc).isoformat()),
        goal=roadmap["request"]["goal"],
        sub_city=roadmap["request"]["subCity"],
        industry=roadmap["request"].get("industry"),
        documents_held=roadmap["request"].get("documentsHeld", []),
        tracked_completed=roadmap.get("trackedCompleted", []),
        snapshot_json=json.dumps(roadmap),
    )
    node.merge()

    from models.compliance_nodes import ServiceNode

    service = ServiceNode.match(roadmap["request"]["goal"])
    if service:
        ForServiceRel(source=node, target=service).merge()

    _ROADMAP_STORE[roadmap["id"]] = roadmap
    roadmap_store.save_roadmap(roadmap, user=user)
    return roadmap


def get_roadmap(roadmap_id: str) -> dict | None:
    stored = roadmap_store.get_roadmap(roadmap_id)
    if stored:
        return _attach_org_data(stored)

    node = RoadmapNode.match(roadmap_id)
    if node and node.snapshot_json:
        return _attach_org_data(json.loads(node.snapshot_json))

    found = _ROADMAP_STORE.get(roadmap_id)
    return _attach_org_data(found) if found else None


def mark_step(roadmap_id: str, step_id: str, completed: bool) -> dict | None:
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return None

    tracked = set(roadmap.get("trackedCompleted", []))
    if completed:
        tracked.add(step_id)
    else:
        tracked.discard(step_id)
    roadmap["trackedCompleted"] = list(tracked)

    for step in roadmap["steps"]:
        if step["id"] == step_id:
            step["status"] = "completed" if completed else "active"

    node = RoadmapNode.match(roadmap_id)
    if node:
        node.tracked_completed = list(tracked)
        node.snapshot_json = json.dumps(roadmap)
        node.merge()
    else:
        _ROADMAP_STORE[roadmap_id] = roadmap

    roadmap_store.save_roadmap(roadmap)
    return roadmap


# Legacy in-memory fallback when Roadmap node not persisted
_ROADMAP_STORE: dict[str, dict] = {}
