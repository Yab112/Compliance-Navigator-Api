"""Admin: assistant model metrics, low-confidence messages to label, and gated retraining."""

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from assistant import nlu, store
from assistant.training_data import INTENTS
from core.deps import require_admin
from schemas.auth_user import AuthUser

router = APIRouter(prefix="/admin/assistant", tags=["Admin Assistant"], dependencies=[Depends(require_admin)])

API_ROOT = Path(__file__).resolve().parents[3]


def _ok(payload):
    return {"message": "success", "payload": payload}


def _last_run() -> dict | None:
    f = nlu.STORE / ".last_run.json"
    return json.loads(f.read_text()) if f.exists() else None


@router.get("/model")
def model_info():
    version = nlu.active_version()
    metrics, report = None, None
    if version:
        folder = nlu.STORE / version
        if (folder / "metrics.json").exists():
            metrics = json.loads((folder / "metrics.json").read_text())
        if (folder / "report.md").exists():
            report = (folder / "report.md").read_text()
    return _ok({
        "active": version, "metrics": metrics, "report": report, "versions": nlu.list_versions(),
        "intents": INTENTS, "lastRun": _last_run(), "usage": store.turn_stats(),
    })


@router.get("/turns")
def review_turns(max_confidence: float = Query(0.6, ge=0, le=1), limit: int = Query(50, ge=1, le=200),
                 include_labelled: bool = False):
    rows = store.turns_to_review(max_confidence, limit, include_labelled)
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
        if r.get("labelled_at"):
            r["labelled_at"] = r["labelled_at"].isoformat()
    return _ok({"turns": rows})


class Label(BaseModel):
    intent: str | None = Field(None, max_length=40)
    service: str | None = Field(None, max_length=200)


@router.post("/turns/{turn_id}/label")
def label_turn(turn_id: int, body: Label, admin: AuthUser = Depends(require_admin)):
    if body.intent and body.intent not in INTENTS:
        raise HTTPException(status_code=422, detail="Unknown intent")
    row = store.label_turn(turn_id, body.intent, body.service, admin.email)
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    return _ok({"turn": row})


@router.post("/retrain", status_code=202)
def retrain(candidates: str = Query("tfidf,e5,labse", pattern=r"^[a-z0-9,]+$")):
    """Runs scripts/train_assistant.py in the background. The new version only becomes active
    if its test macro-F1 is not lower than the current one."""
    run = _last_run()
    if run and run.get("state") == "running":
        raise HTTPException(status_code=409, detail="A training run is already in progress")
    nlu.STORE.mkdir(parents=True, exist_ok=True)
    log = open(nlu.STORE / ".last_run.log", "w")
    subprocess.Popen(
        [sys.executable, "-m", "scripts.train_assistant", "--candidates", candidates, "--activate"],
        cwd=API_ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    (nlu.STORE / ".last_run.json").write_text(json.dumps({"state": "running"}))
    return _ok({"started": True})


@router.post("/activate/{version}")
def activate(version: str):
    """Roll back or forward to any trained version."""
    if not (nlu.STORE / version / "model.joblib").exists():
        raise HTTPException(status_code=404, detail="Version not found")
    (nlu.STORE / "ACTIVE").write_text(version)
    return _ok({"active": version})
