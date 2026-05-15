# app/api/simulations.py — Simulation, zone, CXU, swarm endpoints
# Genovate exposes thin HTTP endpoints; EpistemicOS does the actual computation.
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.epistemicos_client import epistemicos_client
from ..services.simulation_service import simulation_service

router = APIRouter(prefix="/simulations", tags=["simulations"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ZoneCreateRequest(BaseModel):
    program_id: str
    zone_type: str
    config: Dict[str, Any] = {}
    name: Optional[str] = None


class SimulationRunRequest(BaseModel):
    zone_id: str
    simulation_type: str
    inputs: Dict[str, Any]
    program_id: str
    candidate_id: Optional[str] = None


class CXUCreateRequest(BaseModel):
    zone_id: str
    cxu_type: str
    configuration: Dict[str, Any] = {}
    program_id: str


class SwarmCreateRequest(BaseModel):
    swarm_config: Dict[str, Any]
    program_id: str
    objective: str


class CrossZoneRequest(BaseModel):
    source_zone_id: str
    target_zone_id: str
    coupling_map: Dict[str, str]
    inputs: Dict[str, Any]
    program_id: str


class SemanticSearchRequest(BaseModel):
    query: str
    collection_id: str
    program_id: str
    top_k: int = 10


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/zones")
async def create_zone(request: ZoneCreateRequest) -> Dict[str, Any]:
    """Create a new zone in EpistemicOS."""
    return await simulation_service.create_zone(
        program_id=request.program_id,
        zone_type=request.zone_type,
        config=request.config,
        name=request.name,
    )


@router.post("/run")
async def run_simulation(request: SimulationRunRequest) -> Dict[str, Any]:
    """Run a single-zone simulation via EpistemicOS."""
    try:
        return await simulation_service.run_simulation(
            zone_id=request.zone_id,
            simulation_type=request.simulation_type,
            inputs=request.inputs,
            program_id=request.program_id,
            candidate_id=request.candidate_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/cxus")
async def create_cxu(request: CXUCreateRequest) -> Dict[str, Any]:
    """Create a CXU (Causal Experience Unit) inside a zone."""
    try:
        return await simulation_service.create_cxu(
            zone_id=request.zone_id,
            cxu_type=request.cxu_type,
            configuration=request.configuration,
            program_id=request.program_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/swarms")
async def create_swarm(request: SwarmCreateRequest) -> Dict[str, Any]:
    """Create a swarm of CXUs for multi-agent simulation."""
    return await simulation_service.run_swarm(
        swarm_config=request.swarm_config,
        program_id=request.program_id,
        objective=request.objective,
    )


@router.get("/swarms/{swarm_id}/results")
async def get_swarm_results(swarm_id: str) -> Dict[str, Any]:
    """Get aggregated results for a swarm."""
    return await epistemicos_client.get_swarm_results(swarm_id)


@router.post("/cross-zone")
async def cross_zone_simulate(request: CrossZoneRequest) -> Dict[str, Any]:
    """Run a coupled simulation across two zones."""
    try:
        return await simulation_service.cross_zone_simulate(
            source_zone_id=request.source_zone_id,
            target_zone_id=request.target_zone_id,
            coupling_map=request.coupling_map,
            inputs=request.inputs,
            program_id=request.program_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> Dict[str, Any]:
    """Retrieve a verifiable trace from EpistemicOS."""
    return await simulation_service.get_verifiable_trace(trace_id)


@router.post("/search")
async def semantic_search(request: SemanticSearchRequest) -> Dict[str, Any]:
    """Run a semantic search over an embedding collection in EpistemicOS."""
    return await epistemicos_client.semantic_search(
        query=request.query,
        collection_id=request.collection_id,
        program_id=request.program_id,
        top_k=request.top_k,
    )
