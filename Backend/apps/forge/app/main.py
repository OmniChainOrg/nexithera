"""Forge: Local drug-discovery workbench (EpistemicOS only).

Single-zone CXU simulation, evidence graphs, hypothesis generation.
Standard tier: $500/month ceiling.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from ...core.database import db
from ...core.storage import storage
from ...api import (
    programs, assets, health, evidence, hypotheses, candidates,
    agents, guardian, simulations, analysis, forecast, websocket
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    try:
        await storage.init()
        print("✅ Forge: Database and storage initialized")
    except Exception as e:
        print(f"⚠️  Storage unavailable: {e}")
    yield
    await db.close()


app = FastAPI(
    title="Forge",
    description="Local drug-discovery workbench (EpistemicOS)",
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

# Shared routes (no advanced simulations or swarm)
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(programs.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(hypotheses.router, prefix="/api/v1")
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(guardian.router, prefix="/api/v1")
app.include_router(simulations.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(forecast.router, prefix="/api/v1")
app.include_router(websocket.router)

@app.get("/")
async def root():
    return {"app": "Forge", "tier": "standard", "status": "operational", "version": "1.0.0"}
