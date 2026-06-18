"""ChronoThera platform service.

ChronoThera is NexiThera's formulation and delivery intelligence layer.  The
service intentionally uses deterministic, research-use heuristics: it supports
preclinical planning and traceable assumption mapping, not validated PK/PD,
clinical, regulatory, or manufacturing claims.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..schemas.calibration import ConfidenceInterval, FormulationOutcome
from ..schemas.chronothera import (
    ChronoTheraSimulationRequest,
    ChronoTheraSimulationResult,
    GuardianReviewRequest,
    GuardianReviewState,
    ReleaseDataset,
    ReleaseProfile,
    ScoreExplanation,
)

logger = logging.getLogger(__name__)

ENGINE_VERSION = "chronothera-platform-engine-v0.3"
DISCLAIMER = (
    "ChronoThera simulations are preliminary formulation-intelligence outputs "
    "for research and planning only. Results are not validated PK/PD predictions, "
    "regulatory advice, clinical recommendations, or manufacturing instructions."
)
ZONE_CLUSTER = "ChronoThera Formulation & Delivery Zone Cluster"
ZONES = [
    "Formulation Zone",
    "Delivery Zone",
    "PK/PD Optimization Zone",
    "Stability & Manufacturability Zone",
    "Patient-Centric Design Zone",
    "Regulatory Bridge Zone",
]
CXU_DEFINITIONS = [
    ("CXU_RELEASE_KINETICS", "release kinetics CXU"),
    ("CXU_EXCIPIENT_COMPATIBILITY", "excipient compatibility CXU"),
    ("CXU_ROUTE_FEASIBILITY", "route feasibility CXU"),
    ("CXU_HALF_LIFE_EXTENSION", "half-life extension CXU"),
    ("CXU_MANUFACTURABILITY", "manufacturability CXU"),
    ("CXU_PATIENT_CENTRICITY", "patient-centricity CXU"),
    ("CXU_REGULATORY_BRIDGE", "regulatory bridge CXU"),
]


@dataclass(frozen=True)
class AssetPreset:
    id: str
    label: str
    category: str
    modality: str
    default_apis: List[str]
    suggested_routes: List[str]
    formulation_objectives: List[str]
    chronothera_focus: List[str]
    dossier_anchor: str


ASSET_PRESETS = [
    AssetPreset(
        id="peg-insulin-glargine-citrate",
        label="PEGylated Insulin Glargine-Citrate",
        category="Category A — Near-Term Revenue & Capital Efficiency",
        modality="biologic/formulation-enhanced",
        default_apis=["Insulin Glargine"],
        suggested_routes=["SC"],
        formulation_objectives=["half_life_extension", "pegylation_strategy", "depot_formulation"],
        chronothera_focus=["half-life extension", "weekly dosing", "stability", "patient-centricity"],
        dossier_anchor="category-a/peg-insulin-glargine-citrate",
    ),
    AssetPreset(
        id="metformin-dapagliflozin-dr",
        label="Metformin + Dapagliflozin Delayed-Release Oral Combo",
        category="Category A — Near-Term Revenue & Capital Efficiency",
        modality="oral combination",
        default_apis=["Metformin", "Dapagliflozin"],
        suggested_routes=["oral"],
        formulation_objectives=["oral_delayed_release", "sustained_release", "co_formulation"],
        chronothera_focus=["delayed release", "GI tolerability", "adherence", "co-formulation"],
        dossier_anchor="category-a/metformin-dapagliflozin-dr",
    ),
    AssetPreset("theravac-dryamd-1", "TheraVac-DryAMD-1", "Category B — Differentiated Assets / Medium-Term Value", "peptide therapy", ["DryAMD Peptide Candidate"], ["local", "ocular"], ["local_ocular_delivery"], ["ocular delivery", "oxidative stress", "local safety", "stability"], "category-b/theravac-dryamd-1"),
    AssetPreset("theravac-ac-1", "TheraVac-AC-1", "Category B — Differentiated Assets / Medium-Term Value", "peptide vaccine", ["AC-1 Peptide Antigen"], ["SC", "IM"], ["co_formulation", "sustained_release"], ["immune presentation", "adjuvant compatibility", "stability"], "category-b/theravac-ac-1"),
    AssetPreset("theravac-ac-2", "TheraVac-AC-2", "Category B — Differentiated Assets / Medium-Term Value", "peptide vaccine", ["KRAS Peptide Antigen"], ["SC", "IM"], ["co_formulation", "sustained_release"], ["immune presentation", "KRAS antigen delivery", "stability"], "category-b/theravac-ac-2"),
    AssetPreset("theravac-tnbc-1", "TheraVac-TNBC-1", "Category C — Novel Discovery Programs / Long-Term Upside", "peptide vaccine", ["TNBC Peptide Antigen"], ["SC", "IM"], ["co_formulation"], ["immune presentation", "tumor antigen delivery", "stability"], "category-c/theravac-tnbc-1"),
    AssetPreset("theravac-aa-1", "TheraVac-AA-1", "Category C — Novel Discovery Programs / Long-Term Upside", "peptide therapy", ["AA-1 Peptide Candidate"], ["SC", "IM"], ["sustained_release", "half_life_extension"], ["exposure smoothing", "stability", "patient-centricity"], "category-c/theravac-aa-1"),
    AssetPreset("mpox-pilot-program", "MPOX Pilot Program", "Forge Rapid Response Programs™", "vaccine/therapy-oriented program", ["MPOX Immunogen Candidate"], ["SC", "IM"], ["co_formulation"], ["rapid preclinical package", "intervention strategy", "clinical forecast support"], "rapid-response/mpox-pilot-program"),
    AssetPreset("future-emerging-threat", "Future Emerging Threat Program", "Forge Rapid Response Programs™", "rapid response platform", ["Emerging Threat Immunogen"], ["SC", "IM"], ["co_formulation", "sustained_release"], ["rapid formulation screen", "platform readiness", "preclinical package"], "rapid-response/future-emerging-threat"),
]

EXCIPIENT_STRATEGIES = [
    {"name": "PLGA", "default_percentage": 35, "class": "polymer", "function": "depot/sustained release"},
    {"name": "PEG", "default_percentage": 5, "class": "polyether", "function": "half-life/formulation support"},
    {"name": "Chitosan", "default_percentage": 5, "class": "biopolymer", "function": "mucoadhesive/delivery support"},
    {"name": "Eudragit", "default_percentage": 12, "class": "polymer", "function": "oral modified release"},
    {"name": "HPMC", "default_percentage": 8, "class": "cellulose derivative", "function": "matrix/controlled release"},
    {"name": "Trehalose", "default_percentage": 4, "class": "stabilizer", "function": "lyoprotection/stability"},
    {"name": "Poloxamer", "default_percentage": 6, "class": "surfactant", "function": "solubilization/local delivery"},
]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(value)))


def _has_excipient(request: ChronoTheraSimulationRequest, name: str) -> bool:
    return any(e.name.lower() == name.lower() for e in request.excipients)


class ChronoTheraService:
    """Deterministic formulation and delivery intelligence service."""

    def __init__(
        self,
        persistence_path: Optional[Path] = None,
        epistemicos_client: Optional[Any] = None,
    ) -> None:
        self.persistence_path = persistence_path or Path(__file__).resolve().parents[2] / "data" / "chronothera" / "simulations.json"
        self.epistemicos = epistemicos_client

        # Lazy-import optional components to avoid circular deps at module load
        from ..utils.pk_precedent_adapter import PKPrecedentAdapter
        from .formulation_calibrator import get_calibrator

        self.pk_adapter = PKPrecedentAdapter(epistemicos_client)
        self.calibrator = get_calibrator()

    def catalog(self) -> Dict[str, Any]:
        return {
            "engine_version": ENGINE_VERSION,
            "formulation_objectives": [
                "sustained_release",
                "half_life_extension",
                "pegylation_strategy",
                "depot_formulation",
                "oral_delayed_release",
                "local_ocular_delivery",
                "chronotherapeutic_release",
                "co_formulation",
            ],
            "routes_of_administration": ["oral", "SC", "IM", "IV", "local", "ocular"],
            "regulatory_bodies": ["FDA", "EMA", "PMDA", "TGA", "Health Canada"],
            "excipients": EXCIPIENT_STRATEGIES,
            "asset_presets": [preset.__dict__ for preset in ASSET_PRESETS],
        }

    async def run_simulation(self, request: ChronoTheraSimulationRequest) -> ChronoTheraSimulationResult:
        release_profile = await self._generate_release_profile(request)
        scorecard = await self._generate_scorecard(request)
        overall = _clamp(sum(item.score for item in scorecard.values()) / len(scorecard))
        calibrated_score, overall_confidence = self._compute_calibrated_score(request, overall)
        formulation_delivery_profile = self._build_formulation_delivery_profile(request, scorecard)
        epistemic_trace, epistemicos_status = await self._build_epistemic_trace(request, release_profile, scorecard, overall)
        guardian_review = self._build_guardian_review(request, scorecard, overall)
        input_hash = epistemic_trace["provenance"]["input_hash"]
        created_at = datetime.fromtimestamp(1704067200 + int(input_hash[:8], 16), tz=timezone.utc)
        result = ChronoTheraSimulationResult(
            id=f"chrono-{input_hash[:12]}",
            created_at=created_at,
            asset_id=request.asset_id,
            program_id=request.program_id,
            input=request,
            release_profile=release_profile,
            scorecard=scorecard,
            overall_chronothera_score=calibrated_score,
            overall_confidence=overall_confidence,
            formulation_delivery_profile=formulation_delivery_profile,
            epistemic_trace=epistemic_trace,
            epistemicos_query_status=epistemicos_status,
            guardian_review=guardian_review,
            disclaimer=DISCLAIMER,
        )
        await self.save_simulation(result)
        # Fire-and-forget feedback loop (non-blocking)
        await self._post_to_epistemicos(result)
        return result

    async def list_simulations(self, asset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        store = self._read_store()
        simulations = store.get("simulations", [])
        if asset_id:
            simulations = [sim for sim in simulations if sim.get("asset_id") == asset_id]
        return simulations

    async def get_simulation(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        for simulation in await self.list_simulations():
            if simulation.get("id") == simulation_id:
                return simulation
        return None

    async def save_simulation(self, result: ChronoTheraSimulationResult) -> None:
        store = self._read_store()
        serialized = result.model_dump(mode="json")
        simulations = [sim for sim in store.get("simulations", []) if sim.get("id") != result.id]
        simulations.insert(0, serialized)
        self._write_store({"simulations": simulations})

    async def record_guardian_review(self, simulation_id: str, review: GuardianReviewRequest) -> Optional[Dict[str, Any]]:
        store = self._read_store()
        for simulation in store.get("simulations", []):
            if simulation.get("id") == simulation_id:
                simulation["guardian_review"] = {
                    **simulation.get("guardian_review", {}),
                    "status": review.decision,
                    "reviewer": review.reviewer,
                    "notes": review.notes,
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                }
                self._write_store(store)
                return simulation
        return None

    async def _generate_release_profile(self, request: ChronoTheraSimulationRequest) -> ReleaseProfile:
        labels = [f"Week {week}" for week in range(1, request.release_duration_weeks + 1)]
        datasets: List[ReleaseDataset] = []
        for index, api in enumerate(request.apis):
            # Look up PK parameters for this API (epistemicos or heuristic)
            pk_params = await self.pk_adapter.lookup_pk_parameters(
                api.name,
                request.formulation_objective,
                request.route_of_administration,
            )
            pk_precedent_used = self.epistemicos is not None
            values = []
            previous = 0.0
            for week in range(1, request.release_duration_weeks + 1):
                t = week / request.release_duration_weeks
                value = self._release_curve_with_pk(
                    request.formulation_objective, t, index, pk_params
                )
                previous = max(previous, min(value, 98.0))
                values.append(round(previous, 1))
            datasets.append(
                ReleaseDataset(
                    api=api.name,
                    cumulative_release=values,
                    model=self._release_model_name(request.formulation_objective),
                    rationale=f"PK-informed placeholder curve for {request.formulation_objective.replace('_', ' ')} research planning.",
                    pk_precedent_used=pk_precedent_used,
                )
            )
        return ReleaseProfile(labels=labels, datasets=datasets)

    def _release_curve(self, objective: str, t: float, api_index: int) -> float:
        offset = api_index * 1.5
        if objective == "depot_formulation":
            return 100 * (1 - math.exp(-2.0 * max(0, t - 0.10))) - 5 + offset
        if objective == "local_ocular_delivery":
            return 100 / (1 + math.exp(-8 * (t - 0.52))) + offset
        if objective == "chronotherapeutic_release":
            return 18 + math.floor(t * 4) * 18 + 10 * math.sin(t * math.pi * 6) + offset
        if objective == "oral_delayed_release":
            return 100 / (1 + math.exp(-7 * (t - 0.35))) + offset
        if objective in {"half_life_extension", "pegylation_strategy"}:
            return 100 * (1 - math.exp(-1.75 * t)) + offset
        return 100 * (1 - math.exp(-2.8 * (t**1.25))) + offset

    def _release_curve_with_pk(
        self,
        objective: str,
        t: float,
        api_index: int,
        pk_params: Optional[Dict[str, float]],
    ) -> float:
        """Release curve modulated by PK parameters.

        When PK parameters are available, ``CL`` and ``Tmax`` are used to
        adjust the rate and onset of the base curve:
        - Higher CL → faster clearance → steeper early rise, lower plateau
        - Higher Tmax → delayed absorption onset

        Falls back to the original heuristic curve when no PK params provided.
        """
        if not pk_params:
            return self._release_curve(objective, t, api_index)

        tmax_hours = pk_params.get("Tmax", 2.0)
        cl = pk_params.get("CL", 1.0)

        # Normalise Tmax against ~1-week (168 h) horizon → t_delay in [0,1]
        t_delay = min(tmax_hours / 168.0, 0.3)

        # CL modulation: higher CL shifts the curve leftward (faster)
        cl_factor = max(0.5, min(2.0, cl))  # clamp to [0.5, 2.0]

        # Shift time axis by Tmax delay for depot / slow-absorption objectives
        if objective in {"depot_formulation", "sustained_release"}:
            t_adj = max(0.0, t - t_delay)
        else:
            t_adj = t

        base = self._release_curve(objective, t_adj, api_index)

        # Scale plateau by CL: higher clearance → lower steady-state exposure
        if cl_factor > 1.2:
            base = base * (1.0 - (cl_factor - 1.0) * 0.1)

        return base

    def _release_model_name(self, objective: str) -> str:
        return {
            "depot_formulation": "lagged depot long-tail curve",
            "local_ocular_delivery": "delayed local-delivery sigmoid curve",
            "chronotherapeutic_release": "staged pulsatile curve",
            "oral_delayed_release": "delayed-release sigmoid curve",
            "half_life_extension": "half-life extension exposure-support curve",
            "pegylation_strategy": "PEGylation exposure-support curve",
        }.get(objective, "smooth Weibull-like cumulative curve")

    async def _generate_scorecard(self, request: ChronoTheraSimulationRequest) -> Dict[str, ScoreExplanation]:
        asset = self._asset(request.asset_id)
        rapid = bool(asset and "Rapid Response" in asset.category)
        multi_api = len(request.apis) > 1
        route_fit = request.route_of_administration in (asset.suggested_routes if asset else [])
        objective_fit = request.formulation_objective in (asset.formulation_objectives if asset else [request.formulation_objective])

        scores = {
            "sustained_release": _clamp(68 + (request.release_duration_weeks >= 4) * 8 + _has_excipient(request, "PLGA") * 8 + _has_excipient(request, "HPMC") * 6 - (request.release_duration_weeks > 16) * 8),
            "half_life_extension": _clamp(62 + _has_excipient(request, "PEG") * 16 + (request.formulation_objective in {"half_life_extension", "pegylation_strategy"}) * 10 - (request.route_of_administration == "IV") * 10),
            "delivery_route_fit": _clamp(64 + route_fit * 16 + (request.route_of_administration in {"oral", "SC", "IM"}) * 8 - (request.route_of_administration == "IV") * 18),
            "pkpd_alignment": _clamp(65 + request.pkpd_objective.adherence_priority * 3 + (request.release_duration_weeks >= 4) * 6 - (request.release_duration_weeks > 18) * 8),
            "excipient_compatibility": _clamp(64 + _has_excipient(request, "Trehalose") * 7 + _has_excipient(request, "PEG") * 5 + objective_fit * 8 - max(0, len(request.excipients) - 4) * 4),
            "stability": _clamp(70 + _has_excipient(request, "Trehalose") * 10 + _has_excipient(request, "PEG") * 4 - multi_api * 6 - (request.release_duration_weeks > 12) * 10),
            "manufacturability": _clamp(72 - len(request.excipients) * 2 - (request.route_of_administration == "ocular") * 7 - (request.release_duration_weeks > 18) * 8 + request.optimize_excipient_percentages * 5),
            "patient_centricity": _clamp(68 + (request.route_of_administration in {"oral", "SC"}) * 12 + (request.pkpd_objective.dosing_interval_days >= 7) * 8 - (request.route_of_administration == "IV") * 22),
            "regulatory_fit": _clamp(70 - (request.route_of_administration == "IV") * 15 - (request.release_duration_weeks > 12) * 8 - rapid * 10 + objective_fit * 5),
            "preclinical_package_contribution": _clamp(66 + objective_fit * 10 + route_fit * 6 - rapid * 5),
        }
        return {key: self._explain_score(key, score, request) for key, score in scores.items()}

    def _explain_score(self, key: str, score: int, request: ChronoTheraSimulationRequest) -> ScoreExplanation:
        label = key.replace("_", " ")
        assumptions = [
            "Scores use deterministic heuristic rules for formulation-readiness planning.",
            f"Route assessed as {request.route_of_administration}; duration assessed as {request.release_duration_weeks} weeks.",
            "No wet-lab, validated PK/PD, clinical, or GMP manufacturing dataset is attached to this run.",
        ]
        uncertainty = [
            "Compatibility matrix is provisional.",
            "Release curve is a placeholder model for planning support.",
        ]
        recommendation = "Advance to a targeted formulation screen if score is strong; otherwise revise route, excipient strategy, or duration assumptions."
        if score < 65:
            recommendation = f"Improve {label} before using this profile for portfolio planning."

        # Compute confidence interval via calibrator
        formulation = FormulationOutcome(
            id="transient",
            formulation_objective=request.formulation_objective,
            route=request.route_of_administration,
            release_duration_weeks=request.release_duration_weeks,
            apis=[api.name for api in request.apis],
            excipients=[exc.name for exc in request.excipients],
            predicted_score=float(score),
            actual_outcome="success",  # placeholder; calibrator uses this for featurisation only
        )
        try:
            lower, mean, upper = self.calibrator.predict_confidence_interval(
                formulation, float(score)
            )
            ci = ConfidenceInterval(lower=lower, mean=mean, upper=upper)
        except Exception:  # noqa: BLE001
            ci = ConfidenceInterval(
                lower=max(0.0, float(score) - 10.0),
                mean=float(score),
                upper=min(100.0, float(score) + 10.0),
            )

        return ScoreExplanation(
            score=score,
            rationale=f"{label.title()} score reflects objective-route fit, excipient strategy, duration burden, and asset context.",
            assumptions=assumptions,
            uncertainty=uncertainty,
            recommendation=recommendation,
            next_best_step=f"Run a focused {label} evidence package: bench compatibility, release assay design, and EpistemicOS evidence review.",
            confidence=ci,
        )

    def _build_formulation_delivery_profile(self, request: ChronoTheraSimulationRequest, scorecard: Dict[str, ScoreExplanation]) -> Dict[str, Any]:
        asset = self._asset(request.asset_id)
        return {
            "asset_dossier_link": asset.dossier_anchor if asset else None,
            "formulation_strategy": request.formulation_objective.replace("_", " "),
            "route_strategy": request.route_of_administration,
            "co_formulation": len(request.apis) > 1,
            "pegylation_strategy": _has_excipient(request, "PEG") or request.formulation_objective == "pegylation_strategy",
            "depot_strategy": _has_excipient(request, "PLGA") or request.formulation_objective == "depot_formulation",
            "patient_burden_signal": "lower" if scorecard["patient_centricity"].score >= 75 else "requires review",
            "preclinical_package_contribution": scorecard["preclinical_package_contribution"].score,
        }

    async def _build_epistemic_trace(
        self,
        request: ChronoTheraSimulationRequest,
        release_profile: ReleaseProfile,
        scorecard: Dict[str, ScoreExplanation],
        overall: int,
    ) -> Tuple[Dict[str, Any], str]:
        input_payload = request.model_dump(mode="json")
        output_payload = {
            "release_profile": release_profile.model_dump(mode="json"),
            "scorecard": {key: value.model_dump(mode="json") for key, value in scorecard.items()},
            "overall_chronothera_score": overall,
        }
        input_hash = _hash(input_payload)
        uncertainty = sorted({reason for score in scorecard.values() for reason in score.uncertainty})
        assumptions = sorted({assumption for score in scorecard.values() for assumption in score.assumptions})

        # Try to fetch live CXU/swarm data from EpistemicOS
        live_cxus: Optional[List[Dict[str, Any]]] = None
        live_swarm: Optional[Dict[str, Any]] = None
        epistemicos_status = "unavailable"

        if self.epistemicos is not None:
            from ..clients.epistemicos_client import EpistemicOSClientError
            try:
                zone_data = await self.epistemicos.get_zone(
                    "ChronoThera-Formulation-Cluster",
                    include_cxus=True,
                    include_swarm_metrics=True,
                )
                live_cxus = zone_data.get("cxus")
                live_swarm = zone_data.get("swarm_metrics")
                epistemicos_status = "success"
                logger.info("epistemicos live zone data fetched successfully")
            except EpistemicOSClientError as exc:
                logger.warning(
                    "epistemicos unavailable; using synthetic trace. Reason: %s", exc
                )
                epistemicos_status = "fallback"

        # Build CXU list: prefer live data, fall back to synthetic
        if live_cxus:
            cxus = live_cxus
        else:
            cxus = [
                {
                    "id": cxu_id,
                    "name": name,
                    "question": self._cxu_question(cxu_id),
                    "confidence": round(min(0.92, max(0.45, overall / 100)), 2),
                    "uncertainty": uncertainty,
                }
                for cxu_id, name in CXU_DEFINITIONS
            ]

        swarm = live_swarm or {
            "id": "CHRONOTHERA_FORMULATION_SWARM",
            "mode": request.strategy_mode,
            "participants": [name for _, name in CXU_DEFINITIONS],
            "consensus_score": overall,
            "consensus_rationale": "Consensus summarizes formulation, delivery, PK/PD planning, manufacturability, patient-centricity, and regulatory bridge CXUs.",
        }

        trace = {
            "zone_cluster": ZONE_CLUSTER,
            "zones": ZONES,
            "cxus": cxus,
            "swarm": swarm,
            "provenance": {
                "input_hash": input_hash,
                "output_hash": _hash(output_payload),
                "model_engine_version": ENGINE_VERSION,
                "timestamp": datetime.fromtimestamp(1704067200 + int(input_hash[:8], 16), tz=timezone.utc).isoformat(),
                "assumptions": assumptions,
                "uncertainty_reasons": uncertainty,
                "epistemicos_status": epistemicos_status,
            },
        }
        return trace, epistemicos_status

    def _cxu_question(self, cxu_id: str) -> str:
        return {
            "CXU_RELEASE_KINETICS": "Does the selected objective produce a plausible research-use release profile?",
            "CXU_EXCIPIENT_COMPATIBILITY": "Do the selected excipients fit the API, objective, and route assumptions?",
            "CXU_ROUTE_FEASIBILITY": "Is the proposed route aligned with asset modality and formulation objective?",
            "CXU_HALF_LIFE_EXTENSION": "Does the strategy plausibly support exposure smoothing or half-life extension planning?",
            "CXU_MANUFACTURABILITY": "Does the formulation strategy appear developable enough for a next planning step?",
            "CXU_PATIENT_CENTRICITY": "Does the route and dosing interval reduce patient burden assumptions?",
            "CXU_REGULATORY_BRIDGE": "What uncertainty remains before regulatory-facing planning discussions?",
        }[cxu_id]

    def _build_guardian_review(self, request: ChronoTheraSimulationRequest, scorecard: Dict[str, ScoreExplanation], overall: int) -> GuardianReviewState:
        from .guardian_trigger_config import get_trigger_reasons

        asset = self._asset(request.asset_id)
        category = asset.category if asset else "Category B"
        is_rapid = bool(asset and "Rapid Response" in asset.category)

        # IV route is always a trigger regardless of category
        extra_reasons: List[str] = []
        if request.route_of_administration == "IV":
            extra_reasons.append("IV route of administration")

        risk_reasons = get_trigger_reasons(
            category=category,
            overall_score=overall,
            release_duration_weeks=request.release_duration_weeks,
            scorecard=scorecard,
            is_rapid_response=is_rapid,
        )
        reasons = risk_reasons + [r for r in extra_reasons if r not in risk_reasons]

        # Determine risk tier label
        if is_rapid:
            risk_tier = "rapid_response"
        elif "Category A" in category:
            risk_tier = "category_a"
        elif "Category C" in category:
            risk_tier = "category_c"
        else:
            risk_tier = "category_b"

        return GuardianReviewState(
            required=bool(reasons),
            status="pending" if reasons else "not-required",
            reasons=reasons,
            risk_tier=risk_tier,
        )

    def _compute_calibrated_score(
        self,
        request: ChronoTheraSimulationRequest,
        nominal_overall: int,
    ) -> Tuple[int, ConfidenceInterval]:
        """Compute overall calibrated score and confidence interval."""
        formulation = FormulationOutcome(
            id="transient-overall",
            formulation_objective=request.formulation_objective,
            route=request.route_of_administration,
            release_duration_weeks=request.release_duration_weeks,
            apis=[api.name for api in request.apis],
            excipients=[exc.name for exc in request.excipients],
            predicted_score=float(nominal_overall),
            actual_outcome="success",
        )
        try:
            lower, mean, upper = self.calibrator.predict_confidence_interval(
                formulation, float(nominal_overall)
            )
        except Exception:  # noqa: BLE001
            lower = max(0.0, float(nominal_overall) - 10.0)
            mean = float(nominal_overall)
            upper = min(100.0, float(nominal_overall) + 10.0)

        ci = ConfidenceInterval(lower=lower, mean=mean, upper=upper)
        return _clamp(mean), ci

    async def _post_to_epistemicos(
        self, result: "ChronoTheraSimulationResult"
    ) -> None:
        """Fire-and-forget: post simulation outcome to EpistemicOS feedback loop."""
        if self.epistemicos is None:
            return
        from ..clients.epistemicos_client import EpistemicOSClientError
        try:
            scorecard_summary = {
                k: v.score for k, v in result.scorecard.items()
            }
            await self.epistemicos.post_formulation_result(
                zone_id="ChronoThera-Formulation-Cluster",
                simulation_id=result.id,
                asset_id=result.asset_id,
                overall_score=result.overall_chronothera_score,
                epistemicos_status=result.epistemicos_query_status,
                scorecard_summary=scorecard_summary,
            )
        except EpistemicOSClientError as exc:
            logger.warning("epistemicos feedback post failed (non-blocking): %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error posting to epistemicos: %s", exc)

    def _asset(self, asset_id: Optional[str]) -> Optional[AssetPreset]:
        return next((asset for asset in ASSET_PRESETS if asset.id == asset_id), None)

    def _read_store(self) -> Dict[str, Any]:
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.persistence_path.exists():
            self.persistence_path.write_text(json.dumps({"simulations": []}, indent=2))
        return json.loads(self.persistence_path.read_text())

    def _write_store(self, store: Dict[str, Any]) -> None:
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        self.persistence_path.write_text(json.dumps(store, indent=2, sort_keys=True))


chronothera_service = ChronoTheraService()
