"""
Forge Plus (Enterprise Tier): EpistemicOS + SynapticaOS dual kernel.
$20,000/month - Multi-zone CXU reasoning with cross-zone swarm orchestration.
Full distributed execution and governance federation.
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
    advanced_simulations,
    swarm_orchestration,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("⚡ Forge Plus (EpistemicOS + SynapticaOS Enterprise) starting...")
    yield
    # Shutdown
    print("⚡ Forge Plus shutting down...")


app = FastAPI(
    title="Forge Plus",
    description="Enterprise tier cognitive engine (dual kernel: EpistemicOS + SynapticaOS)",
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

# Include routers (Forge Plus includes advanced_simulations and swarm_orchestration)
app.include_router(ingestion.router, prefix="/api/v1", tags=["ingestion"])
app.include_router(evidence.router, prefix="/api/v1", tags=["evidence"])
app.include_router(hypothesis_formation.router, prefix="/api/v1", tags=["hypotheses"])
app.include_router(reasoning.router, prefix="/api/v1", tags=["reasoning"])
app.include_router(advanced_simulations.router, prefix="/api/v1", tags=["advanced_simulations"])
app.include_router(swarm_orchestration.router, prefix="/api/v1", tags=["swarm_orchestration"])

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "tier": "forge_plus", "kernels": ["epistemicos", "synapticaos"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8020)
