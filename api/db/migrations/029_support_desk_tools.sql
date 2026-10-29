-- Support desk tools: saved replies, a reply deadline after every customer message, and a link
-- from a new request to an older one the customer could no longer reopen.

-- Saved (canned) replies staff pick from. {{name}}, {{ref}}, {{subject}}, {{team}} and {{agent}}
-- are filled in from the ticket when the reply is inserted.
create table if not exists support_canned_replies (
  id uuid primary key default gen_random_uuid(),
  title text not null check (length(title) between 3 and 120),
  body text not null check (length(body) between 1 and 4000),
  -- null means every team can use it
  queue text check (queue in ('customer_support', 'compliance', 'marketplace', 'organizations', 'technical')),
  use_count integer not null default 0,
  created_by uuid,
  created_by_name text,
  updated_by_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists support_canned_replies_title_key on support_canned_replies (lower(title));

-- sla_due_at stays the first-reply target. next_response_due_at is when we owe the customer an
-- answer now: set when they write, cleared when staff reply.
alter table support_tickets add column if not exists next_response_due_at timestamptz;
alter table support_tickets add column if not exists follow_up_of uuid references support_tickets (id) on delete set null;

update support_tickets set next_response_due_at = sla_due_at
where next_response_due_at is null and first_response_at is null and status in ('new', 'open');

with last_public as (
  select distinct on (m.ticket_id) m.ticket_id, m.author_kind, m.created_at
  from support_messages m
  where not m.internal and m.author_kind in ('customer', 'staff')
  order by m.ticket_id, m.id desc
)
update support_tickets t set next_response_due_at = lp.created_at + make_interval(hours =>
  case t.priority when 'urgent' then 2 when 'high' then 8 when 'normal' then 24 else 72 end)
from last_public lp
where lp.ticket_id = t.id and lp.author_kind = 'customer'
  and t.next_response_due_at is null and t.first_response_at is not null and t.status in ('new', 'open');

create index if not exists support_tickets_due_idx on support_tickets (next_response_due_at)
  where status in ('new', 'open');
create index if not exists support_tickets_contact_phone_idx on support_tickets (contact_phone);
