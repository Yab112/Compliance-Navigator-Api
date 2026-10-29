-- Business registry, companies describe themselves so the portal can list them,
-- remind them about license renewals and point them to the right MESOB services.

create table if not exists businesses (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid unique references users (id) on delete set null,
  name text not null,
  name_am text,
  legal_form text not null
    check (legal_form in ('sole_proprietor', 'plc', 'share_company', 'partnership',
                          'cooperative', 'ngo', 'other')),
  tin text check (tin ~ '^\d{10}$'),
  trade_license_no text,
  license_expires_at date,
  sector text not null,
  sub_city text not null,
  address text,
  phone text not null,
  email text,
  website text,
  description text,
  employees_range text check (employees_range in ('1-10', '11-50', '51-200', '200+')),
  founded_year int check (founded_year between 1900 and 2100),
  services_needed text[] not null default '{}', -- MESOB catalog service ids
  logo_url text,
  list_publicly boolean not null default true,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected', 'suspended')),
  admin_note text,
  reviewed_by text,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists businesses_status_idx on businesses (status);
create index if not exists businesses_sector_idx on businesses (sector);
create index if not exists businesses_sub_city_idx on businesses (sub_city);

create table if not exists business_events (
  id bigserial primary key,
  business_id uuid not null references businesses (id) on delete cascade,
  action text not null,
  actor text,
  note text,
  created_at timestamptz not null default now()
);

create index if not exists business_events_business_idx on business_events (business_id, created_at desc);
