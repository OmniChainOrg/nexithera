# tests/test_active_learning.py
"""Tests for PR #9 — Active Learning + Evidence Gap Analysis."""
from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.active_learning_agent import (
    EXPERIMENT_TEMPLATES,
    ActiveLearningAgent,
    binary_entropy,
    expected_posterior_entropy,
    information_gain,
)
from app.agents.gap_analysis_agent import GapAnalysisAgent


# ---------------------------------------------------------------------------
# Helpers (mirror PR #8 test_pipeline_automation pattern)
# ---------------------------------------------------------------------------
def _build_db_mock(
    target,
    *,
    fetchrow_side_effect=None,
    fetchval_side_effect=None,
    fetch_side_effect=None,
):
    mock_conn = AsyncMock()
    if fetchrow_side_effect is not None:
        mock_conn.fetchrow.side_effect = fetchrow_side_effect
    if fetchval_side_effect is not None:
        mock_conn.fetchval.side_effect = fetchval_side_effect
    if fetch_side_effect is not None:
        mock_conn.fetch.side_effect = fetch_side_effect

    mock_pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=acquire_cm)

    target.get_pool = AsyncMock(return_value=mock_pool)
    return mock_conn


# ---------------------------------------------------------------------------
# Entropy / information-gain math
# ---------------------------------------------------------------------------
def test_binary_entropy_endpoints_and_peak():
    # Known boundary values.
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(1.0) == 0.0
    # Peak at 0.5 → 1 bit.
    assert binary_entropy(0.5) == pytest.approx(1.0)
    # None → maximum uncertainty.
    assert binary_entropy(None) == 1.0
    # Symmetry.
    assert binary_entropy(0.2) == pytest.approx(binary_entropy(0.8))
    # Out-of-range inputs are clamped, never raise.
    assert binary_entropy(-0.5) == 0.0
    assert binary_entropy(2.0) == 0.0


def test_expected_posterior_entropy_weighted_average():
    # If both branches collapse to certainty, expected entropy is 0.
    assert (
        expected_posterior_entropy(0.5, 1.0, 0.0) == pytest.approx(0.0)
    )
    # If both branches stay at 0.5, expected entropy is 1 bit.
    assert (
        expected_posterior_entropy(0.5, 0.5, 0.5) == pytest.approx(1.0)
    )


def test_information_gain_is_non_negative_and_bounded():
    gain = information_gain(
        prior=0.5,
        posterior_if_positive=0.9,
        posterior_if_negative=0.1,
    )
    # Symmetric collapse from H(0.5)=1 to ~H(0.9)≈0.469
    assert 0.5 < gain <= 1.0
    # No-info experiment (posterior = prior on both branches) → gain ≈ 0.
    null_gain = information_gain(
        prior=0.5, posterior_if_positive=0.5, posterior_if_negative=0.5
    )
    assert null_gain == pytest.approx(0.0, abs=1e-9)
    # Negative drift is clamped.
    assert (
        information_gain(prior=0.9, posterior_if_positive=0.5, posterior_if_negative=0.5)
        >= 0.0
    )


def test_information_gain_uses_prior_when_p_positive_omitted():
    # When p_positive is omitted, it defaults to the prior. A perfectly
    # informative experiment about a near-certain belief still yields
    # near-zero gain (there is little uncertainty to remove).
    gain = information_gain(
        prior=0.95, posterior_if_positive=1.0, posterior_if_negative=0.0
    )
    assert gain < 0.5


