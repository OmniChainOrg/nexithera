# tests/test_partnerability.py
"""Tests for PR #10 — Partnerability + IND Readiness."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.competitive_landscape_agent import (
    CompetitiveLandscapeAgent,
    _competitive_moat_score,
    _classify_threat,
    _MOCK_COMPETITORS,
)
from app.agents.ip_position_agent import (
    IPPositionAgent,
    _aggregate_fto,
    _ip_strength_score,
    _MOCK_PATENT_LIBRARY,
)
from app.agents.ind_readiness_agent import (
    INDReadinessAgent,
    _estimate_timeline_months,
    _readiness_score,
)
from app.agents.partnerability_agent import (
    PartnerabilityAgent,
    WEIGHTS,
    composite_partnerability,
    estimate_unmet_need,
    rank_partners,
)


# ---------------------------------------------------------------------------
# Test fixtures (mirror PR #9 mocking pattern)
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
# Composite partnerability formula
# ---------------------------------------------------------------------------
def test_partnerability_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_composite_partnerability_matches_spec_formula():
    # Spec example: moat=8, ip=7.5, unmet=9, ind=6.5
    score = composite_partnerability(
        competitive_moat=8.0,
        ip_strength=7.5,
        unmet_need=9.0,
        ind_readiness=6.5,
    )
    expected = 0.30 * 8.0 + 0.25 * 7.5 + 0.25 * 9.0 + 0.20 * 6.5
    assert score == pytest.approx(round(expected, 2), abs=0.01)
    # Bounded to [0, 10].
    assert 0.0 <= score <= 10.0


def test_composite_partnerability_clamps_inputs():
    # Negative & over-range sub-scores are clamped before weighting.
    high = composite_partnerability(15.0, 15.0, 15.0, 15.0)
    low = composite_partnerability(-5.0, -5.0, -5.0, -5.0)
    assert high == 10.0
    assert low == 0.0


def test_rank_partners_returns_sorted_top_n():
    partners = rank_partners("oncology / NSCLC", overall_score=8.0, top_n=3)
    assert len(partners) == 3
    fits = [p["fit_score"] for p in partners]
    assert fits == sorted(fits, reverse=True)
    # Every partner has a non-empty rationale.
    assert all(p["rationale"] for p in partners)


def test_rank_partners_boosts_focus_overlap():
    onco = rank_partners("oncology", overall_score=7.0, top_n=6)
    none = rank_partners("dermatology", overall_score=7.0, top_n=6)
    # Top fit for oncology should be >= top fit for dermatology because
    # most pharma in the library focus on oncology.
    assert onco[0]["fit_score"] >= none[0]["fit_score"]


def test_estimate_unmet_need_buckets():
    assert estimate_unmet_need("pancreatic ductal adenocarcinoma") == 9.0
    assert estimate_unmet_need("NSCLC") == 7.0
    assert estimate_unmet_need("type 2 diabetes") == 4.0
    assert estimate_unmet_need(None) == 6.0


# ---------------------------------------------------------------------------
# Competitive landscape sub-scoring
# ---------------------------------------------------------------------------
def test_classify_threat_levels():
    assert _classify_threat("Approved") == "high"
    assert _classify_threat("Phase 3") == "high"
    assert _classify_threat("Phase 2") == "medium"
    assert _classify_threat("Phase 1") == "low"
    assert _classify_threat(None) == "low"


def test_competitive_moat_score_drops_with_late_stage_competitors():
    none = _competitive_moat_score([])
    one_approved = _competitive_moat_score([{"phase": "Approved"}])
    two_approved = _competitive_moat_score(
        [{"phase": "Approved"}, {"phase": "Approved"}]
    )
    assert none == 10.0
    assert one_approved == 8.0
    assert two_approved == 6.0
    # Cannot go below zero.
    many = _competitive_moat_score(
        [{"phase": "Approved"}] * 20
    )
    assert many == 0.0


@pytest.mark.asyncio
async def test_competitive_landscape_falls_back_to_mock_when_external_fail(
    monkeypatch,
):
    """When external sources are unavailable, the agent must still
    return at least 3 competitors (acceptance criterion)."""
    agent = CompetitiveLandscapeAgent("agent_id")

    candidate_row = {
        "target_name": "KRAS",
        "disease_name": "NSCLC",
    }

    # Force every external fetch to return [] (simulating offline / no
    # API key path).
    async def _empty(*args, **kwargs):
        return []

    with patch(
        "app.agents.competitive_landscape_agent._candidate_context",
        new=AsyncMock(return_value=("KRAS", "NSCLC")),
    ), patch(
        "app.agents.competitive_landscape_agent._fetch_clinicaltrials",
        new=_empty,
    ), patch(
        "app.agents.competitive_landscape_agent._fetch_pubmed", new=_empty,
    ), patch(
        "app.agents.competitive_landscape_agent._fetch_patents", new=_empty,
    ):
        result = await agent.execute({"candidate_id": "cand_1"})

    competitors = result["structure"]["competitors"]
    assert len(competitors) >= 3  # acceptance criterion
    # Every competitor has a threat_level annotation.
    for c in competitors:
        assert c["threat_level"] in {"low", "medium", "high"}
        assert c.get("differentiation")
    assert isinstance(result["structure"]["competitive_moat_score"], float)


@pytest.mark.asyncio
async def test_competitive_landscape_requires_candidate_id():
    agent = CompetitiveLandscapeAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# IP position sub-scoring
# ---------------------------------------------------------------------------
def test_aggregate_fto_uses_min_per_patent():
    # One blocking patent with FTO=0.05 dominates an otherwise clean library.
    positions = [
        {"is_blocking": False},
        {"is_blocking": False},
        {"is_blocking": True, "freedom_to_operate_estimate": 0.05},
    ]
    assert _aggregate_fto(positions) == 0.05


def test_ip_strength_score_drops_with_blocking_patents():
    no_blocks = _ip_strength_score([{"is_blocking": False}])
    with_block = _ip_strength_score([{"is_blocking": True, "expiry_year": 2040}])
    assert with_block < no_blocks


@pytest.mark.asyncio
async def test_ip_position_agent_emits_fto_and_ip_strength():
    agent = IPPositionAgent("agent_id")

    async def _empty(*args, **kwargs):
        return []

    with patch(
        "app.agents.ip_position_agent._candidate_context",
        new=AsyncMock(return_value=("KRAS", "NSCLC")),
    ), patch(
        "app.agents.ip_position_agent._fetch_patents", new=_empty,
    ):
        result = await agent.execute({"candidate_id": "cand_1"})
    structure = result["structure"]
    assert 0.0 <= structure["freedom_to_operate_estimate"] <= 1.0
    assert 0.0 <= structure["ip_strength_score"] <= 10.0
    # Mock library has at least one blocking patent.
    assert structure["blocking_count"] >= 1
    # Every persisted position has an FTO estimate annotated.
    for p in structure["positions"]:
        assert 0.0 <= p["freedom_to_operate_estimate"] <= 1.0


@pytest.mark.asyncio
async def test_ip_position_agent_requires_candidate_id():
    agent = IPPositionAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# IND readiness
# ---------------------------------------------------------------------------
def test_readiness_score_endpoints():
    assert _readiness_score(0.0) == 0.0
    assert _readiness_score(1.0) == 10.0
    assert _readiness_score(0.5) == 5.0


def test_estimate_timeline_months_caps_at_36():
    assert _estimate_timeline_months(0) == 0
    assert _estimate_timeline_months(5) == 10
    assert _estimate_timeline_months(100) == 36


@pytest.mark.asyncio
async def test_ind_readiness_agent_identifies_gaps_and_score():
    agent = INDReadinessAgent("agent_id")
    rows = [
        {  # complete required item
            "item_id": "i1",
            "category": "CMC",
            "item": "Cell line",
            "description": "x",
            "is_required": True,
            "status": "complete",
            "evidence_uri": None,
            "notes": None,
            "updated_at": None,
        },
        {  # incomplete required item -> critical gap
            "item_id": "i2",
            "category": "gmp",
            "item": "GMP batch produced",
            "description": "x",
            "is_required": True,
            "status": "in_progress",
            "evidence_uri": None,
            "notes": None,
            "updated_at": None,
        },
        {  # optional item, ignored from required totals
            "item_id": "i3",
            "category": "regulatory",
            "item": "Pre-IND meeting",
            "description": "x",
            "is_required": False,
            "status": "not_started",
            "evidence_uri": None,
            "notes": None,
            "updated_at": None,
        },
    ]

    with patch("app.agents.ind_readiness_agent.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[{"id": "cand_1", "name": "X"}],
            fetch_side_effect=[rows],
        )
        result = await agent.execute({"candidate_id": "cand_1"})

    s = result["structure"]
    assert s["items_total"] == 2  # only required items
    assert s["items_complete"] == 1
    assert s["overall_readiness"] == 0.5
    assert s["ind_readiness_score"] == 5.0
    assert any("GMP" in g for g in s["critical_gaps"])
    assert s["estimated_timeline_months"] >= 2


@pytest.mark.asyncio
async def test_ind_readiness_agent_requires_candidate_id():
    agent = INDReadinessAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


@pytest.mark.asyncio
async def test_ind_readiness_agent_unknown_candidate_raises():
    agent = INDReadinessAgent("agent_id")
    with patch("app.agents.ind_readiness_agent.db") as mock_db:
        _build_db_mock(mock_db, fetchrow_side_effect=[None])
        with pytest.raises(ValueError, match="Candidate not found"):
            await agent.execute({"candidate_id": "missing"})


# ---------------------------------------------------------------------------
# Partnerability orchestrator
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_partnerability_agent_uses_provided_subscores():
    agent = PartnerabilityAgent("agent_id")
    result = await agent.execute(
        {
            "candidate_id": "cand_1",
            "competitive_moat": 8.0,
            "ip_strength": 7.5,
            "unmet_need": 9.0,
            "ind_readiness": 6.5,
            "therapeutic_area": "oncology / NSCLC",
        }
    )
    s = result["structure"]
    expected = round(
        0.30 * 8.0 + 0.25 * 7.5 + 0.25 * 9.0 + 0.20 * 6.5, 2
    )
    assert s["overall_score"] == expected
    assert s["verdict"] in {
        "Highly Partnerable",
        "Conditionally Partnerable",
        "Not yet Partnerable",
    }
    assert s["potential_partners"], "must rank at least one partner"
    # BD interest scales with overall score.
    assert s["bd_interest_estimate"] == pytest.approx(expected / 10.0, abs=0.01)


@pytest.mark.asyncio
async def test_partnerability_agent_estimates_unmet_need_when_omitted():
    agent = PartnerabilityAgent("agent_id")
    with patch("app.agents.partnerability_agent.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[{"therapeutic_area": "Pancreatic cancer"}],
        )
        result = await agent.execute(
            {
                "candidate_id": "cand_1",
                "competitive_moat": 7.0,
                "ip_strength": 7.0,
                "ind_readiness": 6.0,
                # no unmet_need / no therapeutic_area in inputs
            }
        )
    assert result["structure"]["unmet_need_score"] == 9.0


@pytest.mark.asyncio
async def test_partnerability_agent_requires_candidate_id():
    agent = PartnerabilityAgent("agent_id")
    with pytest.raises(ValueError, match="candidate_id"):
        await agent.execute({})


# ---------------------------------------------------------------------------
# Service: checklist update validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_update_checklist_item_rejects_invalid_status():
    from app.services.partnerability_service import partnerability_service

    with pytest.raises(ValueError, match="Invalid IND checklist status"):
        await partnerability_service.update_checklist_item(
            candidate_id="cand_1",
            item_id="item_1",
            status="bogus",
        )


@pytest.mark.asyncio
async def test_update_checklist_item_upserts_status_row():
    from app.services.partnerability_service import partnerability_service

    candidate_row = {"id": "cand_1"}
    item_row = {"id": "item_1"}
    upsert_row = {
        "id": "row_1",
        "candidate_id": "cand_1",
        "checklist_item_id": "item_1",
        "status": "complete",
        "evidence_uri": None,
        "notes": None,
        "updated_at": None,
    }

    with patch(
        "app.services.partnerability_service.db"
    ) as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[candidate_row, item_row, upsert_row],
        )
        result = await partnerability_service.update_checklist_item(
            candidate_id="cand_1",
            item_id="item_1",
            status="complete",
        )
    assert result["status"] == "complete"
    assert result["checklist_item_id"] == "item_1"


# ---------------------------------------------------------------------------
# Acceptance criterion: IND checklist seed has 20+ items across categories.
# ---------------------------------------------------------------------------
def test_ind_checklist_seed_covers_20_plus_items_across_categories():
    import importlib.util
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    migration_path = os.path.normpath(
        os.path.join(
            here, "..", "migrations", "versions",
            "010_partnerability_ind_readiness.py",
        )
    )
    spec = importlib.util.spec_from_file_location(
        "_pr10_migration", migration_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    seed = module._IND_CHECKLIST_SEED
    assert len(seed) >= 20
    categories = {row[0] for row in seed}
    assert categories >= {
        "CMC", "nonclinical_tox", "clinical_protocol", "regulatory", "gmp"
    }


# ---------------------------------------------------------------------------
# Sanity: mock libraries are non-empty (acceptance fallback path).
# ---------------------------------------------------------------------------
def test_mock_libraries_seed_test_environments():
    assert len(_MOCK_COMPETITORS) >= 3
    assert len(_MOCK_PATENT_LIBRARY) >= 2
