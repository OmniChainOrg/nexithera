"""Forge Plus: Dual-kernel Forge (EpistemicOS + SynapticaOS).

Cross-zone simulations, swarm orchestration, distributed CXU execution.
Enterprise tier: $20,000/month ceiling.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from ...core.database import db
from ...core.storage import storage
from ...api import (
    programs, assets, health, evidence, hypotheses, candidates,
    agents, guardian, simulations, advanced_simulations, analysis, forecast, websocket
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    try:
        await storage.init()
        print("✅ Forge Plus: Database and storage initialized")
    except Exception as e:
        print(f"⚠️  Storage unavailable: {e}")
    yield
    await db.close()


app = FastAPI(
    title="Forge Plus",
    description="Dual-kernel Forge (EpistemicOS + SynapticaOS)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All routes including advanced (cross-zone, swarm)
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
app.include_router(websocket.router)

@app.get("/")
async def root():
    return {"app": "Forge Plus", "tier": "enterprise", "status": "operational", "version": "1.0.0"}
