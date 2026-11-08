"""
ChronoThera (Pro Add-on): Formulation delivery and manufacturing intelligence.
$2,000/month - Requires Forge or Forge Plus.
Adds drug formulation design, temporal release profiles, manufacturing workflows.
Inherits all parent capabilities and adds specialized formulation domain.
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
    chronothera,  # Formulation-specific
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("💊 ChronoThera (Formulation Add-on) starting...")
    yield
    # Shutdown
    print("💊 ChronoThera shutting down...")


app = FastAPI(
    title="ChronoThera",
    description="Pro add-on tier: Formulation delivery & manufacturing intelligence",
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

# Include routers (ChronoThera adds formulation domain, requires Forge/Plus parent)
app.include_router(ingestion.router, prefix="/api/v1", tags=["ingestion"])
app.include_router(evidence.router, prefix="/api/v1", tags=["evidence"])
app.include_router(hypothesis_formation.router, prefix="/api/v1", tags=["hypotheses"])
app.include_router(reasoning.router, prefix="/api/v1", tags=["reasoning"])
app.include_router(chronothera.router, prefix="/api/v1", tags=["chronothera"])

# Health check
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "tier": "chronothera",
        "addon": True,
        "requires_parent": ["forge", "forge_plus"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8030)
