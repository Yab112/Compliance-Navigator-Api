"""
Second-person approval (maker-checker) for risky staff actions.

A staff member asks for the action; it is stored with its exact payload in approval_requests and
nothing happens yet. Another staff member who holds `approvals.decide` and the rule's approver
permission approves or rejects it. On approval the stored payload, never anything sent with the
approval, is executed on the server. Rules:

  - nobody approves their own request, or a request that would give themselves more access
  - a request expires after EXPIRY_HOURS
  - every step is written to the staff audit log
  - when nobody else could approve (for example the very first Super admin setting up the team),
    the action runs at once and the audit log records that the second approval was waived

Two kinds of rules:
  route rules  attached to an admin route in services/access.ROUTE_POLICY; core.deps checks them
               before the route runs and answers 202 with the request when approval is needed
  direct rules used by the staff access routes (api/v1/admin/access.py), which call request() themselves
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from psycopg.errors import UniqueViolation

from auth.service import ClientInfo
from auth.staff_service import audit
from schemas.staff_user import StaffActor
from services import access
from services.db import Jsonb, fetch_all, fetch_one

log = logging.getLogger(__name__)

EXPIRY_HOURS = 72

# Settings that move money or change tax: changing them needs a second person
MONEY_SETTING_KEYS = frozenset({
    "commission_percent", "vat_rate_percent", "platform_vat_registered", "min_payout_etb",
    "payout_approval_threshold_etb", "tin", "vat_number",
})


class ApprovalError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class PendingApproval(Exception):  # noqa: N818 (not an error: the action is waiting for a second person)
    """Raised instead of doing the action; app.py turns it into a 202 response."""

    def __init__(self, request: dict):
        super().__init__(request["summary"])
        self.request = request


@dataclass(frozen=True)
class Rule:
    action: str
    title: str
    approver_permission: str
    execute: Callable[[dict, str], Any]  # (payload, actor label) -> result


# ---------------------------------------------------------------- executors


def _exec_settings(payload: dict, actor: str):
    from services import platform_settings

    result = platform_settings.update(payload["values"], actor)
    return {"changed": result["changed"]}


def _exec_settings_reset(payload: dict, actor: str):
    from services import platform_settings

    platform_settings.reset(payload["key"], actor)
    return {"reset": payload["key"]}


def _exec_payout(payload: dict, actor: str):
    from services import payment_service

    payout = payment_service.decide_payout(payload["payout_id"], decision="approve", note=payload.get("note"), actor=actor)
    return {"payout_id": payout["id"], "status": payout["status"]}


def _exec_refund(payload: dict, actor: str):
    from services import payment_service

    return payment_service.execute_refund(payload, actor)


def _exec_data_source_delete(payload: dict, actor: str):
    from services import custom_sources

    deleted = custom_sources.delete_custom(payload["source_id"])
    if not deleted:
        raise ApprovalError("The data source no longer exists", 404)
    return {"deleted": deleted}


def _staff_exec(name: str):
    def run(payload: dict, actor: str):
        from services import staff_admin

        return getattr(staff_admin, name)(payload, actor)
    return run


RULES: dict[str, Rule] = {r.action: r for r in [
    Rule("settings.money", "Change money or tax settings", "settings.edit", _exec_settings),
    Rule("settings.money_reset", "Reset a money or tax setting", "settings.edit", _exec_settings_reset),
    Rule("payout.large", "Approve a large payout", "payouts.approve", _exec_payout),
    Rule("payment.refund", "Refund a client", "payments.refund", _exec_refund),
    Rule("data_source.delete", "Delete a staff-added data source", "data_sources.manage", _exec_data_source_delete),
    Rule("staff.create", "Invite a staff member", "staff.manage", _staff_exec("exec_create")),
    Rule("staff.set_roles", "Change a staff member's roles", "staff.manage", _staff_exec("exec_set_roles")),
    Rule("staff.super_admin", "Grant or remove Super admin", "roles.manage", _staff_exec("exec_set_roles")),
    Rule("staff.disable", "Disable a staff member", "staff.manage", _staff_exec("exec_disable")),
    Rule("staff.enable", "Enable a staff member again", "staff.manage", _staff_exec("exec_enable")),
    Rule("role.create", "Create a role", "roles.manage", _staff_exec("exec_role_create")),
    Rule("role.update", "Change a role's permissions", "roles.manage", _staff_exec("exec_role_update")),
    Rule("role.delete", "Delete a role", "roles.manage", _staff_exec("exec_role_delete")),
]}


# ---------------------------------------------------------------- requests

COLUMNS = """
  a.id::text, a.action, a.payload, a.summary, a.target, a.requested_by::text, a.requested_by_email,
  a.approver_permission, a.status, a.decided_by::text, a.decided_by_email, a.decision_note, a.result, a.error,
  a.created_at, a.decided_at, a.executed_at, a.expires_at
