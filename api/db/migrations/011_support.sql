-- Support desk: requests the assistant hands to a person, the contact form, and staff replies.

create sequence if not exists support_ticket_ref_seq start 1001;

create table if not exists support_tickets (
  id uuid primary key default gen_random_uuid(),
  ref text not null unique default ('CN-' || lpad(nextval('support_ticket_ref_seq')::text, 6, '0')),
  user_id uuid references users (id) on delete set null,
  contact_name text,
  contact_phone text,
  contact_email text,
  queue text not null default 'customer_support'
    check (queue in ('customer_support', 'compliance', 'marketplace', 'organizations', 'technical')),
  category text,
  subject text not null,
  status text not null default 'new' check (status in ('new', 'open', 'waiting_customer', 'resolved', 'closed')),
  priority text not null default 'normal' check (priority in ('low', 'normal', 'high', 'urgent')),
  source text not null default 'contact_form' check (source in ('assistant', 'contact_form', 'report')),
  conversation_id uuid references assistant_conversations (id) on delete set null,
  service_key text,
  service_title text,
  context jsonb not null default '{}'::jsonb,
  assignee_id uuid references users (id) on delete set null,
  ip text,
  sla_due_at timestamptz not null,
  first_response_at timestamptz,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists support_tickets_queue_idx on support_tickets (queue, status);
create index if not exists support_tickets_user_idx on support_tickets (user_id, created_at desc);
create index if not exists support_tickets_conv_idx on support_tickets (conversation_id);

create table if not exists support_messages (
  id bigserial primary key,
  ticket_id uuid not null references support_tickets (id) on delete cascade,
  author_kind text not null check (author_kind in ('customer', 'staff', 'system', 'assistant')),
  author_id uuid references users (id) on delete set null,
  body text not null,
  internal boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists support_messages_ticket_idx on support_messages (ticket_id, id);

-- Staff replies are posted into the chat the request came from
alter table assistant_messages drop constraint if exists assistant_messages_role_check;
alter table assistant_messages add constraint assistant_messages_role_check
  check (role in ('user', 'assistant', 'staff'));
