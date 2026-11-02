-- How the assistant learns, with a person deciding. A learning run reads recent conversations and the
-- guard log, groups what went wrong into findings, and proposes a next action for each. Nothing it
-- finds changes the data or the model by itself: staff approve, reject or mark each finding done.

alter table assistant_turns add column if not exists gap text
  check (gap in ('not_found', 'out_of_scope', 'grounding_failed', 'correction'));
create index if not exists assistant_turns_gap_idx on assistant_turns (gap, created_at desc) where gap is not null;

create table if not exists assistant_learning_runs (
  id bigserial primary key,
  triggered_by text not null,
  since timestamptz not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  findings_new int not null default 0,
  findings_updated int not null default 0,
  summary jsonb not null default '{}'::jsonb
);

create table if not exists assistant_findings (
  id bigserial primary key,
  kind text not null check (kind in ('missing_service', 'low_confidence', 'grounding_failed', 'user_correction',
                                     'denied_request', 'tool_error')),
  dedupe_key text not null unique,      -- the same problem seen again raises the count, not a new row
  summary text not null,
  next_action text not null,            -- what the assistant proposes a person should do
  action_type text not null check (action_type in ('add_service_data', 'verify_fact', 'label_examples',
                                                    'review_guard', 'fix_tool', 'review_reply')),
  examples jsonb not null default '[]'::jsonb,   -- a few redacted messages, newest first
  seen_count int not null default 1,
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  status text not null default 'new' check (status in ('new', 'approved', 'rejected', 'done')),
  reviewed_by text,
  reviewed_at timestamptz,
  note text,
  run_id bigint references assistant_learning_runs (id) on delete set null
);

create index if not exists assistant_findings_status_idx on assistant_findings (status, last_seen desc);
