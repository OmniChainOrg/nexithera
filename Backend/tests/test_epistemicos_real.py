"""Tests for REAL EpistemicOS wiring (PR #6).

These tests verify that when ``mock_mode`` is False the client actually
issues HTTP requests to EpistemicOS, that the response shape is propagated
correctly, and that the new simulation orchestration surface works end to end.

No live network is required — we stub ``httpx.AsyncClient`` with a fake that
records requests and returns canned JSON responses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from app.services import epistemicos_client as eos_module
from app.services.epistemicos_client import EpistemicOSClient


# ---------------------------------------------------------------------------
# Fake httpx layer
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: Dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeHttpClient:
    """Captures requests and returns canned JSON payloads keyed by path."""

    def __init__(self) -> None:
        self.requests: List[Tuple[str, str, Dict[str, Any] | None]] = []
        self.responses: Dict[str, Dict[str, Any]] = {
            "POST /v1/ingest": {
                "embedding_collection_id": "emb_real_001",
                "chunk_ids": ["chunk_1", "chunk_2", "chunk_3"],
                "vector_count": 3,
                "status": "completed",
                "trace_id": "trace_real_ing",
            },
            "POST /v1/search": {
                "results": [
                    {"chunk_id": "chunk_1", "score": 0.91, "text": "real result"},
                ],
                "trace_id": "trace_real_search",
            },
            "POST /v1/zones": {
                "epistemicos_zone_id": "zone_real_abc",
                "status": "created",
                "zone_type": "tumour_microenvironment",
                "config": {"k": "v"},
            },
            "POST /v1/simulate": {
                "run_id": "sim_real_1",
                "status": "completed",
                "results": {"output": "real"},
                "confidence": 0.93,
                "trace_id": "trace_real_sim",
            },
            "POST /v1/cxus": {
                "cxu_id": "cxu_real_1",
                "zone_id": "zone_real_abc",
                "status": "ready",
            },
            "POST /v1/swarms": {
                "swarm_id": "swarm_real_1",
                "cxu_count": 3,
                "status": "created",
                "objective": "explore",
            },
            "GET /v1/swarms/swarm_real_1/results": {
                "swarm_id": "swarm_real_1",
                "status": "completed",
                "aggregated_results": {"best_cxu": "cxu_real_1"},
            },
            "POST /v1/simulate/cross-zone": {
                "cross_simulation_id": "cross_real_1",
                "status": "completed",
                "results": {"coupled": True},
                "trace_id": "trace_real_cross",
            },
            "GET /v1/traces/trace_real_ing": {
                "trace_id": "trace_real_ing",
                "steps": [{"step": 1, "action": "ingest"}],
                "verifiable_hash": "hash_real",
            },
        }

    async def post(self, url: str, json: Dict[str, Any] | None = None):  # noqa: A002
        key = f"POST {self._path(url)}"
        self.requests.append((key, url, json))
        return _FakeResponse(self.responses.get(key, {}))

    async def get(self, url: str):
        key = f"GET {self._path(url)}"
        self.requests.append((key, url, None))
        return _FakeResponse(self.responses.get(key, {}))

    async def aclose(self) -> None:
        return None

    @staticmethod
    def _path(url: str) -> str:
        # Strip scheme://host so the lookup key is stable across base_url values.
        idx = url.find("/v1")
        return url[idx:] if idx >= 0 else url


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_http() -> _FakeHttpClient:
    return _FakeHttpClient()


@pytest.fixture
def real_client(monkeypatch: pytest.MonkeyPatch, fake_http: _FakeHttpClient) -> EpistemicOSClient:
    """An EpistemicOSClient in REAL mode with HTTP stubbed and DB no-op."""

    client = EpistemicOSClient()
    client.mock_mode = False
    client._client = fake_http  # type: ignore[assignment]

    # No-op the trace/zone DB-store helpers — they're tested elsewhere.
    async def _noop(*_a, **_kw):  # pragma: no cover - trivial
        return None

    monkeypatch.setattr(client, "_store_trace_reference", _noop)
    monkeypatch.setattr(client, "_store_zone_reference", _noop)
    monkeypatch.setattr(client, "_link_simulation_to_candidate", _noop)

    return client


# ---------------------------------------------------------------------------
# Mode / configuration
# ---------------------------------------------------------------------------


def test_default_mode_is_real() -> None:
    """In real mode (default in production), mock_mode must be False."""
    # The shipped default for EPISTEMICOS_MOCK_MODE is "false".
    from app.core import config as config_module

    assert config_module.settings.EPISTEMICOS_MOCK_MODE is False


# ---------------------------------------------------------------------------
# Ingestion + semantic search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_ingest_hits_http_and_returns_collection(
    real_client: EpistemicOSClient, fake_http: _FakeHttpClient
) -> None:
    result = await real_client.ingest_document(
        document_uri="s3://genovate-assets/x.pdf",
        file_type="application/pdf",
        program_context={"program_id": "p1", "filename": "x.pdf"},
        program_id="p1",
    )

    # 1. A real POST was issued.
    assert any(r[0] == "POST /v1/ingest" for r in fake_http.requests)
    # 2. Response shape matches EpistemicOS contract.
    assert result["embedding_collection_id"] == "emb_real_001"
    assert result["vector_count"] == 3
    assert result["trace_id"] == "trace_real_ing"
    # 3. Genovate-provided context is forwarded so EpistemicOS can attribute the run.
    body = next(r[2] for r in fake_http.requests if r[0] == "POST /v1/ingest")
    assert body is not None
    assert body["metadata"]["program_id"] == "p1"
    assert body["metadata"]["source"] == "genovate"


@pytest.mark.asyncio
async def test_real_semantic_search_returns_chunks(
    real_client: EpistemicOSClient, fake_http: _FakeHttpClient
) -> None:
    result = await real_client.semantic_search(
        query="EGFR resistance mechanisms",
        collection_id="emb_real_001",
        program_id="p1",
        top_k=5,
    )

    assert any(r[0] == "POST /v1/search" for r in fake_http.requests)
    assert result["results"][0]["chunk_id"] == "chunk_1"


# ---------------------------------------------------------------------------
# Zones, simulations, CXUs, swarms, cross-zone, traces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_create_zone_hits_http(
    real_client: EpistemicOSClient, fake_http: _FakeHttpClient
) -> None:
    result = await real_client.create_zone(
        program_id="p1",
        zone_type="tumour_microenvironment",
        config={"k": "v"},
        name="zone-A",
    )
    assert any(r[0] == "POST /v1/zones" for r in fake_http.requests)
    assert result["epistemicos_zone_id"] == "zone_real_abc"
    assert result["status"] == "created"


@pytest.mark.asyncio
async def test_real_simulate_hits_http(
    real_client: EpistemicOSClient, fake_http: _FakeHttpClient
) -> None:
    result = await real_client.simulate(
        zone_id="zone_real_abc",
        simulation_type="dose_response",
        inputs={"compound": "X"},
        program_id="p1",
    )
    assert any(r[0] == "POST /v1/simulate" for r in fake_http.requests)
    assert result["run_id"] == "sim_real_1"
    assert result["trace_id"] == "trace_real_sim"


@pytest.mark.asyncio
async def test_real_create_cxu_hits_http(
    real_client: EpistemicOSClient, fake_http: _FakeHttpClient
) -> None:
    result = await real_client.create_cxu(
        zone_id="zone_real_abc",
        cxu_type="pharmacokinetic",
        configuration={"dose": 10},
        program_id="p1",
    )
    assert any(r[0] == "POST /v1/cxus" for r in fake_http.requests)
    assert result["cxu_id"] == "cxu_real_1"


@pytest.mark.asyncio
async def test_real_create_swarm_and_results(
    real_client: EpistemicOSClient, fake_http: _FakeHttpClient
) -> None:
    created = await real_client.create_swarm(
        swarm_config={"variations": [{}, {}, {}]},
        program_id="p1",
        objective="explore",
    )
    assert created["swarm_id"] == "swarm_real_1"

    results = await real_client.get_swarm_results("swarm_real_1")
    assert any(r[0] == "GET /v1/swarms/swarm_real_1/results" for r in fake_http.requests)
    assert results["status"] == "completed"


@pytest.mark.asyncio
async def test_real_cross_zone_simulation(
    real_client: EpistemicOSClient, fake_http: _FakeHttpClient
) -> None:
    result = await real_client.cross_zone_simulate(
        source_zone_id="zone_A",
        target_zone_id="zone_B",
        coupling_map={"tumour_volume": "pk_input"},
        inputs={"t": 0},
        program_id="p1",
    )
    assert any(r[0] == "POST /v1/simulate/cross-zone" for r in fake_http.requests)
    assert result["cross_simulation_id"] == "cross_real_1"


@pytest.mark.asyncio
async def test_real_get_trace_returns_verifiable_payload(
    real_client: EpistemicOSClient, fake_http: _FakeHttpClient
) -> None:
    trace = await real_client.get_trace("trace_real_ing")
    assert any(r[0] == "GET /v1/traces/trace_real_ing" for r in fake_http.requests)
    assert trace["verifiable_hash"] == "hash_real"
    assert trace["steps"][0]["action"] == "ingest"


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------


def test_get_client_sets_bearer_when_api_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """When an API key is configured, the client must send it as a Bearer token."""

    client = EpistemicOSClient()
    client.mock_mode = False
    client.api_key = "secret-key"
    client._client = None  # force construction

    captured: Dict[str, Any] = {}

    class _StubAsync:
        def __init__(self, *_a, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(eos_module.httpx, "AsyncClient", _StubAsync)

    client._get_client()
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    assert captured["headers"]["Content-Type"] == "application/json"
