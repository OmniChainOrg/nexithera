"""Pydantic schemas for the Assets API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssetResponse(BaseModel):
    """Response shape for a successful asset upload."""

    asset_id: UUID
    filename: str
    status: str
    epistemicos_run_id: Optional[UUID] = None
    embedding_collection_id: Optional[str] = None
    chunk_count: Optional[int] = None


class AssetListItem(BaseModel):
    """A single asset entry in a program listing."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    size_bytes: int
    file_type: str
    status: str
    created_at: datetime


class AssetList(BaseModel):
    """Response shape for `GET /api/v1/programs/{program_id}/assets`."""

    assets: List[AssetListItem]
