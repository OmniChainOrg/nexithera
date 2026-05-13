"""Pydantic schemas for the Programs API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProgramCreate(BaseModel):
    """Payload for `POST /api/v1/programs`."""

    name: str = Field(..., min_length=1, max_length=200)
    therapeutic_area: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class ProgramResponse(BaseModel):
    """Response shape for program endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    therapeutic_area: str
    description: Optional[str] = None
    status: str
    created_at: datetime
