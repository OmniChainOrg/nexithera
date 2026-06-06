# app/api/forecast.py
"""PR #11 — Clinical Forecaster API."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.clinical_forecaster_service import (
    clinical_forecaster_service,
)


router = APIRouter(prefix="/forecast", tags=["forecast"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class TrialDesign(BaseModel):
    enrollment: Optional[int] = Field(default=None, ge=1)
    duration_months: Optional[int] = Field(default=None, ge=1)
    statistical_power: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    alpha: Optional[float] = Field(default=None, gt=0.0, le=0.5)


class ScenarioOverride(BaseModel):
    name: str
    factors: Dict[str, float] = Field(default_factory=dict)


class ForecastRequest(BaseModel):
    candidate_id: str
    phase: str = Field(..., description="I | II | III")
    primary_endpoint: Optional[str] = None
    trial_design: Optional[TrialDesign] = None
    known_safety_flags: Optional[List[str]] = None
    scenarios: Optional[List[ScenarioOverride]] = None


class GuardianSubmissionRequest(BaseModel):
    reviewer_id: str
    decision: str
    decision_rationale: str


class PrecedentRequest(BaseModel):
    target_label: str
    disease_label: str
    modality: Optional[str] = None
    phase: str
    met_primary_endpoint: bool
    effect_size: Optional[float] = None
    p_value: Optional[float] = None
    trial_id: Optional[str] = None
    source: Optional[str] = None
    weight: float = Field(default=1.0, ge=0.0, le=5.0)


def _validate_uuid_or_400(value: str, name: str) -> None:
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400, detail=f"{name} must be a valid UUID"
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/clinical")
async def create_clinical_forecast(
    request: ForecastRequest,
) -> Dict[str, Any]:
    """Generate a new clinical endpoint forecast."""
    _validate_uuid_or_400(request.candidate_id, "candidate_id")
    try:
        return await clinical_forecaster_service.generate_forecast(
            candidate_id=request.candidate_id,
            phase=request.phase,
            primary_endpoint=request.primary_endpoint,
            trial_design=(
                request.trial_design.model_dump()
                if request.trial_design else {}
            ),
            scenarios=[s.model_dump() for s in (request.scenarios or [])],
            known_safety_flags=request.known_safety_flags or [],
        )
    except ValueError as exc:
        msg = str(exc)
        status = 400 if "phase must be" in msg else 404
        raise HTTPException(status_code=status, detail=msg)


@router.get("/clinical/{forecast_id}")
async def get_clinical_forecast(forecast_id: str) -> Dict[str, Any]:
    """Retrieve a previously generated forecast."""
    _validate_uuid_or_400(forecast_id, "forecast_id")
    try:
        return await clinical_forecaster_service.get_forecast(forecast_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/clinical/{forecast_id}/guardian")
async def submit_to_guardian(
    forecast_id: str,
    request: GuardianSubmissionRequest,
) -> Dict[str, Any]:
    """Submit a forecast to Guardian for review / sign-off."""
    _validate_uuid_or_400(forecast_id, "forecast_id")
    _validate_uuid_or_400(request.reviewer_id, "reviewer_id")
    try:
        return await clinical_forecaster_service.submit_to_guardian(
            forecast_id=forecast_id,
            reviewer_id=request.reviewer_id,
            decision=request.decision,
            decision_rationale=request.decision_rationale,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("Forecast not found"):
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


@router.post("/clinical/precedent")
async def add_clinical_precedent(
    request: PrecedentRequest,
) -> Dict[str, Any]:
    """Add a curated historical precedent for forecaster training."""
    try:
        return await clinical_forecaster_service.add_precedent(
            target_label=request.target_label,
            disease_label=request.disease_label,
            modality=request.modality,
            phase=request.phase,
            met_primary_endpoint=request.met_primary_endpoint,
            effect_size=request.effect_size,
            p_value=request.p_value,
            trial_id=request.trial_id,
            source=request.source,
            weight=request.weight,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
