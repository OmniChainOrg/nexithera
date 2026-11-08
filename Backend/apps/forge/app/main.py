"""
Forge (Standard Tier): EpistemicOS only cognitive engine.
$500/month - Single-zone CXU reasoning with evidence ingestion.
No cross-zone orchestration or swarm distribution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import routers
from app.routers import (
    ingestion,
    evidence,
    hypothesis_formation,
    reasoning,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🔥 Forge (EpistemicOS Standard) starting...")
    yield
    # Shutdown
    print("🔥 Forge shutting down...")


app = FastAPI(
    title="Forge",
    description="Standard tier cognitive engine (EpistemicOS only)",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (Forge-tier capabilities only)
app.include_router(ingestion.router, prefix="/api/v1", tags=["ingestion"])
app.include_router(evidence.router, prefix="/api/v1", tags=["evidence"])
app.include_router(hypothesis_formation.router, prefix="/api/v1", tags=["hypotheses"])
app.include_router(reasoning.router, prefix="/api/v1", tags=["reasoning"])

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "tier": "forge", "kernel": "epistemicos"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
