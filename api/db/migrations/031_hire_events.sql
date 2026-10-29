-- The history of every hire: each status change, staff action and complaint decision, with who did it.
-- Staff changes always carry a note. The hire detail page in the admin shows this as a timeline.
create table if not exists engagement_events (
  id bigserial primary key,
  engagement_id uuid not null references engagements (id) on delete cascade,
  action text not null,
  actor_kind text not null check (actor_kind in ('client', 'provider', 'staff', 'system')),
  -- Staff email, or the provider's name; null for the client and the system
  actor text,
  from_status text,
  to_status text,
  provider_id uuid,
  note text,
  created_at timestamptz not null default now()
);
create index if not exists engagement_events_engagement_idx on engagement_events (engagement_id, id);

-- A complaint upheld on a paid job means the client is owed money back. Staff see the flag; the
-- refund itself is done through the payments tools, which clear it.
alter table engagements
  add column if not exists refund_needed boolean not null default false,
  add column if not exists refund_flagged_at timestamptz,
  add column if not exists refund_flagged_by text,
  add column if not exists dispute_resolved_at timestamptz;
create index if not exists engagements_refund_needed_idx on engagements (refund_flagged_at) where refund_needed;
