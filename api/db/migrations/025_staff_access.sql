-- Staff access: a separate sign-in realm for the admin app, roles made of permissions,
-- second-person approval for risky actions, and an audit log of everything staff do.
-- See docs/staff-access.md.

create table if not exists staff_users (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  fullname text not null default '',
  password_hash text,
  status text not null default 'invited' check (status in ('invited', 'active', 'disabled')),
  must_change_password boolean not null default false,
  password_changed_at timestamptz,
  last_login_at timestamptz,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists staff_users_email_key on staff_users (lower(email));

-- Same design as auth_sessions: one row per refresh token, rotated on every refresh
create table if not exists staff_sessions (
  id uuid primary key default gen_random_uuid(),
  staff_id uuid not null references staff_users (id) on delete cascade,
  family_id uuid not null,
  refresh_hash text not null unique,
  user_agent text,
  ip text,
  created_at timestamptz not null default now(),
  last_used_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  revoked_reason text,
  replaced_by uuid
);
create index if not exists staff_sessions_staff_idx on staff_sessions (staff_id) where revoked_at is null;
create index if not exists staff_sessions_family_idx on staff_sessions (family_id);

-- One-time links: invitations (set your first password) and password resets
create table if not exists staff_tokens (
  id uuid primary key default gen_random_uuid(),
  staff_id uuid not null references staff_users (id) on delete cascade,
  kind text not null check (kind in ('invite', 'reset')),
  token_hash text not null unique,
  created_by text not null,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists staff_tokens_staff_idx on staff_tokens (staff_id, kind) where used_at is null;

-- Built-in roles carry a builtin_key; their permissions come from code (services/access.py)
-- so they can never drift. Custom roles keep theirs in staff_role_permissions.
create table if not exists staff_roles (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text not null default '',
  builtin_key text unique,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists staff_roles_name_key on staff_roles (lower(name));

create table if not exists staff_role_permissions (
  role_id uuid not null references staff_roles (id) on delete cascade,
  permission text not null,
  primary key (role_id, permission)
);

create table if not exists staff_user_roles (
  staff_id uuid not null references staff_users (id) on delete cascade,
  role_id uuid not null references staff_roles (id) on delete cascade,
  granted_by text,
  granted_at timestamptz not null default now(),
  primary key (staff_id, role_id)
);
create index if not exists staff_user_roles_role_idx on staff_user_roles (role_id);

insert into staff_roles (name, description, builtin_key) values
  ('Super admin', 'Everything, including managing staff, roles and approvals.', 'super_admin'),
  ('Operations manager', 'Runs the day to day: marketplace, organizations, support and feedback. No money, staff or settings changes.', 'operations_manager'),
  ('Finance', 'Payments and payouts, and reads the money settings.', 'finance'),
  ('Compliance reviewer', 'Vets providers (including criminal record checks) and reviews organizations and their services.', 'compliance_reviewer'),
  ('Support agent', 'Answers the support desk and the feedback queue.', 'support_agent'),
  ('Content editor', 'Keeps the knowledge graph, MESOB catalog, data sources and AI assistant up to date.', 'content_editor'),
  ('Viewer', 'Read-only access to every page except private documents, criminal records and the audit log.', 'viewer')
on conflict (builtin_key) do nothing;

-- Maker-checker: a risky action is stored here and only runs when a second person approves it
create table if not exists approval_requests (
  id uuid primary key default gen_random_uuid(),
  action text not null,
  payload jsonb not null default '{}'::jsonb,
  summary text not null,
  target text,
  requested_by uuid references staff_users (id) on delete set null,
  requested_by_email text not null,
  approver_permission text not null,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'cancelled', 'expired', 'executed', 'failed')),
  decided_by uuid references staff_users (id) on delete set null,
  decided_by_email text,
  decision_note text,
  result jsonb,
  error text,
  created_at timestamptz not null default now(),
  decided_at timestamptz,
  executed_at timestamptz,
  expires_at timestamptz not null
);
create index if not exists approval_requests_status_idx on approval_requests (status, created_at desc);
create index if not exists approval_requests_requester_idx on approval_requests (requested_by, created_at desc);
-- Only one open request per thing (a payout, a setting batch, a staff member...)
create unique index if not exists approval_requests_open_target_key
  on approval_requests (action, target) where status = 'pending' and target is not null;

create table if not exists staff_audit_log (
  id bigserial primary key,
  actor_id uuid,
  actor_email text,
  action text not null,
  target text,
  details jsonb not null default '{}'::jsonb,
  ip text,
  user_agent text,
  created_at timestamptz not null default now()
);
create index if not exists staff_audit_created_idx on staff_audit_log (created_at desc, id desc);
create index if not exists staff_audit_actor_idx on staff_audit_log (actor_id, created_at desc);
create index if not exists staff_audit_action_idx on staff_audit_log (action, created_at desc);
create index if not exists staff_audit_email_idx on staff_audit_log (lower(actor_email), created_at desc);
create index if not exists staff_audit_ip_idx on staff_audit_log (ip, created_at desc);
