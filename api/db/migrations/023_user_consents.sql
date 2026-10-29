-- Proof that a person agreed to a version of our legal documents (terms, privacy, marketplace rules,
-- provider agreement). One row per person, document and version.
--
-- No foreign key to users on purpose: deactivating or even removing an account must never remove
-- the record of what that person agreed to. Rows are only ever inserted, never updated.
create table if not exists user_consents (
  id bigserial primary key,
  user_id uuid not null,
  document text not null,
  version text not null,
  accepted_at timestamptz not null default now(),
  ip text,
  user_agent text
);
create unique index if not exists user_consents_user_doc_version_uq on user_consents (user_id, document, version);
create index if not exists user_consents_user_idx on user_consents (user_id, accepted_at desc);
