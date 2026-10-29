from fastapi import APIRouter, HTTPException, Query

from services import catalog_service, provider_service, service_directory

router = APIRouter(prefix="/catalog", tags=["Service catalog"])


@router.get("/stats")
def get_catalog_stats():
    return {"message": "success", "payload": catalog_service.catalog_stats()}


@router.get("/institutions")
def get_institutions():
    return {"message": "success", "payload": {"institutions": catalog_service.list_institutions()}}


@router.get("/centers")
def get_centers():
    return {"message": "success", "payload": {"centers": catalog_service.list_centers()}}


@router.get("/services")
def search_services(
    q: str | None = None,
    institution_id: str | None = None,
    language: str = Query("en", pattern="^(en|am)$"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    result = catalog_service.search_services(
        q=q, institution_id=institution_id, language=language, limit=limit, offset=offset
    )
    return {"message": "success", "payload": result}


@router.get("/directory")
def service_directory_search(
    q: str | None = None,
    source: str | None = Query(None, pattern="^(organization|path|mesob)$"),
    language: str = Query("en", pattern="^(en|am)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Every service on the platform: organization-published, guided paths, and the MESOB catalog."""
    return {"message": "success", "payload": service_directory.search(q, source, language, limit, offset)}


@router.get("/services/{service_id}")
def get_service(service_id: str):
    service = catalog_service.get_service(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    agents = provider_service.public_list(service_id=service_id, limit=6)
    return {
        "message": "success",
        "payload": {"service": service, "agents": agents["items"], "agentCount": agents["total"]},
    }


@router.get("/goal-service/{goal}")
def get_goal_service(goal: str, sub_city: str | None = None):
    """MESOB service(s) behind a roadmap goal, plus approved agents who handle it."""
    services = catalog_service.services_for_document(goal)
    primary = services[0] if services else None
    agents = provider_service.public_list(
        service_id=primary["id"] if primary else None, area=sub_city, limit=12
    )
    # Nobody in that sub-city yet, offer agents from anywhere in the city
    if sub_city and not agents["total"]:
        agents = provider_service.public_list(service_id=primary["id"] if primary else None, limit=12)
        agents["sub_city_fallback"] = True
    return {
        "message": "success",
        "payload": {
            "goal": goal,
            "service": primary,
            "alternatives": services[1:],
            "agents": agents["items"],
            "agentCount": agents["total"],
            "subCityFallback": bool(agents.get("sub_city_fallback")),
        },
    }
