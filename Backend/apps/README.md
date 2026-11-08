# Forge Trilogy: Phase 2 Architecture & Deployment

## Overview

Phase 2 introduces **three independent, containerized cognitive apps** built on top of the CogPM (Cognitive Package Manager) from Phase 1:

| App | Tier | Monthly | Kernel(s) | Capabilities | Port |
|-----|------|---------|-----------|--------------|------|
| **Forge** | Standard | $500 | EpistemicOS | Single-zone ingestion, evidence, hypotheses | 8010 |
| **Forge Plus** | Enterprise | $20k | EpistemicOS + SynapticaOS | Multi-zone orchestration, cross-zone swarms | 8020 |
| **ChronoThera** | Add-on | $2k | EpistemicOS (+ parent) | Formulation design, manufacturing workflows | 8030 |

## App Architecture

### Forge (Standard Tier)

**File**: `Backend/apps/forge/app/main.py`

A lightweight FastAPI app that includes only core reasoning capabilities:
- `/api/v1/ingestion/*` — Drug candidate ingestion
- `/api/v1/evidence/*` — Evidence aggregation & credibility scoring
- `/api/v1/hypotheses/*` — Hypothesis formation from evidence
- `/api/v1/reasoning/*` — Single-zone CXU reasoning

**No advanced simulations or swarm orchestration** (those require Forge Plus).

### Forge Plus (Enterprise Tier)

**File**: `Backend/apps/forge_plus/app/main.py`

Extends Forge with distributed execution:
- All Forge capabilities
- `/api/v1/advanced_simulations/*` — Multi-parameter sensitivity analysis, Monte Carlo, etc.
- `/api/v1/swarm_orchestration/*` — Cross-zone CXU coordination, swarm allocation

Dual kernel backend:
1. **EpistemicOS** handles governance, reasoning, policy adherence
2. **SynapticaOS** orchestrates distributed execution across zones

### ChronoThera (Pro Add-on)

**File**: `Backend/apps/chronothera/app/main.py`

Specialization add-on for formulation domain:
- Inherits all parent app capabilities (Forge or Forge Plus)
- `/api/v1/chronothera/*` — Drug formulation design, release profiles, manufacturing
- Requires `requires_any_of: [forge, forge_plus]` from manifest validation

## Containerization

### Dockerfiles

Each app has a minimal, optimized Dockerfile:

**Backend/apps/forge/Dockerfile**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY Backend/app ./app
COPY Backend/apps/forge/app ./forge_app
COPY app_manifests ./app_manifests
ENV APP_TIER=forge
CMD ["python", "-m", "uvicorn", "forge_app.main:app", "--host", "0.0.0.0", "--port", "8010"]
```

Similar structure for Forge Plus (port 8020) and ChronoThera (port 8030).

**Key features:**
- Alpine Python base (slim) for minimal image size
- Health checks via `/health` endpoint
- Environment variables for kernel backend configuration
- Manifest validation support

### Build & Run Locally

**Individual app:**
```bash
# Build Forge image
docker build -f Backend/apps/forge/Dockerfile -t forge:latest .

# Run Forge app
docker run -p 8010:8010 forge:latest
```

**Full stack (docker-compose):**
```bash
# Start all three apps + kernels + infrastructure
docker-compose -f docker-compose.forge-trilogy.yml up

# Health check
curl http://localhost:8010/health  # Forge
curl http://localhost:8020/health  # Forge Plus
curl http://localhost:8030/health  # ChronoThera
```

## Docker Compose Stack

**File**: `docker-compose.forge-trilogy.yml`

Orchestrates a complete dev/test environment:

**Apps** (3 services):
- `forge` (port 8010)
- `forge_plus` (port 8020)
- `chronothera` (port 8030)

**Kernels** (2 services, stubbed):
- `epistemicos` (port 8001) — Governance & reasoning kernel
- `synapticaos` (port 8002) — Distributed execution kernel

**Infrastructure** (3 services):
- `postgres` (5432) — Persistent state (deployments, installations, audit)
- `redis` (6379) — Caching & task queue
- `minio` (9000/9001) — S3-compatible blob storage

**Network**:
- All services on `forge-network` bridge
- Apps can reach kernels and infrastructure by hostname
- Ports exposed only for external testing

**Health Checks**:
- Each service has `HEALTHCHECK` (10s interval, 5s timeout, 5 retries)
- Compose waits for dependencies (e.g., Forge waits for EpistemicOS and Postgres)

## Deployment Topology

```
┌─────────────────────────────────────────────────────────┐
│                   Docker Network                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │    Forge     │  │ Forge Plus   │  │ ChronoThera  │  │
│  │   (8010)     │  │   (8020)     │  │   (8030)     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                │                   │          │
│         └────────────────┼───────────────────┘          │
│                          │                               │
│  ┌──────────────┐  ┌──────────────┐                     │
│  │ EpistemicOS  │  │ SynapticaOS  │                     │
│  │   (8001)     │  │   (8002)     │                     │
│  └──────────────┘  └──────────────┘                     │
│         │                │                               │
│         └────────────────┼───────────────────┐           │
│                          │                   │           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐    │
│  │  PostgreSQL  │  │    Redis     │  │   MinIO    │    │
│  │   (5432)     │  │   (6379)     │  │ (9000/01)  │    │
│  └──────────────┘  └──────────────┘  └────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Configuration & Environment

