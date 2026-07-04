# app/api/guardian.py
"""FastAPI endpoints for the Guardian review system (PR #5)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.guardian_service import guardian_service

router = APIRouter(prefix="/guardian", tags=["guardian"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class RiskFlag(BaseModel):
    flag: str
    severity: str = Field(..., description="low | medium | high")
    mitigation: Optional[str] = None


class ReviewCreate(BaseModel):
    review_type: str
    entity_id: str
    entity_type: str
    decision: str
    decision_rationale: str
    reviewer_id: str
    risk_flags: Optional[List[RiskFlag]] = None
    reviewer_notes: Optional[str] = None
    review_deadline: Optional[datetime] = None


class DecisionSubmit(BaseModel):
    decision: str
    decision_rationale: str
    reviewer_id: str
    risk_flags: Optional[List[RiskFlag]] = None
    reviewer_notes: Optional[str] = None


class AssignmentCreate(BaseModel):
    assignee_id: str
    assigned_by: str


class AssignmentStatusUpdate(BaseModel):
    status: str


class ChecklistResponseCreate(BaseModel):
    checklist_item_id: str
    passed: bool
    notes: Optional[str] = None


class CommentCreate(BaseModel):
    user_id: str
    comment_text: str
    parent_comment_id: Optional[str] = None


class ReportRequest(BaseModel):
    created_by: str
    artifact_type: str = "report"


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@router.post("/reviews")
async def create_review(payload: ReviewCreate) -> Dict[str, Any]:
    """Create a new guardian review with an initial decision."""
    try:
        return await guardian_service.create_review(
            review_type=payload.review_type,
            entity_id=payload.entity_id,
            entity_type=payload.entity_type,
            reviewer_id=payload.reviewer_id,
            decision=payload.decision,
            decision_rationale=payload.decision_rationale,
            risk_flags=[rf.model_dump() for rf in payload.risk_flags]
            if payload.risk_flags
            else None,
            reviewer_notes=payload.reviewer_notes,
            review_deadline=payload.review_deadline,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/reviews/{review_id}/decision")
async def submit_decision(review_id: str, payload: DecisionSubmit) -> Dict[str, Any]:
    """Supersede an existing final review with a new decision."""
    try:
        return await guardian_service.submit_decision(
            review_id=review_id,
            decision=payload.decision,
            decision_rationale=payload.decision_rationale,
            reviewer_id=payload.reviewer_id,
            risk_flags=[rf.model_dump() for rf in payload.risk_flags]
            if payload.risk_flags
            else None,
            reviewer_notes=payload.reviewer_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/reviews/{review_id}")
async def get_review(review_id: str) -> Dict[str, Any]:
    """Get a review bundle: review + checklist responses + comments + artifacts."""
    result = await guardian_service.get_review(review_id)
    if not result:
        raise HTTPException(status_code=404, detail="Review not found")
    return result


@router.get("/reviews")
async def list_reviews(
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    reviewer_id: Optional[str] = None,
    review_type: Optional[str] = None,
    decision: Optional[str] = None,
    only_final: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """List reviews with filters."""
    rows = await guardian_service.list_reviews(
        entity_id=entity_id,
        entity_type=entity_type,
        reviewer_id=reviewer_id,
        review_type=review_type,
        decision=decision,
        only_final=only_final,
        limit=limit,
        offset=offset,
    )
    return rows


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
@router.post("/reviews/{review_id}/assign")
async def assign_reviewer(review_id: str, payload: AssignmentCreate) -> Dict[str, Any]:
    return await guardian_service.assign_reviewer(
        review_id=review_id,
        assignee_id=payload.assignee_id,
        assigned_by=payload.assigned_by,
    )


@router.patch("/assignments/{assignment_id}")
async def update_assignment(
    assignment_id: str, payload: AssignmentStatusUpdate
) -> Dict[str, Any]:
    try:
        return await guardian_service.update_assignment_status(
            assignment_id=assignment_id, status=payload.status
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Checklists
# ---------------------------------------------------------------------------
@router.get("/checklists/{review_type}")
async def get_checklist(review_type: str) -> Dict[str, Any]:
    """Return the structured checklist for a given review type."""
    try:
        items = await guardian_service.get_checklist(review_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"review_type": review_type, "items": items, "count": len(items)}


@router.post("/reviews/{review_id}/checklist")
async def add_checklist_response(
    review_id: str, payload: ChecklistResponseCreate
) -> Dict[str, Any]:
    try:
        return await guardian_service.add_checklist_response(
            review_id=review_id,
            checklist_item_id=payload.checklist_item_id,
            passed=payload.passed,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
@router.post("/reviews/{review_id}/comments")
async def add_comment(review_id: str, payload: CommentCreate) -> Dict[str, Any]:
    try:
        return await guardian_service.add_comment(
            review_id=review_id,
            user_id=payload.user_id,
            comment_text=payload.comment_text,
            parent_comment_id=payload.parent_comment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Signed reports / artifacts
# ---------------------------------------------------------------------------
@router.post("/reviews/{review_id}/report")
async def generate_report(review_id: str, payload: ReportRequest) -> Dict[str, Any]:
    """Generate a signed artifact (report / certificate / decision letter)."""
    try:
        return await guardian_service.generate_report(
            review_id=review_id,
            created_by=payload.created_by,
            artifact_type=payload.artifact_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# PR #8: Bulk decisions for pipeline review
# ---------------------------------------------------------------------------
class BulkDecisionRequest(BaseModel):
    candidate_ids: List[str] = Field(..., min_length=1)
    decision: str
    decision_rationale: str
    reviewer_id: str
    review_type: str = "candidate_review"
    risk_flags: Optional[List[RiskFlag]] = None
    reviewer_notes: Optional[str] = None


@router.post("/bulk")
async def bulk_decision(payload: BulkDecisionRequest) -> Dict[str, Any]:
    """Apply the same Guardian decision (approve/kill/park/...) to many
    candidates in a single call (PR #8 pipeline review)."""
    try:
        return await guardian_service.bulk_decide_candidates(
            candidate_ids=payload.candidate_ids,
            decision=payload.decision,
            decision_rationale=payload.decision_rationale,
            reviewer_id=payload.reviewer_id,
            review_type=payload.review_type,
            risk_flags=[rf.model_dump() for rf in payload.risk_flags]
            if payload.risk_flags
            else None,
            reviewer_notes=payload.reviewer_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
