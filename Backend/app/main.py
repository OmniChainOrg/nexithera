from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .core.database import db
from .core.storage import storage
from .api import (
    programs,
    assets,
    health,
    evidence,
    hypotheses,
    candidates,
    agents,
    guardian,
    simulations,
    advanced_simulations,
    analysis,
    forecast,
    chronothera,
    websocket,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await db.init()
    await storage.init()
    print("✅ Database and storage initialized")

    # Initialise ChronoThera epistemicos client and inject into service
    from .clients.epistemicos_client import EpistemicOSClient
    from .services.chronothera_service import chronothera_service as _ct_service

    _epistemicos_client = EpistemicOSClient()
    is_live = await _epistemicos_client.health_check()
    if is_live:
        _ct_service.epistemicos = _epistemicos_client
        _ct_service.pk_adapter._client = _epistemicos_client
        print("✅ EpistemicOS client connected (live mode)")
    else:
        print("⚠️  EpistemicOS unreachable; ChronoThera will use synthetic fallback")

    yield

    # Shutdown
    await _epistemicos_client.close()
    await db.close()
    print("👋 Shutting down")

app = FastAPI(
    title="Genovate API",
    description="NexiThera's internal drug-discovery workbench",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(programs.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(hypotheses.router, prefix="/api/v1")
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(guardian.router, prefix="/api/v1")
app.include_router(simulations.router, prefix="/api/v1")
app.include_router(advanced_simulations.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(forecast.router, prefix="/api/v1")
app.include_router(chronothera.router, prefix="/api/v1")
# WebSocket routes are mounted at the root (no /api/v1 prefix) since the
# frontend already speaks `/ws/program/{program_id}` (PR #8).
app.include_router(websocket.router)

@app.get("/")
async def root():
    return {"service": "Genovate", "status": "operational", "version": "0.1.0"}
