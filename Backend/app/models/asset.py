"""DataAsset domain model.

Genovate stores only metadata about uploaded files. The file lives in S3/MinIO
and any chunking/embedding is owned by EpistemicOS – referenced here via
`epistemicos_run_id`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID


ASSET_STATUSES = ("pending", "ingested", "failed")


@dataclass
class DataAsset:
    """Metadata for a single uploaded data asset."""

    id: UUID
    filename: str
    s3_uri: str
    size_bytes: int
    file_type: str
    status: str
    program_id: UUID
    created_at: datetime
    epistemicos_run_id: Optional[UUID] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in ASSET_STATUSES:
            raise ValueError(
                f"Invalid status {self.status!r}; must be one of {ASSET_STATUSES}"
            )

    @classmethod
    def from_row(cls, row) -> "DataAsset":
        return cls(
            id=row["id"],
            filename=row["filename"],
            s3_uri=row["s3_uri"],
            size_bytes=row["size_bytes"],
            file_type=row["file_type"],
            status=row["status"],
            program_id=row["program_id"],
            epistemicos_run_id=row.get("epistemicos_run_id"),
            metadata=row.get("metadata") or {},
            created_at=row["created_at"],
        )
