-- Data sources staff add from the admin app (an official web page or pasted document text).
-- Their runs go into data_source_runs like the built-in pipelines, with source = 'custom:<id>'.
create table if not exists custom_data_sources (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text not null default '',
  kind text not null check (kind in ('web_page', 'pasted_text')),
  url text,
  body text,
  issuing_body text,
  language text not null default 'en' check (language in ('en', 'am')),
  tags text[] not null default '{}',
  schedule text not null default 'manual' check (schedule in ('manual', 'daily', 'weekly')),
  enabled boolean not null default true,
  paused_by text,
  paused_at timestamptz,
  created_by text,
  created_at timestamptz not null default now(),
  updated_by text,
  updated_at timestamptz not null default now()
);

-- Pause switch for the built-in pipelines, which are defined in code. A missing row means "on".
create table if not exists data_source_state (
  source text primary key,
  enabled boolean not null default true,
  paused_by text,
  paused_at timestamptz
);

create index if not exists data_source_runs_started_idx on data_source_runs (started_at desc);
