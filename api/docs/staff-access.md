# Staff access

How people who run Compliance Navigator sign in to the admin app, what each of them may do, and
which actions need a second person. Built like AWS IAM: permissions, roles made of permissions,
staff members holding roles, plus maker-checker approval for risky changes and an audit log.

Code: `services/access.py` (permissions, built-in roles, route policy), `services/approvals.py`
(second-person approval), `services/staff_admin.py` (staff and role rules), `auth/staff_service.py`
(sign-in, sessions, links, audit log), `core/deps.py` (`require_admin`, `get_current_staff`),
routes in `api/v1/staff.py` and `api/v1/admin/access.py`. Migrations 025 and 026.

## 1. Two realms, no connection

| | Public site | Admin app (staff) |
|---|---|---|
| Accounts | `users` (role `user` or `agent`) | `staff_users` (status invited, active or disabled) |
| Sessions | `auth_sessions` | `staff_sessions` (12 hours, refresh never extends it) |
| Sign-in | `POST /auth/login` | `POST /staff/auth/login` |
| Refresh cookie | `cn_refresh`, path `/api/v1/auth` | `cn_staff_refresh`, path `/api/v1/staff/auth` |
| Access token | issuer `compliance-navigator` | issuer `compliance-navigator-staff`, claim `realm: "staff"` |
| Who may call admin routes | nobody | staff, per permission |

- A public token on an admin route gets 403 ("Staff access required"); with no token, 401.
- A staff token on any public route gets 401: the public decoder rejects the other issuer and the
  `realm` claim, and the session id isn't in `auth_sessions` anyway.
- The same email can exist in both realms; they are different accounts with different passwords.
- Nothing on the public site grants admin power. `ADMIN_EMAILS` was removed (it promoted anyone who
  registered with a listed email, with no email check). The `users.role` check now allows only
  `user` and `agent`.
- The public site has no link to the admin app, and `/admin` on the public site no longer redirects.
- Lockout matches the public sign-in: 5 failures per email or 25 per network address in 15 minutes
  block sign-in for 15 minutes. A rotated refresh token presented again ends the whole sign-in.

Bootstrap on a fresh install: `uv run python -m scripts.create_staff email "Name"` (asks for the
password) creates a Super admin. Everyone else is invited from the admin app.

## 2. Permissions

Fixed in code (`access.PERMISSIONS`). Each has an area, a plain-language label, a description and a
risk level (low, medium, high, critical). `GET /admin/access/permissions` lists them with the roles
that include each.

| Area | Permissions |
|---|---|
| Dashboard | overview.view |
| Marketplace | providers.view, providers.approve, providers.suspend, providers.edit, providers.view_documents, vetting.view, vetting.manage, vetting.view_criminal_records (critical), hires.view, hires.manage, hires.export (high), reviews.view, reviews.moderate, marketplace.maintenance |
| Payments and payouts | payments.view, payments.export (high), payments.refund (critical), payouts.view, payouts.approve (critical) |
| Organizations | organizations.view, organizations.review, submissions.view, submissions.publish |
| Support and feedback | support.view, support.reply, support.assign, support.export (high), feedback.view, feedback.manage |
| Data and AI | data_sources.view, data_sources.run, data_sources.manage, graph.view, graph.query, graph.edit, catalog.manage, ai.view, ai.manage |
| Platform settings | settings.view, settings.edit (critical) |
| Public users | users.view, users.manage |
| Staff access | staff.view, staff.manage (critical), roles.view, roles.manage (critical), approvals.decide, audit.view |

## 3. Roles

Built-in roles are read-only and their permissions always come from code (`access.BUILTIN_ROLES`),
so they can't drift. They can be duplicated into a custom role and changed there.

| Role | What it covers |
|---|---|
| Super admin | Everything, including roles.manage and staff.manage. New permissions are included automatically. |
| Operations manager | Marketplace, organizations, support, feedback, read-only data and settings; decides approvals in that area. No money moves, no staff or settings changes. |
| Finance | Payments, payouts (including approving), reads settings; decides payout approvals. |
| Compliance reviewer | Providers, vetting including criminal records, private documents, organizations and submissions. |
| Support agent | Support desk, feedback, reads providers, hires and public users. |
| Content editor | Knowledge graph, MESOB catalog, data sources, AI assistant. |
| Viewer | Every `.view` permission except staff and the audit log. No private documents or criminal records. |

Custom roles: created with any permissions the creator holds. A staff member's permissions are the
union of their roles.

## 4. Enforcement

Every admin route depends on `require_admin` (unchanged in the route files). It:

1. signs in the staff member from the bearer token (staff realm only);
2. looks up `METHOD /path` in `access.ROUTE_POLICY` using the route template FastAPI matched;
3. **denies by default**: a route with no entry answers 403 even for a Super admin, and logs an error;
4. checks the permission. A few entries pick a stricter permission from one body field
   (provider review with `action: suspend` needs providers.suspend);
5. runs the entry's approval rule, if any (section 5);
6. after the route runs, writes the outcome of every change (not reads) to the audit log.

It returns a `StaffActor` with `.id`, `.email`, `.fullname`, `.permissions` and `.can(perm)` /
`.has(perm)`, so existing code (`actor=user.email`) keeps working. Route code that needs an extra
check calls `access.require(actor, "perm")`, which raises 403.

