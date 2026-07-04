from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import programs as programs_api


class _FakeConn:
    def __init__(self, store: "_ProgramStore") -> None:
        self._store = store

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        return self._store.fetch(query, args)

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        return self._store.fetchrow(query, args)


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_exc: Any) -> None:
        return None


class _FakePool:
    def __init__(self, store: "_ProgramStore") -> None:
        self._store = store

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(_FakeConn(self._store))


class _ProgramStore:
    def __init__(self) -> None:
        self.programs: dict[str, dict[str, Any]] = {}
        self._created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def seed_program(
        self,
        *,
        program_id: str,
        name: str,
        therapeutic_area: str = "Oncology",
        description: str | None = None,
        status: str = "active",
        organization_id: str = "11111111-1111-1111-1111-111111111111",
        created_at: datetime | None = None,
    ) -> None:
        self.programs[program_id] = {
            "id": program_id,
            "name": name,
            "therapeutic_area": therapeutic_area,
            "description": description,
            "status": status,
            "created_at": created_at or self._created_at,
            "organization_id": organization_id,
        }

    def fetch(self, query: str, args: tuple[Any, ...]) -> list[dict[str, Any]]:
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT id, name, therapeutic_area, description, status, created_at FROM programs WHERE organization_id = $1 ORDER BY created_at DESC"):
            (organization_id,) = args
            rows = [
                self._public(row)
                for row in self.programs.values()
                if row["organization_id"] == organization_id
            ]
            return sorted(rows, key=lambda row: row["created_at"], reverse=True)
        raise AssertionError(f"Unhandled SQL in fake store: {normalized!r}")

    def fetchrow(self, query: str, args: tuple[Any, ...]) -> dict[str, Any] | None:
        normalized = " ".join(query.split())
        if normalized.startswith("INSERT INTO programs (id, name, therapeutic_area, description, organization_id) VALUES ($1, $2, $3, $4, $5) RETURNING id, name, therapeutic_area, description, status, created_at"):
            program_id, name, therapeutic_area, description, organization_id = args
            created_at = self._created_at + timedelta(minutes=len(self.programs))
            row = {
                "id": str(program_id),
                "name": name,
                "therapeutic_area": therapeutic_area,
                "description": description,
                "status": "active",
                "created_at": created_at,
                "organization_id": organization_id,
            }
            self.programs[str(program_id)] = row
            return self._public(row)
        if normalized.startswith("UPDATE programs SET status = $2, updated_at = NOW() WHERE id = $1 RETURNING id, name, therapeutic_area, description, status, created_at"):
            program_id, status = args
            row = self.programs.get(str(program_id))
            if row is None:
                return None
            row["status"] = status
            return self._public(row)
        raise AssertionError(f"Unhandled SQL in fake store: {normalized!r}")

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "therapeutic_area": row["therapeutic_area"],
            "description": row["description"],
            "status": row["status"],
            "created_at": row["created_at"],
        }


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, _ProgramStore]:
    store = _ProgramStore()
    pool = _FakePool(store)

    async def _get_pool() -> _FakePool:
        return pool

    monkeypatch.setattr(programs_api.db, "get_pool", _get_pool)

    app = FastAPI()
    app.include_router(programs_api.router, prefix="/api/v1")
    return TestClient(app), store


def test_list_programs_returns_default_org_programs(client: tuple[TestClient, _ProgramStore]) -> None:
    test_client, store = client
    store.seed_program(
        program_id="11111111-1111-1111-1111-111111111112",
        name="Newest Program",
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    store.seed_program(
        program_id="11111111-1111-1111-1111-111111111113",
        name="Older Program",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    store.seed_program(
        program_id="22222222-2222-2222-2222-222222222222",
        name="Other Org Program",
        organization_id="22222222-2222-2222-2222-222222222222",
    )

    response = test_client.get("/api/v1/programs")

    assert response.status_code == 200
    assert [program["id"] for program in response.json()] == [
        "11111111-1111-1111-1111-111111111112",
        "11111111-1111-1111-1111-111111111113",
    ]


def test_create_program_still_works(client: tuple[TestClient, _ProgramStore]) -> None:
    test_client, _store = client

    response = test_client.post(
        "/api/v1/programs",
        json={
            "name": "TNBC Program",
            "therapeutic_area": "Oncology",
            "description": "Triple-negative breast cancer",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "TNBC Program"
    assert response.json()["status"] == "active"


def test_patch_program_updates_status(client: tuple[TestClient, _ProgramStore]) -> None:
    test_client, store = client
    store.seed_program(
        program_id="11111111-1111-1111-1111-111111111114",
        name="Archive Me",
    )

    response = test_client.patch(
        "/api/v1/programs/11111111-1111-1111-1111-111111111114",
        json={"status": "archived"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "archived"