### App Environment Variables

**Forge**:
```
EPISTEMICOS_URL=http://epistemicos:8001
POSTGRES_URL=postgresql://user:password@postgres:5432/forge
REDIS_URL=redis://redis:6379/0
APP_TIER=forge
KERNEL_BACKEND=epistemicos
```

**Forge Plus**:
```
EPISTEMICOS_URL=http://epistemicos:8001
SYNAPTICAOS_URL=http://synapticaos:8002
POSTGRES_URL=postgresql://user:password@postgres:5432/forge_plus
REDIS_URL=redis://redis:6379/1
APP_TIER=forge_plus
KERNEL_BACKENDS=epistemicos,synapticaos
```

**ChronoThera**:
```
EPISTEMICOS_URL=http://epistemicos:8001
POSTGRES_URL=postgresql://user:password@postgres:5432/chronothera
REDIS_URL=redis://redis:6379/2
APP_TIER=chronothera
APP_ADDON=true
```

## Testing Phase 2

### Unit/Integration Tests

All existing Genovate tests continue to work. Phase 2 adds no breaking changes.

```bash
cd Backend
python -m pytest tests/ -v
```

### Container Tests

**Build all images:**
```bash
docker-compose -f docker-compose.forge-trilogy.yml build
```

**Start stack:**
```bash
docker-compose -f docker-compose.forge-trilogy.yml up -d
```

**Health checks:**
```bash
# Wait for services to be healthy
sleep 10

# Test Forge
curl http://localhost:8010/health
# Expected: {"status": "healthy", "tier": "forge", "kernel": "epistemicos"}

# Test Forge Plus
curl http://localhost:8020/health
# Expected: {"status": "healthy", "tier": "forge_plus", "kernels": ["epistemicos", "synapticaos"]}

# Test ChronoThera
curl http://localhost:8030/health
# Expected: {"status": "healthy", "tier": "chronothera", "addon": true, "requires_parent": ["forge", "forge_plus"]}
```

**Stop stack:**
```bash
docker-compose -f docker-compose.forge-trilogy.yml down
```

## Phase 2 Files Summary

| File | Purpose |
|------|---------|
| `Backend/apps/forge/app/main.py` | Forge Standard tier app |
| `Backend/apps/forge_plus/app/main.py` | Forge Plus Enterprise tier app |
| `Backend/apps/chronothera/app/main.py` | ChronoThera Pro add-on app |
| `Backend/apps/forge/Dockerfile` | Forge container image definition |
| `Backend/apps/forge_plus/Dockerfile` | Forge Plus container image definition |
| `Backend/apps/chronothera/Dockerfile` | ChronoThera container image definition |
| `docker-compose.forge-trilogy.yml` | Full stack orchestration (all 3 apps + kernels + infra) |
| `Backend/apps/README.md` | This file |

## Next Steps: Phase 3

Phase 3 will add:
1. **SQLAlchemy models** — persistent Installation, Deployment, StateTransition records
2. **ProvisioningService** — bridge between in-memory CogPM and database
3. **REST API** — `/api/v1/provisioning/install`, `/api/v1/provisioning/install/{id}/approve`, etc.
4. **Alembic migration** — database schema for provisioning state machine
5. **Integration tests** — end-to-end provisioning workflows

Phase 3 will be a separate PR (#46) that builds on Phase 2 apps.

## Known Limitations (Phase 2)

- Kernel backends (EpistemicOS, SynapticaOS) are **stubbed** — no actual kernel API calls yet (Phase 3)
- Apps load manifest YAML but don't yet validate against kernel requirements
- No spending/quota enforcement yet (Phase 4)
- No real kernel health checks (will improve in Phase 3)

---

**Status**: Phase 2 ✅ Complete — Three apps + Docker setup ready for testing.
