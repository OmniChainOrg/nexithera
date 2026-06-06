# app/api/candidates.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from ..services.candidate_service import candidate_service
from ..services.pipeline_service import pipeline_service

router = APIRouter(prefix="/candidates", tags=["candidates"])

class CandidateCreate(BaseModel):
    name: str
    candidate_type: str
    therapeutic_area: str
    program_id: str
    target_id: Optional[str] = None
    mechanism_of_action: Optional[str] = None
    description: Optional[str] = None
    created_by: Optional[str] = None

class ScorecardCreate(BaseModel):
    evidence_score: float
    simulation_score: float
    safety_score: float
    formulation_score: float
    translational_score: float
    program_fit_score: float
    scored_by: Optional[str] = None
    scoring_rationale: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str
    user_id: Optional[str] = None
    kill_rationale: Optional[str] = None

@router.post("")
async def create_candidate(candidate: CandidateCreate):
    """Create a new candidate."""
    result = await candidate_service.create_candidate(
        name=candidate.name,
        candidate_type=candidate.candidate_type,
        therapeutic_area=candidate.therapeutic_area,
        program_id=candidate.program_id,
        target_id=candidate.target_id,
        mechanism_of_action=candidate.mechanism_of_action,
        description=candidate.description,
        created_by=candidate.created_by
    )
    return result

@router.patch("/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: str,
    update: StatusUpdate
):
    """Update candidate pipeline status."""
    result = await candidate_service.update_candidate_status(
        candidate_id=candidate_id,
        new_status=update.status,
        user_id=update.user_id,
        kill_rationale=update.kill_rationale
    )
    return result

@router.post("/{candidate_id}/scorecards")
async def add_scorecard(
    candidate_id: str,
    scorecard: ScorecardCreate
):
    """Add a new scorecard for a candidate."""
    result = await candidate_service.add_scorecard(
        candidate_id=candidate_id,
        evidence_score=scorecard.evidence_score,
        simulation_score=scorecard.simulation_score,
        safety_score=scorecard.safety_score,
        formulation_score=scorecard.formulation_score,
        translational_score=scorecard.translational_score,
        program_fit_score=scorecard.program_fit_score,
        scored_by=scorecard.scored_by,
        scoring_rationale=scorecard.scoring_rationale
    )
    return result

@router.post("/{candidate_id}/hypotheses/{hypothesis_id}")
async def link_hypothesis(
    candidate_id: str,
    hypothesis_id: str
):
    """Link a hypothesis to a candidate."""
    result = await candidate_service.link_hypothesis_to_candidate(
        candidate_id=candidate_id,
        hypothesis_id=hypothesis_id
    )
    return result

@router.get("/{candidate_id}")
async def get_candidate(candidate_id: str):
    """Get candidate with latest scorecard and hypotheses."""
    result = await candidate_service.get_candidate_with_scorecard(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return result

@router.get("/program/{program_id}")
async def list_candidates_by_program(
    program_id: str,
    status: Optional[str] = Query(None, description="Filter by status")
):
    """List all candidates in a program."""
    results = await candidate_service.list_candidates_by_program(program_id, status)
    return {"candidates": results, "count": len(results)}


# ---------------------------------------------------------------------------
# PR #8: Pipeline automation
# ---------------------------------------------------------------------------
@router.post("/{candidate_id}/auto-advance")
async def auto_advance_candidate(candidate_id: str):
    """Manually trigger the auto-advance pipeline evaluation (normally automatic)."""
    try:
        return await pipeline_service.auto_advance(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{candidate_id}/transitions")
async def list_candidate_transitions(candidate_id: str):
    """Return the full transition log for a candidate (PR #8)."""
    transitions = await pipeline_service.list_transitions(candidate_id)
    return {"candidate_id": candidate_id, "transitions": transitions, "count": len(transitions)}
