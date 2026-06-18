"""Integration tests for ChronoThera ↔ EpistemicOS connectivity.

Covers:
1. epistemicos available → live zone data used in trace
2. epistemicos unavailable → graceful synthetic fallback
3. PK precedent lookup from epistemicos
4. PK precedent fallback to heuristic when no results
5. EpistemicOS client error handling (timeout)
6. Guardian review risk stratification (Category A vs C)
7. Bayesian calibrator fit and predict
8. Confidence interval bounds invariant (lower ≤ mean ≤ upper)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.epistemicos_client import EpistemicOSClient, EpistemicOSClientError
from app.schemas.calibration import (
    CalibrationDataset,
    ConfidenceInterval,
    FormulationOutcome,
)
from app.schemas.chronothera import ChronoTheraSimulationRequest
from app.services.chronothera_service import ChronoTheraService
from app.services.formulation_calibrator import FormulationScorecardCalibrator
from app.services.guardian_trigger_config import get_trigger_reasons
from app.utils.pk_precedent_adapter import PKPrecedentAdapter


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def base_payload() -> dict:
    return {
        "asset_id": "peg-insulin-glargine-citrate",
        "program_id": "prog-test",
        "formulation_objective": "depot_formulation",
        "apis": [{"name": "Insulin Glargine", "dose_mg": 100, "modality": "biologic"}],
        "excipients": [
            {"name": "PLGA", "percentage": 35, "function": "depot"},
            {"name": "Trehalose", "percentage": 4, "function": "stability"},
        ],
        "release_duration_weeks": 4,
        "route_of_administration": "SC",
        "regulatory_body": "FDA",
        "strategy_mode": "cooperative",
        "optimize_excipient_percentages": True,
        "pkpd_objective": {
            "target_exposure": "weekly",
            "dosing_interval_days": 7,
            "peak_to_trough_priority": 3,
            "adherence_priority": 4,
        },
    }


@pytest.fixture()
def mock_epistemicos_client() -> AsyncMock:
    """Mock EpistemicOSClient that returns live zone data."""
    client = AsyncMock(spec=EpistemicOSClient)
    client.get_zone.return_value = {
        "zone_id": "ChronoThera-Formulation-Cluster",
        "cxus": [
            {
                "id": "CXU_LIVE_1",
                "name": "live release kinetics CXU",
                "question": "Does the live release profile match target?",
                "confidence": 0.88,
                "uncertainty": [],
            }
        ],
        "swarm_metrics": {
            "id": "LIVE_SWARM",
            "mode": "cooperative",
            "participants": ["live release kinetics CXU"],
            "consensus_score": 80,
            "consensus_rationale": "Live EpistemicOS consensus.",
        },
    }
    client.post_formulation_result.return_value = {"status": "accepted"}
    client.search_precedent.return_value = []
    return client


@pytest.fixture()
def service_with_epistemicos(
    tmp_path: Path, mock_epistemicos_client: AsyncMock
) -> ChronoTheraService:
    return ChronoTheraService(
        persistence_path=tmp_path / "simulations.json",
        epistemicos_client=mock_epistemicos_client,
    )


@pytest.fixture()
def service_no_epistemicos(tmp_path: Path) -> ChronoTheraService:
    return ChronoTheraService(persistence_path=tmp_path / "simulations.json")


# ---------------------------------------------------------------------------
# 1. epistemicos available → live data used
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chronothera_service_with_epistemicos_available(
    service_with_epistemicos: ChronoTheraService,
    mock_epistemicos_client: AsyncMock,
    base_payload: dict,
) -> None:
    result = await service_with_epistemicos.run_simulation(
        ChronoTheraSimulationRequest(**base_payload)
    )

    # Live data should have been requested
    mock_epistemicos_client.get_zone.assert_called_once_with(
        "ChronoThera-Formulation-Cluster",
        include_cxus=True,
        include_swarm_metrics=True,
    )

    # Status should be "success"
    assert result.epistemicos_query_status == "success"
    assert result.epistemic_trace["provenance"]["epistemicos_status"] == "success"

    # CXUs should be the live ones returned by the mock
    cxu_ids = [c["id"] for c in result.epistemic_trace["cxus"]]
    assert "CXU_LIVE_1" in cxu_ids

    # Feedback post should have been called
    mock_epistemicos_client.post_formulation_result.assert_called_once()


# ---------------------------------------------------------------------------
# 2. epistemicos unavailable → graceful synthetic fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chronothera_service_epistemicos_unavailable(
    tmp_path: Path,
    base_payload: dict,
) -> None:
    failing_client = AsyncMock(spec=EpistemicOSClient)
    failing_client.get_zone.side_effect = EpistemicOSClientError("HTTP 500")
    failing_client.post_formulation_result.side_effect = EpistemicOSClientError("HTTP 500")
    failing_client.search_precedent.side_effect = EpistemicOSClientError("HTTP 500")

    service = ChronoTheraService(
        persistence_path=tmp_path / "simulations.json",
        epistemicos_client=failing_client,
    )

    result = await service.run_simulation(ChronoTheraSimulationRequest(**base_payload))

    # Should degrade gracefully
    assert result.epistemicos_query_status == "fallback"
    assert result.epistemic_trace["provenance"]["epistemicos_status"] == "fallback"

    # Synthetic CXUs still present
    assert len(result.epistemic_trace["cxus"]) == 7

    # Simulation should still complete with a valid score
    assert 0 < result.overall_chronothera_score <= 100


# ---------------------------------------------------------------------------
# 3. PK precedent lookup from epistemicos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pk_precedent_lookup(mock_epistemicos_client: AsyncMock) -> None:
    mock_epistemicos_client.search_precedent.return_value = [
        {
            "api_name": "Insulin Glargine",
            "formulation_objective": "depot_formulation",
            "route": "SC",
            "modality": "biologic",
            "excipients": ["PLGA"],
            "release_duration_weeks": 4,
            "pk_parameters": {"CL": 0.5, "V": 40.0, "Tmax": 4.0, "F": 0.9, "ka": 0.3},
            "outcome": "success",
            "source": "epistemicos",
            "confidence": 0.92,
        }
    ]

    adapter = PKPrecedentAdapter(epistemicos_client=mock_epistemicos_client)
    params = await adapter.lookup_pk_parameters(
        "Insulin Glargine", "depot_formulation", "SC"
    )

    assert params["CL"] == pytest.approx(0.5)
    assert params["Tmax"] == pytest.approx(4.0)
    assert params["F"] == pytest.approx(0.9)
    mock_epistemicos_client.search_precedent.assert_called_once()


# ---------------------------------------------------------------------------
# 4. PK precedent fallback to heuristic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pk_precedent_fallback_to_heuristic(
    mock_epistemicos_client: AsyncMock,
) -> None:
    # Return records with no pk_parameters so they are filtered out
    mock_epistemicos_client.search_precedent.return_value = [
        {
            "api_name": "X",
            "formulation_objective": "sustained_release",
            "route": "SC",
            "modality": "small molecule",
            "pk_parameters": {},  # empty → excluded
            "confidence": 0.5,
        }
    ]

    adapter = PKPrecedentAdapter(epistemicos_client=mock_epistemicos_client)
    params = await adapter.lookup_pk_parameters("X", "sustained_release", "SC")

    # Should fall back to heuristic; sustained release → delayed Tmax
    assert params["Tmax"] == 6.0
    assert params["ka"] == 0.2


@pytest.mark.asyncio
async def test_pk_precedent_no_client() -> None:
    """When no client is configured, heuristic defaults are always used."""
    adapter = PKPrecedentAdapter(epistemicos_client=None)
    params = await adapter.lookup_pk_parameters("SomeAPI", "oral_delayed_release", "oral")
    assert params["Tmax"] == 4.0
    assert "CL" in params


# ---------------------------------------------------------------------------
# 5. EpistemicOS client error handling (timeout)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_epistemicos_client_error_handling() -> None:
    import httpx

    client = EpistemicOSClient(base_url="http://localhost:9999", timeout=0.001)

    # All methods should raise EpistemicOSClientError, not propagate httpx internals
    with pytest.raises(EpistemicOSClientError, match="[Tt]imeout|[Nn]etwork|[Cc]onnect"):
        await client.get_zone("zone-1")

    with pytest.raises(EpistemicOSClientError):
        await client.search_precedent("test query")

    with pytest.raises(EpistemicOSClientError):
        await client.post_formulation_result(
            "zone-1", "sim-1", overall_score=70, epistemicos_status="success"
        )


# ---------------------------------------------------------------------------
# 6. Guardian review risk stratification (Category A vs C)
# ---------------------------------------------------------------------------

def _make_scorecard(manufacturability: int, regulatory_fit: int, stability: int) -> Dict[str, Any]:
    class _Score:
        def __init__(self, s: int):
            self.score = s

    return {
        "manufacturability": _Score(manufacturability),
        "regulatory_fit": _Score(regulatory_fit),
        "stability": _Score(stability),
    }


def test_guardian_review_risk_stratified_category_a() -> None:
    """Category A: higher thresholds → triggers sooner."""
    # Score 68 → below Cat A threshold (70) but above Cat C (50)
    sc = _make_scorecard(manufacturability=70, regulatory_fit=70, stability=70)
    reasons_a = get_trigger_reasons(
        category="Category A — Near-Term Revenue",
        overall_score=68,
        release_duration_weeks=10,
        scorecard=sc,
    )
    reasons_c = get_trigger_reasons(
        category="Category C — Novel Discovery",
        overall_score=68,
        release_duration_weeks=10,
        scorecard=sc,
    )
    assert any("overall" in r.lower() or "threshold" in r.lower() for r in reasons_a), (
        f"Cat A should trigger on score 68; reasons={reasons_a}"
    )
    assert not reasons_c, f"Cat C should not trigger on score 68; reasons={reasons_c}"


def test_guardian_review_risk_stratified_category_c() -> None:
    """Category C: lower thresholds → only triggers on very low scores."""
    sc = _make_scorecard(manufacturability=50, regulatory_fit=50, stability=50)
    reasons = get_trigger_reasons(
        category="Category C — Novel Discovery Programs",
        overall_score=55,
        release_duration_weeks=18,
        scorecard=sc,
    )
    # Score 55 > Cat C threshold (50) and duration 18 ≤ 24 → no trigger
    assert not reasons, f"Cat C should not trigger; reasons={reasons}"


def test_guardian_review_rapid_response_always_triggers() -> None:
    """Rapid Response category always escalates."""
    sc = _make_scorecard(manufacturability=80, regulatory_fit=80, stability=80)
    reasons = get_trigger_reasons(
        category="Forge Rapid Response Programs",
        overall_score=90,
        release_duration_weeks=8,
        scorecard=sc,
        is_rapid_response=True,
    )
    assert any("Rapid Response" in r for r in reasons)


@pytest.mark.asyncio
async def test_guardian_review_risk_tier_in_simulation(
    service_no_epistemicos: ChronoTheraService, base_payload: dict
) -> None:
    """Guardian review result should include risk_tier field."""
    result = await service_no_epistemicos.run_simulation(
        ChronoTheraSimulationRequest(**base_payload)
    )
    assert result.guardian_review.risk_tier is not None


# ---------------------------------------------------------------------------
# 7. Bayesian calibrator fit and predict
# ---------------------------------------------------------------------------

def _make_sample_dataset(n: int = 10) -> CalibrationDataset:
    outcomes = []
    for i in range(n):
        outcomes.append(
            FormulationOutcome(
                id=f"fo-{i}",
                formulation_objective="depot_formulation",
                route="SC",
                release_duration_weeks=4,
                apis=["API-X"],
                excipients=["PLGA"],
                predicted_score=float(60 + i * 2),
                actual_outcome="success" if i % 3 != 0 else "failure",
            )
        )
    return CalibrationDataset(formulations=outcomes)


def test_calibrator_fit_and_predict(tmp_path: Path) -> None:
    calibrator = FormulationScorecardCalibrator(
        data_path=tmp_path / "nonexistent.json"
    )
    dataset = _make_sample_dataset(15)

    # Write sample data to disk so fit() can load it
    data_path = tmp_path / "formulations.json"
    data_path.write_text(dataset.model_dump_json())
    calibrator.data_path = data_path

    result = calibrator.fit()

    assert result["n_samples"] == 15
    # Either fitted or skipped gracefully
    assert result["n_samples"] >= 0

    # Predict CI for a new formulation
    fo = FormulationOutcome(
        id="new",
        formulation_objective="depot_formulation",
        route="SC",
        release_duration_weeks=4,
        apis=["API-X"],
        excipients=["PLGA"],
        predicted_score=70.0,
        actual_outcome="success",
    )
    lower, mean, upper = calibrator.predict_confidence_interval(fo, 70.0)
    assert lower <= mean <= upper


# ---------------------------------------------------------------------------
# 8. Confidence interval bounds invariant
# ---------------------------------------------------------------------------

def test_confidence_interval_bounds() -> None:
    """ConfidenceInterval must always satisfy lower ≤ mean ≤ upper."""
    ci = ConfidenceInterval(lower=60.0, mean=70.0, upper=80.0)
    assert ci.lower <= ci.mean <= ci.upper
    assert ci.uncertainty == pytest.approx(10.0)


def test_confidence_interval_invalid() -> None:
    """Creating an out-of-order CI should raise a validation error."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ConfidenceInterval(lower=80.0, mean=70.0, upper=90.0)


