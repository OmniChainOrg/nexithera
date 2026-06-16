"""FastAPI endpoints for ChronoThera formulation intelligence."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.chronothera import ChronoTheraSimulationRequest, GuardianReviewRequest
from ..services.chronothera_service import chronothera_service

router = APIRouter(prefix="/chronothera", tags=["chronothera"])


@router.get("/catalog")
async def get_catalog() -> Dict[str, Any]:
    """Return formulation objectives, routes, excipients, and asset presets."""
    return chronothera_service.catalog()


@router.post("/simulations")
async def run_simulation(payload: ChronoTheraSimulationRequest) -> Dict[str, Any]:
    """Run a deterministic ChronoThera research-use simulation."""
    result = await chronothera_service.run_simulation(payload)
    return result.model_dump(mode="json")


@router.get("/simulations")
async def list_simulations(asset_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """List persisted ChronoThera simulations, optionally filtered by asset."""
    simulations = await chronothera_service.list_simulations(asset_id=asset_id)
    return {"simulations": simulations, "count": len(simulations)}


@router.get("/simulations/{simulation_id}")
async def get_simulation(simulation_id: str) -> Dict[str, Any]:
    """Fetch a persisted ChronoThera simulation by ID."""
    simulation = await chronothera_service.get_simulation(simulation_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="ChronoThera simulation not found")
    return simulation


@router.get("/assets/{asset_id}/formulation-profile")
async def build_asset_formulation_profile(asset_id: str) -> Dict[str, Any]:
    """Return the most recent ChronoThera profile linked to an asset dossier."""
    simulations = await chronothera_service.list_simulations(asset_id=asset_id)
    if not simulations:
        raise HTTPException(status_code=404, detail="No ChronoThera simulations found for asset")
    latest = simulations[0]
    return {
        "asset_id": asset_id,
        "simulation_id": latest["id"],
        "formulation_delivery_profile": latest["formulation_delivery_profile"],
        "overall_chronothera_score": latest["overall_chronothera_score"],
        "guardian_review": latest["guardian_review"],
    }


@router.post("/simulations/{simulation_id}/guardian-review")
async def record_guardian_review(simulation_id: str, payload: GuardianReviewRequest) -> Dict[str, Any]:
    """Attach a Guardian decision to a ChronoThera simulation record."""
    simulation = await chronothera_service.record_guardian_review(simulation_id, payload)
    if not simulation:
        raise HTTPException(status_code=404, detail="ChronoThera simulation not found")
    return simulation
