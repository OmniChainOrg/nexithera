# app/api/hypotheses.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from ..services.hypothesis_service import hypothesis_service

router = APIRouter(prefix="/hypotheses", tags=["hypotheses"])

class HypothesisCreate(BaseModel):
    hypothesis_text: str
    claim_type: str
    program_id: str
    created_by: Optional[str] = None
    confidence: Optional[float] = None
    uncertainty_reason: Optional[str] = None
    parent_hypothesis_id: Optional[str] = None

class EvidenceLink(BaseModel):
    evidence_edge_id: str
    supports: bool = True
    weight: float = 1.0
    note: Optional[str] = None

@router.post("")
async def create_hypothesis(hypothesis: HypothesisCreate):
    """Create a new hypothesis."""
    result = await hypothesis_service.create_hypothesis(
        hypothesis_text=hypothesis.hypothesis_text,
        claim_type=hypothesis.claim_type,
        program_id=hypothesis.program_id,
        created_by=hypothesis.created_by,
        confidence=hypothesis.confidence,
        uncertainty_reason=hypothesis.uncertainty_reason,
        parent_hypothesis_id=hypothesis.parent_hypothesis_id
    )
    return result

@router.post("/{hypothesis_id}/evidence")
async def add_evidence_to_hypothesis(
    hypothesis_id: str,
    evidence: EvidenceLink
):
    """Link evidence to a hypothesis."""
    result = await hypothesis_service.add_evidence_to_hypothesis(
        hypothesis_id=hypothesis_id,
        evidence_edge_id=evidence.evidence_edge_id,
        supports=evidence.supports,
        weight=evidence.weight,
        note=evidence.note
    )
    return result

@router.get("/{hypothesis_id}")
async def get_hypothesis(hypothesis_id: str):
    """Get hypothesis with all supporting/contradicting evidence."""
    result = await hypothesis_service.get_hypothesis_with_evidence(hypothesis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return result


# ---------------------------------------------------------------------------
# PR #8: Hypothesis versioning
# ---------------------------------------------------------------------------
class HypothesisVersionCreate(BaseModel):
    hypothesis_text: str
    created_by: Optional[str] = None
    confidence: Optional[float] = None
    uncertainty_reason: Optional[str] = None


@router.post("/{hypothesis_id}/versions")
async def create_hypothesis_version(
    hypothesis_id: str, payload: HypothesisVersionCreate
):
    """Create a new child version of an existing hypothesis (PR #8).

    The parent link is preserved so the dashboard can render an
    evolution timeline.
    """
    try:
        return await hypothesis_service.create_version(
            parent_hypothesis_id=hypothesis_id,
            hypothesis_text=payload.hypothesis_text,
            created_by=payload.created_by,
            confidence=payload.confidence,
            uncertainty_reason=payload.uncertainty_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{hypothesis_id}/timeline")
async def get_hypothesis_timeline(hypothesis_id: str):
    """Return the full version timeline for a hypothesis (PR #8)."""
    rows = await hypothesis_service.get_version_timeline(hypothesis_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return {"hypothesis_id": hypothesis_id, "versions": rows, "count": len(rows)}
