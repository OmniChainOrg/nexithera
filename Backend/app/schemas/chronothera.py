"""ChronoThera formulation and delivery intelligence schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


FormulationObjective = Literal[
    "sustained_release",
    "half_life_extension",
    "pegylation_strategy",
    "depot_formulation",
    "oral_delayed_release",
    "local_ocular_delivery",
    "chronotherapeutic_release",
    "co_formulation",
]
RouteOfAdministration = Literal["oral", "SC", "IM", "IV", "local", "ocular"]
RegulatoryBody = Literal["FDA", "EMA", "PMDA", "TGA", "Health Canada"]
StrategyMode = Literal["cooperative", "competitive"]
ExcipientDoseUnit = Literal["mg", "g"]
GuardianDecision = Literal["approved", "needs-revision", "rejected"]


class APIComponent(BaseModel):
    name: str
    dose_mg: float = Field(gt=0)
    modality: Optional[str] = None


class ExcipientComponent(BaseModel):
    name: str
    percentage: float = Field(ge=0, le=100)
    amount_mg: float = Field(default=1, gt=0)
    amount: Optional[float] = Field(default=None, gt=0)
    unit: ExcipientDoseUnit = "mg"
    function: Optional[str] = None


class PKPDObjective(BaseModel):
    target_exposure: str = "planning-range"
    dosing_interval_days: int = Field(default=7, ge=1, le=90)
    peak_to_trough_priority: int = Field(default=3, ge=1, le=5)
    adherence_priority: int = Field(default=4, ge=1, le=5)


class ChronoTheraSimulationRequest(BaseModel):
    asset_id: Optional[str] = None
    program_id: Optional[str] = None
    formulation_objective: FormulationObjective
    apis: List[APIComponent]
    excipients: List[ExcipientComponent]
    release_duration_weeks: int = Field(ge=1, le=24)
    route_of_administration: RouteOfAdministration
    regulatory_body: RegulatoryBody
    strategy_mode: StrategyMode = "cooperative"
    optimize_excipient_percentages: bool = True
    pkpd_objective: PKPDObjective = Field(default_factory=PKPDObjective)

    @field_validator("apis")
    @classmethod
    def validate_apis(cls, value: List[APIComponent]) -> List[APIComponent]:
        if not value:
            raise ValueError("At least one API is required")
        if len(value) > 5:
            raise ValueError("ChronoThera supports up to five APIs per simulation")
        return value

    @field_validator("excipients")
    @classmethod
    def validate_excipients(cls, value: List[ExcipientComponent]) -> List[ExcipientComponent]:
        if not value:
            raise ValueError("At least one excipient is required")
        return value


class ReleaseDataset(BaseModel):
    api: str
    cumulative_release: List[float]
    model: str
    rationale: str


class ReleaseProfile(BaseModel):
    labels: List[str]
    datasets: List[ReleaseDataset]


class ScoreExplanation(BaseModel):
    score: int
    rationale: str
    assumptions: List[str]
    uncertainty: List[str]
    recommendation: str
    next_best_step: str


class GuardianReviewState(BaseModel):
    required: bool
    status: str
    reasons: List[str]
    reviewer: Optional[str] = None
    notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class ChronoTheraSimulationResult(BaseModel):
    id: str
    created_at: datetime
    asset_id: Optional[str]
    program_id: Optional[str]
    input: ChronoTheraSimulationRequest
    release_profile: ReleaseProfile
    scorecard: Dict[str, ScoreExplanation]
    overall_chronothera_score: int
    formulation_delivery_profile: Dict[str, Any]
    epistemic_trace: Dict[str, Any]
    guardian_review: GuardianReviewState
    disclaimer: str


class GuardianReviewRequest(BaseModel):
    decision: GuardianDecision
    reviewer: str = "Guardian"
    notes: str = ""
