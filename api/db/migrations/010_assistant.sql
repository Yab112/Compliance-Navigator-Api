-- Interactive assistant: server-side conversation state, transcript, and the NLU learning log.

create table if not exists assistant_conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users (id) on delete set null,
  language text not null default 'en',
  state jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists assistant_conversations_user_idx on assistant_conversations (user_id, updated_at desc);

create table if not exists assistant_messages (
  id bigserial primary key,
  conversation_id uuid not null references assistant_conversations (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null default '',
  payload jsonb,
  created_at timestamptz not null default now()
);
create index if not exists assistant_messages_conv_idx on assistant_messages (conversation_id, id);

-- One row per user turn: what the model predicted, so admins can label mistakes and retrain.
-- Long digit runs (IDs, phone numbers) are masked before anything is stored.
create table if not exists assistant_turns (
  id bigserial primary key,
  conversation_id uuid references assistant_conversations (id) on delete set null,
  message_redacted text not null,
  language text,
  intent text,
  confidence real,
  ranked jsonb,
  resolved_service text,
  model_version text,
  labelled_intent text,
  labelled_service text,
  labelled_by text,
  labelled_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists assistant_turns_confidence_idx on assistant_turns (confidence) where labelled_intent is null;
