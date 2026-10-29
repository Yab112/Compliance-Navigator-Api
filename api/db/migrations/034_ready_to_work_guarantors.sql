-- Ready to work: a provider is listed, can be assigned, requested by clients and can accept or start
-- new work only while every rule holds (listing approved and in date, vetting complete, current legal
-- documents accepted, profile complete). provider_service.refresh_readiness() keeps these columns
-- current; the API recomputes everyone on startup, so existing listings are checked right away.
alter table providers add column if not exists ready_to_work boolean not null default false;
-- [{key, label, fix}] shown to the provider and staff: why they are not ready
alter table providers add column if not exists not_ready_reasons jsonb not null default '[]'::jsonb;
-- The earliest date a required document or the listing runs out: after it the flag no longer counts,
-- even if the daily run has not happened yet
alter table providers add column if not exists ready_until date;
alter table providers add column if not exists readiness_checked_at timestamptz;
create index if not exists providers_ready_idx on providers (ready_to_work) where ready_to_work;

-- Guarantor (ተያዥ): a person who signs that they answer for the provider's conduct and losses.
-- Only one guarantor is current; a replaced one stays on file as superseded.
create table if not exists provider_guarantors (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references providers (id) on delete cascade,
  full_name text not null,
  phone text not null,
  relationship text not null,
  sub_city text,
  woreda text,
  address text,
  occupation text not null,
  employer text,
  -- National ID or Fayda number, encrypted (core/crypto.py); only the last 4 digits are ever shown
  id_number_enc text not null,
  id_last4 text not null,
  status text not null default 'pending'
    check (status in ('pending', 'confirmed', 'failed', 'superseded')),
  checked_by text,
  checked_at timestamptz,
  note text,
  created_by text,
  created_at timestamptz not null default now(),
  superseded_at timestamptz
);
create unique index if not exists provider_guarantors_current_uq
  on provider_guarantors (provider_id) where status <> 'superseded';
create index if not exists provider_guarantors_provider_idx on provider_guarantors (provider_id, created_at desc);

-- The guarantor's papers are vetting documents like any other
alter table provider_documents drop constraint if exists provider_documents_kind_check;
alter table provider_documents add constraint provider_documents_kind_check check (kind in (
  'police_clearance', 'education', 'photo', 'trade_licence', 'tin_certificate', 'id_copy',
  'guarantee_letter', 'guarantor_id', 'guarantor_employment'
));
-- Which guarantor a guarantee letter or ID copy belongs to
alter table provider_documents add column if not exists guarantor_id uuid references provider_guarantors (id);
