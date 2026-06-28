# Supabase setup

Compliance Navigator uses **Supabase** for:

- **Auth** — users, JWT sessions (API verifies tokens; no Neo4j `User` nodes)
- **Postgres** — roadmaps, profiles, manual reference metadata
- **pgvector** — legal text chunks for RAG grounding

**Neo4j** remains the compliance **graph** (services, documents, REQUIRES paths).

**S3** (optional) stores uploaded PDFs; configure `AWS_*` / `S3_*` in `api/.env` (see `.env.sample`).

## 1. Create a Supabase project

1. https://supabase.com/dashboard → New project
2. Copy **Project URL** and **service_role** key (Settings → API)

## 2. Run migration

SQL Editor → paste and run [`migrations/001_initial.sql`](migrations/001_initial.sql)

## 3. Configure API

In `api/.env` (not `web/` — secrets stay on the API side):

```env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key
```

## 4. Web env

In `web/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

## 5. S3 uploads (recommended)

Set `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` in `api/.env`.  
Without S3, uploads are saved under `api/uploads/`.

## 6. Seed sample legal chunks

```bash
cd api
uv run python -m scripts.seed_rag_samples
```

## Architecture

| Layer | Store |
|-------|--------|
| Graph paths | Neo4j |
| Users / auth | Supabase Auth |
| Roadmaps / metadata | Supabase Postgres |
| File uploads | S3 (or local `uploads/`) |
| Embeddings / RAG | Supabase `legal_chunks` + pgvector |
