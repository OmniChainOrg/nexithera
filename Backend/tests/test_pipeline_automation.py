# tests/test_pipeline_automation.py
"""Tests for PR #8 — Genovate Precog: pipeline automation,
target discovery, hypothesis versioning, bulk Guardian decisions."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.target_discovery_agent import TargetDiscoveryAgent
from app.services.candidate_service import candidate_service
from app.services.hypothesis_service import hypothesis_service
from app.services.guardian_service import guardian_service
from app.services.pipeline_service import pipeline_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_db_mock(
    target,
    *,
    fetchrow_side_effect=None,
    fetchval_side_effect=None,
    fetch_side_effect=None,
):
    """Wire up an async-aware mock for the ``db`` module variable on
    ``target``.  ``target`` may be the patched ``db`` mock returned by
    ``patch(...)``.

    Returns the connection mock so callers can assert call patterns.
    """
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
# Target Discovery Agent
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_target_discovery_agent_ranks_under_supported_targets():
    """The agent returns a ranked list of novel high-impact targets."""
    agent = TargetDiscoveryAgent("agent_id")

    program_row = {
        "id": "prog_1",
        "therapeutic_area": "Glioblastoma",
    }
    in_pipeline_rows = []  # nothing in pipeline yet
    disease_entity = {"id": "disease_1"}
    # Two candidate targetable entities in the graph.
    candidate_rows = [
        {
            "id": "ent_well_known",
            "name": "EGFR",
            "entity_type": "gene",
            "edge_count": 40,
        },
        {
            "id": "ent_novel",
            "name": "GPR75",
            "entity_type": "gene",
            "edge_count": 20,
        },
    ]
    # Direct disease-edge confidence: well-known target has strong (0.9)
    # evidence, novel target has none.
    edge_rows_well_known = [
        {"id": "edge_1", "predicate": "associated_with", "confidence": 0.9}
    ]
    edge_rows_novel = []

    with patch("app.agents.target_discovery_agent.db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[program_row, disease_entity],
            fetch_side_effect=[
                in_pipeline_rows,
                candidate_rows,
                edge_rows_well_known,
                edge_rows_novel,
            ],
        )

        result = await agent.execute(
            {"program_id": "prog_1", "top_k": 5}
        )

    structure = result["structure"]
    targets_by_name = {
        t["target_name"]: t for t in structure["ranked_targets"]
    }
    assert {"EGFR", "GPR75"}.issubset(targets_by_name)
    # The novel under-supported target must outrank the well-established one
    # because opportunity_score = potential_impact * novelty - evidence_strength.
    assert (
        targets_by_name["GPR75"]["score"]
        > targets_by_name["EGFR"]["score"]
    )
    assert targets_by_name["GPR75"]["proposed_hypothesis"]
    assert targets_by_name["GPR75"]["recommended_next_experiment"]
    # Confidence is in [0, 1]
    for t in structure["ranked_targets"]:
        assert 0.0 <= t["confidence"] <= 1.0
    assert mock_conn.fetchrow.await_count >= 2


@pytest.mark.asyncio
async def test_target_discovery_agent_excludes_pipeline_targets():
    """Targets already linked to a candidate are excluded from the ranking."""
    agent = TargetDiscoveryAgent("agent_id")

    with patch("app.agents.target_discovery_agent.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {"id": "prog_1", "therapeutic_area": "Glioblastoma"},
                None,  # no disease entity in graph
            ],
            fetch_side_effect=[
                [{"target_id": "ent_taken"}],  # already in pipeline
                [
                    {
                        "id": "ent_taken",
                        "name": "EGFR",
                        "entity_type": "gene",
                        "edge_count": 40,
                    },
                    {
                        "id": "ent_free",
                        "name": "GPR75",
                        "entity_type": "gene",
                        "edge_count": 25,
                    },
                ],
            ],
        )

        result = await agent.execute({"program_id": "prog_1"})

    names = [t["target_name"] for t in result["structure"]["ranked_targets"]]
    assert "EGFR" not in names
    assert "GPR75" in names


# ---------------------------------------------------------------------------
# Pipeline auto-advance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auto_advance_idea_to_evidence_map_when_hypothesis_linked():
    """Candidate at 'idea' with a linked hypothesis advances to 'evidence_map'."""
    with patch("app.services.pipeline_service.db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                # candidate row
                {
                    "id": "cand_1",
                    "status": "idea",
                    "program_id": "prog_1",
                },
                # programs row
                {
                    "id": "prog_1",
                    "auto_promote_threshold": 0.7,
                    "auto_kill_threshold": 0.3,
                },
                # latest scorecard (none)
                None,
            ],
            fetchval_side_effect=[1],  # 1 hypothesis linked
        )

        result = await pipeline_service.auto_advance("cand_1")

    assert result["moved"] is True
    assert result["from_status"] == "idea"
    assert result["to_status"] == "evidence_map"
    assert result["trigger_type"] == "agent"
    # Verify a transition row was inserted (one of the conn.execute calls)
    insert_calls = [
        c for c in mock_conn.execute.await_args_list
        if "candidate_transitions" in str(c.args[0])
    ]
    assert insert_calls, "Expected an INSERT into candidate_transitions"


@pytest.mark.asyncio
async def test_auto_advance_terminal_status_is_noop():
    with patch("app.services.pipeline_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {
                    "id": "cand_1",
                    "status": "promoted",
                    "program_id": "prog_1",
                },
            ],
        )
        result = await pipeline_service.auto_advance("cand_1")

    assert result["moved"] is False
    assert result["to_status"] == "promoted"


@pytest.mark.asyncio
async def test_auto_advance_kills_below_threshold():
    """A scorecard below auto_kill_threshold triggers an auto-kill."""
    with patch("app.services.pipeline_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                # candidate row
                {
                    "id": "cand_1",
                    "status": "candidate",
                    "program_id": "prog_1",
                },
                # programs row
                {
                    "id": "prog_1",
                    "auto_promote_threshold": 0.7,
                    "auto_kill_threshold": 0.3,
                },
                # latest scorecard — overall_score 1.5/10 = 0.15 < 0.3
                {
                    "id": "sc_1",
                    "candidate_id": "cand_1",
                    "overall_score": 1.5,
                    "version": 1,
                },
            ],
        )

        result = await pipeline_service.auto_advance("cand_1")

    assert result["moved"] is True
    assert result["to_status"] == "killed"
    assert result["trigger_type"] == "threshold"


@pytest.mark.asyncio
async def test_log_transition_validates_trigger_type():
    with patch("app.services.pipeline_service.db") as mock_db:
        _build_db_mock(mock_db)
        with pytest.raises(ValueError, match="trigger_type"):
            await pipeline_service.log_transition(
                candidate_id="cand_1",
                from_status="idea",
                to_status="evidence_map",
                trigger_type="not_a_real_trigger",
            )


# ---------------------------------------------------------------------------
# Manual status update logs a transition (PR #8 traceability)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_manual_status_update_logs_transition():
    with patch("app.services.candidate_service.db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                # 1) lookup of previous status / program_id
                {"status": "idea", "program_id": "prog_1"},
                # 2) final SELECT * after update
                {
                    "id": "cand_1",
                    "name": "X",
                    "status": "evidence_map",
                },
            ],
        )

        result = await candidate_service.update_candidate_status(
            candidate_id="cand_1",
            new_status="evidence_map",
        )

    assert result["status"] == "evidence_map"
    insert_calls = [
        c for c in mock_conn.execute.await_args_list
        if "candidate_transitions" in str(c.args[0])
    ]
    assert insert_calls, (
        "Manual status updates must log a candidate_transitions row"
    )


# ---------------------------------------------------------------------------
# Hypothesis versioning
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_hypothesis_version_preserves_parent_link():
    parent = {
        "id": "hyp_parent",
        "version": 1,
        "claim_type": "target_disease_association",
        "program_id": "prog_1",
    }
    child = {
        "id": "hyp_child",
        "version": 2,
        "parent_hypothesis_id": "hyp_parent",
        "hypothesis_text": "Refined claim",
        "status": "draft",
    }
    with patch("app.services.hypothesis_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[parent, child],
        )

        result = await hypothesis_service.create_version(
            parent_hypothesis_id="hyp_parent",
            hypothesis_text="Refined claim",
        )

    assert result["parent_hypothesis_id"] == "hyp_parent"
    assert result["version"] == 2


@pytest.mark.asyncio
async def test_create_hypothesis_version_requires_parent():
    with patch("app.services.hypothesis_service.db") as mock_db:
        _build_db_mock(mock_db, fetchrow_side_effect=[None])

        with pytest.raises(ValueError, match="Parent hypothesis not found"):
            await hypothesis_service.create_version(
                parent_hypothesis_id="missing",
                hypothesis_text="x",
            )


# ---------------------------------------------------------------------------
# Guardian bulk decisions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bulk_decide_candidates_creates_per_entity_reviews():
    """A single bulk call must create one review per candidate."""
    created_ids = []

    async def fake_create_review(*args, **kwargs):
        new_id = f"rev_{kwargs['entity_id']}"
        created_ids.append(new_id)
        return {
            "id": new_id,
            "entity_id": kwargs["entity_id"],
            "decision": kwargs["decision"],
        }

    async def fake_log(*args, **kwargs):
        return None

    with patch.object(
        guardian_service, "create_review", new=AsyncMock(side_effect=fake_create_review)
    ), patch.object(
        guardian_service, "_log_guardian_transition", new=AsyncMock(side_effect=fake_log)
    ):
        result = await guardian_service.bulk_decide_candidates(
            candidate_ids=["c1", "c2", "c3", "c4", "c5"],
            decision="approve",
            decision_rationale="All five pass scorecards",
            reviewer_id="user_1",
        )

    assert result["total"] == 5
    assert result["successes"] == 5
    assert result["failures"] == 0
    assert len(result["results"]) == 5
    assert created_ids == [
        "rev_c1",
        "rev_c2",
        "rev_c3",
        "rev_c4",
        "rev_c5",
    ]


@pytest.mark.asyncio
async def test_bulk_decide_candidates_requires_ids():
    with pytest.raises(ValueError, match="candidate_ids"):
        await guardian_service.bulk_decide_candidates(
            candidate_ids=[],
            decision="approve",
            decision_rationale="x",
            reviewer_id="u",
        )
