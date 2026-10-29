-- Guday Geday (ጉዳይ ገዳይ), registered agents who handle government errands
-- for clients, plus the client requests (cases) they take on.

create sequence if not exists guday_registration_seq start 1;

create table if not exists guday_agents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique references users (id) on delete set null,
  registration_no text unique,
  full_name text not null,
  full_name_am text,
  phone text not null,
  email text,
  national_id text not null, -- Fayda FAN or Kebele ID number
  tin text,
  sub_city text not null,
  address text,
  languages text[] not null default '{}',
  service_ids text[] not null default '{}', -- MESOB catalog service ids
  institution_ids text[] not null default '{}', -- MESOB institution ids
  experience_years int not null default 0 check (experience_years >= 0),
  bio text,
  photo_url text,
  id_document_url text,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'suspended')),
  license_expires_at date,
  reviewed_by text,
  reviewed_at timestamptz,
  review_note text,
  rating_avg numeric(3, 2) not null default 0,
  rating_count int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists guday_agents_status_idx on guday_agents (status);
create index if not exists guday_agents_sub_city_idx on guday_agents (sub_city);
create index if not exists guday_agents_service_ids_idx on guday_agents using gin (service_ids);

-- Append-only audit trail: registration, approvals, suspensions, edits.
create table if not exists guday_agent_events (
  id bigserial primary key,
  agent_id uuid not null references guday_agents (id) on delete cascade,
  action text not null,
  actor text,
  note text,
  created_at timestamptz not null default now()
);

create index if not exists guday_agent_events_agent_idx on guday_agent_events (agent_id, created_at desc);

create table if not exists guday_cases (
  id uuid primary key default gen_random_uuid(),
  client_user_id uuid references users (id) on delete set null,
  client_name text not null,
  client_phone text not null,
  agent_id uuid references guday_agents (id) on delete set null,
  service_id text not null,
  service_name text,
  sub_city text,
  details text,
  status text not null default 'open'
    check (status in ('open', 'assigned', 'in_progress', 'completed', 'cancelled')),
  rating int check (rating between 1 and 5),
  rating_comment text,
  admin_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists guday_cases_status_idx on guday_cases (status);
create index if not exists guday_cases_agent_idx on guday_cases (agent_id);
create index if not exists guday_cases_client_idx on guday_cases (client_user_id);
