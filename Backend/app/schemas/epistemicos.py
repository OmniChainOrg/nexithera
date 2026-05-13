"""Pydantic schemas describing payloads exchanged with EpistemicOS.

These are response-shape contracts only – Genovate never produces embeddings
itself; it merely consumes the IDs that EpistemicOS returns.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class IngestResponse(BaseModel):
    """Response from EpistemicOS `/v1/ingest`."""

    embedding_collection_id: str
    chunk_ids: List[str]
    vector_count: int
    status: str
    trace_id: Optional[str] = None


class ZoneResponse(BaseModel):
    """Response from EpistemicOS `/v1/zones`."""

    epistemicos_zone_id: str
    status: str
    zone_type: str


class SimulateResponse(BaseModel):
    """Response from EpistemicOS `/v1/simulate`."""

    run_id: str
    status: str
    results: Dict[str, Any]
    confidence: Optional[float] = None
