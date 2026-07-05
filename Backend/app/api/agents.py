# app/api/agents.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from ..core.database import db
from ..services.agent_orchestrator import agent_orchestrator, get_or_create_agent
from ..services.agent_run_service import agent_run_service

router = APIRouter(prefix="/agents", tags=["agents"])

class TargetAssessmentRequest(BaseModel):
    program_id: str
    target_name: str
    disease_name: str
    tumor_type: Optional[str] = None

class SimulationCritiqueRequest(BaseModel):
    program_id: str
    target_name: str
    simulation_plan: Dict[str, Any]
    candidate_id: Optional[str] = None

class SingleAgentRunRequest(BaseModel):
    program_id: str
    agent_name: str
    inputs: Dict[str, Any]
    hypothesis_id: Optional[str] = None
    candidate_id: Optional[str] = None
    run_type: str = "target_assessment"

@router.post("/assess-target")
async def assess_target(request: TargetAssessmentRequest):
    """Run complete target assessment using multiple agents."""
    result = await agent_orchestrator.run_target_assessment(
        program_id=request.program_id,
        target_name=request.target_name,
        disease_name=request.disease_name,
        tumor_type=request.tumor_type
    )
    return result

@router.post("/critique-simulation")
async def critique_simulation(request: SimulationCritiqueRequest):
    """Run simulation critic on a simulation plan."""
    result = await agent_orchestrator.critique_simulation(
        program_id=request.program_id,
        target_name=request.target_name,
        simulation_plan=request.simulation_plan,
        candidate_id=request.candidate_id
    )
    return result

@router.post("/run")
async def run_agent(request: SingleAgentRunRequest):
    """Run a single agent by name."""
    agent = await get_or_create_agent(request.agent_name)
    result = await agent.run(
        program_id=request.program_id,
        inputs=request.inputs,
        hypothesis_id=request.hypothesis_id,
        candidate_id=request.candidate_id,
        run_type=request.run_type
    )
    return result

@router.get("/runs")
async def list_agent_runs(
    program_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List agent runs with optional program filter."""
    runs = await agent_run_service.list_runs(program_id, limit, offset)
    return runs

@router.get("/runs/{run_id}")
async def get_agent_run(run_id: str):
    """Get detailed agent run with tool calls and critiques."""
    result = await agent_run_service.get_run_details(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return result

@router.get("")
async def list_agents():
    """List all available agents."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, role, description, is_active FROM agents ORDER BY name"
        )
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# PR #8: Target Discovery
# ---------------------------------------------------------------------------
class TargetDiscoveryRequest(BaseModel):
    program_id: str
    disease_name: Optional[str] = None
    top_k: int = 10


@router.post("/discover-targets")
async def discover_targets(request: TargetDiscoveryRequest):
    """Run the Target Discovery Agent for a program (PR #8).

    Returns a ranked list of novel, under-supported targets with proposed
    hypotheses and a recommended next experiment.
    """
    try:
        return await agent_orchestrator.discover_targets(
            program_id=request.program_id,
            disease_name=request.disease_name,
            top_k=request.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
