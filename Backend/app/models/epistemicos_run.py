"""EpistemicOSRun domain model – traces every delegated call to EpistemicOS.

Genovate never owns embeddings/simulations; it only owns the *trace* of asking
EpistemicOS to perform them. This model represents one such trace row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID


RUN_TYPES = ("ingest", "embed", "simulate", "swarm")
RUN_STATUSES = ("pending", "completed", "failed")


@dataclass
class EpistemicOSRun:
    """A single delegated call to EpistemicOS."""

    id: UUID
    run_type: str
    request_payload: Dict[str, Any]
    status: str
    created_at: datetime
    response_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.run_type not in RUN_TYPES:
            raise ValueError(
                f"Invalid run_type {self.run_type!r}; must be one of {RUN_TYPES}"
            )
        if self.status not in RUN_STATUSES:
            raise ValueError(
                f"Invalid status {self.status!r}; must be one of {RUN_STATUSES}"
            )

    @classmethod
    def from_row(cls, row) -> "EpistemicOSRun":
        return cls(
            id=row["id"],
            run_type=row["run_type"],
            request_payload=row["request_payload"],
            response_payload=row.get("response_payload"),
            status=row["status"],
            error_message=row.get("error_message"),
            created_at=row["created_at"],
            completed_at=row.get("completed_at"),
        )