`tests/test_staff_access.py::test_every_admin_route_has_a_policy_and_known_permission` fails when an
`/admin` route has no entry, names an unknown permission, or doesn't depend on `require_admin`.

## 5. Second-person approval

Stored in `approval_requests` with the exact payload. Nothing runs until another staff member
approves; then the stored payload is executed on the server (never anything sent with the approval).

| Action | When | Approver needs |
|---|---|---|
| settings.money | a settings change that touches commission, VAT rate, VAT registration, minimum payout, payout approval limit, TIN or VAT number (the whole batch waits) | settings.edit |
| settings.money_reset | resetting one of those to its default | settings.edit |
| payout.large | approving a payout at or above the "Second approval for payouts from" setting (default 50,000 ETB) | payouts.approve |
| payment.refund | every refund, full or partial, through Chapa or by bank transfer | payments.refund |
| data_source.delete | deleting a staff-added data source | data_sources.manage |
| staff.create | inviting a staff member | staff.manage |
| staff.set_roles | changing a staff member's roles | staff.manage |
| staff.super_admin | inviting with, granting or removing Super admin | roles.manage |
| staff.disable / staff.enable | disabling or re-enabling a staff member | staff.manage |
| role.update | changing a custom role's permissions | roles.manage |
| role.delete | deleting a custom role someone holds | roles.manage |

Not gated: creating a role (nobody holds it yet), renaming a role, resending or revoking an
invitation, sending a password reset link (it goes to the person's own email), signing someone out.

Rules:
- The approver must hold `approvals.decide` and the action's approver permission.
- Nobody approves their own request, or a request that would raise their own access.
- A request expires after 72 hours. One open request per target (a payout, a staff member, a role).
- Approving claims the request atomically, so two approvers can't run it twice. If the action
  fails (for example the payout was already decided), the request is marked failed with the reason.
- The requester can cancel a pending request. A rejection needs a reason.
- **Waiver:** when no other active staff member could approve (for example the only Super admin
  inviting the first teammate), the action runs at once and the audit log records
  `approval.waived`. Product owner: say if you would rather block in that case.
- Routes with a rule answer **202** with `{"message": "approval_required", "payload": {"approval": ...}}`
  instead of running. The staff access routes return `{"approval": ...}` or `{"waived": true}`.

## 6. Hierarchy

- Super admins manage roles and staff, and are the only ones who can change another Super admin.
- At least one active Super admin always exists: disabling or demoting the last one is refused, at
  request time and again when the approval runs.
- Nobody changes their own roles or status, and nobody adds permissions to a role they hold.
- You can only grant permissions you hold (custom role permissions, or roles given to staff).
- Built-in roles are read-only.

## 7. Staff lifecycle

1. A Super admin (or anyone with staff.manage) invites email + name + roles. After approval the
   person gets an email with their sign-in email and a one-time link to
   `ADMIN_BASE_URL/accept-invite?token=...` (48 hours, single use, only the newest link works).
   Without SMTP the email goes to the API log and "Copy invite link" (resend) shows the link.
2. They choose a password; the account becomes active.
3. Forgotten password: "Forgot password" on the sign-in page, or a reset link sent by staff
   (60 minutes, single use). Using it signs out every session.
4. Disable signs them out at once and voids open links. Enable restores the same roles.
5. My account: change password (signs out other sessions), list and end sessions, own activity.

Two-factor sign-in (TOTP) is not built yet.

## 8. Audit log

`staff_audit_log`: actor, action, target, details, network address, browser, time. Written for
sign-ins (success, failure, lockout, token reuse), sign-outs, password changes and links, every
admin change with its outcome (the permission key is the action, with method, path, a copy of the
request body with passwords and account numbers hidden, and the status), refused changes
(`access.denied`), and every approval step (requested, waived, approved, rejected, cancelled,
expired, executed, failed). `GET /admin/access/audit` filters by actor, action prefix, target and
dates, with paging.

## 9. Threat model

| Threat | Defence |
|---|---|
| A public account gains admin power (ADMIN_EMAILS, role edit, SQL check) | Separate realm; ADMIN_EMAILS removed; role check excludes admin; admin role not offered |
| Stolen public token used on admin routes | Different issuer and realm claim; staff session lookup |
| Stolen staff refresh cookie | httpOnly, own path, rotation with reuse detection, 12 hour hard expiry |
| Password guessing | Lockout per email and per network; bcrypt |
| New admin route forgotten | Deny by default plus the coverage test |
| One insider moves money or changes tax | Second approval, executed from the stored payload, audited |
| Insider gives themselves more access | No self changes, no granting what you lack, beneficiaries can't approve |
| Locking everyone out | Last Super admin can't be disabled or demoted |
| Invite link intercepted | Single use, 48 hours, newest only, voided on disable |
| Approval replay or double execution | Atomic claim, status machine, one open request per target |

Known gaps: no two-factor sign-in; no IP allow-list; the waiver above; staff notifications (the
old "notify every admin" calls in payment and review services now reach nobody, the admin app shows
the queues instead).

## 10. Migration plan

- 025 creates the tables and the seven built-in roles.
- 026 copies every `users` row with role admin into `staff_users` with the same id and password
  hash (so a password set by SQL still works), makes them Super admins, sets their public role to
  `user`, narrows the role check, and points support ticket assignees at staff.
- The admin app signs in only through `/staff/auth/*`. Staff who were signed in must sign in again.
