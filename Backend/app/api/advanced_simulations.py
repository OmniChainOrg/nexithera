# app/api/advanced_simulations.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from ..services.cxu_service import cxu_service
from ..services.swarm_service import swarm_service
from ..services.cross_zone_service import cross_zone_service

router = APIRouter(prefix="/advanced", tags=["advanced_simulations"])

# ========== CXU Endpoints ==========

class CXUCreate(BaseModel):
    name: str
    cxu_type: str
    zone_id: str
    configuration: Dict[str, Any]
    created_by: Optional[str] = None

class CXUStart(BaseModel):
    initial_state: Optional[Dict[str, Any]] = None

@router.post("/cxus")
async def create_cxu(cxu: CXUCreate):
    """Create a new CXU."""
    result = await cxu_service.create_cxu(
        name=cxu.name,
        cxu_type=cxu.cxu_type,
        zone_id=cxu.zone_id,
        configuration=cxu.configuration,
        created_by=cxu.created_by
    )
    return result

@router.post("/cxus/{cxu_id}/start")
async def start_cxu(cxu_id: str, start: CXUStart):
    """Start a CXU."""
    result = await cxu_service.start_cxu(cxu_id, start.initial_state)
    return result

@router.post("/cxus/{cxu_id}/pause")
async def pause_cxu(cxu_id: str):
    """Pause a CXU."""
    result = await cxu_service.pause_cxu(cxu_id)
    return result

@router.post("/cxus/{cxu_id}/terminate")
async def terminate_cxu(cxu_id: str):
    """Terminate a CXU."""
    result = await cxu_service.terminate_cxu(cxu_id)
    return result

@router.get("/cxus/{cxu_id}/status")
async def get_cxu_status(cxu_id: str):
    """Get CXU status with latest iteration."""
    result = await cxu_service.get_cxu_status(cxu_id)
    return result

# ========== Swarm Endpoints ==========

class SwarmCreate(BaseModel):
    name: str
    swarm_type: str
    objective: str
    configuration: Dict[str, Any]
    program_id: str
    created_by: Optional[str] = None

class SwarmMemberAdd(BaseModel):
    cxu_id: str
    role: str = "worker"
    weight: float = 1.0

@router.post("/swarms")
async def create_swarm(swarm: SwarmCreate):
    """Create a new swarm."""
    result = await swarm_service.create_swarm(
        name=swarm.name,
        swarm_type=swarm.swarm_type,
        objective=swarm.objective,
        configuration=swarm.configuration,
        program_id=swarm.program_id,
        created_by=swarm.created_by
    )
    return result

@router.post("/swarms/{swarm_id}/members")
async def add_swarm_member(swarm_id: str, member: SwarmMemberAdd):
    """Add a CXU to a swarm."""
    result = await swarm_service.add_member(
        swarm_id=swarm_id,
        cxu_id=member.cxu_id,
        role=member.role,
        weight=member.weight
    )
    return result

@router.post("/swarms/{swarm_id}/start")
async def start_swarm(swarm_id: str):
    """Start a swarm."""
    result = await swarm_service.start_swarm(swarm_id)
    return result

@router.get("/swarms/{swarm_id}/results")
async def get_swarm_results(swarm_id: str):
    """Get aggregated swarm results."""
    result = await swarm_service.get_swarm_results(swarm_id)
    return result

@router.get("/swarms/program/{program_id}")
async def list_swarms(program_id: str):
    """List all swarms for a program."""
    results = await swarm_service.list_swarms(program_id)
    return {"swarms": results, "count": len(results)}

# ========== Cross-Zone Endpoints ==========

class CouplingRegister(BaseModel):
    source_zone_type: str
    target_zone_type: str
    coupling_name: str
    coupling_map: Dict[str, str]
    is_bidirectional: bool = False
    created_by: Optional[str] = None

class CrossZoneRun(BaseModel):
    name: Optional[str] = None
    source_zone_id: str
    target_zone_id: str
    input_state: Dict[str, Any]
    program_id: str
    coupling_id: Optional[str] = None
    coupling_map_override: Optional[Dict[str, str]] = None

@router.post("/couplings")
async def register_coupling(coupling: CouplingRegister):
    """Register a reusable zone coupling."""
    result = await cross_zone_service.register_coupling(
        source_zone_type=coupling.source_zone_type,
        target_zone_type=coupling.target_zone_type,
        coupling_name=coupling.coupling_name,
        coupling_map=coupling.coupling_map,
        is_bidirectional=coupling.is_bidirectional,
        created_by=coupling.created_by
    )
    return result

@router.post("/cross-zone")
async def run_cross_zone_simulation(run: CrossZoneRun):
    """Run a cross-zone simulation."""
    result = await cross_zone_service.run_cross_zone_simulation(
        name=run.name,
        source_zone_id=run.source_zone_id,
        target_zone_id=run.target_zone_id,
        input_state=run.input_state,
        program_id=run.program_id,
        coupling_id=run.coupling_id,
        coupling_map_override=run.coupling_map_override
    )
    return result

@router.get("/cross-zone/{run_id}")
async def get_cross_zone_run(run_id: str):
    """Get cross-zone simulation results."""
    result = await cross_zone_service.get_cross_zone_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result

@router.get("/couplings")
async def list_couplings(source_zone_type: Optional[str] = None):
    """List registered zone couplings."""
    results = await cross_zone_service.list_couplings(source_zone_type)
    return {"couplings": results, "count": len(results)}
