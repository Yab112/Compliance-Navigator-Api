"""The second-person approval may only be skipped in production while the first team is being invited."""

import uuid

import pytest

from config.config import settings
from schemas.staff_user import StaffActor
from services import approvals
from services.db import execute


@pytest.fixture
def lone_staff(make_staff, monkeypatch):
    staff = make_staff()
    # Nobody else could approve, as on a fresh install with a single Super admin
    monkeypatch.setattr(approvals, "eligible_approvers", lambda *a, **k: [])
    yield StaffActor(id=staff["id"], email=staff["email"])
    execute("delete from approval_requests where requested_by = %s", (staff["id"],))


def _delete_source(actor: StaffActor) -> dict:
    return approvals.request("data_source.delete", {"source_id": str(uuid.uuid4())}, "Delete a test source",
                             actor, target="test", execute_if_waived=False)


def test_waived_outside_production(lone_staff, monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    assert _delete_source(lone_staff) == {"waived": True, "result": None}


def test_production_waits_for_a_second_person(lone_staff, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    outcome = _delete_source(lone_staff)
    assert "pending" in outcome
    assert outcome["pending"]["status"] == "pending"
    assert outcome["pending"]["action"] == "data_source.delete"


def test_production_still_lets_the_first_admin_invite_the_team(lone_staff, monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    for action in approvals.TEAM_BOOTSTRAP_ACTIONS:
        outcome = approvals.request(action, {"email": "x@example.com"}, "Invite", lone_staff,
                                    execute_if_waived=False)
        assert outcome == {"waived": True, "result": None}
