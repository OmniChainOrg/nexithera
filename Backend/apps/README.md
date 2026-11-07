# Forge Trilogy: App Architecture

## Directory Structure

```
Backend/
├── app/                           # Shared core (database, storage, services, API)
│   ├── cogpm/                     # Cognitive Package Manager
│   │   ├── manifest.py            # App manifest schema + signing
│   │   ├── validator.py           # Policy + entitlement validation
│   │   ├── provisioner.py         # State machine + orchestration
│   │   └── kernel_backends.py     # EpistemicOS + SynapticaOS adapters
│   ├── core/                      # Database, storage, config
│   ├── services/                  # Business logic (evidence, simulation, etc.)
│   ├── api/                       # Route handlers
│   └── main.py                    # Legacy Genovate (monolith)
│
├── apps/                          # Forge Trilogy: three separate apps
│   ├── forge/
│   │   ├── app/main.py            # Forge app (EpistemicOS only)
│   │   └── Dockerfile
│   ├── forge_plus/
│   │   ├── app/main.py            # Forge Plus (EpistemicOS + SynapticaOS)
│   │   └── Dockerfile
│   └── chronothera/
│       ├── app/main.py            # ChronoThera add-on
│       └── Dockerfile
```

## Apps

### Forge (Standard, $500/mo)
- **Kernels**: EpistemicOS only
- **Routes**: ingestion, evidence graphs, hypotheses, single-zone CXU
- **Excludes**: cross-zone simulation, swarm orchestration
- **Target**: researchers, small labs, proof-of-concept

### Forge Plus (Enterprise, $20k/mo)
- **Kernels**: EpistemicOS (governance) + SynapticaOS (execution)
- **Routes**: Forge + cross-zone & swarm orchestration
- **Hosting deps**: protein folding service
- **Target**: pharma companies, hospitals, multi-zone simulations

### ChronoThera (Pro Add-on, $2k/mo)
- **Kernels**: EpistemicOS (governance only)
- **Routes**: formulation delivery, manufacturing intelligence
- **Requires**: Forge or Forge Plus installed
- **Target**: specialized formulation teams within enterprises

## Provisioning Flow

1. **Submit** manifest + signature
2. **Validate**:
   - Publisher signature
   - Tenant entitlements
   - Install authority
   - Kernel version & capabilities
   - Hosting dependencies
   - Spend ceiling policy
3. **Provision** (Forge Plus example):
   - Create EpistemicOS zone (governance)
   - Link SynapticaOS swarm to that zone
   - Tag with spend ceiling & enforcement policy
4. **Activate**: installation transitions to ACTIVE
5. **Rollback** (on any failure): deprovision in reverse order

## Running Locally

```bash
docker-compose -f docker-compose.forge-trilogy.yml up
```

Services:
- Forge: `http://localhost:8010/docs`
- Forge Plus: `http://localhost:8020/docs`
- ChronoThera: `http://localhost:8030/docs`
- EpistemicOS: `http://localhost:8001/docs`
- SynapticaOS: `http://localhost:8002/docs` (stub)

## Manifest & Kernel Pins

See `app_manifests/`:
- `forge.yaml`
- `forge_plus.yaml`
- `chronothera.yaml`

All pin EpistemicOS commit `b438512` (post-merge v0.1.0).
SynapticaOS pins are pending (awaits Synaptica repository).

## Testing

```bash
cd Backend
python -m pytest tests/test_cogpm.py -v
```

## Next Steps

### Phase 3: Persistence & REST API
- [ ] SQLAlchemy models for `Installation` state
- [ ] REST endpoints: `/provisioning/install`, `/provisioning/install/{id}`, approve
- [ ] Real EpistemicOS zone provisioning (currently stubbed)
- [ ] Real SynapticaOS swarm allocation (awaits SynapticaOS API)

### Phase 4: Spend Enforcement
- [ ] Track usage: events table (app, tenant, cost, timestamp)
- [ ] Runtime budget checks before new CXU zones
- [ ] Return 429 when ceiling hit

### Phase 5: End-to-End Testing & Release
- [ ] Package each app as Docker image with version tag
- [ ] Simulate tenant onboarding (submit → approve → active → spend limit)
- [ ] Release checklist (manifests, signatures, kernel pins)
