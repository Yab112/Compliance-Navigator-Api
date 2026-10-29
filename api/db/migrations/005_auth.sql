-- Self-hosted auth: refresh-token sessions, an audit log, and password-reset links.

alter table users add column if not exists password_changed_at timestamptz;

-- One row per refresh token. Rotation revokes the old row and adds a new one in the
-- same family; presenting a rotated token again revokes the whole family.
create table if not exists auth_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
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
create index if not exists auth_sessions_user_idx on auth_sessions (user_id) where revoked_at is null;
create index if not exists auth_sessions_family_idx on auth_sessions (family_id);

create table if not exists auth_events (
  id bigserial primary key,
  user_id uuid references users (id) on delete cascade,
  email text,
  event text not null,
  ip text,
  user_agent text,
  detail text,
  created_at timestamptz not null default now()
);
create index if not exists auth_events_email_idx on auth_events (lower(email), created_at desc);
create index if not exists auth_events_ip_idx on auth_events (ip, created_at desc);
create index if not exists auth_events_user_idx on auth_events (user_id, created_at desc);

create table if not exists password_reset_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  token_hash text not null unique,
  created_by text not null,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
