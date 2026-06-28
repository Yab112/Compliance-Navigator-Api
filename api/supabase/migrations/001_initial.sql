-- Compliance Navigator — Supabase Postgres + pgvector
-- Run in Supabase Dashboard → SQL Editor

create extension if not exists vector;

-- App profiles (optional link to Supabase Auth users)
create table if not exists public.profiles (
  id uuid primary key,
  email text unique not null,
  fullname text,
  preferred_sub_city text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Persisted roadmaps (graph logic stays in Neo4j; snapshot stored here)
create table if not exists public.roadmaps (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles (id) on delete set null,
  goal text not null,
  sub_city text not null,
  industry text,
  documents_held text[] default '{}',
  tracked_completed text[] default '{}',
  snapshot_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists roadmaps_user_id_idx on public.roadmaps (user_id);
create index if not exists roadmaps_goal_idx on public.roadmaps (goal);

-- Manual uploads (metadata; files in Supabase Storage or local path)
create table if not exists public.manual_references (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles (id) on delete set null,
  title text not null,
  service_id text,
  company_name text,
  institution_id text,
  file_path text,
  mime_type text,
  extraction_status text default 'pending',
  raw_text text,
  verified boolean default false,
  created_at timestamptz not null default now()
);

-- RAG legal chunks (384-dim = fastembed all-MiniLM-L6-v2)
create table if not exists public.legal_chunks (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  embedding vector (384),
  proclamation_number text,
  article_number text,
  issuing_body text,
  topic_tags text[] default '{}',
  sector_tags text[] default '{}',
  source_url text,
  language text default 'en',
  document_id text,
  service_id text,
  created_at timestamptz not null default now()
);

create index if not exists legal_chunks_document_id_idx on public.legal_chunks (document_id);
create index if not exists legal_chunks_embedding_idx
  on public.legal_chunks using hnsw (embedding vector_cosine_ops);

-- Vector similarity search
create or replace function public.match_legal_chunks (
  query_embedding vector (384),
  match_threshold float default 0.75,
  match_count int default 5,
  filter_document_id text default null,
  filter_service_id text default null
)
returns table (
  id uuid,
  content text,
  similarity float,
  proclamation_number text,
  article_number text,
  issuing_body text,
  source_url text,
  document_id text
)
language sql
stable
as $$
  select
    lc.id,
    lc.content,
    (1 - (lc.embedding <=> query_embedding))::float as similarity,
    lc.proclamation_number,
    lc.article_number,
    lc.issuing_body,
    lc.source_url,
    lc.document_id
  from public.legal_chunks lc
  where lc.embedding is not null
    and (filter_document_id is null or lc.document_id = filter_document_id)
    and (filter_service_id is null or lc.service_id = filter_service_id)
    and (1 - (lc.embedding <=> query_embedding)) > match_threshold
  order by lc.embedding <=> query_embedding
  limit match_count;
$$;

-- RLS (service role bypasses; enable when using anon key from client)
alter table public.profiles enable row level security;
alter table public.roadmaps enable row level security;
alter table public.manual_references enable row level security;
alter table public.legal_chunks enable row level security;

create policy "Public read legal chunks"
  on public.legal_chunks for select
  using (true);

create policy "Users read own roadmaps"
  on public.roadmaps for select
  using (auth.uid() = user_id);

create policy "Users insert own roadmaps"
  on public.roadmaps for insert
  with check (auth.uid() = user_id or user_id is null);
