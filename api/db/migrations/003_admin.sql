-- Admin dashboard: data source run history, user feedback queue, runtime settings.

create table if not exists data_source_runs (
  id uuid primary key default gen_random_uuid(),
  source text not null,
  status text not null default 'running'
    check (status in ('running', 'success', 'failed')),
  triggered_by text,
  stats jsonb not null default '{}',
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create index if not exists data_source_runs_source_idx on data_source_runs (source, started_at desc);

-- "This information is wrong" flags from users; surfaced in the admin queue.
create table if not exists feedback_flags (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users (id) on delete set null,
  target_type text not null,      -- document | gov_service | office | agent | other
  target_id text,
  message text not null,
  status text not null default 'open' check (status in ('open', 'resolved', 'dismissed')),
  resolution_note text,
  resolved_by text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create index if not exists feedback_flags_status_idx on feedback_flags (status);

create table if not exists app_settings (
  key text primary key,
  value jsonb not null,
  updated_by text,
  updated_at timestamptz not null default now()
);
