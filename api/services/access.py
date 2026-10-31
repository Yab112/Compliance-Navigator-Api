"""
Who on staff may do what.

Three layers, like AWS IAM:
  permissions  fixed in code below (PERMISSIONS); each guards one kind of action
  roles        named sets of permissions; built-in ones are defined here, custom ones live in the database
  staff        each staff member holds one or more roles; their permissions are the union

Every admin route is mapped to one permission in ROUTE_POLICY. core.deps.require_admin looks the
route up on every request and refuses anything not listed (deny by default), so a new admin route
does nothing until someone decides who may call it. tests/test_staff_access.py fails when a route
has no entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from services.db import fetch_all, fetch_one

RISK_LEVELS = ("low", "medium", "high", "critical")


@dataclass(frozen=True)
class Permission:
    key: str
    area: str
    label: str
    description: str
    risk: str  # low | medium | high | critical


AREAS = [
    ("dashboard", "Dashboard"),
    ("marketplace", "Marketplace"),
    ("money", "Payments and payouts"),
    ("organizations", "Organizations"),
    ("support", "Support and feedback"),
    ("data", "Data and AI"),
    ("platform", "Platform settings"),
    ("people", "Public users"),
    ("access", "Staff access"),
]

PERMISSIONS: list[Permission] = [
    Permission("overview.view", "dashboard", "See the dashboard", "Totals and charts on the overview page.", "low"),

    Permission("providers.view", "marketplace", "See providers", "Provider list, profiles and vetting status.", "low"),
    Permission("providers.approve", "marketplace", "Approve providers",
               "Approve, reject or renew a provider's listing and decide on licences.", "high"),
    Permission("providers.suspend", "marketplace", "Suspend providers", "Take a provider off the marketplace or bring them back.", "high"),
    Permission("providers.edit", "marketplace", "Edit provider profiles", "Change a provider's public profile on their behalf.", "medium"),
    Permission("providers.view_documents", "marketplace", "Open private documents",
               "Open ID cards, licences and other private uploads.", "high"),
    Permission("vetting.view", "marketplace", "See vetting checks", "The checks run on a provider before approval.", "medium"),
    Permission("vetting.manage", "marketplace", "Record vetting checks", "Record and update the results of vetting checks.", "high"),
    Permission("vetting.view_criminal_records", "marketplace", "See criminal record checks",
               "Read the result and details of police clearance checks. Highly sensitive personal data.", "critical"),
    Permission("hires.view", "marketplace", "See hires", "Hires, complaints and their history.", "low"),
    Permission("hires.manage", "marketplace", "Manage hires", "Reassign hires, change their status and decide complaints.", "medium"),
    Permission("hires.export", "marketplace", "Export hires",
               "Download the hires list as a spreadsheet, with clients' phone numbers.", "high"),
    Permission("reviews.view", "marketplace", "See reviews", "Reviews and requests to change them.", "low"),
    Permission("reviews.moderate", "marketplace", "Moderate reviews", "Hide or restore reviews and decide change requests.", "medium"),
    Permission("marketplace.maintenance", "marketplace", "Remove demo data", "Delete the sample providers and hires.", "high"),

    Permission("payments.view", "money", "See payments", "Client payments, commission and VAT.", "medium"),
    Permission("payments.export", "money", "Export payments",
               "Download the payments list as a spreadsheet, with client and provider names.", "high"),
    Permission("payments.refund", "money", "Refund clients",
               "Give a client all or part of a payment back. Another staff member must approve each refund.", "critical"),
    Permission("payouts.view", "money", "See payouts", "Withdrawal requests and the checks on them.", "medium"),
    Permission("payouts.approve", "money", "Approve payouts", "Send or refuse money to a provider's bank account.", "critical"),

    Permission("organizations.view", "organizations", "See organizations", "Registered organizations and their details.", "low"),
    Permission("organizations.review", "organizations", "Review organizations", "Approve or reject an organization's registration.", "high"),
    Permission("submissions.view", "organizations", "See service submissions", "Changes organizations propose to their services.", "low"),
    Permission("submissions.publish", "organizations", "Publish service submissions",
               "Approve a submission so it goes live for the public.", "high"),

    Permission("support.view", "support", "See the support desk", "Tickets and conversations people started.", "medium"),
    Permission("support.reply", "support", "Reply to tickets", "Write to people and add internal notes.", "medium"),
    Permission("support.export", "support", "Export tickets",
               "Download the ticket list as a spreadsheet, with people's contact details.", "high"),
    Permission("support.assign", "support", "Assign and triage tickets", "Change assignee, priority, queue and status.", "low"),
    Permission("feedback.view", "support", "See feedback", "Reports people send about wrong information.", "low"),
    Permission("feedback.manage", "support", "Resolve feedback", "Mark feedback resolved or dismissed.", "low"),

    Permission("data_sources.view", "data", "See data sources", "Data sources, their runs and background tasks.", "low"),
    Permission("data_sources.run", "data", "Run data sources", "Run, pause and resume imports.", "medium"),
    Permission("data_sources.manage", "data", "Manage data sources", "Add, edit and delete staff-added sources and start imports.", "high"),
    Permission("graph.view", "data", "See the knowledge graph", "Graph counts, diagram and documents.", "low"),
    Permission("graph.query", "data", "Query the graph", "Run read-only queries in the graph console.", "medium"),
    Permission("graph.edit", "data", "Edit the knowledge graph", "Change requirement documents in the graph.", "high"),
    Permission("catalog.manage", "data", "Manage the MESOB catalog", "Upload references and rebuild the catalog and search index.", "high"),
    Permission("ai.view", "data", "See the AI assistant", "Model status, test questions and search the knowledge base.", "low"),
    Permission("ai.manage", "data", "Manage the AI assistant", "Switch models, label messages, retrain and activate versions.", "high"),

    Permission("settings.view", "platform", "See platform settings", "Business rules and their change history.", "low"),
    Permission("settings.edit", "platform", "Change platform settings",
               "Change business rules. Money and tax changes also need a second person.", "critical"),

    Permission("users.view", "people", "See public users", "Customer and provider accounts and sign-in activity.", "medium"),
    Permission("users.manage", "people", "Manage public users",
               "Deactivate accounts, sign them out and issue password reset links.", "high"),

    Permission("staff.view", "access", "See staff", "Staff members, their roles, sessions and recent actions.", "medium"),
    Permission("staff.manage", "access", "Manage staff",
               "Invite staff, change their roles, disable them and reset their passwords.", "critical"),
    Permission("roles.view", "access", "See roles", "Roles and the permissions in each.", "low"),
    Permission("roles.manage", "access", "Manage roles",
               "Create and edit roles, and grant or remove Super admin. Needs a second person.", "critical"),
    Permission("approvals.decide", "access", "Decide approvals",
               "Approve or reject requests other staff made, within your own permissions.", "high"),
    Permission("audit.view", "access", "See the audit log", "Everything staff did, with time and network address.", "high"),
]

BY_KEY = {p.key: p for p in PERMISSIONS}
ALL = frozenset(BY_KEY)

_READ_ONLY = frozenset(p.key for p in PERMISSIONS if p.key.endswith(".view"))

# Built-in roles: their permissions always come from here, so code changes reach them at once
BUILTIN_ROLES: dict[str, frozenset[str]] = {
    "super_admin": ALL,
    "operations_manager": frozenset({
        "overview.view", "providers.view", "providers.approve", "providers.suspend", "providers.edit",
        "providers.view_documents", "vetting.view", "vetting.manage", "hires.view", "hires.manage",
        "reviews.view", "reviews.moderate", "payments.view", "payouts.view", "organizations.view",
        "organizations.review", "submissions.view", "submissions.publish", "support.view", "support.reply",
        "support.assign", "support.export", "feedback.view", "feedback.manage", "data_sources.view", "graph.view",
        "hires.export",
        "ai.view", "settings.view", "users.view", "staff.view", "roles.view", "approvals.decide",
    }),
    "finance": frozenset({
        "overview.view", "providers.view", "hires.view", "payments.view", "payments.export", "payments.refund",
        "payouts.view", "payouts.approve", "settings.view", "approvals.decide",
    }),
    "compliance_reviewer": frozenset({
        "overview.view", "providers.view", "providers.approve", "providers.suspend", "providers.view_documents",
        "vetting.view", "vetting.manage", "vetting.view_criminal_records", "hires.view", "reviews.view",
        "organizations.view", "organizations.review", "submissions.view", "submissions.publish", "approvals.decide",
    }),
    "support_agent": frozenset({
        "overview.view", "providers.view", "hires.view", "reviews.view", "organizations.view", "support.view",
        "support.reply", "support.assign", "feedback.view", "feedback.manage", "users.view",
    }),
    "content_editor": frozenset({
        "overview.view", "data_sources.view", "data_sources.run", "data_sources.manage", "graph.view",
        "graph.query", "graph.edit", "catalog.manage", "ai.view", "ai.manage", "feedback.view",
        "submissions.view", "organizations.view", "approvals.decide",
    }),
    "viewer": _READ_ONLY - {"staff.view", "audit.view"},
}
SUPER_ADMIN = "super_admin"


# ---------------------------------------------------------------- route policy


@dataclass(frozen=True)
class Policy:
    permission: str
    # Some routes do different things depending on one field of the JSON body
    # (approve vs suspend); the mapping picks a stricter permission for those values.
    body_field: str | None = None
    by_value: dict[str, str] = field(default_factory=dict)
    # Name of an approval rule in services/approvals.py checked before the route runs
    approval: str | None = None


P = Policy
# "METHOD /path" with the /api/v1 prefix left off, exactly as FastAPI declares the route
ROUTE_POLICY: dict[str, Policy] = {
    # dashboard
    "GET /admin/overview": P("overview.view"),
    # marketplace
    "GET /admin/marketplace/stats": P("providers.view"),
    "GET /admin/marketplace/providers": P("providers.view"),
    "GET /admin/marketplace/providers/{provider_id}": P("providers.view"),
    "POST /admin/marketplace/providers/{provider_id}/review": P(
        "providers.approve", "action", {"suspend": "providers.suspend", "reinstate": "providers.suspend"}),
    "POST /admin/marketplace/providers/{provider_id}/license": P("providers.approve"),
    "PATCH /admin/marketplace/providers/{provider_id}": P("providers.edit"),
    # approve or refuse a held name, legal name, TIN, trade licence or VAT change from an approved provider
    "POST /admin/marketplace/providers/{provider_id}/changes/{change_id}": P("providers.approve"),
    "GET /admin/files": P("providers.view_documents"),
    "GET /admin/marketplace/providers/{provider_id}/documents": P("vetting.view"),
    "GET /admin/marketplace/providers/{provider_id}/documents/{document_id}/file": P("providers.view_documents"),
    "POST /admin/marketplace/providers/{provider_id}/documents/{document_id}/review": P("vetting.manage"),
    "POST /admin/marketplace/providers/{provider_id}/references/{reference_id}": P("vetting.manage"),
    "POST /admin/marketplace/providers/{provider_id}/guarantor/{guarantor_id}": P("vetting.manage"),
    "GET /admin/marketplace/engagements": P("hires.view"),
    "GET /admin/marketplace/engagements.csv": P("hires.export"),
    "GET /admin/marketplace/engagements/{engagement_id}": P("hires.view"),
    "GET /admin/marketplace/engagements/{engagement_id}/candidates": P("hires.manage"),
    "PATCH /admin/marketplace/engagements/{engagement_id}": P("hires.manage"),
    "POST /admin/marketplace/engagements/{engagement_id}/dispute": P("hires.manage"),
    "GET /admin/marketplace/reviews": P("reviews.view"),
    "POST /admin/marketplace/reviews/{review_id}/moderate": P("reviews.moderate"),
    "GET /admin/marketplace/review-changes": P("reviews.view"),
    "POST /admin/marketplace/review-changes/{change_id}": P("reviews.moderate"),
    "GET /admin/marketplace/samples": P("providers.view"),
    "POST /admin/marketplace/samples/purge": P("marketplace.maintenance"),
    # money
    "GET /admin/marketplace/payments": P("payments.view"),
    "GET /admin/marketplace/payments.csv": P("payments.export"),
    # asks the gateway again about a pending payment; it only records what the gateway says
    "POST /admin/marketplace/payments/{tx_ref}/verify": P("payments.view"),
    "POST /admin/marketplace/payments/{tx_ref}/refund": P("payments.refund", approval="payment.refund"),
    "GET /admin/marketplace/refunds": P("payments.view"),
    "POST /admin/marketplace/refunds/{refund_id}": P("payments.refund"),
    "GET /admin/marketplace/payouts": P("payouts.view"),
    "GET /admin/marketplace/payouts/{payout_id}": P("payouts.view"),
    "POST /admin/marketplace/payouts/{payout_id}": P("payouts.approve", approval="payout.large"),
    # Payment health: how Chapa is answering, its errors, and money that needs a person. The check asks
    # Chapa for its bank list once; it moves no money.
    "GET /admin/marketplace/payment-health": P("payments.view"),
    "GET /admin/marketplace/payment-health/errors": P("payments.view"),
    "POST /admin/marketplace/payment-health/check": P("payments.view"),
    # organizations
    "GET /admin/organizations/stats": P("organizations.view"),
    "GET /admin/organizations": P("organizations.view"),
    "GET /admin/organizations/export.csv": P("organizations.view"),
    "GET /admin/organizations/{org_id}": P("organizations.view"),
    "POST /admin/organizations/{org_id}/review": P("organizations.review"),
    "GET /admin/organizations-freshness": P("organizations.view"),
    "GET /admin/submissions": P("submissions.view"),
    "GET /admin/submissions/{revision_id}": P("submissions.view"),
    "POST /admin/submissions/{revision_id}/review": P("submissions.publish"),
    # support and feedback
    "GET /admin/support/summary": P("support.view"),
    "GET /admin/support/tickets": P("support.view"),
    "GET /admin/support/tickets/{ticket_id}": P("support.view"),
    "POST /admin/support/tickets/{ticket_id}/messages": P("support.reply"),
    "PATCH /admin/support/tickets/{ticket_id}": P("support.assign"),
    "GET /admin/support/tickets.csv": P("support.export"),
    "GET /admin/support/tickets/{ticket_id}/customer": P("support.view"),
    "GET /admin/support/replies": P("support.view"),
    "POST /admin/support/replies": P("support.assign"),
    "PUT /admin/support/replies/{reply_id}": P("support.assign"),
    "DELETE /admin/support/replies/{reply_id}": P("support.assign"),
    "GET /admin/feedback": P("feedback.view"),
    "PATCH /admin/feedback/{flag_id}": P("feedback.manage"),
    # data sources, catalog, graph, AI
    "GET /admin/data-sources": P("data_sources.view"),
    "GET /admin/data-sources/runs": P("data_sources.view"),
    "POST /admin/data-sources/runs/{run_id}/mark-failed": P("data_sources.run"),
    "POST /admin/data-sources/{source}/run": P("data_sources.run"),
    "POST /admin/data-sources/{source}/pause": P("data_sources.run"),
    "POST /admin/data-sources/{source}/resume": P("data_sources.run"),
    "GET /admin/data-sources/custom/{source_id}": P("data_sources.view"),
    "POST /admin/data-sources/custom": P("data_sources.manage"),
    "PUT /admin/data-sources/custom/{source_id}": P("data_sources.manage"),
    "DELETE /admin/data-sources/custom/{source_id}": P("data_sources.manage", approval="data_source.delete"),
    "GET /admin/tasks/{task_id}": P("data_sources.view"),
    "POST /admin/jobs/scrape": P("catalog.manage"),
    "POST /admin/jobs/ingest": P("catalog.manage"),
    "POST /admin/jobs/stale-check": P("catalog.manage"),
    "POST /admin/references/upload": P("catalog.manage"),
    "POST /admin/rag/ingest": P("catalog.manage"),
    "POST /admin/rag/search": P("ai.view"),
    "GET /admin/graph/stats": P("graph.view"),
    "GET /admin/graph/view": P("graph.view"),
    "GET /admin/graph/documents": P("graph.view"),
    "GET /admin/graph/documents/{doc_id}": P("graph.view"),
    "PATCH /admin/graph/documents/{doc_id}": P("graph.edit"),
    "GET /admin/graph/institutions": P("graph.view"),
    "POST /admin/graph/query": P("graph.query"),
    "GET /admin/ai/status": P("ai.view"),
    "PUT /admin/ai/settings": P("ai.manage"),
    "POST /admin/ai/test": P("ai.view"),
    "POST /admin/ai/search": P("ai.view"),
    "GET /admin/assistant/model": P("ai.view"),
    "GET /admin/assistant/turns": P("ai.view"),
    "POST /admin/assistant/turns/{turn_id}/label": P("ai.manage"),
    "POST /admin/assistant/retrain": P("ai.manage"),
    "POST /admin/assistant/activate/{version}": P("ai.manage"),
    # platform settings
    "GET /admin/settings": P("settings.view"),
    "GET /admin/settings/history": P("settings.view"),
    "PATCH /admin/settings": P("settings.edit", approval="settings.money"),
    "DELETE /admin/settings/{key}": P("settings.edit", approval="settings.money_reset"),
    # public users
    "GET /admin/users": P("users.view"),
    "PATCH /admin/users/{user_id}": P("users.manage"),
    "POST /admin/users/{user_id}/revoke-sessions": P("users.manage"),
    "POST /admin/users/{user_id}/reset-link": P("users.manage"),
    "GET /admin/auth/events": P("users.view"),
    "GET /admin/auth/summary": P("users.view"),
    # staff access (api/v1/admin/access.py); approvals there are decided inside the route
    "GET /admin/access/permissions": P("roles.view"),
    "GET /admin/access/roles": P("roles.view"),
    "GET /admin/access/roles/{role_id}": P("roles.view"),
    "POST /admin/access/roles": P("roles.manage"),
    "PUT /admin/access/roles/{role_id}": P("roles.manage"),
    "DELETE /admin/access/roles/{role_id}": P("roles.manage"),
    "GET /admin/access/staff": P("staff.view"),
    "GET /admin/access/staff/{staff_id}": P("staff.view"),
    "GET /admin/access/staff/{staff_id}/sessions": P("staff.view"),
    "POST /admin/access/staff": P("staff.manage"),
    "PATCH /admin/access/staff/{staff_id}": P("staff.manage"),
    "PUT /admin/access/staff/{staff_id}/roles": P("staff.manage"),
    "POST /admin/access/staff/{staff_id}/disable": P("staff.manage"),
    "POST /admin/access/staff/{staff_id}/enable": P("staff.manage"),
    "POST /admin/access/staff/{staff_id}/resend-invite": P("staff.manage"),
    "POST /admin/access/staff/{staff_id}/revoke-invite": P("staff.manage"),
    "POST /admin/access/staff/{staff_id}/reset-password": P("staff.manage"),
    "POST /admin/access/staff/{staff_id}/sign-out": P("staff.manage"),
    "GET /admin/access/audit": P("audit.view"),
    # Every signed-in staff member sees approvals they asked for; deciding is checked per request
    "GET /admin/access/approvals": P("*"),
    "GET /admin/access/approvals/{request_id}": P("*"),
    "POST /admin/access/approvals/{request_id}/approve": P("approvals.decide"),
    "POST /admin/access/approvals/{request_id}/reject": P("approvals.decide"),
    "POST /admin/access/approvals/{request_id}/cancel": P("*"),
}
del P

API_PREFIX = "/api/v1"


def policy_key(method: str, route_path: str) -> str:
    path = route_path.removeprefix(API_PREFIX)
    return f"{method.upper()} {path}"


def policy_for(method: str, route_path: str) -> Policy | None:
    return ROUTE_POLICY.get(policy_key(method, route_path))


def require(actor, permission: str) -> None:
    """For route code that needs an extra check beyond its ROUTE_POLICY entry. Raises 403."""
    from fastapi import HTTPException

    if not getattr(actor, "permissions", None) or permission not in actor.permissions:
        perm = BY_KEY.get(permission)
        raise HTTPException(status_code=403, detail=f"You don't have permission for this ({perm.label if perm else permission})")


# ---------------------------------------------------------------- who holds what


def role_permissions(role: dict) -> frozenset[str]:
    """Permissions of one role row (needs builtin_key and id)."""
    if role.get("builtin_key"):
        return BUILTIN_ROLES.get(role["builtin_key"], frozenset())
    rows = fetch_all("select permission from staff_role_permissions where role_id = %s", (role["id"],))
    return frozenset(r["permission"] for r in rows if r["permission"] in BY_KEY)


def staff_roles(staff_id: str) -> list[dict]:
    return fetch_all(
        """
        select r.id::text, r.name, r.builtin_key from staff_user_roles ur join staff_roles r on r.id = ur.role_id
        where ur.staff_id = %s order by r.builtin_key is null, r.name
        """,
        (staff_id,),
    )


def staff_permissions(staff_id: str) -> frozenset[str]:
    """The union of the staff member's roles. Built-in roles from code, custom roles from the table."""
    rows = fetch_all(
        """
        select r.builtin_key, p.permission
        from staff_user_roles ur join staff_roles r on r.id = ur.role_id
        left join staff_role_permissions p on p.role_id = r.id and r.builtin_key is null
        where ur.staff_id = %s
        """,
        (staff_id,),
    )
    perms: set[str] = set()
    for r in rows:
        if r["builtin_key"]:
            perms |= BUILTIN_ROLES.get(r["builtin_key"], frozenset())
        elif r["permission"] in BY_KEY:
            perms.add(r["permission"])
    return frozenset(perms)


