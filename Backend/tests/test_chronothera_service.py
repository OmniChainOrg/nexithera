"""Tests for the ChronoThera platform service and API router."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chronothera import router
from app.schemas.chronothera import ChronoTheraSimulationRequest, GuardianReviewRequest
from app.services.chronothera_service import ChronoTheraService, chronothera_service


@pytest.fixture()
def service(tmp_path: Path) -> ChronoTheraService:
    return ChronoTheraService(tmp_path / "simulations.json")


@pytest.fixture()
def payload() -> dict:
    return {
        "asset_id": "metformin-dapagliflozin-dr",
        "program_id": "program-category-a",
        "formulation_objective": "oral_delayed_release",
        "apis": [
            {"name": "Metformin", "dose_mg": 500, "modality": "small molecule"},
            {"name": "Dapagliflozin", "dose_mg": 10, "modality": "small molecule"},
        ],
        "excipients": [
            {"name": "HPMC", "percentage": 8, "function": "matrix"},
            {"name": "Eudragit", "percentage": 12, "function": "delayed release"},
        ],
        "release_duration_weeks": 8,
        "route_of_administration": "oral",
        "regulatory_body": "FDA",
        "strategy_mode": "cooperative",
        "optimize_excipient_percentages": True,
        "pkpd_objective": {
            "target_exposure": "smooth weekly planning exposure",
            "dosing_interval_days": 7,
            "peak_to_trough_priority": 3,
            "adherence_priority": 5,
        },
    }


@pytest.mark.asyncio
async def test_valid_chronothera_simulation(service: ChronoTheraService, payload: dict) -> None:
    result = await service.run_simulation(ChronoTheraSimulationRequest(**payload))

    assert result.asset_id == "metformin-dapagliflozin-dr"
    assert result.formulation_delivery_profile["asset_dossier_link"] == "category-a/metformin-dapagliflozin-dr"
    assert result.overall_chronothera_score > 0
    assert "research and planning only" in result.disclaimer


def test_invalid_input_handling(payload: dict) -> None:
    payload["apis"] = []

    with pytest.raises(ValueError, match="At least one API"):
        ChronoTheraSimulationRequest(**payload)


@pytest.mark.asyncio
async def test_deterministic_output(service: ChronoTheraService, payload: dict) -> None:
    request = ChronoTheraSimulationRequest(**payload)
    first = await service.run_simulation(request)
    second = await service.run_simulation(request)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


@pytest.mark.asyncio
async def test_release_profile_generation(service: ChronoTheraService, payload: dict) -> None:
    payload["release_duration_weeks"] = 12
    result = await service.run_simulation(ChronoTheraSimulationRequest(**payload))

    assert len(result.release_profile.labels) == 12
    assert all(len(dataset.cumulative_release) == 12 for dataset in result.release_profile.datasets)
    assert result.release_profile.datasets[0].model


@pytest.mark.asyncio
async def test_complete_scorecard_with_explanations(service: ChronoTheraService, payload: dict) -> None:
    result = await service.run_simulation(ChronoTheraSimulationRequest(**payload))

    required = {
        "sustained_release",
        "half_life_extension",
        "delivery_route_fit",
        "pkpd_alignment",
        "excipient_compatibility",
        "stability",
        "manufacturability",
        "patient_centricity",
        "regulatory_fit",
        "preclinical_package_contribution",
    }
    assert set(result.scorecard) == required
    for explanation in result.scorecard.values():
        assert explanation.score >= 0
        assert explanation.rationale
        assert explanation.assumptions
        assert explanation.uncertainty
        assert explanation.recommendation
        assert explanation.next_best_step


@pytest.mark.asyncio
async def test_epistemicos_trace_cxu_swarm_and_provenance(service: ChronoTheraService, payload: dict) -> None:
    result = await service.run_simulation(ChronoTheraSimulationRequest(**payload))
    trace = result.epistemic_trace

    assert trace["zone_cluster"] == "ChronoThera Formulation & Delivery Zone Cluster"
    assert "Regulatory Bridge Zone" in trace["zones"]
    assert len(trace["cxus"]) == 7
    assert trace["swarm"]["id"] == "CHRONOTHERA_FORMULATION_SWARM"
    assert trace["provenance"]["input_hash"]
    assert trace["provenance"]["assumptions"]
    assert trace["provenance"]["uncertainty_reasons"]


@pytest.mark.asyncio
async def test_guardian_review_triggers(service: ChronoTheraService, payload: dict) -> None:
    payload.update(
        {
            "asset_id": "mpox-pilot-program",
            "formulation_objective": "co_formulation",
            "route_of_administration": "IV",
            "release_duration_weeks": 20,
        }
    )
    result = await service.run_simulation(ChronoTheraSimulationRequest(**payload))

    assert result.guardian_review.required is True
    assert "Rapid Response Program" in result.guardian_review.reasons
    assert "IV route of administration" in result.guardian_review.reasons


@pytest.mark.asyncio
async def test_asset_linked_persistence_and_guardian_update(service: ChronoTheraService, payload: dict) -> None:
    result = await service.run_simulation(ChronoTheraSimulationRequest(**payload))
    simulations = await service.list_simulations(asset_id="metformin-dapagliflozin-dr")
    updated = await service.record_guardian_review(
        result.id,
        GuardianReviewRequest(decision="needs-revision", reviewer="Guardian", notes="Add bench compatibility data."),
    )

    assert simulations[0]["id"] == result.id
    assert updated is not None
    assert updated["guardian_review"]["status"] == "needs-revision"
    assert "bench compatibility" in updated["guardian_review"]["notes"]


def test_api_route_behavior(tmp_path: Path, payload: dict) -> None:
    chronothera_service.persistence_path = tmp_path / "api-simulations.json"
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)

    catalog = client.get("/api/v1/chronothera/catalog")
    created = client.post("/api/v1/chronothera/simulations", json=payload)
    simulation_id = created.json()["id"]
    fetched = client.get(f"/api/v1/chronothera/simulations/{simulation_id}")
    profile = client.get("/api/v1/chronothera/assets/metformin-dapagliflozin-dr/formulation-profile")

    assert catalog.status_code == 200
    assert created.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["id"] == simulation_id
    assert profile.status_code == 200
