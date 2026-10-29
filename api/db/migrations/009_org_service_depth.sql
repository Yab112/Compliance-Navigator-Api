-- Everything a path step shows, published by the organization that gives the service,
-- plus the workflow that keeps it current.
--
-- Field map: what a roadmap step displays today and where an organization now supplies it.
--   Step title / issuing authority ......... org_services.name, organizations.name
--   Office name, address, landmark ......... organization_branches.name, address, landmark
--   Sub-city / woreda, map ................. organization_branches.sub_city, woreda, map_url, lat/lng
--   Phones ................................. organization_branches.phone, org_services.branch_details[].phone
--   Working hours .......................... organization_branches.hours_schedule (per weekday, lunch, Saturday)
--   Window / desk .......................... org_services.branch_details[].window
--   Fee (ETB) and payment methods .......... org_services.fee_schedule[], is_free, payment_methods, where_to_pay
--   Processing time ........................ org_services.processing_time_text, processing_minutes
--   Required inputs (what to bring) ........ org_service_requirements (+ original/copy, copies, notarized,
--                                            translated, max age, photo specs, applies to, alternatives)
--   Prerequisites (must have first) ........ org_service_requirements.issuing_service_id / document_id
--   Form code, forms ....................... org_services.forms
--   Legal basis ............................ org_services.legal_basis, legal_reference_number, legal_effective_date
--   Common rejection reasons ............... org_services.common_rejection_reasons
--   Official source / online URL ........... org_services.online_url, online_parts
--   Steps at the window .................... org_service_steps
--   Last verified .......................... org_services.last_confirmed_at (organization confirms every 90 days)
-- New, not shown before: appointments, applying on someone's behalf, languages served, accessibility,
-- who the service is for, what the applicant receives and how long it is valid, renewal and late
-- penalty, a contact for questions, scheduled changes with an effective date, and a change log.

-- Registration can be saved and resumed: 'draft' organizations are not yet sent for verification.
alter table organizations drop constraint if exists organizations_status_check;
alter table organizations add constraint organizations_status_check
  check (status in ('draft', 'pending', 'verified', 'rejected', 'suspended'));
alter table organizations add column if not exists onboarding_step integer not null default 0;
alter table organizations add column if not exists submitted_at timestamptz;
-- The person who keeps the data current, and the organization's commitment to do so
alter table organizations add column if not exists steward_name text;
alter table organizations add column if not exists steward_role text;
alter table organizations add column if not exists steward_phone text;
alter table organizations add column if not exists steward_email text;
alter table organizations add column if not exists data_commitment_at timestamptz;

alter table organization_branches add column if not exists landmark text;
alter table organization_branches add column if not exists email text;
-- [{"day": "mon", "open": "08:30", "close": "17:30", "lunch_start": "12:30", "lunch_end": "13:30", "closed": false}]
alter table organization_branches add column if not exists hours_schedule jsonb not null default '[]';

alter table org_services drop constraint if exists org_services_status_check;
alter table org_services add constraint org_services_status_check
  check (status in ('draft', 'submitted', 'published', 'scheduled', 'changes_requested', 'archived'));
-- [{"category": "ethiopian", "speed": "regular", "amount_min": 302, "amount_max": null,
--   "currency": "ETB", "covers": "License certificate", "notes": null}]
alter table org_services add column if not exists fee_schedule jsonb not null default '[]';
alter table org_services add column if not exists is_free boolean not null default false;
alter table org_services add column if not exists where_to_pay text;
alter table org_services add column if not exists no_documents_required boolean not null default false;
alter table org_services add column if not exists appointment_required boolean not null default false;
alter table org_services add column if not exists appointment_how text;
alter table org_services add column if not exists appointment_url text;
alter table org_services add column if not exists appointment_phone text;
alter table org_services add column if not exists proxy_allowed text check (proxy_allowed in ('yes', 'with_poa', 'no'));
alter table org_services add column if not exists proxy_notes text;
alter table org_services add column if not exists online_parts text;
alter table org_services add column if not exists languages text[] not null default '{}';
alter table org_services add column if not exists accessibility_notes text;
alter table org_services add column if not exists audience text[] not null default '{}';
alter table org_services add column if not exists legal_reference_number text;
alter table org_services add column if not exists legal_effective_date date;
alter table org_services add column if not exists contact_name text;
alter table org_services add column if not exists contact_phone text;
alter table org_services add column if not exists contact_email text;
alter table org_services add column if not exists output_validity_months integer;
alter table org_services add column if not exists renewal_service_id uuid references org_services (id) on delete set null;
alter table org_services add column if not exists late_renewal_penalty text;
-- [{"branch_id": "...", "window": "Window 2", "phone": "...", "hours_note": "...", "notes": "..."}]
alter table org_services add column if not exists branch_details jsonb not null default '[]';
alter table org_services add column if not exists last_confirmed_at timestamptz;
alter table org_services add column if not exists last_confirmed_by text;

alter table org_service_requirements add column if not exists notarized boolean not null default false;
alter table org_service_requirements add column if not exists translated boolean not null default false;
alter table org_service_requirements add column if not exists max_age_days integer;
alter table org_service_requirements add column if not exists photo_specs text;
alter table org_service_requirements add column if not exists applies_to text
  check (applies_to in ('applicant', 'each_party', 'each_partner', 'company', 'representative'));
alter table org_service_requirements add column if not exists alternatives text[] not null default '{}';

-- A change to a live service says what changed, why, and from when. Approved changes with a
-- future effective date wait as 'scheduled' and go live on that date.
alter table org_service_revisions drop constraint if exists org_service_revisions_status_check;
alter table org_service_revisions add constraint org_service_revisions_status_check
  check (status in ('pending', 'scheduled', 'published', 'changes_requested', 'superseded'));
alter table org_service_revisions add column if not exists change_summary text;
alter table org_service_revisions add column if not exists change_reason text;
alter table org_service_revisions add column if not exists effective_at date;
alter table org_service_revisions add column if not exists live_at timestamptz;
create index if not exists org_service_revisions_scheduled_idx on org_service_revisions (effective_at) where status = 'scheduled';

-- Existing live services count as confirmed when they were published
update org_services set last_confirmed_at = published_at, last_confirmed_by = 'publish'
where published_snapshot is not null and last_confirmed_at is null;
update org_service_revisions set live_at = reviewed_at where status = 'published' and live_at is null;

-- "This information is wrong" reports about an organization's service reach that organization
alter table feedback_flags add column if not exists org_id uuid references organizations (id) on delete set null;
alter table feedback_flags add column if not exists org_response text;
alter table feedback_flags add column if not exists org_responded_by text;
alter table feedback_flags add column if not exists org_responded_at timestamptz;
create index if not exists feedback_flags_org_idx on feedback_flags (org_id, status);

create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  kind text not null,
  title text not null,
  body text,
  link text,
  created_at timestamptz not null default now(),
  read_at timestamptz
);
create index if not exists notifications_user_idx on notifications (user_id, created_at desc);
