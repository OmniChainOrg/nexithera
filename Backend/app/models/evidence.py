# app/models/evidence.py
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import json

@dataclass
class BioEntity:
    id: uuid.UUID
    entity_type: str
    name: str
    external_id: Optional[str]
    external_db: Optional[str]
    description: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            entity_type=row['entity_type'],
            name=row['name'],
            external_id=row.get('external_id'),
            external_db=row.get('external_db'),
            description=row.get('description'),
            metadata=row.get('metadata', {}),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

@dataclass
class EvidenceEdge:
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    predicate: str
    confidence: float
    is_contradiction: bool
    claim_id: Optional[uuid.UUID]
    reference_id: uuid.UUID
    direction: str
    evidence_strength: Optional[str]
    notes: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            source_id=row['source_id'],
            target_id=row['target_id'],
            predicate=row['predicate'],
            confidence=row['confidence'],
            is_contradiction=row['is_contradiction'],
            claim_id=row.get('claim_id'),
            reference_id=row['reference_id'],
            direction=row['direction'],
            evidence_strength=row.get('evidence_strength'),
            notes=row.get('notes'),
            metadata=row.get('metadata', {}),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

@dataclass
class Reference:
    id: uuid.UUID
    ref_type: str
    ref_id: str
    title: Optional[str]
    authors: List[str]
    journal: Optional[str]
    year: Optional[int]
    url: Optional[str]

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            ref_type=row['ref_type'],
            ref_id=row['ref_id'],
            title=row.get('title'),
            authors=row.get('authors', []),
            journal=row.get('journal'),
            year=row.get('year'),
            url=row.get('url')
        )
