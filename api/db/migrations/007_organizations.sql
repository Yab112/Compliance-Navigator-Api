-- Organization onboarding. Organizations that give services (institutions, sub-city
-- offices, banks, utilities, hospitals, embassies, NGOs, private providers) describe
-- their services: requirements, eligibility questions, steps, fees and branches.
-- Published services feed the knowledge graph and the cross-organization paths.

drop table if exists business_events;
drop table if exists businesses;

create table if not exists organizations (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null,
  name_am text,
  org_type text not null check (org_type in (
    'federal_institution', 'regional_bureau', 'sub_city_office', 'woreda_office', 'bank',
    'utility', 'health', 'education', 'embassy', 'ngo', 'private_provider', 'other')),
  sector text,
  parent_org_id uuid references organizations (id) on delete set null,
  description text,
  logo_url text,
  website text,
  phone text,
  email text,
  hq_address text,
  region text,
  sub_city text,
  catalog_institution_id text,
  representative_name text,
  representative_title text,
  official_email text,
  authorization_letter_key text,
  status text not null default 'pending' check (status in ('pending', 'verified', 'rejected', 'suspended')),
  verification_note text,
  reviewed_by text,
  reviewed_at timestamptz,
  created_by uuid references users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists organizations_status_idx on organizations (status);

create table if not exists organization_members (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations (id) on delete cascade,
  user_id uuid references users (id) on delete cascade,
  invited_email text not null,
  role text not null default 'editor' check (role in ('owner', 'editor')),
  accepted boolean not null default false,
  created_at timestamptz not null default now(),
  unique (org_id, invited_email)
);
create index if not exists organization_members_user_idx on organization_members (user_id);

create table if not exists organization_branches (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations (id) on delete cascade,
  name text not null,
  region text,
  sub_city text,
  woreda text,
  address text,
  latitude double precision,
  longitude double precision,
  map_url text,
  phone text,
  hours text,
  created_at timestamptz not null default now()
);

-- The row and its child tables are the working copy the organization edits.
-- published_snapshot is what the public sees; it only changes when staff publish.
create table if not exists org_services (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations (id) on delete cascade,
  slug text not null,
  name text not null,
  name_am text,
  summary text,
  who_can_apply text,
  delivery text not null default 'in_person' check (delivery in ('in_person', 'online', 'both')),
  online_url text,
  fee_amount_min numeric,
  fee_amount_max numeric,
  fee_currency text not null default 'ETB',
  fee_notes text,
  payment_methods text[] not null default '{}',
  processing_time_text text,
  processing_minutes integer,
  legal_basis text,
  forms jsonb not null default '[]',
  common_rejection_reasons text[] not null default '{}',
  faq jsonb not null default '[]',
  branch_ids uuid[] not null default '{}',
  outputs jsonb not null default '[]',
  status text not null default 'draft' check (status in ('draft', 'submitted', 'published', 'changes_requested', 'archived')),
  admin_note text,
  published_snapshot jsonb,
  published_at timestamptz,
  version integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (org_id, slug)
);
create index if not exists org_services_status_idx on org_services (status);

create table if not exists org_service_requirements (
  id uuid primary key default gen_random_uuid(),
  service_id uuid not null references org_services (id) on delete cascade,
  position integer not null default 0,
  key text not null,
  kind text not null default 'document' check (kind in ('document', 'prerequisite_service')),
  name text not null,
  document_id text,
  issuing_service_id uuid references org_services (id) on delete set null,
  required text not null default 'always' check (required in ('always', 'conditional')),
  notes text,
  original_or_copy text check (original_or_copy in ('original', 'copy', 'both')),
  copies integer,
  unique (service_id, key)
);

create table if not exists org_service_questions (
  id uuid primary key default gen_random_uuid(),
  service_id uuid not null references org_services (id) on delete cascade,
  position integer not null default 0,
  key text not null,
  prompt text not null,
  prompt_am text,
  type text not null default 'yes_no' check (type in ('yes_no', 'single_choice', 'number', 'text')),
  options jsonb not null default '[]',
  rules jsonb not null default '[]',
  unique (service_id, key)
);

create table if not exists org_service_steps (
  id uuid primary key default gen_random_uuid(),
  service_id uuid not null references org_services (id) on delete cascade,
  position integer not null default 0,
  title text not null,
  location text,
  description text,
  estimated_minutes integer
);

create table if not exists org_service_revisions (
  id uuid primary key default gen_random_uuid(),
  service_id uuid not null references org_services (id) on delete cascade,
  snapshot jsonb not null,
  status text not null default 'pending' check (status in ('pending', 'published', 'changes_requested', 'superseded')),
  submitted_by text,
  reviewed_by text,
  admin_note text,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);
create index if not exists org_service_revisions_pending_idx on org_service_revisions (status, created_at);

create table if not exists org_events (
  id bigserial primary key,
  org_id uuid references organizations (id) on delete cascade,
  service_id uuid references org_services (id) on delete cascade,
  action text not null,
  actor text,
  note text,
  created_at timestamptz not null default now()
);
create index if not exists org_events_org_idx on org_events (org_id, created_at desc);

create table if not exists org_service_stats (
  service_id uuid not null references org_services (id) on delete cascade,
  metric text not null check (metric in ('view', 'eligibility_check', 'path_view')),
  day date not null default current_date,
  count integer not null default 0,
  primary key (service_id, metric, day)
);
