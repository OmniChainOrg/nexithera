# tests/test_clinical_forecaster.py
"""Tests for PR #11 — Clinical Forecaster (Oracle)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.biology_evidence_agent import (
    BiologyEvidenceAgent,
    _normalize_score,
)
from app.agents.clinical_competitive_landscape_agent import (
    ClinicalCompetitiveLandscapeAgent,
    competition_score,
)
from app.agents.forecast_synthesizer_agent import (
    DEFAULT_WEIGHTS,
    FACTOR_NAMES,
    ForecastSynthesizerAgent,
    bayesian_update_weights,
    combine_probability,
    decompose_contributions,
    normalize_weights,
    scenario_explorer,
    tornado_sensitivity,
)
from app.agents.historical_precedent_agent import (
    HistoricalPrecedentAgent,
    aggregate_precedent_prior,
    wilson_interval,
)
from app.agents.safety_toxicity_agent import (
    SafetyToxicityAgent,
    _apply_flags,
    _scorecard_to_safety,
)
from app.agents.trial_design_agent import (
    TrialDesignAgent,
    design_score,
)


# ---------------------------------------------------------------------------
# Shared DB mock helper (same pattern as PR #9 / #10).
# ---------------------------------------------------------------------------
def _build_db_mock(
    target,
    *,
    fetchrow_side_effect=None,
    fetchval_side_effect=None,
    fetch_side_effect=None,
    execute_side_effect=None,
):
    mock_conn = AsyncMock()
    if fetchrow_side_effect is not None:
        mock_conn.fetchrow.side_effect = fetchrow_side_effect
    if fetchval_side_effect is not None:
        mock_conn.fetchval.side_effect = fetchval_side_effect
    if fetch_side_effect is not None:
        mock_conn.fetch.side_effect = fetch_side_effect
    if execute_side_effect is not None:
        mock_conn.execute.side_effect = execute_side_effect

    mock_pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=acquire_cm)

    target.get_pool = AsyncMock(return_value=mock_pool)
    return mock_conn


# ---------------------------------------------------------------------------
# Synthesizer core: weights, decomposition, combination, sensitivity
# ---------------------------------------------------------------------------
def test_default_weights_sum_to_one():
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)


def test_normalize_weights_rescales_and_filters():
    weights = {"biology": 2.0, "safety": 1.0, "design": 1.0,
               "competition": 0.0, "precedent": 0.0, "junk": 99.0}
    norm = normalize_weights(weights)
    assert "junk" not in norm
    assert sum(norm.values()) == pytest.approx(1.0, abs=1e-3)
    # Biology should still be the largest after normalization.
    assert max(norm, key=norm.get) == "biology"


def test_combine_probability_matches_weighted_sum():
    factors = {"biology": 0.8, "safety": 0.7, "design": 0.6,
               "competition": 0.5, "precedent": 0.4}
    p = combine_probability(factors, DEFAULT_WEIGHTS)
    expected = (
        0.30 * 0.8 + 0.20 * 0.7 + 0.15 * 0.6
        + 0.10 * 0.5 + 0.25 * 0.4
    )
    assert p == pytest.approx(round(expected, 4), abs=1e-3)


def test_combine_probability_clamps_inputs_to_unit_interval():
    out_of_range = {k: 2.0 for k in FACTOR_NAMES}
    assert combine_probability(out_of_range, DEFAULT_WEIGHTS) == 1.0
    neg = {k: -1.0 for k in FACTOR_NAMES}
    assert combine_probability(neg, DEFAULT_WEIGHTS) == 0.0


def test_decomposition_sums_to_probability():
    factors = {"biology": 0.7, "safety": 0.6, "design": 0.5,
               "competition": 0.4, "precedent": 0.5}
    decomp = decompose_contributions(factors, DEFAULT_WEIGHTS)
    p = combine_probability(factors, DEFAULT_WEIGHTS)
    assert sum(decomp.values()) == pytest.approx(p, abs=1e-3)


def test_sensitivity_changing_biology_by_10pct_changes_probability_proportionally():
    """Acceptance: changing biology_score by 10% changes probability
    proportionally to its weight."""
    factors = {"biology": 0.5, "safety": 0.5, "design": 0.5,
               "competition": 0.5, "precedent": 0.5}
    base = combine_probability(factors, DEFAULT_WEIGHTS)

    bumped = dict(factors, biology=0.6)
    new = combine_probability(bumped, DEFAULT_WEIGHTS)
    delta = new - base
    # Expected delta = weight_biology * 0.1
    assert delta == pytest.approx(
        DEFAULT_WEIGHTS["biology"] * 0.1, abs=1e-3
    )


def test_tornado_returns_factor_ordered_by_swing():
    factors = {"biology": 0.5, "safety": 0.5, "design": 0.5,
               "competition": 0.5, "precedent": 0.5}
    sens = tornado_sensitivity(factors, DEFAULT_WEIGHTS, delta=0.1)
    rows = sens["tornado_data"]
    swings = [r["swing"] for r in rows]
    assert swings == sorted(swings, reverse=True)
    # Highest-weighted factor should top the tornado.
    top_factor = max(DEFAULT_WEIGHTS, key=DEFAULT_WEIGHTS.get)
    assert rows[0]["factor"] == top_factor
    assert sens["most_influential_factor"] == f"{top_factor}_score"


def test_scenario_explorer_returns_optimistic_pessimistic_and_custom():
    factors = {"biology": 0.5, "safety": 0.5, "design": 0.5,
               "competition": 0.5, "precedent": 0.5}
    scenarios = scenario_explorer(
        factors, DEFAULT_WEIGHTS,
        overrides=[
            {"name": "enrich_population",
             "factors": {"design": 0.9, "precedent": 0.7}},
        ],
    )
    assert "optimistic" in scenarios and "pessimistic" in scenarios
    assert scenarios["optimistic"] > scenarios["pessimistic"]
    assert "enrich_population" in scenarios
    # What-if: enriching population should not equal the base.
    base = combine_probability(factors, DEFAULT_WEIGHTS)
    assert scenarios["enrich_population"] != base


# ---------------------------------------------------------------------------
# Bayesian weight calibration
# ---------------------------------------------------------------------------
def test_bayesian_update_pushes_weight_toward_accurate_factor():
    """Acceptance: weight calibration moves weight toward the factor that
    best predicted the observed outcome."""
    initial = dict(DEFAULT_WEIGHTS)
    # Trial succeeded; biology assigned high prob to success, others 0.5.
    likelihoods = {
        "biology": 0.9, "safety": 0.5, "design": 0.5,
        "competition": 0.5, "precedent": 0.5,
    }
    updated = bayesian_update_weights(initial, True, likelihoods,
                                      learning_rate=0.1)
    # Biology weight should go up; others should slightly drop after
    # renormalization since biology grew.
    assert updated["biology"] > initial["biology"]
    assert sum(updated.values()) == pytest.approx(1.0, abs=1e-3)


def test_bayesian_update_does_not_collapse_weights_in_one_step():
    initial = dict(DEFAULT_WEIGHTS)
    likelihoods = {k: 0.99 for k in FACTOR_NAMES}
    updated = bayesian_update_weights(initial, True, likelihoods,
                                      learning_rate=0.1)
    # No single weight should leap by more than ~10% of its prior.
    for k in FACTOR_NAMES:
        assert abs(updated[k] - initial[k]) <= 0.2


# ---------------------------------------------------------------------------
# Historical precedent agent: aggregator + Wilson interval
# ---------------------------------------------------------------------------
def test_wilson_interval_bounds_within_unit_interval():
    lo, hi = wilson_interval(5, 10)
    assert 0.0 <= lo <= 0.5 <= hi <= 1.0


def test_wilson_interval_handles_zero_total():
    lo, hi = wilson_interval(0, 0)
    assert (lo, hi) == (0.0, 1.0)


def test_aggregate_precedent_prior_prefers_high_similarity_matches():
    precedents = [
        {"target_label": "KRAS", "disease_label": "NSCLC",
         "modality": "small_molecule", "phase": "II",
         "met_primary_endpoint": True, "weight": 1.0, "trial_id": "A"},
        {"target_label": "KRAS", "disease_label": "NSCLC",
         "modality": "small_molecule", "phase": "II",
         "met_primary_endpoint": True, "weight": 1.0, "trial_id": "B"},
        {"target_label": "EGFR", "disease_label": "Glioblastoma",
         "modality": "biologic", "phase": "III",
         "met_primary_endpoint": False, "weight": 1.0, "trial_id": "C"},
    ]
    agg = aggregate_precedent_prior(
        precedents,
        target="KRAS", disease="NSCLC",
        modality="small_molecule", phase="II",
    )
    # Both high-similarity matches succeeded so prior should be close to 1.
    assert agg["precedent_prior"] >= 0.9
    assert agg["top_precedents"][0]["trial_id"] in {"A", "B"}
    assert agg["effective_n"] > 0


def test_aggregate_precedent_prior_no_matches_returns_default_prior():
    agg = aggregate_precedent_prior(
        [], target="KRAS", disease="NSCLC",
        modality="small_molecule", phase="II",
    )
    assert agg["precedent_prior"] == 0.5
    assert agg["top_precedents"] == []


@pytest.mark.asyncio
async def test_historical_precedent_agent_uses_in_memory_precedents():
    agent = HistoricalPrecedentAgent("agent_id")
    precedents = [
        {"target_label": "KRAS", "disease_label": "NSCLC",
         "modality": "small_molecule", "phase": "II",
         "met_primary_endpoint": True, "weight": 1.0,
         "trial_id": "NCT01"},
    ]
    result = await agent.execute(
        {
            "candidate_id": "cand_1",
            "target_label": "KRAS", "disease_label": "NSCLC",
            "modality": "small_molecule", "phase": "II",
            "precedents": precedents,
        }
    )
    s = result["structure"]
    assert s["precedent_prior"] == pytest.approx(1.0, abs=0.01)
    assert len(s["top_precedents"]) == 1
    assert s["top_precedents"][0]["trial_id"] == "NCT01"


@pytest.mark.asyncio
async def test_historical_precedent_agent_requires_candidate_id():
    agent = HistoricalPrecedentAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# Biology evidence agent
# ---------------------------------------------------------------------------
def test_normalize_score_smooths_extremes():
    # 0/0 -> 0.5 prior.
    assert _normalize_score(0, 0) == 0.5
    # 10/0 should be high but not 1.0 due to Laplace smoothing.
    assert 0.85 < _normalize_score(10, 0) < 1.0


@pytest.mark.asyncio
async def test_biology_evidence_agent_uses_edge_counts():
    agent = BiologyEvidenceAgent("agent_id")
    candidate_row = {"target_id": "tid_1"}
    edges = [
        {"relation_type": "supports", "confidence": 0.8},
        {"relation_type": "supports", "confidence": 0.7},
        {"relation_type": "contradicts", "confidence": 0.6},
        {"relation_type": "associated_with", "confidence": 0.5},
    ]
    target_row = {"name": "KRAS"}
    with patch("app.agents.biology_evidence_agent.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[candidate_row, target_row],
            fetch_side_effect=[edges],
        )
        result = await agent.execute({"candidate_id": "cand_1"})
    s = result["structure"]
    assert s["supporting_edges"] == 3  # supports + supports + associated_with
    assert s["contradicting_edges"] == 1
    assert 0.0 <= s["biology_score"] <= 1.0
    assert s["target_label"] == "KRAS"


@pytest.mark.asyncio
async def test_biology_evidence_agent_requires_candidate_id():
    agent = BiologyEvidenceAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# Safety toxicity agent
# ---------------------------------------------------------------------------
def test_scorecard_to_safety_handles_none_and_clamps():
    assert _scorecard_to_safety(None) == 0.6
    assert _scorecard_to_safety(15) == 1.0
    assert _scorecard_to_safety(-5) == 0.0
    assert _scorecard_to_safety(7.0) == 0.7


def test_apply_flags_subtracts_penalties_and_clamps():
    base = 0.8
    out = _apply_flags(base, ["herg_liability", "genotoxicity"])
    assert out < base
    # Many flags should clamp at zero.
    assert _apply_flags(0.3, ["herg_liability"] * 20) == 0.0


@pytest.mark.asyncio
async def test_safety_agent_uses_inline_scorecard_and_flags_without_db():
    agent = SafetyToxicityAgent("agent_id")
    result = await agent.execute(
        {
            "candidate_id": "cand_1",
            "safety_scorecard": 8.0,
            "known_safety_flags": ["herg_liability"],
        }
    )
    s = result["structure"]
    assert s["base_score"] == 0.8
    assert s["safety_score"] == pytest.approx(0.65, abs=0.01)
    assert s["flags"] == ["herg_liability"]


@pytest.mark.asyncio
async def test_safety_agent_requires_candidate_id():
    agent = SafetyToxicityAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# Trial design agent
# ---------------------------------------------------------------------------
def test_design_score_penalises_underpowered_trial():
    good = design_score(
        "II", enrollment=120, duration_months=18,
        statistical_power=0.8, alpha=0.05,
        primary_endpoint="Overall Response Rate",
    )
    bad = design_score(
        "II", enrollment=10, duration_months=3,
        statistical_power=0.4, alpha=0.20,
        primary_endpoint="biomarker",
    )
    assert good["design_score"] > bad["design_score"]
    assert good["design_score"] <= 1.0
    assert bad["design_score"] >= 0.0


@pytest.mark.asyncio
async def test_trial_design_agent_emits_score_and_risks():
    agent = TrialDesignAgent("agent_id")
    result = await agent.execute(
        {
            "candidate_id": "cand_1",
            "phase": "II",
            "primary_endpoint": "Overall Response Rate",
            "trial_design": {
                "enrollment": 30, "duration_months": 6,
                "statistical_power": 0.6, "alpha": 0.1,
            },
        }
    )
    s = result["structure"]
    assert 0.0 <= s["design_score"] <= 1.0
    assert s["risks"], "should flag underpowered / short trial"


@pytest.mark.asyncio
async def test_trial_design_agent_requires_candidate_id():
    agent = TrialDesignAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# Clinical competitive landscape
# ---------------------------------------------------------------------------
def test_competition_score_drops_with_late_stage_competitors():
    none = competition_score([])
    one = competition_score([{"phase": "Approved"}])
    many = competition_score(
        [{"phase": "Approved"}, {"phase": "Phase 3"},
         {"phase": "Phase 3"}, {"phase": "Approved"}]
    )
    assert none > one > many
    assert many < 0.2
    # 5+ approved competitors should saturate to zero.
    saturated = competition_score([{"phase": "Approved"}] * 5)
    assert saturated == 0.0


@pytest.mark.asyncio
async def test_clinical_competitive_landscape_inline_competitors():
    agent = ClinicalCompetitiveLandscapeAgent("agent_id")
    result = await agent.execute(
        {
            "candidate_id": "cand_1",
            "competitors": [{"phase": "Phase 2"}, {"phase": "Phase 1"}],
        }
    )
    s = result["structure"]
    assert 0.0 <= s["competition_score"] <= 1.0
    assert s["competitor_count"] == 2


@pytest.mark.asyncio
async def test_clinical_competitive_landscape_requires_candidate_id():
    agent = ClinicalCompetitiveLandscapeAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# Forecast synthesizer agent: end-to-end (no DB run)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_synthesizer_returns_probability_decomposition_sensitivity_scenarios():
    agent = ForecastSynthesizerAgent("agent_id")
    factors = {"biology": 0.7, "safety": 0.6, "design": 0.7,
               "competition": 0.6, "precedent": 0.5}
    result = await agent.execute(
        {
            "candidate_id": "cand_1",
            "factors": factors,
            "weights": DEFAULT_WEIGHTS,
            "precedent_confidence_interval": [0.4, 0.7],
            "factor_confidences": {k: 0.6 for k in factors},
            "scenarios": [{"name": "what_if_larger_trial",
                           "factors": {"design": 0.9}}],
        }
    )
    s = result["structure"]
    assert 0.0 <= s["probability"] <= 1.0
    assert len(s["decomposition"]) == len(FACTOR_NAMES)
    # Decomposition contributions sum to probability.
    assert sum(s["decomposition"].values()) == pytest.approx(
        s["probability"], abs=1e-3
    )
    assert s["sensitivity"]["tornado_data"]
    assert "what_if_larger_trial" in s["scenarios"]
    assert s["confidence_interval"][0] <= s["probability"] <= s["confidence_interval"][1]


@pytest.mark.asyncio
async def test_synthesizer_requires_candidate_id():
    agent = ForecastSynthesizerAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({"factors": {}})


# ---------------------------------------------------------------------------
# Service: precedent insertion + weight calibration roundtrip
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_add_precedent_rejects_invalid_phase():
    from app.services.clinical_forecaster_service import (
        clinical_forecaster_service,
    )
    with pytest.raises(ValueError, match="phase must be"):
        await clinical_forecaster_service.add_precedent(
            target_label="X", disease_label="Y", modality="small_molecule",
            phase="IV", met_primary_endpoint=True,
        )


@pytest.mark.asyncio
async def test_load_save_weights_roundtrip_normalises():
    from app.services import clinical_forecaster_service as svc_mod
    svc = svc_mod.clinical_forecaster_service

    stored = []

    async def _fake_execute(query, *args):
        stored.append((query, args))

    # First load: empty -> fall back to DEFAULT_WEIGHTS.
    with patch.object(svc_mod, "db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db, fetch_side_effect=[[]],
            execute_side_effect=_fake_execute,
        )
        weights = await svc.load_weights()
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-3)

    # Save un-normalised weights -> service should normalise & persist them.
    with patch.object(svc_mod, "db") as mock_db:
        _build_db_mock(mock_db, execute_side_effect=_fake_execute)
        saved = await svc.save_weights(
            {"biology": 2.0, "safety": 1.0, "design": 1.0,
             "competition": 0.5, "precedent": 0.5}
        )
    assert sum(saved.values()) == pytest.approx(1.0, abs=1e-3)
    # Persisted one row per factor.
    assert sum(1 for q, _ in stored if "forecast_factors" in q) == 5


@pytest.mark.asyncio
async def test_calibrate_from_outcome_persists_updated_weights():
    from app.services import clinical_forecaster_service as svc_mod
    svc = svc_mod.clinical_forecaster_service

    persisted_weights = {}

    async def _fake_execute(query, *args):
        if "forecast_factors" in query and "INSERT" in query:
            persisted_weights[args[0]] = args[1]

    rows = [
        {"factor_name": name, "base_weight": w}
        for name, w in DEFAULT_WEIGHTS.items()
    ]
    with patch.object(svc_mod, "db") as mock_db:
        _build_db_mock(
            mock_db, fetch_side_effect=[rows],
            execute_side_effect=_fake_execute,
        )
        updated = await svc.calibrate_from_outcome(
            observed_outcome=True,
            factor_likelihoods={
                "biology": 0.9, "safety": 0.5, "design": 0.5,
                "competition": 0.5, "precedent": 0.5,
            },
        )
    assert sum(updated.values()) == pytest.approx(1.0, abs=1e-3)
    assert updated["biology"] > DEFAULT_WEIGHTS["biology"]
    # All factors persisted.
    assert set(persisted_weights.keys()) == set(FACTOR_NAMES)


# ---------------------------------------------------------------------------
# Acceptance: migration seeds 100+ precedents
# ---------------------------------------------------------------------------
def test_clinical_precedent_seed_has_100_plus_rows_across_phases():
    import importlib.util
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    migration_path = os.path.normpath(
        os.path.join(
            here, "..", "migrations", "versions",
            "011_clinical_forecaster.py",
        )
    )
    spec = importlib.util.spec_from_file_location(
        "_pr11_migration", migration_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    seed = module._PRECEDENT_SEED
    assert len(seed) >= 100, f"expected >=100 precedents, got {len(seed)}"
    phases = {row[3] for row in seed}
    assert phases >= {"I", "II", "III"}
    # Both positive and negative outcomes present (so the forecaster is
    # not trivially biased to 100% success).
    outcomes = {row[4] for row in seed}
    assert outcomes == {True, False}
    # Factor seeds cover the 5 canonical factors.
    factor_names = {row[0] for row in module._FACTOR_SEED}
    assert factor_names == set(FACTOR_NAMES)