# ---------------------------------------------------------------------------
# Gap Analysis Agent
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gap_analysis_flags_low_confidence_and_contradictions():
    agent = GapAnalysisAgent("agent_id")
    program_row = {"id": "prog_1", "therapeutic_area": "NSCLC"}
    hypotheses = [
        {
            "id": "hyp_1",
            "hypothesis_text": "GPR75 is required in NSCLC growth",
            "claim_type": "target_disease_association",
            "confidence": 0.4,
            "status": "draft",
        }
    ]
    impact_rows = [
        {
            "hypothesis_id": "hyp_1",
            "source_id": "ent_a",
            "target_id": "ent_b",
        }
    ]
    low_conf_rows = [
        {
            "id": "edge_low",
            "source_id": "ent_a",
            "target_id": "ent_b",
            "predicate": "associated_with",
            "confidence": 0.25,
            "is_contradiction": False,
            "source_name": "GPR75",
            "source_type": "gene",
            "target_name": "NSCLC",
            "target_type": "disease",
        }
    ]
    contradiction_rows = [
        {
            "id": "edge_contra",
            "source_id": "ent_a",
            "target_id": "ent_c",
            "predicate": "inhibits",
            "confidence": 0.6,
            "source_name": "GPR75",
            "source_type": "gene",
            "target_name": "Apoptosis",
        }
    ]

    with patch("app.agents.gap_analysis_agent.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[program_row],
            fetch_side_effect=[
                hypotheses,
                impact_rows,
                low_conf_rows,
                contradiction_rows,
            ],
            fetchval_side_effect=[0],  # hypothesis has no evidence yet → missing_edge
        )

        result = await agent.execute({"program_id": "prog_1"})

    gap_types = {g["gap_type"] for g in result["structure"]["gaps"]}
    assert "low_confidence" in gap_types
    assert "contradiction_unresolved" in gap_types
    assert "missing_edge" in gap_types
    # Severity bounded.
    for g in result["structure"]["gaps"]:
        assert 0.0 <= g["severity"] <= 1.0
    # Sorted by severity descending.
    severities = [g["severity"] for g in result["structure"]["gaps"]]
    assert severities == sorted(severities, reverse=True)


@pytest.mark.asyncio
async def test_gap_analysis_requires_program_id():
    agent = GapAnalysisAgent("agent_id")
    with pytest.raises(ValueError, match="program_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# Active Learning Agent
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_active_learning_ranks_by_information_gain():
    agent = ActiveLearningAgent("agent_id")
    program_row = {"id": "prog_1", "therapeutic_area": "NSCLC"}
    hypotheses = [
        {
            "id": "hyp_1",
            "hypothesis_text": "GPR75 drives NSCLC proliferation",
            "confidence": 0.5,
        }
    ]

    with patch("app.agents.active_learning_agent.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[program_row],
            fetch_side_effect=[hypotheses],
        )

        result = await agent.execute(
            {
                "program_id": "prog_1",
                "max_experiments": 3,
                "include_cost": False,
            }
        )

    experiments = result["structure"]["experiments"]
    assert experiments
    # Top experiment must have highest info gain.
    gains = [e["information_gain"] for e in experiments]
    assert gains == sorted(gains, reverse=True)
    assert experiments[0]["priority"] == 1
    # Every emitted experiment maps to a registered template id.
    template_ids = {t["id"] for t in EXPERIMENT_TEMPLATES}
    for exp in experiments:
        assert exp["template_id"] in template_ids


@pytest.mark.asyncio
async def test_active_learning_cost_weighted_ranking_prefers_cheaper_experiments():
    agent = ActiveLearningAgent("agent_id")
    program_row = {"id": "prog_1", "therapeutic_area": "NSCLC"}
    hypotheses = [
        {
            "id": "hyp_1",
            "hypothesis_text": "X drives Y",
            "confidence": 0.5,
        }
    ]

    with patch("app.agents.active_learning_agent.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[program_row],
            fetch_side_effect=[hypotheses],
        )

        result = await agent.execute(
            {
                "program_id": "prog_1",
                "max_experiments": 5,
                "include_cost": True,
            }
        )

    experiments = result["structure"]["experiments"]
    # Verify ordering by value_per_unit_cost.
    vpcs = [e["value_per_unit_cost"] for e in experiments]
    assert vpcs == sorted(vpcs, reverse=True)
    # The expensive in-vivo PDX template (cost=8) should *not* be the
    # top recommendation when a cheap literature mining (cost=1) achieves
    # comparable info gain.
    assert experiments[0]["template_id"] != "in_vivo_pdx_v1"


@pytest.mark.asyncio
async def test_active_learning_requires_program_id():
    agent = ActiveLearningAgent("agent_id")
    with pytest.raises(ValueError, match="program_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# Active Learning Service: outcome → confidence update
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_record_outcome_updates_hypothesis_confidence_and_resolves_gap():
    from app.services.active_learning_service import active_learning_service

    experiment_row = {
        "id": "exp_1",
        "program_id": "prog_1",
        "hypothesis_id": "hyp_1",
        "candidate_id": None,
        "gap_id": "gap_1",
        "template_id": "lit_mining_v1",
    }
    hypothesis_row = {"confidence": 0.45}
    candidate_link_rows: list = []  # no candidates linked → no pipeline calls

    with patch(
        "app.services.active_learning_service.db"
    ) as mock_db, patch(
        "app.services.active_learning_service.pipeline_service"
    ) as mock_pipeline:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[experiment_row, hypothesis_row],
            fetch_side_effect=[candidate_link_rows],
        )

        result = await active_learning_service.record_outcome(
            experiment_id="exp_1",
            result_summary="Knockout reduced proliferation by 60%",
            result_data={"ic50": 0.5},
            updated_confidence=0.82,
        )

    assert result["prior_confidence"] == 0.45
    assert result["updated_confidence"] == 0.82
    # Realised information gain is the entropy reduction H(0.45) − H(0.82).
    expected = max(
        0.0,
        binary_entropy(0.45) - binary_entropy(0.82),
    )
    assert result["information_gain_observed"] == pytest.approx(
        round(expected, 4), abs=1e-4
    )
    # Hypothesis confidence update + gap resolution + status update SQL.
    sql_calls = [str(c.args[0]) for c in mock_conn.execute.await_args_list]
    assert any("INSERT INTO experiment_outcomes" in s for s in sql_calls)
    assert any(
        "UPDATE proposed_experiments SET status = 'completed'" in s
        for s in sql_calls
    )
    assert any("UPDATE hypotheses SET confidence" in s for s in sql_calls)
    assert any(
        "UPDATE evidence_gaps" in s and "resolved = TRUE" in s
        for s in sql_calls
    )
    # No candidate links → no pipeline calls.
    mock_pipeline.auto_advance.assert_not_called()


@pytest.mark.asyncio
async def test_record_outcome_triggers_pipeline_reevaluation_for_linked_candidates():
    from app.services.active_learning_service import active_learning_service

    experiment_row = {
        "id": "exp_1",
        "program_id": "prog_1",
        "hypothesis_id": "hyp_1",
        "candidate_id": None,
        "gap_id": None,
        "template_id": "lit_mining_v1",
    }
    hypothesis_row = {"confidence": 0.6}
    candidate_link_rows = [{"candidate_id": "cand_a"}, {"candidate_id": "cand_b"}]

    auto_advance_mock = AsyncMock(
        return_value={"moved": False, "to_status": "candidate"}
    )
    with patch(
        "app.services.active_learning_service.db"
    ) as mock_db, patch(
        "app.services.active_learning_service.pipeline_service"
    ) as mock_pipeline:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[experiment_row, hypothesis_row],
            fetch_side_effect=[candidate_link_rows],
        )
        mock_pipeline.auto_advance = auto_advance_mock

        result = await active_learning_service.record_outcome(
            experiment_id="exp_1",
            result_summary="Confirmed",
            result_data={},
            updated_confidence=0.85,
        )

    assert auto_advance_mock.await_count == 2
    assert len(result["pipeline_updates"]) == 2


