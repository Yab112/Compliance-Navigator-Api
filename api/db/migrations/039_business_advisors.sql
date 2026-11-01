-- Tax and business advisors: a third provider type, their professional licences, and where the
-- work happens (at the client's office, at the advisor's office, or online).

alter table providers drop constraint if exists providers_provider_type_check;
alter table providers add constraint providers_provider_type_check
  check (provider_type in ('guday_geday', 'agency', 'advisor'));

alter table providers add column if not exists delivery_modes text[] not null default '{}';
alter table providers drop constraint if exists providers_delivery_modes_check;
alter table providers add constraint providers_delivery_modes_check
  check (delivery_modes <@ array['client_office', 'provider_office', 'online']::text[]);
-- What a visit to the client's office costs on top of the work, shown on the profile
alter table providers add column if not exists visit_fee numeric(12, 2) check (visit_fee is null or visit_fee >= 0);

alter table engagements add column if not exists delivery_mode text
  check (delivery_mode is null or delivery_mode in ('client_office', 'provider_office', 'online'));

alter table provider_documents drop constraint if exists provider_documents_kind_check;
alter table provider_documents add constraint provider_documents_kind_check check (kind in (
  'police_clearance', 'education', 'photo', 'trade_licence', 'tin_certificate', 'id_copy',
  'guarantee_letter', 'guarantor_id', 'guarantor_employment',
  'tax_agent_licence', 'audit_licence', 'accounting_qualification'
));
