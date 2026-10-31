# Compliance Navigator

Graph-based decision support for Ethiopian business compliance. Maps regulatory requirements as a dependency graph and produces step-by-step roadmaps grounded in legal sources.

## Repository layout

```
Compliance Navigator/
├── Doc/              # Product & architecture specs
├── web/              # Public site: Next.js (shadcn, Zod, Zustand), port 3000
├── admin/            # Staff app: Next.js, port 3001, its own deployment
├── packages/
│   ├── core/         # @cn/core: API client, auth session, types, data hooks, navigation
│   └── ui/           # @cn/ui: design tokens, UI primitives, shared display components
└── api/              # FastAPI backend
```

`web`, `admin` and `packages/*` are one pnpm workspace. The packages are TypeScript source that each app compiles
(`transpilePackages`), so a change to a button or a type lands in both apps.

## What's inside

| Area | What it does |
|------|--------------|
| **Roadmaps** | Graph-based step-by-step path to a goal (passport, TIN, trade license, …) per sub-city; each step shows office, fee, documents, legal basis, and where it can be done at **MESOB** |
| **MESOB catalog** | Live scrape of [mesobcenter.et](https://mesobcenter.et/service-catalogue): 24 institutions, ~470 services (EN/AM), 19 centers, searchable at `/services`, mirrored into the knowledge graph, embedded for the AI |
| **Guday Geday (ጉዳይ ገዳይ)** | Registry of licensed errand agents: self-registration with ID upload → admin review (approve / reject / suspend / renew) → public directory → client requests → ratings |
| **AI assistant** | Chat (EN/AM, voice) that extracts goal/sub-city/documents, builds roadmaps, and cites MESOB + legal references via pgvector RAG. Providers: Ollama, Claude, or offline keyword mode — switchable from the dashboard |
| **Admin app** (`admin/`, port 3001) | Overview metrics, data-source runs, MESOB catalog, knowledge-graph viewer/editor with search, AI status/testing, Guday Geday management, feedback queue, users & roles |

## Data stores

| Store | Role |
|-------|------|
| **Postgres + pgvector** (docker, port 5433) | System of record: users & roles, roadmaps, Guday Geday agents/cases/audit log, data-source runs, feedback, settings, RAG embeddings, and the compliance graph. Migrations in `api/db/migrations` run automatically at startup |
| **Compliance graph** (in Postgres) | `graph_nodes` and `graph_edges`: services, documents, REQUIRES paths, offices, plus MESOB `GovService` / `Institution` / `MesobCenter` nodes. Prerequisite chains are a recursive SQL query (`services/graph_store.py`) |
| **Redis + Celery** (optional) | Scheduled jobs: nightly MESOB refresh, daily maintenance |
| **Local disk / S3** | Uploads. Agent photos → `api/uploads/public` (served); ID documents → `api/uploads/private` (admin-only endpoint) |

Everything runs self-hosted — no third-party auth or database service.

## Quick start

### 1. Infrastructure

```bash
cd api
cp .env.sample .env          # set SECRET_KEY
docker compose up -d postgres redis
```

### 2. API

```bash
cd api
uv sync
uv run python -m scripts.seed_graph          # compliance graph
uv run python -m scripts.seed_rag_samples    # legal citations
uv run main.py                               # http://localhost:8080 (docs at /docs)
```

Then sign in as an admin and open **Admin → Data sources** to run *MESOB service catalog* (scrape + graph) and *MESOB → AI knowledge base* (embeddings).

### 3. Web and admin

```bash
pnpm install                                 # once, at the repository root
cp web/.env.example web/.env.local
cp admin/.env.example admin/.env.local
pnpm dev:web                                 # public site, http://localhost:3000
pnpm dev:admin                               # staff app,  http://localhost:3001
```

Both apps sign in against the same API, so `CORS_ORIGINS` in `api/.env` must list both origins.
`NEXT_PUBLIC_SITE_URL` and `NEXT_PUBLIC_ADMIN_URL` tell each app where the other one lives; old `/admin/...`
links on the public site redirect to the admin app.

### Admin accounts

Staff accounts are separate from public accounts: the admin app has its own sign-in, and nothing on the
public site grants admin power. Create the first Super admin from the shell (it asks for the password):

```bash
cd api && uv run python -m scripts.create_staff admin@example.gov.et "Full Name"
```

Everyone else is invited from **Admin → Access → Staff** (they get an email with a one-time link to choose
a password). Roles, permissions and second-person approvals are described in `api/docs/staff-access.md`.

### AI provider

`LLM_PROVIDER` in `.env` (or **Admin → AI assistant**) selects:

- `keyword` — offline rule-based extraction, instant, no model needed
- `ollama` — local model (`OLLAMA_MODEL`). On CPU-only machines replies take ~1 minute; use a GPU host for production
- `anthropic` — Claude via `ANTHROPIC_API_KEY`; best Amharic quality

### Background jobs (optional)

```bash
cd api
celery -A worker.celery_app worker --loglevel=info
celery -A worker.celery_app beat --loglevel=info   # nightly MESOB refresh + daily maintenance
```

The same jobs can be run on demand from **Admin → Data sources**; every run is logged with its stats.

### Tests

```bash
cd api && uv run pytest -q     # needs postgres running and a seeded graph (scripts.seed_graph)
```

## Auth model

Self-hosted, in `api/auth/` (`security.py` primitives, `service.py` flows) and `api/v1/auth.py`.

- **Passwords:** bcrypt (cost 12). At least 8 characters with a letter and a number; over 72 bytes is rejected rather than truncated.
- **Sessions:** a 15-minute HS256 access token (signed with `SECRET_KEY`), kept only in browser memory, plus a 30-day refresh token in an httpOnly cookie scoped to `/api/v1/auth`. Every request checks that the session row is still live, so sign-out, deactivation and password changes take effect immediately.
- **Refresh rotation:** each refresh replaces the token. Presenting an old token again (after a 30-second grace window for two tabs refreshing at once) revokes the whole session family and is logged as `refresh_reuse`.
- **Protection:** 5 failed sign-ins per email (25 per IP) in 15 minutes locks sign-in for 15 minutes; 10 registrations per IP per hour; unknown emails take the same time and get the same error as wrong passwords.
- **Passwords forgotten:** `POST /auth/forgot-password` emails a one-hour, single-use link when `SMTP_*` is set (otherwise the link is written to the API log), and admins can issue a link from **Admin → Users & roles**. Resetting signs out every device.
- **Self-service** at `/account`: profile, change password (signs out other devices), list and sign out devices, recent security activity.
- **Audit:** every sign-in, failure, lockout, logout, reset and admin action goes to `auth_events`; admins see a summary and the log on the Users page.
- **Production:** set `ENVIRONMENT=production` (refuses the default `SECRET_KEY`), `AUTH_COOKIE_SECURE=true` behind HTTPS, and `AUTH_COOKIE_SAMESITE=none` only if the web and API live on different sites. Run uvicorn with `--proxy-headers` behind a reverse proxy so rate limits see real client IPs.
- **Roles:** `user`, `agent` (granted automatically when a Guday Geday application is approved), staff are separate accounts (see Admin accounts).
- **Public:** catalog, Guday Geday directory, business directory, roadmap create/get, feedback.
- **Signed in:** chat, saving progress, Guday Geday registration (needs Fayda ID verification), client requests, business registration.
- **Admin only:** everything under `/api/v1/admin/*`.

## National ID verification (Fayda)

Guday Geday applicants verify their identity with Fayda (National ID Program, MOSIP eSignet OIDC) before applying.

- `FAYDA_MODE=sandbox` (default): a clearly marked test screen; one-time code `111111`. Use only for demos.
- `FAYDA_MODE=live`: real eSignet flow (PKCE, `private_key_jwt`, signed userinfo checked against Fayda's JWKS). Requires registering as a relying party with NIDP: client ID, an RSA key pair (public key as JWK to NIDP), the whitelisted callback `…/guday/register/fayda-callback`, and the authorize/token/userinfo/JWKS URLs. Set `FAYDA_*` and a permanent `ID_HASH_PEPPER` in `api/.env`.
- The full Fayda number is never stored: only a peppered hash (one ID per account) and the last four digits.

## Deploying

The API ships as a Docker image (`api/Dockerfile`): it runs as a non-root user, without auto-reload, with a health check on `/`, and `api/.dockerignore` keeps `.env`, logs, `uploads/` and tests out of the image. `docker compose` (in `api/`) publishes every port on `127.0.0.1` only; put a TLS reverse proxy (nginx, Caddy) in front of the API on `127.0.0.1:8080`.

```bash
cd api
cp .env.sample .env            # then fill in every value below
docker compose up -d --build postgres redis web worker beat
```

Run exactly one `beat`: it starts the scheduled jobs (Chapa payout checks every 15 minutes, daily upkeep). The trained assistant models (`models_store/`, not in git) are copied into the image when the build machine has them and kept on the `models` volume; on a fresh server either build from a machine that has them or retrain from Admin, Assistant.

### Production checklist

Set these in `api/.env` (or your host's secret store) before the first start:

- [ ] `ENVIRONMENT=production`: hides `/docs` and `/openapi.json`, turns off auto-reload and refuses a weak `SECRET_KEY`.
- [ ] `SECRET_KEY`: 32 or more random characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`). Never reuse the sample value.
- [ ] `PAYOUT_ENCRYPTION_KEY`: a Fernet key (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) that encrypts bank accounts and guarantor ID numbers. Production refuses to start without it. Keep it with your backups: without it those values can't be read.
- [ ] `ID_HASH_PEPPER`: its own random value, set once and never changed (it keys the stored national ID hashes).
- [ ] `POSTGRES_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`: strong, unique passwords. Compose refuses to start without them. Use letters and digits only for `POSTGRES_PASSWORD`, since it is placed inside `DATABASE_URL`.
- [ ] `AUTH_COOKIE_SECURE=true` (HTTPS only). `AUTH_COOKIE_SAMESITE=none` only if the web site and the API are on different sites.
- [ ] `CORS_ORIGINS`: only your real web and admin addresses, for example `https://example.et,https://admin.example.et`.
- [ ] `WEB_BASE_URL`, `ADMIN_BASE_URL`, `API_PUBLIC_URL`: the public HTTPS addresses (used in emails, payment returns and the Chapa webhook).
- [ ] `PAYMENTS_MODE=chapa` with the live `CHAPA_SECRET_KEY` (not `CHASECK_TEST-`) and `CHAPA_WEBHOOK_SECRET` from the Chapa dashboard.
- [ ] `FAYDA_MODE=live` with the `FAYDA_*` values issued by the National ID Program. Never run the sandbox in production.
- [ ] SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`) so password reset links go by email and are never written to logs.
- [ ] `FORWARDED_ALLOW_IPS`: the address of your reverse proxy, so rate limits see real client IPs.
- [ ] `WEB_CONCURRENCY`: number of API worker processes. Migrations take a database lock, so more than one is safe.
- [ ] VAT and receipts: `PLATFORM_LEGAL_NAME`, `PLATFORM_TIN`, `PLATFORM_VAT_NUMBER`, `PLATFORM_ADDRESS`.

### Logs

- `LOG_LEVEL` (default `INFO`). Do not run production at `DEBUG`.
- Outside Docker, logs go to stdout and to `LOG_FILE` (default `logs/api.log`), rotated at `LOG_MAX_BYTES` (10 MB) keeping `LOG_BACKUP_COUNT` (5) old files. The image sets `LOG_FILE` empty and logs to stdout only; read them with `docker compose logs web`.
- Request bodies are never logged, and access log lines drop the query string.

### Data and backups

- Uploaded files (including national ID copies) live on the `uploads` volume, never in the image. Back it up together with the databases and keep the backups encrypted.
- Postgres is the system of record. Back it up every day, for example `docker compose exec postgres pg_dump -U navigator compliance_navigator | gzip > backup-$(date +%F).sql.gz`, keep copies off the server, and test a restore regularly.
- The compliance graph is in Postgres (`graph_nodes`, `graph_edges`), so the daily dump covers it. It can also be rebuilt from the seed scripts and data sources.
- Moving an older install off Neo4j: `uv sync --group migrate`, then `uv run python -m scripts.copy_graph_from_neo4j --dry-run` (counts only) and without `--dry-run` to copy, with `NEO4J_URI`, `NEO4J_USERNAME` and `NEO4J_PASSWORD` set. It is safe to run again.
- Database migrations run automatically when the API starts.
