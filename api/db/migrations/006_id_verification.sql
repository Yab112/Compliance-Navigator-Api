-- National ID verification through Fayda (MOSIP eSignet) for Guday Geday sign-up.
-- The full Fayda number is never stored: only a keyed hash (duplicate detection)
-- and the last four digits (display).

create table if not exists id_verifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  mode text not null check (mode in ('sandbox', 'live')),
  state text not null unique,
  nonce text not null,
  code_verifier text not null,
  status text not null default 'pending'
    check (status in ('pending', 'verified', 'failed', 'superseded')),
  method text check (method in ('fayda', 'fayda_sandbox')),
  id_type text,                 -- FIN (12 digits), FCN (16 digits) or SUB (eSignet subject)
  id_hash text,
  id_last4 text,
  verified_name text,
  birthdate text,
  gender text,
  phone text,
  error text,
  expires_at timestamptz not null,
  verified_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists id_verifications_user_idx on id_verifications (user_id);
-- One active verification per account, and one account per national ID
create unique index if not exists id_verifications_user_verified_uq
  on id_verifications (user_id) where status = 'verified';
create unique index if not exists id_verifications_hash_verified_uq
  on id_verifications (id_hash) where status = 'verified';

alter table guday_agents add column if not exists national_id_verified boolean not null default false;
alter table guday_agents add column if not exists id_verification_method text;
alter table guday_agents add column if not exists verified_name text;
