# app/services/clinical_forecaster_service.py
"""Clinical Forecaster service (PR #11).

Orchestrates the five evidence agents + Forecast Synthesizer, persists
``clinical_forecasts``, and provides:

    * forecast generation with full decomposition / sensitivity /
      scenario data,
    * retrieval and Guardian submission (status transitions),
    * curated precedent insertion,
    * Bayesian weight calibration from observed trial outcomes.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from ..agents.biology_evidence_agent import BiologyEvidenceAgent
from ..agents.clinical_competitive_landscape_agent import (
    ClinicalCompetitiveLandscapeAgent,
)
from ..agents.forecast_synthesizer_agent import (
    DEFAULT_WEIGHTS,
    FACTOR_NAMES,
    ForecastSynthesizerAgent,
    bayesian_update_weights,
    normalize_weights,
)
from ..agents.historical_precedent_agent import HistoricalPrecedentAgent
from ..agents.safety_toxicity_agent import SafetyToxicityAgent
from ..agents.trial_design_agent import TrialDesignAgent
from ..core.database import db
from ..services.guardian_service import GuardianService


_VALID_PHASES = {"I", "II", "III"}
_VALID_STATUSES = {"draft", "under_review", "approved", "superseded"}


class ClinicalForecasterService:
    """Service layer for clinical forecasts (PR #11)."""

    def __init__(self) -> None:
        self._guardian = GuardianService()

    # ------------------------------------------------------------------
    # Weight calibration
    # ------------------------------------------------------------------
    async def load_weights(self) -> Dict[str, float]:
        """Load calibrated factor weights from ``forecast_factors``."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT factor_name, base_weight FROM forecast_factors"
            )
        weights = {row["factor_name"]: float(row["base_weight"])
                   for row in rows}
        # Fall back to defaults for any missing entries.
        for name in FACTOR_NAMES:
            weights.setdefault(name, DEFAULT_WEIGHTS[name])
        return normalize_weights(weights)

    async def save_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        normalized = normalize_weights(weights)
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            for name, w in normalized.items():
                await conn.execute(
                    """INSERT INTO forecast_factors
                            (factor_name, base_weight, last_calibrated_at)
                       VALUES ($1, $2, NOW())
                       ON CONFLICT (factor_name) DO UPDATE
                          SET base_weight = EXCLUDED.base_weight,
                              last_calibrated_at = NOW()""",
                    name, float(w),
                )
        return normalized

    async def calibrate_from_outcome(
        self,
        observed_outcome: bool,
        factor_likelihoods: Dict[str, float],
        learning_rate: float = 0.10,
    ) -> Dict[str, float]:
        """Apply one Bayesian-style update to the persisted weights."""
        current = await self.load_weights()
        updated = bayesian_update_weights(
            current, observed_outcome, factor_likelihoods, learning_rate
        )
        return await self.save_weights(updated)

    # ------------------------------------------------------------------
    # Precedents
    # ------------------------------------------------------------------
    async def add_precedent(
        self,
        *,
        target_label: str,
        disease_label: str,
        modality: Optional[str],
        phase: str,
        met_primary_endpoint: bool,
        effect_size: Optional[float] = None,
        p_value: Optional[float] = None,
        trial_id: Optional[str] = None,
        source: Optional[str] = None,
        weight: float = 1.0,
    ) -> Dict[str, Any]:
        if phase not in _VALID_PHASES:
            raise ValueError(f"phase must be one of {sorted(_VALID_PHASES)}")
        row_id = str(uuid.uuid4())
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO clinical_precedents
                        (id, target_label, disease_label, modality, phase,
                         met_primary_endpoint, effect_size, p_value,
                         trial_id, source, weight)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                   ON CONFLICT (trial_id, target_label, disease_label, phase)
                       DO NOTHING""",
                row_id, target_label, disease_label, modality, phase,
                bool(met_primary_endpoint), effect_size, p_value,
                trial_id, source, float(weight),
            )
        return {
            "id": row_id,
            "target_label": target_label,
            "disease_label": disease_label,
            "modality": modality,
            "phase": phase,
            "met_primary_endpoint": met_primary_endpoint,
            "effect_size": effect_size,
            "p_value": p_value,
            "trial_id": trial_id,
            "source": source,
            "weight": float(weight),
        }

    # ------------------------------------------------------------------
    # Forecast generation
    # ------------------------------------------------------------------
    async def generate_forecast(
        self,
        *,
        candidate_id: str,
        phase: str,
        primary_endpoint: Optional[str] = None,
        trial_design: Optional[Dict[str, Any]] = None,
        scenarios: Optional[List[Dict[str, Any]]] = None,
        known_safety_flags: Optional[List[str]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        if phase not in _VALID_PHASES:
            raise ValueError(f"phase must be one of {sorted(_VALID_PHASES)}")
        trial_design = trial_design or {}

        candidate_ctx = await self._candidate_context(candidate_id)

        weights = await self.load_weights()
        sub_errors: Dict[str, str] = {}
        factor_confidences: Dict[str, float] = {}

        # 1. Biology
        bio = await self._safe_run(
            agent_factory=lambda aid: BiologyEvidenceAgent(aid),
            name="Biology Evidence Agent",
            role="clinical_biology",
            inputs={
                "candidate_id": candidate_id,
                "target_label": candidate_ctx.get("target_label"),
            },
            run_type="clinical_biology",
            program_id=candidate_ctx["program_id"],
            candidate_id=candidate_id,
            sub_errors=sub_errors,
            key="biology",
        )
        biology_score = float(
            bio["structure"].get("biology_score", 0.5)
        )
        factor_confidences["biology"] = float(bio.get("confidence", 0.5))

        # 2. Safety
        safe = await self._safe_run(
            agent_factory=lambda aid: SafetyToxicityAgent(aid),
            name="Safety Toxicity Agent",
            role="clinical_safety",
            inputs={
                "candidate_id": candidate_id,
                "known_safety_flags": known_safety_flags or [],
            },
            run_type="clinical_safety",
            program_id=candidate_ctx["program_id"],
            candidate_id=candidate_id,
            sub_errors=sub_errors,
            key="safety",
        )
        safety_score = float(safe["structure"].get("safety_score", 0.6))
        factor_confidences["safety"] = float(safe.get("confidence", 0.5))

        # 3. Trial design
        design = await self._safe_run(
            agent_factory=lambda aid: TrialDesignAgent(aid),
            name="Trial Design Agent",
            role="clinical_trial_design",
            inputs={
                "candidate_id": candidate_id,
                "phase": phase,
                "trial_design": trial_design,
                "primary_endpoint": primary_endpoint,
            },
            run_type="clinical_trial_design",
            program_id=candidate_ctx["program_id"],
            candidate_id=candidate_id,
            sub_errors=sub_errors,
            key="design",
        )
        design_score_value = float(
            design["structure"].get("design_score", 0.6)
        )
        factor_confidences["design"] = float(design.get("confidence", 0.5))

        # 4. Competition (clinical)
        comp = await self._safe_run(
            agent_factory=lambda aid: ClinicalCompetitiveLandscapeAgent(aid),
            name="Clinical Competitive Landscape Agent",
            role="clinical_competitive_landscape",
            inputs={"candidate_id": candidate_id},
            run_type="clinical_competitive_landscape",
            program_id=candidate_ctx["program_id"],
            candidate_id=candidate_id,
            sub_errors=sub_errors,
            key="competition",
        )
        competition_score = float(
            comp["structure"].get("competition_score", 0.7)
        )
        factor_confidences["competition"] = float(comp.get("confidence", 0.5))

        # 5. Historical precedent
        prec = await self._safe_run(
            agent_factory=lambda aid: HistoricalPrecedentAgent(aid),
            name="Historical Precedent Agent",
            role="clinical_precedent",
            inputs={
                "candidate_id": candidate_id,
                "target_label": candidate_ctx.get("target_label"),
                "disease_label": candidate_ctx.get("disease_label"),
                "modality": candidate_ctx.get("modality"),
                "phase": phase,
            },
            run_type="clinical_precedent",
            program_id=candidate_ctx["program_id"],
            candidate_id=candidate_id,
            sub_errors=sub_errors,
            key="precedent",
        )
        precedent_prior = float(
            prec["structure"].get("precedent_prior", 0.5)
        )
        precedent_ci = prec["structure"].get(
            "confidence_interval", [0.2, 0.8]
        )
        top_precedents = prec["structure"].get("top_precedents", [])
        factor_confidences["precedent"] = float(prec.get("confidence", 0.5))

        # 6. Synthesizer
        synth_agent_id = await _ensure_agent_record(
            "Forecast Synthesizer", "clinical_forecast"
        )
        synthesizer = ForecastSynthesizerAgent(synth_agent_id)
        synth = await synthesizer.run(
            program_id=candidate_ctx["program_id"],
            inputs={
                "candidate_id": candidate_id,
                "factors": {
                    "biology": biology_score,
                    "safety": safety_score,
                    "design": design_score_value,
                    "competition": competition_score,
                    "precedent": precedent_prior,
                },
                "weights": weights,
                "precedent_confidence_interval": precedent_ci,
                "factor_confidences": factor_confidences,
                "scenarios": scenarios or [],
            },
            candidate_id=candidate_id,
            run_type="clinical_forecast",
        )
        structure = (synth.get("output") or {}).get("structure", {}) or {}
        run_id = synth["run_id"]

        probability = float(structure.get("probability", 0.0))
        ci = structure.get("confidence_interval") or [None, None]

        forecast_id = str(uuid.uuid4())
        if persist:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO clinical_forecasts
                            (id, candidate_id, phase, primary_endpoint,
                             forecasted_probability,
                             confidence_interval_lower,
                             confidence_interval_upper,
                             decomposition, sensitivity_analysis,
                             scenario_alternatives, trace_id, status)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                    forecast_id, candidate_id, phase, primary_endpoint,
                    probability,
                    ci[0], ci[1],
                    json.dumps(structure.get("decomposition", {})),
                    json.dumps(structure.get("sensitivity", {})),
                    json.dumps(structure.get("scenarios", {})),
                    run_id, "draft",
                )

        return {
            "forecast_id": forecast_id,
            "candidate_id": candidate_id,
            "phase": phase,
            "primary_endpoint": primary_endpoint,
            "probability": probability,
            "confidence_interval": ci,
            "decomposition": structure.get("decomposition", {}),
            "sensitivity": structure.get("sensitivity", {}),
            "scenarios": structure.get("scenarios", {}),
            "factors": structure.get("factors", {}),
            "weights": structure.get("weights", weights),
            "verdict": structure.get("verdict"),
            "top_precedents": top_precedents,
            "trace_id": run_id,
            "status": "draft",
            "sub_errors": sub_errors,
        }

    # ------------------------------------------------------------------
    # Retrieval / Guardian submission
    # ------------------------------------------------------------------
    async def get_forecast(self, forecast_id: str) -> Dict[str, Any]:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM clinical_forecasts WHERE id = $1",
                forecast_id,
            )
        if not row:
            raise ValueError(f"Forecast not found: {forecast_id}")
        return _row_to_dict(row)

    async def submit_to_guardian(
        self,
        *,
        forecast_id: str,
        reviewer_id: str,
        decision: str,
        decision_rationale: str,
    ) -> Dict[str, Any]:
        forecast = await self.get_forecast(forecast_id)
        review = await self._guardian.create_review(
            review_type="candidate_review",
            entity_id=forecast["candidate_id"],
            entity_type="candidate",
            reviewer_id=reviewer_id,
            decision=decision,
            decision_rationale=decision_rationale,
        )
        new_status = (
            "approved" if decision in {"approve", "promote_to_epistemicos"}
            else "under_review"
        )
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE clinical_forecasts
                      SET guardian_review_id = $1, status = $2,
                          updated_at = NOW()
                    WHERE id = $3""",
                review["id"], new_status, forecast_id,
            )
        forecast["guardian_review_id"] = review["id"]
        forecast["status"] = new_status
        forecast["guardian_review"] = review
        return forecast

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _candidate_context(self, candidate_id: str) -> Dict[str, Any]:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT c.program_id, c.candidate_type AS modality,
                          c.therapeutic_area, b.name AS target_label
                     FROM candidates c
                     LEFT JOIN bio_entities b ON b.id = c.target_id
                    WHERE c.id = $1""",
                candidate_id,
            )
        if not row:
            raise ValueError(f"Candidate not found: {candidate_id}")
        return {
            "program_id": str(row["program_id"]),
            "modality": row["modality"],
            "target_label": row["target_label"],
            "disease_label": row["therapeutic_area"],
        }

    async def _safe_run(
        self,
        *,
        agent_factory,
        name: str,
        role: str,
        inputs: Dict[str, Any],
        run_type: str,
        program_id: str,
        candidate_id: str,
        sub_errors: Dict[str, str],
        key: str,
    ) -> Dict[str, Any]:
        try:
            agent_id = await _ensure_agent_record(name, role)
            agent = agent_factory(agent_id)
            result = await agent.run(
                program_id=program_id,
                inputs=inputs,
                candidate_id=candidate_id,
                run_type=run_type,
            )
            return result.get("output") or {"structure": {}, "confidence": 0.5}
        except Exception as exc:  # noqa: BLE001
            sub_errors[key] = str(exc)
            return {"structure": {}, "confidence": 0.4}


# ---------------------------------------------------------------------------
# Module-level helpers (shared with PR #10 service style)
# ---------------------------------------------------------------------------
async def _ensure_agent_record(name: str, role: str) -> str:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM agents WHERE name = $1", name
        )
        if row:
            return str(row["id"])
        new_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO agents (id, name, role, is_active)
               VALUES ($1, $2, $3, TRUE)
               ON CONFLICT (name) DO NOTHING""",
            new_id, name, role,
        )
        row = await conn.fetchrow(
            "SELECT id FROM agents WHERE name = $1", name
        )
        return str(row["id"]) if row else new_id


def _row_to_dict(row: Any) -> Dict[str, Any]:
    out = dict(row)
    for key in ("decomposition", "sensitivity_analysis",
                "scenario_alternatives"):
        val = out.get(key)
        if isinstance(val, str):
            try:
                out[key] = json.loads(val)
            except (TypeError, ValueError):
                pass
    return out


clinical_forecaster_service = ClinicalForecasterService()
