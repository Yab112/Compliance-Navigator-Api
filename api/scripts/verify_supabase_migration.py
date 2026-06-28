"""Verify Supabase migration 001 was applied."""

from __future__ import annotations

from pathlib import Path
import os
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[1]
env_path = ROOT / ".env"

for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip())

url = os.environ.get("DATABASE_URL")
if not url:
    print("DATABASE_URL missing in api/.env", file=sys.stderr)
    sys.exit(1)

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('profiles', 'roadmaps', 'manual_references', 'legal_chunks')
            ORDER BY 1
            """
        )
        tables = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        has_vector = cur.fetchone() is not None
        cur.execute(
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid "
            "WHERE n.nspname = 'public' AND p.proname = 'match_legal_chunks'"
        )
        has_fn = cur.fetchone() is not None

print("Tables:", tables)
print("pgvector:", has_vector)
print("match_legal_chunks:", has_fn)
if len(tables) == 4 and has_vector and has_fn:
    print("OK")
else:
    sys.exit(1)
