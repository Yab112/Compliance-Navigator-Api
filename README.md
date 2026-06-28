# Compliance Navigator

Graph-based decision support for Ethiopian business compliance. Maps regulatory requirements as a dependency graph and produces step-by-step roadmaps grounded in legal sources.

## Repository layout

```
Compliance Navigator/
├── Doc/          # Product & architecture specs
├── web/          # Next.js frontend (shadcn, Zod, Zustand)
└── api/          # FastAPI backend
```

## Data stores

| Store | Role |
|-------|------|
| **Neo4j** | Compliance graph — services, documents, REQUIRES paths |
| **Supabase Auth** | Users & JWT sessions (replaces custom JWT + Neo4j users) |
| **Supabase Postgres** | Roadmaps, profiles, manual references |
| **Supabase pgvector** | Legal text embeddings for RAG grounding |
| **S3** | Manual document uploads (falls back to `api/uploads/` when unset) |

## Quick start

### API

```bash
cd api
cp .env.sample .env
docker compose up -d
uv run main.py
```

API runs at http://localhost:8080

### Celery worker (background jobs)

Scraping, ingestion, and graph maintenance run off the main event loop via Celery + Redis:

```bash
cd api
docker compose up -d   # starts neo4j, redis, api, worker
# or run worker locally:
celery -A worker.celery_app worker --loglevel=info
# Windows dev:
celery -A worker.celery_app worker --loglevel=info --pool=solo
```

Enqueue jobs (authenticated): `POST /api/v1/admin/jobs/scrape`, `POST /api/v1/admin/jobs/ingest`, `POST /api/v1/admin/jobs/stale-check`  
Poll status: `GET /api/v1/admin/tasks/{task_id}`

Seed the compliance graph (Neo4j must be running):

```bash
cd api
uv run python -m scripts.seed_graph
uv run python -m scripts.validate_graph
```

Or enqueue via Celery: `POST /api/v1/admin/jobs/ingest` with body `{"source": "graph"}`.

### Supabase (Auth + Postgres + vectors)

See [`api/supabase/README.md`](api/supabase/README.md). Add to `api/.env` only:

```env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_ANON_KEY=...
```

Run SQL migration, then:

```bash
cd api
uv run python -m scripts.seed_rag_samples
```

### S3 (manual uploads)

Optional — when unset, files land in `api/uploads/`:

```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=compliance-navigator-uploads
# MinIO / R2: S3_ENDPOINT_URL=http://localhost:9000
```

### Web

```bash
cd web
cp .env.example .env.local
pnpm install
pnpm dev
```

Web runs at http://localhost:3000 (`web/.env.local` — API URL only; Supabase keys stay in `api/.env`)

## Auth model

- **Supabase Auth** issues JWTs; the API verifies them via `supabase.auth.get_user(token)`
- **Public:** process list, roadmap create/get (guest OK), health checks
- **Login required:** profile (`/auth/me`), chat, admin uploads, step PATCH

The web app signs in via the API (`POST /users/login`), stores the Supabase JWT in `localStorage`, and sends `Authorization: Bearer` to the API.
