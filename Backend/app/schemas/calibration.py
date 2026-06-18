"""Data structures for formulation scorecard calibration.

These schemas support the Bayesian calibration pipeline:
- ``ConfidenceInterval``   – (lower, mean, upper) bounds around a score
- ``CalibratedScore``      – score enriched with a confidence interval
- ``FormulationOutcome``   – historical record of a formulation run
- ``CalibrationDataset``   – collection of outcomes + fitted model artefacts
- ``PrecedentRecord``      – an EpistemicOS formulation precedent record
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ConfidenceInterval(BaseModel):
    """Symmetric confidence bounds around a 0–100 score."""

    lower: float = Field(ge=0, le=100, description="Lower bound of the CI.")
    mean: float = Field(ge=0, le=100, description="Central estimate.")
    upper: float = Field(ge=0, le=100, description="Upper bound of the CI.")

    @model_validator(mode="after")
    def _order_check(self) -> "ConfidenceInterval":
        if not (self.lower <= self.mean <= self.upper):
            raise ValueError(
                f"CI must satisfy lower ≤ mean ≤ upper; got "
                f"{self.lower} / {self.mean} / {self.upper}"
            )
        return self

    @property
    def uncertainty(self) -> float:
        """Half-width of the confidence interval."""
        return (self.upper - self.lower) / 2


class CalibratedScore(BaseModel):
    """A formulation dimension score augmented with calibration metadata."""

    score: int = Field(ge=0, le=100)
    confidence: ConfidenceInterval
    rationale: str
    assumptions: List[str] = Field(default_factory=list)
    uncertainty: List[str] = Field(default_factory=list)
    recommendation: str = ""
    next_best_step: str = ""


ActualOutcome = Literal["success", "partial_success", "failure"]


class FormulationOutcome(BaseModel):
    """Historical formulation run with labelled outcome for model training."""

    id: str
    asset_id: Optional[str] = None
    formulation_objective: str
    route: str
    release_duration_weeks: int
    apis: List[str] = Field(default_factory=list)
    excipients: List[str] = Field(default_factory=list)
    predicted_score: float = Field(ge=0, le=100)
    actual_outcome: ActualOutcome
    actual_score: Optional[float] = Field(default=None, ge=0, le=100)
    notes: str = ""


class CalibrationDataset(BaseModel):
    """Persisted calibration state: historical outcomes + fitted weights."""

    model_config = {"protected_namespaces": ()}

    formulations: List[FormulationOutcome] = Field(default_factory=list)
    fitted_weights: Dict[str, Any] = Field(default_factory=dict)
    model_accuracy: Optional[float] = None
    sample_count: int = 0
    calibrated_at: Optional[datetime] = None


class PrecedentRecord(BaseModel):
    """An EpistemicOS formulation precedent record returned by ``search_precedent``."""

    api_name: str
    formulation_objective: str
    route: str
    modality: str = ""
    excipients: List[str] = Field(default_factory=list)
    release_duration_weeks: Optional[int] = None
    pk_parameters: Dict[str, float] = Field(
        default_factory=dict,
        description="PK params: CL, V, Tmax, F, ka.",
    )
    outcome: Optional[str] = None
    source: str = "epistemicos"
    confidence: float = Field(default=1.0, ge=0, le=1)
