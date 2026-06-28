from fastapi import APIRouter, Query

from services.graph_service import list_offices

router = APIRouter(prefix="/offices", tags=["Offices"])


@router.get("")
def get_offices(sub_city: str | None = Query(None, alias="sub_city")):
    offices = list_offices(sub_city)
    return {"message": "success", "payload": {"offices": offices}}
