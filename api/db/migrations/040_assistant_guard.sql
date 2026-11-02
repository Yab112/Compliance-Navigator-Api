-- Every request the AI assistant makes for data or an action, as the guard decided it.
-- The model never reads the database itself: it asks the guard for a listed tool, and the guard
-- checks the request, runs our own code, and records the outcome here. No personal data: arguments
-- are stored after emails and long ID-like numbers are removed.

create table if not exists assistant_guard_log (
  id bigserial primary key,
  conversation_id uuid,
  tool text not null,
  args jsonb not null default '{}'::jsonb,
  decision text not null check (decision in ('allowed', 'denied', 'error')),
  reason text,                 -- why it was denied, or the error type
  result_chars int not null default 0,
  duration_ms int not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists assistant_guard_log_created_idx on assistant_guard_log (created_at desc);
create index if not exists assistant_guard_log_decision_idx on assistant_guard_log (decision, created_at desc);
create index if not exists assistant_guard_log_conversation_idx on assistant_guard_log (conversation_id, id);
