# app/api/analysis.py
"""PR #9 — Active Learning + Evidence Gap Analysis API."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.active_learning_service import active_learning_service
from ..services.partnerability_service import partnerability_service


router = APIRouter(prefix="/analysis", tags=["analysis"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class GapAnalysisRequest(BaseModel):
    program_id: str
    low_confidence_threshold: Optional[float] = None


class NextExperimentsRequest(BaseModel):
    program_id: str
    max_experiments: int = Field(default=10, ge=1, le=50)
    include_cost: bool = True


class ConductExperimentRequest(BaseModel):
    result_summary: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    updated_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    conducted_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/gap-analysis")
async def run_gap_analysis(request: GapAnalysisRequest) -> Dict[str, Any]:
    """Run gap analysis for a program."""
    try:
        return await active_learning_service.run_gap_analysis(
            program_id=request.program_id,
            low_confidence_threshold=request.low_confidence_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/next-experiments")
async def next_experiments(
    request: NextExperimentsRequest,
) -> Dict[str, Any]:
    """Generate the top-N proposed experiments for a program."""
    try:
        return await active_learning_service.propose_next_experiments(
            program_id=request.program_id,
            max_experiments=request.max_experiments,
            include_cost=request.include_cost,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/experiments/{experiment_id}/conduct")
async def conduct_experiment(
    experiment_id: str,
    request: ConductExperimentRequest,
) -> Dict[str, Any]:
    """Record an experiment outcome and update beliefs."""
    try:
        uuid.UUID(experiment_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400, detail="experiment_id must be a valid UUID"
        )
    try:
        return await active_learning_service.record_outcome(
            experiment_id=experiment_id,
            result_summary=request.result_summary,
            result_data=request.result_data,
            updated_confidence=request.updated_confidence,
            conducted_by=request.conducted_by,
        )
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Proposed experiment not found",
        )
    except Exception:  # noqa: BLE001 — sanitize before returning to client
        raise HTTPException(
            status_code=500,
            detail="Failed to record experiment outcome",
        )


@router.get("/programs/{program_id}/gaps")
async def list_open_gaps(program_id: str) -> Dict[str, Any]:
    """List unresolved evidence gaps for a program (gap heatmap source)."""
    gaps = await active_learning_service.list_open_gaps(program_id)
    return {"program_id": program_id, "gaps": gaps, "count": len(gaps)}


@router.get("/programs/{program_id}/experiments")
async def list_proposed_experiments(
    program_id: str,
    status: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List proposed experiments for the experiment-queue dashboard card."""
    experiments = await active_learning_service.list_experiments(
        program_id=program_id, status=status, limit=limit
    )
    return {
        "program_id": program_id,
        "experiments": experiments,
        "count": len(experiments),
    }


@router.get("/hypotheses/{hypothesis_id}/belief-timeline")
async def belief_timeline(hypothesis_id: str) -> Dict[str, Any]:
    """Return chronological belief updates for a hypothesis."""
    timeline = await active_learning_service.get_belief_timeline(hypothesis_id)
    return {"hypothesis_id": hypothesis_id, "timeline": timeline}


# ---------------------------------------------------------------------------
# What-if simulator: predict info gain for a hypothetical experiment
# without persisting anything.
# ---------------------------------------------------------------------------
class WhatIfRequest(BaseModel):
    prior_confidence: float = Field(..., ge=0.0, le=1.0)
    posterior_if_positive: float = Field(..., ge=0.0, le=1.0)
    posterior_if_negative: float = Field(..., ge=0.0, le=1.0)
    p_positive: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    cost_estimate: Optional[float] = Field(default=None, gt=0.0)


@router.post("/what-if")
async def what_if(request: WhatIfRequest) -> Dict[str, Any]:
    from ..agents.active_learning_agent import (
        binary_entropy,
        expected_posterior_entropy,
        information_gain,
    )

    gain = information_gain(
        prior=request.prior_confidence,
        posterior_if_positive=request.posterior_if_positive,
        posterior_if_negative=request.posterior_if_negative,
        p_positive=request.p_positive,
    )
    expected_h = expected_posterior_entropy(
        p_positive=(
            request.p_positive
            if request.p_positive is not None
            else request.prior_confidence
        ),
        posterior_if_positive=request.posterior_if_positive,
        posterior_if_negative=request.posterior_if_negative,
    )
    return {
        "prior_entropy": round(binary_entropy(request.prior_confidence), 4),
        "expected_posterior_entropy": round(expected_h, 4),
        "information_gain": round(gain, 4),
        "value_per_unit_cost": (
            round(gain / request.cost_estimate, 4)
            if request.cost_estimate
            else None
        ),
    }


# ---------------------------------------------------------------------------
# PR #10 — Partnerability + IND Readiness
# ---------------------------------------------------------------------------
class CandidateAnalysisRequest(BaseModel):
    candidate_id: str

    @classmethod
    def _validate_uuid(cls, value: str) -> str:
        try:
            uuid.UUID(value)
        except (ValueError, AttributeError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="candidate_id must be a valid UUID",
            )
        return value


class PartnerabilityRequest(CandidateAnalysisRequest):
    assessed_by: Optional[str] = None


class INDChecklistUpdateRequest(BaseModel):
    status: str = Field(..., description="not_started|in_progress|complete|waived|failed")
    evidence_uri: Optional[str] = None
    notes: Optional[str] = None
    updated_by: Optional[str] = None


def _validate_uuid_or_400(value: str, name: str) -> None:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400, detail=f"{name} must be a valid UUID"
        )


@router.post("/competitive-landscape")
async def competitive_landscape(
    request: CandidateAnalysisRequest,
) -> Dict[str, Any]:
    """Run competitive landscape analysis for a candidate."""
    _validate_uuid_or_400(request.candidate_id, "candidate_id")
    try:
        return await partnerability_service.run_competitive_landscape(
            request.candidate_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/ip-position")
async def ip_position(
    request: CandidateAnalysisRequest,
) -> Dict[str, Any]:
    """Estimate freedom-to-operate and IP strength for a candidate."""
    _validate_uuid_or_400(request.candidate_id, "candidate_id")
    try:
        return await partnerability_service.run_ip_position(
            request.candidate_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/ind-readiness")
async def ind_readiness(
    request: CandidateAnalysisRequest,
) -> Dict[str, Any]:
    """Assess IND readiness against the seeded checklist."""
    _validate_uuid_or_400(request.candidate_id, "candidate_id")
    try:
        return await partnerability_service.run_ind_readiness(
            request.candidate_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/partnerability")
async def partnerability(
    request: PartnerabilityRequest,
) -> Dict[str, Any]:
    """Calculate composite partnerability score for a candidate."""
    _validate_uuid_or_400(request.candidate_id, "candidate_id")
    try:
        return await partnerability_service.assess_partnerability(
            candidate_id=request.candidate_id,
            assessed_by=request.assessed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/ind-checklist/{candidate_id}/{item_id}")
async def update_ind_checklist_item(
    candidate_id: str,
    item_id: str,
    request: INDChecklistUpdateRequest,
) -> Dict[str, Any]:
    """Update a single IND checklist item for a candidate."""
    _validate_uuid_or_400(candidate_id, "candidate_id")
    _validate_uuid_or_400(item_id, "item_id")
    try:
        return await partnerability_service.update_checklist_item(
            candidate_id=candidate_id,
            item_id=item_id,
            status=request.status,
            evidence_uri=request.evidence_uri,
            notes=request.notes,
            updated_by=request.updated_by,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("Invalid IND checklist status"):
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=404, detail=msg)
