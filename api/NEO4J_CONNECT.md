# Connect to local Neo4j (Docker)

## Your database is fine if this works

```bash
cd api
docker compose up -d neo4j
docker exec api-neo4j-1 cypher-shell -u neo4j -p darixsamani "RETURN 1"
```

`uv run python -m scripts.seed_graph` also proves Bolt works.

---

## Error: "Failure discovering endpoints" / "Failed to fetch"

This almost always means **Neo4j Desktop** or Browser is trying **cloud/Aura discovery** (`neo4j://` + routing), not your Docker box.

### Fix — use the web UI (simplest)

1. Open **Chrome or Edge**: http://localhost:7474
2. **Do not** use Neo4j Desktop for this project.
3. Connect URL: `bolt://127.0.0.1:7687` (on Windows, prefer this over `localhost`)
4. User: `neo4j` / Password: `darixsamani`

### If you must use Neo4j Desktop

1. **File → Add → Remote connection** (not Aura, not "Open local")
2. URL: `bolt://localhost:7687`
3. Sign out of / ignore Aura instances in Desktop
4. Do not paste an Aura `neo4j+s://` URL

### Never use for local Docker

| URL | Result |
|-----|--------|
| `neo4j://localhost:7687` | Routing discovery error |
| `neo4j+s://....` | Aura only |
| Empty / Aura instance | "Failed to fetch" |

---

## Query without Browser

```bash
docker exec -it api-neo4j-1 cypher-shell -u neo4j -p darixsamani
```

Then:

```cypher
MATCH (s:Service) RETURN s.id, s.name LIMIT 10;
```