def is_super_admin(staff_id: str) -> bool:
    return fetch_one(
        """
        select 1 as x from staff_user_roles ur join staff_roles r on r.id = ur.role_id
        where ur.staff_id = %s and r.builtin_key = 'super_admin'
        """,
        (staff_id,),
    ) is not None


def active_super_admin_ids() -> list[str]:
    return [r["id"] for r in fetch_all(
        """
        select s.id::text from staff_users s
        join staff_user_roles ur on ur.staff_id = s.id join staff_roles r on r.id = ur.role_id
        where r.builtin_key = 'super_admin' and s.status = 'active'
        """
    )]


def holders_of(permission: str) -> list[dict]:
    """Active staff who hold a permission through any role (for counting possible approvers)."""
    builtin = [k for k, perms in BUILTIN_ROLES.items() if permission in perms]
    return fetch_all(
        """
        select distinct s.id::text, s.email from staff_users s
        join staff_user_roles ur on ur.staff_id = s.id join staff_roles r on r.id = ur.role_id
        left join staff_role_permissions p on p.role_id = r.id
        where s.status = 'active' and (r.builtin_key = any(%s) or (r.builtin_key is null and p.permission = %s))
        """,
        (builtin, permission),
    )


def catalogue() -> list[dict]:
    """Permissions grouped by area, each with the roles that include it."""
    roles = fetch_all("select id::text, name, builtin_key from staff_roles order by builtin_key is null, name")
    custom = fetch_all("select role_id::text, permission from staff_role_permissions")
    holders: dict[str, list[str]] = {}
    for role in roles:
        perms = BUILTIN_ROLES.get(role["builtin_key"], frozenset()) if role["builtin_key"] else \
            {c["permission"] for c in custom if c["role_id"] == role["id"]}
        for perm in perms:
            holders.setdefault(perm, []).append(role["name"])
    return [
        {
            "key": key, "title": title,
            "permissions": [
                {"key": p.key, "label": p.label, "description": p.description, "risk": p.risk,
                 "roles": holders.get(p.key, [])}
                for p in PERMISSIONS if p.area == key
            ],
        }
        for key, title in AREAS
    ]
