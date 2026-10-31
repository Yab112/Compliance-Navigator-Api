# Compliance Navigator API

FastAPI backend for Compliance Navigator. Postgres (with pgvector) holds everything, including the
compliance graph (`graph_nodes` and `graph_edges`, see `services/graph_store.py`). Redis and Celery run
the scheduled jobs.

```bash
cp .env.sample .env
docker compose up -d postgres redis
uv sync
uv run python -m scripts.seed_graph     # compliance graph
uv run main.py                          # http://localhost:8080
```

Setup, tests, deployment and backups are in the [repository README](../README.md).
