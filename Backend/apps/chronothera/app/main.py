"""ChronoThera: Formulation delivery and manufacturing intelligence.

Add-on app for Forge or Forge Plus. Requires one of them to be installed.
Pro tier: $2,000/month ceiling (with controlled overage).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from ...core.database import db
from ...core.storage import storage
from ...api import health, chronothera, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    try:
        await storage.init()
        print("✅ ChronoThera: Database and storage initialized")
    except Exception as e:
        print(f"⚠️  Storage unavailable: {e}")
    yield
    await db.close()


app = FastAPI(
    title="ChronoThera",
    description="Formulation delivery and manufacturing intelligence",
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

# ChronoThera-specific routes
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(chronothera.router, prefix="/api/v1")
app.include_router(websocket.router)

@app.get("/")
async def root():
    return {"app": "ChronoThera", "tier": "pro_addon", "status": "operational", "version": "1.0.0"}
