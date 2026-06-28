from fastapi import APIRouter

from services.roadmap_service import list_processes

router = APIRouter(prefix="/processes", tags=["Processes"])


@router.get("")
def get_processes():
    return {
        "message": "success",
        "payload": {"processes": list_processes()},
    }
