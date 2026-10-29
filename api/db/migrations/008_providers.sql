-- Provider marketplace: Guday Geday agents, delalas (brokers) and agencies, as
-- individuals or companies. Generalises guday_agents / guday_cases into providers /
-- engagements, adds verified-hire reviews, agency membership and a stored trust score.

alter table guday_agents rename to providers;
alter table guday_agent_events rename to provider_events;
alter table provider_events rename column agent_id to provider_id;
alter table guday_cases rename to engagements;
alter table engagements rename column agent_id to provider_id;
alter sequence guday_registration_seq rename to provider_registration_seq;

alter index if exists guday_agents_status_idx rename to providers_status_idx;
alter index if exists guday_agents_sub_city_idx rename to providers_sub_city_idx;
alter index if exists guday_agents_service_ids_idx rename to providers_service_ids_idx;
alter index if exists guday_agent_events_agent_idx rename to provider_events_provider_idx;
alter index if exists guday_cases_status_idx rename to engagements_status_idx;
alter index if exists guday_cases_agent_idx rename to engagements_provider_idx;
alter index if exists guday_cases_client_idx rename to engagements_client_idx;

-- ---------------------------------------------------------------- providers

alter table providers rename column full_name to display_name;
alter table providers rename column full_name_am to display_name_am;
alter table providers alter column national_id drop not null;
alter table providers alter column sub_city drop not null;

alter table providers
  add column provider_type text not null default 'guday_geday'
    check (provider_type in ('guday_geday', 'delala', 'agency')),
  add column entity_type text not null default 'individual'
    check (entity_type in ('individual', 'company')),
  add column slug text,
  add column headline text,
  add column specialties text[] not null default '{}',
  add column service_areas text[] not null default '{}',
  add column fee_from numeric(12, 2),
  add column fee_to numeric(12, 2),
  add column fee_unit text not null default 'negotiable'
    check (fee_unit in ('per_job', 'percent', 'per_hour', 'negotiable')),
  add column pricing_notes text,
  -- Companies: registered entity details; the representative is the Fayda-verified user
  add column legal_name text,
  add column trade_license_no text,
  add column license_document_url text,
  add column representative_title text,
  -- Sector licence (broker licence, customs clearing permit, travel agency licence...)
  add column external_license_type text,
  add column external_license_no text,
  add column external_license_status text not null default 'none'
    check (external_license_status in ('none', 'pending', 'verified', 'rejected')),
  add column external_license_verified_by text,
  add column external_license_verified_at timestamptz,
  add column highlights text[] not null default '{}',
  add column website text,
  add column accepting_work boolean not null default true,
  add column completed_count int not null default 0,
  add column response_hours numeric(8, 2),
  add column trust_score int not null default 0,
  add column score_breakdown jsonb not null default '[]',
  add column approved_at timestamptz,
  add column is_sample boolean not null default false;

-- Existing agents: readable slugs and their sub-city as service area
update providers set
  slug = trim(both '-' from regexp_replace(lower(display_name), '[^a-z0-9]+', '-', 'g'))
         || '-' || substr(id::text, 1, 6),
  service_areas = case when sub_city is not null then array[sub_city] else '{}' end,
  approved_at = case when status = 'approved' then coalesce(reviewed_at, created_at) end;
alter table providers alter column slug set not null;
create unique index if not exists providers_slug_uq on providers (slug);
create index if not exists providers_type_idx on providers (provider_type, status);
create index if not exists providers_score_idx on providers (trust_score desc);
create index if not exists providers_specialties_idx on providers using gin (specialties);
create index if not exists providers_areas_idx on providers using gin (service_areas);

-- Agency teams: an individual asks to join (or the agency invites) and the other side accepts
create table if not exists provider_members (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null references providers (id) on delete cascade,
  member_id uuid references providers (id) on delete cascade,
  invited_email text,
  initiated_by text not null check (initiated_by in ('member', 'agency')),
  role_title text,
  status text not null default 'pending' check (status in ('pending', 'active', 'declined', 'removed')),
  created_at timestamptz not null default now(),
  responded_at timestamptz,
  check (member_id is not null or invited_email is not null)
);
create unique index if not exists provider_members_pair_uq
  on provider_members (agency_id, member_id) where status in ('pending', 'active');
-- A person works for at most one agency at a time
create unique index if not exists provider_members_one_agency_uq
  on provider_members (member_id) where status = 'active';

-- ---------------------------------------------------------------- engagements

alter table engagements drop constraint if exists guday_cases_status_check;
update engagements set status = 'requested' where status = 'assigned';
alter table engagements add constraint engagements_status_check check (status in (
  'open', 'requested', 'accepted', 'in_progress', 'completed', 'declined', 'cancelled'
));
alter table engagements alter column service_id drop not null;
alter table engagements
  add column title text,
  add column specialty text,
  add column budget text,
  add column accepted_at timestamptz,
  add column declined_reason text,
  add column client_confirmed_at timestamptz,
  add column disputed boolean not null default false,
  add column dispute_reason text,
  add column dispute_status text check (dispute_status in ('open', 'upheld', 'dismissed')),
  add column dispute_resolved_by text,
  add column dispute_note text,
  add column is_sample boolean not null default false;
update engagements set title = coalesce(service_name, 'Service request');
alter table engagements alter column title set not null;

-- ---------------------------------------------------------------- reviews

create table if not exists reviews (
  id uuid primary key default gen_random_uuid(),
  engagement_id uuid not null unique references engagements (id) on delete cascade,
  provider_id uuid not null references providers (id) on delete cascade,
  client_user_id uuid references users (id) on delete set null,
  rating int not null check (rating between 1 and 5),
  communication int check (communication between 1 and 5),
  fee_honesty int check (fee_honesty between 1 and 5),
  speed int check (speed between 1 and 5),
  outcome int check (outcome between 1 and 5),
  would_hire_again boolean,
  comment text,
  reply text,
  replied_at timestamptz,
  hidden boolean not null default false,
  hidden_reason text,
  hidden_by text,
  hidden_at timestamptz,
  is_sample boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists reviews_provider_idx on reviews (provider_id, created_at desc);

-- Ratings left on old cases become reviews
insert into reviews (engagement_id, provider_id, client_user_id, rating, comment, created_at)
select id, provider_id, client_user_id, rating, rating_comment, coalesce(completed_at, updated_at)
from engagements
where rating is not null and provider_id is not null
on conflict (engagement_id) do nothing;

update providers p set completed_count = (
  select count(*) from engagements e where e.provider_id = p.id and e.status = 'completed'
);
