from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.deps import require_admin
from schemas.auth_user import AuthUser
from worker.celery_app import celery_app

router = APIRouter(prefix="/admin/tasks", tags=["Admin Tasks"])


class TaskStatusResponse(BaseModel):
    message: str
    payload: dict


@router.get("/{task_id}")
def get_task_status(task_id: str, _: AuthUser = Depends(require_admin)):
    result = celery_app.AsyncResult(task_id)
    if result.state == "PENDING" and not result.result:
        payload = {"task_id": task_id, "state": "PENDING"}
    elif result.failed():
        payload = {
            "task_id": task_id,
            "state": result.state,
            "error": str(result.result),
        }
    else:
        payload = {
            "task_id": task_id,
            "state": result.state,
            "result": result.result,
        }
    return TaskStatusResponse(message="success", payload=payload)
