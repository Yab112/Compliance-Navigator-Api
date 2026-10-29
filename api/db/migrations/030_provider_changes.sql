-- Changes an approved provider makes to who they are or how they are taxed (name, legal name, TIN,
-- trade licence number, VAT) wait here for staff; the old values stay live until approved.
create table if not exists provider_change_requests (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references providers (id) on delete cascade,
  changes jsonb not null,
  old_values jsonb not null,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  requested_by text,
  requested_at timestamptz not null default now(),
  decided_by text,
  decided_at timestamptz,
  note text
);
create unique index if not exists provider_change_requests_pending_uq
  on provider_change_requests (provider_id) where status = 'pending';

-- Explicit consent before a police clearance (offence data, Proclamation 1321/2024) is kept and checked
alter table provider_documents add column if not exists consent_at timestamptz;
