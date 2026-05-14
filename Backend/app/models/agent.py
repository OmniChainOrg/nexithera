# app/models/agent.py
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

@dataclass
class Agent:
    id: uuid.UUID
    name: str
    role: str
    description: Optional[str]
    capabilities: List[str]
    system_prompt: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            name=row['name'],
            role=row['role'],
            description=row.get('description'),
            capabilities=row.get('capabilities', []),
            system_prompt=row.get('system_prompt'),
            is_active=row['is_active'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

@dataclass
class AgentRun:
    id: uuid.UUID
    agent_id: uuid.UUID
    program_id: uuid.UUID
    hypothesis_id: Optional[uuid.UUID]
    candidate_id: Optional[uuid.UUID]
    run_type: str
    input_bundle: Dict[str, Any]
    output_summary: Optional[str]
    output_structure: Optional[Dict[str, Any]]
    confidence: Optional[float]
    uncertainty_reason: Optional[str]
    recommended_next_step: Optional[str]
    status: str
    error_message: Optional[str]
    trace_summary: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            agent_id=row['agent_id'],
            program_id=row['program_id'],
            hypothesis_id=row.get('hypothesis_id'),
            candidate_id=row.get('candidate_id'),
            run_type=row['run_type'],
            input_bundle=row['input_bundle'],
            output_summary=row.get('output_summary'),
            output_structure=row.get('output_structure'),
            confidence=row.get('confidence'),
            uncertainty_reason=row.get('uncertainty_reason'),
            recommended_next_step=row.get('recommended_next_step'),
            status=row['status'],
            error_message=row.get('error_message'),
            trace_summary=row.get('trace_summary'),
            started_at=row.get('started_at'),
            completed_at=row.get('completed_at'),
            created_at=row['created_at']
        )
