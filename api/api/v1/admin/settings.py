"""Platform settings staff edit in the admin app; the form is built from the field definitions served here."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.deps import require_admin
from schemas.auth_user import AuthUser
from services import platform_settings as svc
from services.platform_settings import SettingsError

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"], dependencies=[Depends(require_admin)])


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


def _ok(payload):
    return {"message": "success", "payload": payload}


@router.get("")
def get_settings():
    return _ok(svc.admin_view())


@router.patch("")
def update_settings(body: SettingsUpdate, user: AuthUser = Depends(require_admin)):
    try:
        return _ok(svc.update(body.values, user.email))
    except SettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.delete("/{key}")
def reset_setting(key: str, user: AuthUser = Depends(require_admin)):
    try:
        return _ok(svc.reset(key, user.email))
    except SettingsError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.get("/history")
def settings_history(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _ok(svc.history(limit, offset))