@pytest.mark.asyncio
async def test_simulation_scorecard_has_confidence_intervals(
    service_no_epistemicos: ChronoTheraService, base_payload: dict
) -> None:
    """All scorecard entries should carry a confidence interval."""
    result = await service_no_epistemicos.run_simulation(
        ChronoTheraSimulationRequest(**base_payload)
    )
    for key, explanation in result.scorecard.items():
        assert explanation.confidence is not None, f"Missing CI for scorecard key '{key}'"
        ci = explanation.confidence
        assert ci.lower <= ci.mean <= ci.upper, (
            f"CI order violated for '{key}': {ci.lower} / {ci.mean} / {ci.upper}"
        )


@pytest.mark.asyncio
async def test_simulation_overall_confidence_present(
    service_no_epistemicos: ChronoTheraService, base_payload: dict
) -> None:
    """Simulation result should include an overall_confidence CI."""
    result = await service_no_epistemicos.run_simulation(
        ChronoTheraSimulationRequest(**base_payload)
    )
    assert result.overall_confidence is not None
    ci = result.overall_confidence
    assert ci.lower <= ci.mean <= ci.upper


@pytest.mark.asyncio
async def test_release_profile_pk_precedent_flag(
    service_no_epistemicos: ChronoTheraService, base_payload: dict
) -> None:
    """Without epistemicos, pk_precedent_used should be False."""
    result = await service_no_epistemicos.run_simulation(
        ChronoTheraSimulationRequest(**base_payload)
    )
    for dataset in result.release_profile.datasets:
        assert dataset.pk_precedent_used is False


@pytest.mark.asyncio
async def test_backward_compat_no_epistemicos(
    service_no_epistemicos: ChronoTheraService, base_payload: dict
) -> None:
    """Existing API contract is preserved when epistemicos is absent."""
    result = await service_no_epistemicos.run_simulation(
        ChronoTheraSimulationRequest(**base_payload)
    )
    serialized = result.model_dump(mode="json")

    # Core fields still present
    assert "id" in serialized
    assert "overall_chronothera_score" in serialized
    assert "epistemic_trace" in serialized
    assert "guardian_review" in serialized
    assert "release_profile" in serialized
    assert "scorecard" in serialized

    # New fields present with sensible defaults
    assert serialized["epistemicos_query_status"] == "unavailable"
    assert serialized["overall_confidence"] is not None
