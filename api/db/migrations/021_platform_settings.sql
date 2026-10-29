-- Business rules staff change from the admin app, instead of redeploying with a new .env.
-- A missing row means "use the default" (the .env value or the built-in one).
create table if not exists platform_settings (
  key text primary key,
  value jsonb not null,
  updated_by text,
  updated_at timestamptz not null default now()
);

-- Every change is kept: who, when, from what to what
create table if not exists platform_settings_history (
  id bigserial primary key,
  key text not null,
  old_value jsonb,
  new_value jsonb,
  changed_by text,
  changed_at timestamptz not null default now()
);
create index if not exists platform_settings_history_recent on platform_settings_history (changed_at desc);