@pytest.mark.asyncio
async def test_record_outcome_raises_for_unknown_experiment():
    from app.services.active_learning_service import active_learning_service

    with patch("app.services.active_learning_service.db") as mock_db:
        _build_db_mock(mock_db, fetchrow_side_effect=[None])
        with pytest.raises(ValueError, match="Proposed experiment not found"):
            await active_learning_service.record_outcome(
                experiment_id="missing",
                result_summary="x",
                result_data={},
                updated_confidence=0.5,
            )


# ---------------------------------------------------------------------------
# Acceptance: no hallucinated experiments slip through propose_next_experiments
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_propose_next_experiments_rejects_unknown_template():
    from app.services import active_learning_service as als_module

    fake_run_result = {
        "run_id": "run_1",
        "output": {
            "summary": "x",
            "structure": {
                "experiments": [
                    {
                        "template_id": "totally_made_up",
                        "experiment_type": "in_vitro_assay",
                        "description": "free-form",
                        "expected_outcomes": {},
                        "information_gain": 0.5,
                        "cost_estimate": 1,
                        "duration_days": 1,
                        "value_per_unit_cost": 0.5,
                        "priority": 1,
                    }
                ],
            },
        },
    }

    with patch.object(
        als_module, "_ensure_agent_record", new=AsyncMock(return_value="aid")
    ), patch.object(
        als_module.ActiveLearningAgent,
        "run",
        new=AsyncMock(return_value=fake_run_result),
    ), patch.object(
        als_module.ActiveLearningService,
        "list_open_gaps",
        new=AsyncMock(return_value=[]),
    ):
        with pytest.raises(ValueError, match="unknown template"):
            await als_module.active_learning_service.propose_next_experiments(
                program_id="prog_1"
            )