"""


def _shape(row: dict | None) -> dict | None:
    if row:
        rule = RULES.get(row["action"])
        row["title"] = rule.title if rule else row["action"]
    return row


def expire_stale() -> int:
    rows = fetch_all(
        "update approval_requests set status = 'expired' where status = 'pending' and expires_at < now() "
        "returning id::text, action, target"
    )
    for r in rows:
        audit("approval.expired", target=f"approval:{r['id']}", details={"action": r["action"], "target": r["target"]})
    return len(rows)


def get(request_id: str) -> dict | None:
    expire_stale()
    try:
        return _shape(fetch_one(f"select {COLUMNS} from approval_requests a where a.id = %s", (request_id,)))
    except Exception:  # malformed id
        return None


def eligible_approvers(rule: Rule, requester_id: str, beneficiaries: list[str] | None = None) -> list[dict]:
    excluded = {requester_id, *(beneficiaries or [])}
    deciders = {r["id"] for r in access.holders_of("approvals.decide")}
    return [s for s in access.holders_of(rule.approver_permission) if s["id"] in deciders and s["id"] not in excluded]


def request(action: str, payload: dict, summary: str, actor: StaffActor, *, target: str | None = None,
            beneficiaries: list[str] | None = None, client: ClientInfo | None = None,
            execute_if_waived: bool = True) -> dict:
    """
    Ask for an action. Returns {"pending": request} when a second person must approve, or
    {"waived": True, "result": ...} when nobody else could approve (it ran at once, or, with
    execute_if_waived=False, the caller runs it).
    `beneficiaries`: staff whose access the action would raise; they can't approve it.
    """
    rule = RULES[action]
    payload = {**payload, "beneficiaries": beneficiaries or []}
    if not eligible_approvers(rule, actor.id, beneficiaries):
        audit("approval.waived", actor=actor, target=target, client=client,
              details={"action": action, "summary": summary, "reason": "no other staff member can approve this"})
        if not execute_if_waived:
            return {"waived": True, "result": None}
        result = rule.execute(payload, f"{actor.email} (no second approver available)")
        return {"waived": True, "result": result}
    expire_stale()
    try:
        row = fetch_one(
            """
            insert into approval_requests (action, payload, summary, target, requested_by, requested_by_email,
                                           approver_permission, expires_at)
            values (%s, %s, %s, %s, %s, %s, %s, now() + make_interval(hours => %s))
            returning id::text
            """,
            (action, Jsonb(_jsonable(payload)), summary, target, actor.id, actor.email, rule.approver_permission,
             EXPIRY_HOURS),
        )
    except UniqueViolation:
        raise ApprovalError("There is already a request waiting for approval for this. Approve, reject or cancel it first.",
                            409) from None
    audit("approval.requested", actor=actor, target=f"approval:{row['id']}", client=client,
          details={"action": action, "summary": summary, "target": target})
    return {"pending": get(row["id"])}


def request_or_raise(action: str, payload: dict, summary: str, actor: StaffActor, **kw) -> dict:
    """
    For route rules: raises PendingApproval so the route answers 202 instead of running. When the
    approval is waived nothing is executed here; the route itself goes ahead.
    """
    outcome = request(action, payload, summary, actor, execute_if_waived=False, **kw)
    if "pending" in outcome:
        raise PendingApproval(outcome["pending"])
    return outcome["result"]


def _jsonable(value):
    return json.loads(json.dumps(value, default=lambda v: float(v) if isinstance(v, Decimal) else str(v)))


def _pending_for_decision(request_id: str, approver: StaffActor) -> tuple[dict, Rule]:
    req = get(request_id)
    if not req:
        raise ApprovalError("Request not found", 404)
    if req["status"] != "pending":
        raise ApprovalError(f"This request is already {req['status']}", 409)
    if req["requested_by"] == approver.id:
        raise ApprovalError("You can't decide your own request. Another staff member has to.", 403)
    if approver.id in (req["payload"].get("beneficiaries") or []):
        raise ApprovalError("This request would give you more access, so someone else has to decide it.", 403)
    if not approver.can(req["approver_permission"]) or not approver.can("approvals.decide"):
        raise ApprovalError("You don't have the permission needed to decide this request", 403)
    return req, RULES[req["action"]]


def approve(request_id: str, approver: StaffActor, note: str | None, client: ClientInfo | None = None) -> dict:
    req, rule = _pending_for_decision(request_id, approver)
    # Claim it atomically so two approvers clicking at once can't both run it
    claimed = fetch_one(
        """
        update approval_requests set status = 'approved', decided_by = %s, decided_by_email = %s,
          decision_note = %s, decided_at = now()
        where id = %s and status = 'pending' and expires_at > now() returning id
        """,
        (approver.id, approver.email, (note or "").strip()[:1000] or None, request_id),
    )
    if not claimed:
        raise ApprovalError("This request is no longer waiting for approval", 409)
    audit("approval.approved", actor=approver, target=f"approval:{request_id}", client=client,
          details={"action": req["action"], "summary": req["summary"], "requested_by": req["requested_by_email"]})
    actor_label = f"{req['requested_by_email']} (approved by {approver.email})"
    try:
        result = rule.execute(req["payload"], actor_label)
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        if not hasattr(exc, "status_code"):
            log.exception("Approved action %s failed", req["action"])
        fetch_one("update approval_requests set status = 'failed', error = %s, executed_at = now() where id = %s "
                  "returning id", (message[:1000], request_id))
        audit("approval.failed", actor=approver, target=f"approval:{request_id}", client=client,
              details={"action": req["action"], "error": message[:500]})
        return get(request_id)
    fetch_one("update approval_requests set status = 'executed', result = %s, executed_at = now() where id = %s "
              "returning id", (Jsonb(_jsonable(result)), request_id))
    audit("approval.executed", actor=approver, target=f"approval:{request_id}", client=client,
          details={"action": req["action"], "summary": req["summary"], "requested_by": req["requested_by_email"]})
    return get(request_id)


def reject(request_id: str, approver: StaffActor, note: str | None, client: ClientInfo | None = None) -> dict:
    req, _ = _pending_for_decision(request_id, approver)
    if not (note or "").strip():
        raise ApprovalError("Say why you are rejecting it")
    row = fetch_one(
        """
        update approval_requests set status = 'rejected', decided_by = %s, decided_by_email = %s,
          decision_note = %s, decided_at = now()
        where id = %s and status = 'pending' returning id
        """,
        (approver.id, approver.email, note.strip()[:1000], request_id),
    )
    if not row:
        raise ApprovalError("This request is no longer waiting for approval", 409)
    audit("approval.rejected", actor=approver, target=f"approval:{request_id}", client=client,
          details={"action": req["action"], "summary": req["summary"], "note": note.strip()[:300]})
    return get(request_id)


def cancel(request_id: str, actor: StaffActor, client: ClientInfo | None = None) -> dict:
    req = get(request_id)
    if not req or req["requested_by"] != actor.id:
        raise ApprovalError("Request not found", 404)
    row = fetch_one("update approval_requests set status = 'cancelled', decided_at = now() "
                    "where id = %s and status = 'pending' returning id", (request_id,))
    if not row:
        raise ApprovalError(f"This request is already {req['status']}", 409)
    audit("approval.cancelled", actor=actor, target=f"approval:{request_id}", client=client,
          details={"action": req["action"], "summary": req["summary"]})
    return get(request_id)


def list_requests(viewer: StaffActor, box: str, status: str | None = None, limit: int = 25, offset: int = 0) -> dict:
    """
    box: "waiting" (pending requests this person may decide), "mine" (requests they made),
    "all" (history, needs approvals.decide or audit.view; otherwise only their own and those they decided).
    """
    expire_stale()
    where, params = ["true"], []
    if box == "waiting":
        decidable = sorted(viewer.permissions) if viewer.can("approvals.decide") else []
        where += ["a.status = 'pending'", "a.requested_by is distinct from %s::uuid",
                  "a.approver_permission = any(%s)", "not coalesce(a.payload -> 'beneficiaries' ? %s, false)"]
        params += [viewer.id, decidable, viewer.id]
    elif box == "mine":
        where.append("a.requested_by = %s")
        params.append(viewer.id)
    else:
        if not (viewer.can("approvals.decide") or viewer.can("audit.view")):
            where.append("(a.requested_by = %s or a.decided_by = %s)")
            params += [viewer.id, viewer.id]
    if status:
        where.append("a.status = %s")
        params.append(status)
    clause = " and ".join(where)
    order = "a.created_at" if box == "waiting" else "a.created_at desc"
    items = fetch_all(f"select {COLUMNS} from approval_requests a where {clause} order by {order}, a.id "
                      f"limit %s offset %s", [*params, limit, offset])
    total = fetch_one(f"select count(*) as n from approval_requests a where {clause}", params)["n"]
    return {"items": [_shape(i) for i in items], "total": total}


def can_view(req: dict, viewer: StaffActor) -> bool:
    return (req["requested_by"] == viewer.id or req["decided_by"] == viewer.id
            or viewer.can("approvals.decide") or viewer.can("audit.view"))


def waiting_count(viewer: StaffActor) -> int:
    if not viewer.can("approvals.decide"):
        return 0
    return list_requests(viewer, "waiting", limit=1)["total"]


# ---------------------------------------------------------------- route rules (checked by core.deps)


def _fmt(field, value) -> str:
    if field is None:
        return json.dumps(value)
    if field.type == "bool":
        return "on" if value else "off"
    if value in ("", None):
        return "(empty)"
    unit = field.unit or ""
    return f"{value:g}{unit}" if unit == "%" and isinstance(value, (int, float)) else f"{value} {unit}".strip()


def _settings_rule(body: dict, actor: StaffActor, path_params: dict, client: ClientInfo | None):
    from services import platform_settings

    values = (body or {}).get("values")
    if not isinstance(values, dict) or any(k not in platform_settings.BY_KEY for k in values):
        return  # the route reports the problem
    try:
        cleaned = {k: platform_settings._clean(platform_settings.BY_KEY[k], v) for k, v in values.items()}
    except platform_settings.SettingsError:
        return
    changes = {k: v for k, v in cleaned.items() if platform_settings.get(k) != v}
    money = [k for k in changes if k in MONEY_SETTING_KEYS]
    if not money:
        return
    parts = []
    for key, value in changes.items():
        f = platform_settings.BY_KEY[key]
        parts.append(f"{f.label}: {_fmt(f, platform_settings.get(key))} to {_fmt(f, value)}")
    request_or_raise("settings.money", {"values": changes, "before": {k: platform_settings.get(k) for k in changes}},
                     "Change settings. " + "; ".join(parts), actor, client=client)


def _settings_reset_rule(body: dict, actor: StaffActor, path_params: dict, client: ClientInfo | None):
    from services import platform_settings

    key = path_params.get("key")
    if key not in MONEY_SETTING_KEYS or key not in platform_settings.BY_KEY:
        return
    f = platform_settings.BY_KEY[key]
    current, default = platform_settings.get(key), f.default()
    if current == default:
        return
    request_or_raise("settings.money_reset", {"key": key, "before": current, "after": default},
                     f"Reset {f.label} from {_fmt(f, current)} to the default {_fmt(f, default)}", actor,
                     target=f"setting:{key}", client=client)


def _payout_rule(body: dict, actor: StaffActor, path_params: dict, client: ClientInfo | None):
    from services import payment_service, platform_settings

    if (body or {}).get("decision") != "approve":
        return
    payout_id = path_params.get("payout_id")
    try:
        payout = fetch_one("select id::text, amount, status, provider_id::text from payouts where id = %s", (payout_id,))
    except Exception:
        return
    if not payout or payout["status"] != "requested":
        return  # the route answers 404/409
    threshold = Decimal(str(platform_settings.get("payout_approval_threshold_etb")))
    if Decimal(str(payout["amount"])) < threshold:
        return
    note = ((body or {}).get("note") or "").strip()
    checks = payment_service.payout_review(payout_id)["checks"]
    blocks = [c for c in checks if c["level"] == "block"]
    if any(c["level"] == "hard" for c in checks) or (blocks and len(note) < 10):
        return  # the route explains what must be checked first
    provider = fetch_one("select display_name from providers where id = %s", (payout["provider_id"],))
    request_or_raise(
        "payout.large", {"payout_id": payout_id, "note": note or None, "amount": float(payout["amount"])},
        f"Pay {float(payout['amount']):,.2f} ETB to {provider['display_name'] if provider else 'a provider'} "
        f"(at or above the {float(threshold):,.2f} ETB second-approval limit)",
        actor, target=f"payout:{payout_id}", client=client,
    )


def _refund_rule(body: dict, actor: StaffActor, path_params: dict, client: ClientInfo | None):
    """Every refund waits for a second staff member. The stored payload has the client's account number encrypted."""
    from services import payment_service

    body = body or {}
    try:
        plan = payment_service.refund_plan(str(path_params.get("tx_ref")), amount=body.get("amount"),
                                           reason=str(body.get("reason") or ""), method=str(body.get("method") or "gateway"),
                                           client_bank=body.get("client_bank") if isinstance(body.get("client_bank"), dict) else None)
    except payment_service.PaymentError:
        return  # the route reports the problem
    request_or_raise("payment.refund", plan["payload"], plan["summary"], actor,
                     target=f"payment:{plan['payload']['tx_ref']}", client=client)


def _data_source_delete_rule(body: dict, actor: StaffActor, path_params: dict, client: ClientInfo | None):
    source = fetch_one("select id::text, name from custom_data_sources where id::text = %s",
                       (str(path_params.get("source_id")),))
    if not source:
        return
    request_or_raise("data_source.delete", {"source_id": source["id"], "name": source["name"]},
                     f"Delete the data source \"{source['name']}\" and its passages in the AI knowledge base",
                     actor, target=f"data_source:{source['id']}", client=client)


ROUTE_RULES: dict[str, Callable[..., None]] = {
    "settings.money": _settings_rule,
    "settings.money_reset": _settings_reset_rule,
    "payout.large": _payout_rule,
    "payment.refund": _refund_rule,
    "data_source.delete": _data_source_delete_rule,
}
