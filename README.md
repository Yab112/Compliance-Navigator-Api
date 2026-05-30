# Compliance Navigator

Graph-based decision support for Ethiopian business compliance. Maps regulatory requirements as a dependency graph and produces step-by-step roadmaps grounded in legal sources.

## Repository layout

```
Compliance Navigator/
├── Doc/          # Product & architecture specs
├── web/          # Next.js frontend (shadcn, Zod, Zustand)
└── api/          # FastAPI backend (Neo4j, JWT auth)
```

## Quick start

### API

```bash
cd api
cp .env.sample .env.dev
docker compose up -d
uv run main.py
```

API runs at http://localhost:8080

### Web

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

Web runs at http://localhost:3000

## Auth model

- **Public:** compliance reads, `GET /posts`, health checks
- **Login required:** register, profile (`/auth/me`), mutating user-owned data

Frontend stores JWT in `localStorage` and sends `Authorization: Bearer` to the API.
