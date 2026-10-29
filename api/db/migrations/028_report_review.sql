-- "This is wrong" reports: a per-address limit for anonymous reports, the organization's verdict
-- when it answers, and a history that only grows (reopening adds a line instead of erasing one).
alter table feedback_flags add column if not exists ip text;
alter table feedback_flags add column if not exists org_verdict text check (org_verdict in ('fixed', 'correct'));
create index if not exists feedback_flags_ip_idx on feedback_flags (ip, created_at);

create table if not exists feedback_flag_events (
  id uuid primary key default gen_random_uuid(),
  flag_id uuid not null references feedback_flags (id) on delete cascade,
  action text not null check (action in ('created', 'org_responded', 'resolved', 'dismissed', 'reopened')),
  actor text,
  note text,
  created_at timestamptz not null default now()
);
create index if not exists feedback_flag_events_flag_idx on feedback_flag_events (flag_id, created_at);

-- History for reports made before this table existed
insert into feedback_flag_events (flag_id, action, actor, note, created_at)
select id, 'created', null, null, created_at from feedback_flags;
insert into feedback_flag_events (flag_id, action, actor, note, created_at)
select id, 'org_responded', org_responded_by, org_response, org_responded_at
from feedback_flags where org_responded_at is not null;
insert into feedback_flag_events (flag_id, action, actor, note, created_at)
select id, status, resolved_by, resolution_note, resolved_at
from feedback_flags where status in ('resolved', 'dismissed') and resolved_at is not null;

-- Only staff close reports now. Reports an organization closed itself go back to the staff queue,
-- keeping the organization's answer as its verdict.
update feedback_flags set org_verdict = case when status = 'resolved' then 'fixed' else 'correct' end
where org_responded_by is not null and org_verdict is null;
insert into feedback_flag_events (flag_id, action, actor, note)
select id, 'reopened', 'system', 'Closed by the organization; waiting for staff to check'
from feedback_flags
where org_id is not null and status in ('resolved', 'dismissed') and resolved_by = org_responded_by;
update feedback_flags set status = 'open', resolved_by = null, resolved_at = null, resolution_note = null
where org_id is not null and status in ('resolved', 'dismissed') and resolved_by = org_responded_by;
