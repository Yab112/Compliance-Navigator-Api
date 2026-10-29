"""Admin: assistant model metrics, low-confidence messages to label, and gated retraining."""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from assistant import nlu, store
from assistant.training_data import INTENTS
from core.deps import require_admin
from schemas.auth_user import AuthUser
from services.db import fetch_all, fetch_one

router = APIRouter(prefix="/admin/assistant", tags=["Admin Assistant"], dependencies=[Depends(require_admin)])

API_ROOT = Path(__file__).resolve().parents[3]
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")
log = logging.getLogger(__name__)


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
def review_turns(max_confidence: float = Query(0.6, ge=0, le=1), limit: int = Query(20, ge=1, le=200),
                 offset: int = Query(0, ge=0), include_labelled: bool = False):
    """Messages the model was unsure about, newest first, one page at a time."""
    labelled = "" if include_labelled else "and labelled_intent is null"
    where = f"where (confidence is null or confidence < %s) {labelled}"
    rows = fetch_all(
        f"""
        select id, message_redacted, language, intent, confidence, resolved_service, model_version,
               labelled_intent, labelled_service, labelled_by, labelled_at, created_at
        from assistant_turns {where}
        order by created_at desc, id desc limit %s offset %s
        """,
        (max_confidence, limit, offset),
    )
    total = fetch_one(f"select count(*) as c from assistant_turns {where}", (max_confidence,))["c"]
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
        if r.get("labelled_at"):
            r["labelled_at"] = r["labelled_at"].isoformat()
    return _ok({"items": rows, "total": total})


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
def retrain(candidates: str = Query("tfidf,e5,labse", pattern=r"^[a-z0-9,]+$"),
            admin: AuthUser = Depends(require_admin)):
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
    log.info("assistant retrain started by %s (candidates=%s)", admin.email, candidates)
    return _ok({"started": True})


@router.post("/activate/{version}")
def activate(version: str, admin: AuthUser = Depends(require_admin)):
    """Roll back or forward to any trained version."""
    # Version folders are plain names; never let a path like "../x" pick a file outside the store
    if not VERSION_RE.match(version) or not (nlu.STORE / version / "model.joblib").exists():
        raise HTTPException(status_code=404, detail="Version not found")
    (nlu.STORE / "ACTIVE").write_text(version)
    log.info("assistant model %s activated by %s", version, admin.email)
    return _ok({"active": version})
