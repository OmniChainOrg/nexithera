# app/models/guardian.py
"""Dataclass models for the Guardian review system (PR #5).

The Guardian governs transitions between epistemic states.  Every decision
is immutable, requires rationale, and produces signed artifacts.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional


# Allowed enum values mirrored from the SQL CHECK constraints so the
# service / API layers can validate without round-tripping to Postgres.
REVIEW_TYPES = (
    "hypothesis_review",
    "candidate_review",
    "simulation_review",
    "program_gate_review",
    "epistemicos_promotion",
)

ENTITY_TYPES = ("hypothesis", "candidate", "simulation", "program")

DECISIONS = (
    "approve",
    "request_revision",
    "escalate",
    "park",
    "kill",
    "promote_to_epistemicos",
)

ASSIGNMENT_STATUSES = ("pending", "accepted", "declined", "completed")

ARTIFACT_TYPES = ("report", "certificate", "evidence_package", "decision_letter")


@dataclass
class GuardianReview:
    id: uuid.UUID
    review_type: str
    entity_id: uuid.UUID
    entity_type: str
    decision: str
    decision_rationale: str
    reviewer_id: uuid.UUID
    reviewed_at: datetime
    created_at: datetime
    risk_flags: List[Any] = field(default_factory=list)
    reviewer_notes: Optional[str] = None
    review_deadline: Optional[datetime] = None
    is_final: bool = True
    superseded_by: Optional[uuid.UUID] = None
    signed_artifact_uri: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "GuardianReview":
        return cls(
            id=row["id"],
            review_type=row["review_type"],
            entity_id=row["entity_id"],
            entity_type=row["entity_type"],
            decision=row["decision"],
            decision_rationale=row["decision_rationale"],
            reviewer_id=row["reviewer_id"],
            reviewed_at=row["reviewed_at"],
            created_at=row["created_at"],
            risk_flags=row.get("risk_flags") or [],
            reviewer_notes=row.get("reviewer_notes"),
            review_deadline=row.get("review_deadline"),
            is_final=row.get("is_final", True),
            superseded_by=row.get("superseded_by"),
            signed_artifact_uri=row.get("signed_artifact_uri"),
        )


@dataclass
class ReviewAssignment:
    id: uuid.UUID
    review_id: uuid.UUID
    assignee_id: uuid.UUID
    assigned_by: uuid.UUID
    assigned_at: datetime
    status: str
    completed_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "ReviewAssignment":
        return cls(
            id=row["id"],
            review_id=row["review_id"],
            assignee_id=row["assignee_id"],
            assigned_by=row["assigned_by"],
            assigned_at=row["assigned_at"],
            status=row.get("status", "pending"),
            completed_at=row.get("completed_at"),
        )


@dataclass
class ReviewChecklist:
    id: uuid.UUID
    review_type: str
    criterion: str
    order_index: int
    is_required: bool
    created_at: datetime
    criterion_description: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "ReviewChecklist":
        return cls(
            id=row["id"],
            review_type=row["review_type"],
            criterion=row["criterion"],
            order_index=row.get("order_index", 0),
            is_required=row.get("is_required", True),
            created_at=row["created_at"],
            criterion_description=row.get("criterion_description"),
        )


@dataclass
class ReviewChecklistResponse:
    id: uuid.UUID
    review_id: uuid.UUID
    checklist_item_id: uuid.UUID
    passed: bool
    created_at: datetime
    notes: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "ReviewChecklistResponse":
        return cls(
            id=row["id"],
            review_id=row["review_id"],
            checklist_item_id=row["checklist_item_id"],
            passed=row["passed"],
            created_at=row["created_at"],
            notes=row.get("notes"),
        )


@dataclass
class ReviewComment:
    id: uuid.UUID
    review_id: uuid.UUID
    user_id: uuid.UUID
    comment_text: str
    created_at: datetime
    parent_comment_id: Optional[uuid.UUID] = None
    edited_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "ReviewComment":
        return cls(
            id=row["id"],
            review_id=row["review_id"],
            user_id=row["user_id"],
            comment_text=row["comment_text"],
            created_at=row["created_at"],
            parent_comment_id=row.get("parent_comment_id"),
            edited_at=row.get("edited_at"),
        )


@dataclass
class ReviewArtifact:
    id: uuid.UUID
    review_id: uuid.UUID
    artifact_type: str
    artifact_uri: str
    created_by: uuid.UUID
    created_at: datetime
    checksum: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "ReviewArtifact":
        return cls(
            id=row["id"],
            review_id=row["review_id"],
            artifact_type=row["artifact_type"],
            artifact_uri=row["artifact_uri"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            checksum=row.get("checksum"),
        )
