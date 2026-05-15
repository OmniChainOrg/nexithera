from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .core.database import db
from .core.storage import storage
from .api import programs, assets, health, evidence, hypotheses, candidates, agents, guardian, simulations

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await db.init()
    await storage.init()
    print("✅ Database and storage initialized")
    yield
    # Shutdown
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

@app.get("/")
async def root():
    return {"service": "Genovate", "status": "operational", "version": "0.1.0"}
