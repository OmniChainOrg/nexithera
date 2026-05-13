# Genovate – Backend (MVP)

Genovate is NexiThera's internal drug-discovery workbench. This backend is the
**foundation PR (#1)**: a FastAPI application backed by PostgreSQL, Redis and
S3-compatible storage (MinIO) plus a **stub** EpistemicOS client.

> **Key principle**: Genovate delegates all ingestion, embedding, and
> simulation to EpistemicOS via a clean client interface. No real embedding,
> chunking, vector search, evidence graph, agent orchestration, Guardian
> review or simulation logic lives in this codebase. Those arrive in later
> PRs.

---

## What this PR delivers

- ✅ FastAPI app with Postgres + Redis + MinIO via `docker-compose`
- ✅ Multi-tenant organization + user model (auth-ready)
- ✅ Program creation (oncology & immunotherapy as first vertical)
- ✅ Data asset upload with metadata tracking
- ✅ EpistemicOS client **stub** that simulates the ingestion pipeline
- ✅ Alembic migrations skeleton (`migrations/versions/001_initial_schema.py`)
- ✅ Basic unit tests for `AssetService` and the EpistemicOS stub client

What this PR explicitly does **not** do: real embedding/chunking, vector
search, evidence graph, agent orchestration, Guardian reviews, or any kind
of simulation.

---

## Layout

```
Backend/
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app
│   ├── api/                          # HTTP routes
│   │   ├── __init__.py
│   │   ├── health.py                 # GET /api/v1/health
│   │   ├── programs.py               # POST/GET /api/v1/programs
│   │   └── assets.py                 # POST/GET /api/v1/programs/{id}/assets
│   ├── core/                         # config, database, storage
│   ├── models/                       # domain dataclasses (no ORM)
│   ├── schemas/                      # Pydantic request/response schemas
│   └── services/
│       ├── asset_service.py          # upload + metadata + EpistemicOS handoff
│       └── epistemicos_client.py     # **stub** client
├── migrations/                       # Alembic
│   ├── env.py
│   └── versions/001_initial_schema.py
├── tests/                            # pytest unit tests
├── alembic.ini
└── pytest.ini
```

`Dockerfile`, `docker-compose.yml`, `.env.example` and `requirements.txt`
live at the repository root.

---

## Run with Docker Compose

From the repository root:

```bash
docker-compose up -d
```

This starts:

| Service        | Port  | Notes                              |
| -------------- | ----- | ---------------------------------- |
| `postgres`     | 5432  | user/pwd/db: `genovate`            |
| `redis`        | 6379  |                                    |
| `minio`        | 9000  | console on 9001 (`minioadmin`)     |
| `genovate-api` | 8000  | OpenAPI docs at `/docs`            |

The application creates its schema on startup (idempotent
`CREATE TABLE IF NOT EXISTS`). The Alembic migration in
`migrations/versions/001_initial_schema.py` is the canonical schema for
versioned environments.

---

## API

| Method | Path                                         | Purpose                |
| ------ | -------------------------------------------- | ---------------------- |
| GET    | `/api/v1/health`                             | Liveness + DB check    |
| POST   | `/api/v1/programs`                           | Create a program       |
| GET    | `/api/v1/programs/{program_id}`              | Fetch a program        |
| POST   | `/api/v1/programs/{program_id}/assets`       | Upload a data asset    |
| GET    | `/api/v1/programs/{program_id}/assets`       | List program assets    |

### Example

```bash
# Create a program
curl -X POST http://localhost:8000/api/v1/programs \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "TNBC Immune Resistance",
        "therapeutic_area": "oncology_immunotherapy",
        "description": "PD-1/PD-L1 resistance mechanisms"
      }'

# Upload an asset
curl -X POST -F "file=@test.pdf" \
  http://localhost:8000/api/v1/programs/<program_id>/assets
```

---

## Running tests

```bash
cd Backend
pip install -r ../requirements.txt
pytest
```

The tests stub out PostgreSQL, MinIO and the EpistemicOS service, so they
require no infrastructure.

---

## Verifying the "no embedding logic in Genovate" invariant

```bash
grep -RInE 'embed|chunk|vector' Backend/app
```

Hits should be limited to **stub IDs and mock fields** (e.g.
`embedding_collection_id`, `chunk_ids`, `vector_count`, `chunk_count`) or
docstrings. There must be no real chunking, embedding or vector-search
implementation in this codebase – all of that lives in EpistemicOS.
