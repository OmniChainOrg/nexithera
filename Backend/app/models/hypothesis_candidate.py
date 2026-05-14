# app/models/hypothesis_candidate.py
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

@dataclass
class Hypothesis:
    id: uuid.UUID
    version: int
    hypothesis_text: str
    claim_type: str
    status: str
    confidence: Optional[float]
    uncertainty_reason: Optional[str]
    program_id: uuid.UUID
    parent_hypothesis_id: Optional[uuid.UUID]
    created_by: Optional[uuid.UUID]
    reviewed_by: Optional[uuid.UUID]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            version=row['version'],
            hypothesis_text=row['hypothesis_text'],
            claim_type=row['claim_type'],
            status=row['status'],
            confidence=row.get('confidence'),
            uncertainty_reason=row.get('uncertainty_reason'),
            program_id=row['program_id'],
            parent_hypothesis_id=row.get('parent_hypothesis_id'),
            created_by=row.get('created_by'),
            reviewed_by=row.get('reviewed_by'),
            reviewed_at=row.get('reviewed_at'),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

@dataclass
class Candidate:
    id: uuid.UUID
    name: str
    candidate_type: str
    target_id: Optional[uuid.UUID]
    mechanism_of_action: Optional[str]
    therapeutic_area: str
    description: Optional[str]
    status: str
    kill_rationale: Optional[str]
    killed_at: Optional[datetime]
    killed_by: Optional[uuid.UUID]
    program_id: uuid.UUID
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            name=row['name'],
            candidate_type=row['candidate_type'],
            target_id=row.get('target_id'),
            mechanism_of_action=row.get('mechanism_of_action'),
            therapeutic_area=row['therapeutic_area'],
            description=row.get('description'),
            status=row['status'],
            kill_rationale=row.get('kill_rationale'),
            killed_at=row.get('killed_at'),
            killed_by=row.get('killed_by'),
            program_id=row['program_id'],
            created_by=row.get('created_by'),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

@dataclass
class Scorecard:
    id: uuid.UUID
    candidate_id: uuid.UUID
    evidence_score: float
    simulation_score: float
    safety_score: float
    formulation_score: float
    translational_score: float
    program_fit_score: float
    overall_score: float
    scoring_rationale: Optional[str]
    scored_by: Optional[uuid.UUID]
    scored_at: datetime
    version: int

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            candidate_id=row['candidate_id'],
            evidence_score=row['evidence_score'],
            simulation_score=row['simulation_score'],
            safety_score=row['safety_score'],
            formulation_score=row['formulation_score'],
            translational_score=row['translational_score'],
            program_fit_score=row['program_fit_score'],
            overall_score=row['overall_score'],
            scoring_rationale=row.get('scoring_rationale'),
            scored_by=row.get('scored_by'),
            scored_at=row['scored_at'],
            version=row['version']
        )
