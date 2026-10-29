-- Vetting: the documents a provider hands in (police clearance, education, photo, trade licence,
-- TIN certificate) and the references staff call. Nothing is ever deleted: a newer upload of the
-- same kind supersedes the older one, so staff can always see what was on file and when.

create table if not exists provider_documents (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references providers (id) on delete cascade,
  kind text not null check (kind in (
    'police_clearance', 'education', 'photo', 'trade_licence', 'tin_certificate', 'id_copy'
  )),
  -- Education only: grade_10, grade_12, tvet, diploma, degree
  level text,
  file_key text not null,
  content_type text,
  size_bytes int,
  issued_on date,
  expires_on date,
  reference_no text,
  issuer text,
  status text not null default 'pending'
    check (status in ('pending', 'verified', 'rejected', 'expired', 'superseded')),
  reviewed_by text,
  reviewed_at timestamptz,
  review_note text,
  -- Set when the provider was told the document is about to get too old, so we tell them once
  reminded_at timestamptz,
  uploaded_by text,
  uploaded_at timestamptz not null default now()
);
create index if not exists provider_documents_provider_idx
  on provider_documents (provider_id, kind, uploaded_at desc);
create index if not exists provider_documents_status_idx on provider_documents (status, kind);
-- At most one verified document per kind. It stays in force until its replacement is verified,
-- so a provider is never left without cover while staff check the new one.
create unique index if not exists provider_documents_verified_uq
  on provider_documents (provider_id, kind) where status = 'verified';

create table if not exists provider_references (
  id uuid primary key default gen_random_uuid(),
  provider_id uuid not null references providers (id) on delete cascade,
  name text not null,
  phone text not null,
  relationship text not null,
  status text not null default 'pending' check (status in ('pending', 'confirmed', 'failed', 'removed')),
  checked_by text,
  checked_at timestamptz,
  note text,
  created_at timestamptz not null default now()
);
create index if not exists provider_references_provider_idx on provider_references (provider_id, status);

-- Copies uploaded before this table existed become pending documents for staff to check
insert into provider_documents (provider_id, kind, file_key, status, uploaded_by, uploaded_at)
select id, 'id_copy', id_document_url, 'pending', 'migration 024', coalesce(created_at, now())
from providers where id_document_url is not null and id_document_url <> ''
on conflict do nothing;

insert into provider_documents (provider_id, kind, file_key, status, uploaded_by, uploaded_at)
select id, 'trade_licence', license_document_url, 'pending', 'migration 024', coalesce(updated_at, created_at, now())
from providers where license_document_url is not null and license_document_url <> ''
on conflict do nothing;
