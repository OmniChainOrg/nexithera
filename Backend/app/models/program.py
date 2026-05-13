"""Program and Zone domain models.

A Program is a therapeutic effort owned by an organization (e.g. an oncology
immunotherapy program). Zones are references to epistemic zones that live in
EpistemicOS – Genovate only stores the reference, not the zone contents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID


# Therapeutic areas mirror the verticals described in the PR.
THERAPEUTIC_AREAS = (
    "oncology_immunotherapy",
    "synthetic_biology",
    "regenerative_medicine",
    "advanced_formulation",
    "biodefense",
)

PROGRAM_STATUSES = ("active", "archived")


@dataclass
class Program:
    """A drug-discovery program."""

    id: UUID
    name: str
    therapeutic_area: str
    organization_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "Program":
        return cls(
            id=row["id"],
            name=row["name"],
            therapeutic_area=row["therapeutic_area"],
            description=row.get("description"),
            organization_id=row["organization_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Zone:
    """Reference to an EpistemicOS zone (the zone itself lives in EpistemicOS)."""

    id: UUID
    program_id: UUID
    epistemicos_zone_id: str
    zone_type: str
    created_at: datetime
    config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "Zone":
        return cls(
            id=row["id"],
            program_id=row["program_id"],
            epistemicos_zone_id=row["epistemicos_zone_id"],
            zone_type=row["zone_type"],
            config=row.get("config") or {},
            created_at=row["created_at"],
        )
