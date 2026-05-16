# tests/test_advanced_simulations.py
"""Unit tests for the advanced EpistemicOS workflows (PR #7).

These tests exercise the orchestration layer in isolation by mocking the
EpistemicOS client and the database pool, so they do not require a live
PostgreSQL instance or EpistemicOS deployment.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cxu_service import cxu_service
from app.services.swarm_service import swarm_service
from app.services.cross_zone_service import cross_zone_service


def _make_pool(conn: MagicMock) -> MagicMock:
    """Build a mock asyncpg pool whose ``acquire()`` yields ``conn``."""

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = _acquire
    return pool


def _patch_db(target: str, conn: MagicMock):
    """Patch the ``db.get_pool`` reference inside a service module."""
    pool = _make_pool(conn)
    return patch(f"{target}.db.get_pool", AsyncMock(return_value=pool))


@pytest.mark.asyncio
async def test_cxu_lifecycle():
    """Create + start exercises both the EpistemicOS client and the DB layer."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            # 1) zone lookup in create_cxu
            {"epistemicos_zone_id": "eos_zone_xyz"},
            # 2) row read-back after INSERT
            {"id": "cxu_uuid", "name": "Test CXU", "status": "created"},
            # 3) cxu lookup in start_cxu
            {"id": "cxu_uuid", "epistemicos_cxu_id": "eos_cxu_123"},
        ]
    )
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    with _patch_db("app.services.cxu_service", conn), patch(
        "app.services.cxu_service.epistemicos_client"
    ) as mock_eos:
        mock_eos.create_cxu = AsyncMock(return_value={"cxu_id": "eos_cxu_123"})
        mock_eos.start_cxu = AsyncMock(
            return_value={"cxu_id": "eos_cxu_123", "trace_id": "trace_123"}
        )

        cxu = await cxu_service.create_cxu(
            name="Test CXU",
            cxu_type="tumor_microenvironment",
            zone_id="zone_123",
            configuration={"param": "value"},
        )
        assert cxu["status"] == "created"
        mock_eos.create_cxu.assert_awaited_once()

        result = await cxu_service.start_cxu(cxu["id"], initial_state={"x": 1})
        assert result["status"] == "running"
        assert result["trace_id"] == "trace_123"
        mock_eos.start_cxu.assert_awaited_once()


@pytest.mark.asyncio
async def test_cxu_pause_and_terminate():
    """Pause and terminate must call EpistemicOS and update DB status."""
    conn = MagicMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")

    with _patch_db("app.services.cxu_service", conn), patch(
        "app.services.cxu_service.epistemicos_client"
    ) as mock_eos:
        mock_eos.pause_cxu = AsyncMock(return_value={"status": "paused"})
        mock_eos.terminate_cxu = AsyncMock(return_value={"status": "terminated"})

        paused = await cxu_service.pause_cxu("cxu_uuid")
        terminated = await cxu_service.terminate_cxu("cxu_uuid")

        assert paused["status"] == "paused"
        assert terminated["status"] == "terminated"
        mock_eos.pause_cxu.assert_awaited_once_with("cxu_uuid")
        mock_eos.terminate_cxu.assert_awaited_once_with("cxu_uuid")


@pytest.mark.asyncio
async def test_swarm_with_results():
    """Swarm creation + result aggregation round-trip."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            # row read-back after create_swarm INSERT
            {"id": "swarm_uuid", "name": "Test Swarm", "status": "created"},
            # swarm lookup in get_swarm_results
            {"id": "swarm_uuid", "epistemicos_swarm_id": "eos_swarm_123"},
        ]
    )
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    with _patch_db("app.services.swarm_service", conn), patch(
        "app.services.swarm_service.epistemicos_client"
    ) as mock_eos:
        mock_eos.create_swarm = AsyncMock(return_value={"swarm_id": "eos_swarm_123"})
        mock_eos.get_swarm_results = AsyncMock(
            return_value={
                "aggregation_method": "consensus",
                "consensus_score": 0.87,
                "diversity_metric": 0.42,
                "aggregated_output": {"recommendation": "high_confidence"},
            }
        )

        swarm = await swarm_service.create_swarm(
            name="Test Swarm",
            swarm_type="cooperative",
            objective="Find optimal dosing",
            configuration={},
            program_id="prog_123",
        )
        assert swarm["status"] == "created"

        results = await swarm_service.get_swarm_results(swarm["id"])
        assert results["consensus_score"] == 0.87
        assert results["diversity_metric"] == 0.42


@pytest.mark.asyncio
async def test_cross_zone_simulation():
    """Cross-zone simulation must resolve coupling map and persist results."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            # source zone lookup
            {"epistemicos_zone_id": "eos_src", "zone_type": "tumor_microenvironment"},
            # target zone lookup
            {"epistemicos_zone_id": "eos_tgt", "zone_type": "pkpd"},
            # coupling lookup
            {"coupling_map": {"tumor_volume": "initial_tumor_volume"}},
        ]
    )
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    with _patch_db("app.services.cross_zone_service", conn), patch(
        "app.services.cross_zone_service.epistemicos_client"
    ) as mock_eos:
        mock_eos.cross_zone_simulate = AsyncMock(
            return_value={
                "run_id": "eos_run_999",
                "results": {"coupled_output": "ok"},
                "trace_id": "trace_xz",
            }
        )

        result = await cross_zone_service.run_cross_zone_simulation(
            name="TME->PKPD",
            source_zone_id="zone_a",
            target_zone_id="zone_b",
            input_state={"tumor_volume": 1.0},
            program_id="prog_123",
            coupling_id="coupling_uuid",
        )

        assert result["status"] == "completed"
        assert result["trace_id"] == "trace_xz"
        mock_eos.cross_zone_simulate.assert_awaited_once()


@pytest.mark.asyncio
async def test_cross_zone_requires_coupling_map():
    """Without a coupling_id or override, the run should be rejected."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        side_effect=[
            {"epistemicos_zone_id": "eos_src", "zone_type": "tumor_microenvironment"},
            {"epistemicos_zone_id": "eos_tgt", "zone_type": "pkpd"},
        ]
    )
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    with _patch_db("app.services.cross_zone_service", conn), patch(
        "app.services.cross_zone_service.epistemicos_client"
    ):
        with pytest.raises(ValueError, match="coupling map"):
            await cross_zone_service.run_cross_zone_simulation(
                name=None,
                source_zone_id="zone_a",
                target_zone_id="zone_b",
                input_state={},
                program_id="prog_123",
            )


@pytest.mark.asyncio
async def test_epistemicos_client_cxu_and_swarm_mocks():
    """The new EpistemicOSClient methods must return the documented shape in mock mode."""
    from app.services.epistemicos_client import EpistemicOSClient

    client = EpistemicOSClient()
    client.mock_mode = True

    started = await client.start_cxu("cxu_1", {"x": 1})
    assert started["status"] == "running"
    assert started["trace_id"].startswith("trace_")

    paused = await client.pause_cxu("cxu_1")
    assert paused["status"] == "paused"

    terminated = await client.terminate_cxu("cxu_1")
    assert terminated["status"] == "terminated"

    swarm = await client.start_swarm("swarm_1", [{"cxu_id": "cxu_1"}])
    assert swarm["status"] == "running"
    assert swarm["member_count"] == 1
