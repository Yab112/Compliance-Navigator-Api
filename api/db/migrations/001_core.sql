-- Core schema: accounts, roadmaps, manual references, RAG chunks.
-- Works on plain Postgres (docker pgvector image) and on Supabase.

create extension if not exists vector;
create extension if not exists pgcrypto;

-- Local accounts. When Supabase Auth is used, id mirrors auth.users.id and
-- password_hash stays null.
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  password_hash text,
  fullname text not null default '',
  phone text,
  role text not null default 'user' check (role in ('user', 'agent', 'admin')),
  is_active boolean not null default true,
  preferred_sub_city text,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists roadmaps (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users (id) on delete set null,
  goal text not null,
  sub_city text not null,
  industry text,
  documents_held text[] not null default '{}',
  tracked_completed text[] not null default '{}',
  snapshot_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists roadmaps_user_id_idx on roadmaps (user_id);
create index if not exists roadmaps_goal_idx on roadmaps (goal);
create index if not exists roadmaps_created_at_idx on roadmaps (created_at);

create table if not exists manual_references (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users (id) on delete set null,
  title text not null,
  service_id text,
  company_name text,
  institution_id text,
  file_path text,
  mime_type text,
  extraction_status text not null default 'pending',
  raw_text text,
  verified boolean not null default false,
  created_at timestamptz not null default now()
);

-- RAG legal chunks (384-dim = fastembed all-MiniLM-L6-v2)
create table if not exists legal_chunks (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  embedding vector (384),
  proclamation_number text,
  article_number text,
  issuing_body text,
  topic_tags text[] not null default '{}',
  sector_tags text[] not null default '{}',
  source_url text,
  language text not null default 'en',
  document_id text,
  service_id text,
  created_at timestamptz not null default now()
);

create index if not exists legal_chunks_document_id_idx on legal_chunks (document_id);
create index if not exists legal_chunks_embedding_idx
  on legal_chunks using hnsw (embedding vector_cosine_ops);
