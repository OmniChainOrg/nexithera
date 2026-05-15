"""Unit tests for `AssetService`.

These tests exercise the upload flow end-to-end with the DB and S3 layers
replaced by in-memory fakes, and verify that:

1. The file is handed to the storage layer.
2. `EpistemicOSClient.ingest_document` is invoked exactly once.
3. The resulting asset row ends in status ``'ingested'``.
4. The corresponding ``epistemicos_runs`` row stores the mock response payload.

This is the contract the rest of Genovate (and downstream PRs) relies on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

import pytest

from app.services import asset_service as asset_service_module


# ---------------------------------------------------------------------------
# In-memory fakes
# ---------------------------------------------------------------------------


class _FakeConn:
    def __init__(self, store: "_FakeDBStore") -> None:
        self._store = store

    async def execute(self, query: str, *args: Any) -> None:
        self._store.record(query, args)

    async def fetchrow(self, query: str, *args: Any) -> Dict[str, Any] | None:
        return self._store.fetchrow(query, args)

    async def fetch(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        return self._store.fetch(query, args)


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_exc: Any) -> None:
        return None


class _FakePool:
    def __init__(self, store: "_FakeDBStore") -> None:
        self._store = store

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(_FakeConn(self._store))


class _FakeDBStore:
    """Tiny in-memory stand-in: tracks executed SQL + a couple of tables."""

    def __init__(self) -> None:
        self.executed: List[Tuple[str, Tuple[Any, ...]]] = []
        self.epistemicos_runs: Dict[str, Dict[str, Any]] = {}
        self.data_assets: Dict[str, Dict[str, Any]] = {}

    def record(self, query: str, args: Tuple[Any, ...]) -> None:
        self.executed.append((query, args))
        q = " ".join(query.split())
        if q.startswith("INSERT INTO epistemicos_runs"):
            run_id, run_type, payload, status = args
            self.epistemicos_runs[str(run_id)] = {
                "id": run_id,
                "run_type": run_type,
                "request_payload": payload,
                "response_payload": None,
                "status": status,
                "error_message": None,
                "completed_at": None,
            }
        elif q.startswith("INSERT INTO data_assets"):
            (
                asset_id,
                filename,
                s3_uri,
                size_bytes,
                file_type,
                status,
                program_id,
                eos_run_id,
            ) = args
            self.data_assets[str(asset_id)] = {
                "id": asset_id,
                "filename": filename,
                "s3_uri": s3_uri,
                "size_bytes": size_bytes,
                "file_type": file_type,
                "status": status,
                "program_id": program_id,
                "epistemicos_run_id": eos_run_id,
                "created_at": datetime.utcnow(),
            }
        elif q.startswith("UPDATE epistemicos_runs SET status = 'failed'"):
            err, run_id = args
            row = self.epistemicos_runs[str(run_id)]
            row["status"] = "failed"
            row["error_message"] = err
            row["completed_at"] = datetime.utcnow()
        elif q.startswith("UPDATE epistemicos_runs SET response_payload"):
            response_payload, run_id = args
            row = self.epistemicos_runs[str(run_id)]
            row["response_payload"] = response_payload
            row["status"] = "completed"
            row["completed_at"] = datetime.utcnow()
        elif q.startswith("UPDATE data_assets SET status = 'ingested'"):
            asset_id = args[0]
            self.data_assets[str(asset_id)]["status"] = "ingested"
            if len(args) >= 2:
                # New flow also merges metadata JSON as the second arg.
                self.data_assets[str(asset_id)]["metadata"] = args[1]
        elif q.startswith("UPDATE data_assets SET status = 'failed'"):
            (asset_id,) = args
            self.data_assets[str(asset_id)]["status"] = "failed"
        else:
            # Surface unknown SQL so test-store drift is loud rather than silent.
            raise AssertionError(f"Unhandled SQL in fake DB store: {q[:80]!r}")

    def fetchrow(self, query: str, args: Tuple[Any, ...]) -> Dict[str, Any] | None:
        return None

    def fetch(self, query: str, args: Tuple[Any, ...]) -> List[Dict[str, Any]]:
        (program_id,) = args
        return [
            r for r in self.data_assets.values() if str(r["program_id"]) == str(program_id)
        ]


class _FakeStorage:
    def __init__(self) -> None:
        self.uploads: List[Dict[str, Any]] = []

    async def upload_file(
        self, bucket: str, key: str, content: bytes, content_type: str
    ) -> str:
        self.uploads.append(
            {"bucket": bucket, "key": key, "content": content, "content_type": content_type}
        )
        return f"s3://{bucket}/{key}"


class _RecordingEpistemicOSClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.response: Dict[str, Any] = {
            "embedding_collection_id": "emb_test123",
            "chunk_ids": ["chunk_a", "chunk_b", "chunk_c"],
            "vector_count": 3,
            "status": "completed",
            "trace_id": "trace_xyz",
        }
        self.should_raise: Exception | None = None

    async def ingest_document(
        self,
        document_uri: str,
        file_type: str,
        program_context: Dict[str, Any],
        program_id: str | None = None,
    ) -> Dict[str, Any]:
        self.calls.append(
            {
                "document_uri": document_uri,
                "file_type": file_type,
                "program_context": program_context,
                "program_id": program_id,
            }
        )
        if self.should_raise is not None:
            raise self.should_raise
        return self.response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_db_store() -> _FakeDBStore:
    return _FakeDBStore()


@pytest.fixture
def fake_storage() -> _FakeStorage:
    return _FakeStorage()


@pytest.fixture
def fake_eos() -> _RecordingEpistemicOSClient:
    return _RecordingEpistemicOSClient()


@pytest.fixture
def asset_service(
    monkeypatch: pytest.MonkeyPatch,
    fake_db_store: _FakeDBStore,
    fake_storage: _FakeStorage,
    fake_eos: _RecordingEpistemicOSClient,
):
    pool = _FakePool(fake_db_store)

    async def _get_pool() -> _FakePool:
        return pool

    monkeypatch.setattr(asset_service_module.db, "get_pool", _get_pool)
    monkeypatch.setattr(asset_service_module, "storage", fake_storage)
    monkeypatch.setattr(asset_service_module, "epistemicos_client", fake_eos)

    return asset_service_module.AssetService()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_asset_calls_epistemicos_stub(
    asset_service,
    fake_db_store: _FakeDBStore,
    fake_storage: _FakeStorage,
    fake_eos: _RecordingEpistemicOSClient,
) -> None:
    program_id = "550e8400-e29b-41d4-a716-446655440000"

    result = await asset_service.create_asset(
        program_id=program_id,
        filename="pubmed_tnbc_2024.pdf",
        file_content=b"%PDF-1.7 mock",
        file_type="application/pdf",
    )

    # 1. EpistemicOS stub was invoked exactly once with the S3 URI.
    assert len(fake_eos.calls) == 1
    call = fake_eos.calls[0]
    assert call["file_type"] == "application/pdf"
    assert call["document_uri"].startswith(f"s3://genovate-assets/{program_id}/")
    assert call["program_context"]["program_id"] == program_id

    # 2. File was uploaded to S3 exactly once with the same key.
    assert len(fake_storage.uploads) == 1
    upload = fake_storage.uploads[0]
    assert upload["bucket"] == "genovate-assets"
    assert upload["content"] == b"%PDF-1.7 mock"
    assert upload["content_type"] == "application/pdf"

    # 3. Response shape matches the public AssetResponse contract.
    assert result["status"] == "ingested"
    assert result["filename"] == "pubmed_tnbc_2024.pdf"
    assert result["embedding_collection_id"] == "emb_test123"
    assert result["chunk_count"] == 3

    # 4. data_assets row landed with status='ingested'.
    asset_row = fake_db_store.data_assets[result["asset_id"]]
    assert asset_row["status"] == "ingested"
    assert asset_row["size_bytes"] == len(b"%PDF-1.7 mock")

    # 5. epistemicos_runs row stores the mock response payload + completed.
    run_row = fake_db_store.epistemicos_runs[result["epistemicos_run_id"]]
    assert run_row["status"] == "completed"
    assert run_row["response_payload"] == fake_eos.response
    assert run_row["completed_at"] is not None


@pytest.mark.asyncio
async def test_upload_marks_asset_failed_when_epistemicos_errors(
    asset_service,
    fake_db_store: _FakeDBStore,
    fake_eos: _RecordingEpistemicOSClient,
) -> None:
    fake_eos.should_raise = RuntimeError("EpistemicOS down")

    with pytest.raises(RuntimeError, match="EpistemicOS down"):
        await asset_service.create_asset(
            program_id="abc",
            filename="x.csv",
            file_content=b"a,b\n1,2\n",
            file_type="text/csv",
        )

    # Exactly one asset + one run, both marked failed.
    [asset_row] = fake_db_store.data_assets.values()
    [run_row] = fake_db_store.epistemicos_runs.values()
    assert asset_row["status"] == "failed"
    assert run_row["status"] == "failed"
    assert run_row["error_message"] == "EpistemicOS down"


@pytest.mark.asyncio
async def test_list_assets_returns_only_program_rows(
    asset_service,
    fake_eos: _RecordingEpistemicOSClient,
) -> None:
    program_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    program_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    await asset_service.create_asset(program_a, "a1.pdf", b"a1", "application/pdf")
    await asset_service.create_asset(program_a, "a2.pdf", b"a2", "application/pdf")
    await asset_service.create_asset(program_b, "b1.pdf", b"b1", "application/pdf")

    listed_a = await asset_service.list_assets(program_a)
    listed_b = await asset_service.list_assets(program_b)

    assert {row["filename"] for row in listed_a} == {"a1.pdf", "a2.pdf"}
    assert {row["filename"] for row in listed_b} == {"b1.pdf"}
