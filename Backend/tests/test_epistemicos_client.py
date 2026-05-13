"""Unit tests for the EpistemicOS stub client.

The stub is the boundary that lets Genovate keep moving while the real
EpistemicOS service is still being built. These tests guarantee the stub
always returns the shape the rest of Genovate depends on, and that no real
network call is made while `EPISTEMICOS_MOCK_MODE` is on.
"""

from __future__ import annotations

import pytest

from app.services.epistemicos_client import EpistemicOSClient
from app.schemas.epistemicos import IngestResponse, SimulateResponse, ZoneResponse


@pytest.fixture
def client() -> EpistemicOSClient:
    c = EpistemicOSClient()
    c.mock_mode = True  # force stub regardless of env
    return c


@pytest.mark.asyncio
async def test_ingest_document_returns_mock_payload(client: EpistemicOSClient) -> None:
    result = await client.ingest_document(
        document_uri="s3://genovate-assets/example.pdf",
        file_type="application/pdf",
        program_context={"program_id": "prog-1", "filename": "example.pdf"},
    )

    # Shape matches the IngestResponse contract (no real embeddings produced).
    parsed = IngestResponse.model_validate(result)
    assert parsed.status == "completed"
    assert parsed.vector_count == len(parsed.chunk_ids) == 5
    assert parsed.embedding_collection_id.startswith("emb_")
    assert all(cid.startswith("chunk_") for cid in parsed.chunk_ids)


@pytest.mark.asyncio
async def test_create_zone_returns_mock_zone(client: EpistemicOSClient) -> None:
    result = await client.create_zone(
        program_id="prog-1",
        zone_type="tumour_microenvironment",
        config={"foo": "bar"},
    )
    parsed = ZoneResponse.model_validate(result)
    assert parsed.zone_type == "tumour_microenvironment"
    assert parsed.epistemicos_zone_id.startswith("zone_")
    assert parsed.status == "created"


@pytest.mark.asyncio
async def test_simulate_returns_mock_results(client: EpistemicOSClient) -> None:
    result = await client.simulate(
        zone_id="zone_abc",
        simulation_type="dose_response",
        inputs={"compound": "X"},
    )
    parsed = SimulateResponse.model_validate(result)
    assert parsed.status == "completed"
    assert 0.0 <= (parsed.confidence or 0.0) <= 1.0
    assert "mock_output" in parsed.results


@pytest.mark.asyncio
async def test_mock_mode_never_calls_network(monkeypatch, client: EpistemicOSClient) -> None:
    """If mock_mode is True, httpx must not be touched."""

    def _boom(*_args, **_kwargs):  # pragma: no cover - failure path
        raise AssertionError("httpx.AsyncClient must not be used in mock mode")

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _boom)

    await client.ingest_document("s3://x", "application/pdf", {})
    await client.create_zone("p", "t", {})
    await client.simulate("z", "s", {})
