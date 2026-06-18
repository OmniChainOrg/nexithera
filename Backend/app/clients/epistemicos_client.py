"""ChronoThera-specific async HTTP client for EpistemicOS connectivity.

This thin client handles the ChronoThera ↔ EpistemicOS integration:
- Fetching zone/CXU/swarm data for live epistemic traces
- Semantic search for formulation precedents (PK parameters)
- Posting formulation results back to epistemicos for feedback loop
- Health checks with short timeout

All methods raise ``EpistemicOSClientError`` on failure. Callers are
expected to catch this error and fall back to synthetic / heuristic data.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class EpistemicOSClientError(Exception):
    """Raised when the EpistemicOS API is unavailable or returns an error."""


class EpistemicOSClient:
    """Async HTTP client for ChronoThera → EpistemicOS integration.

    Configuration is read from environment variables so that no code change is
    needed to point the client at a real EpistemicOS instance:

    * ``EPISTEMICOS_API_URL``  – base URL  (default: ``http://localhost:8000``)
    * ``EPISTEMICOS_API_KEY``  – optional bearer token
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("EPISTEMICOS_API_URL", "http://localhost:8000")
        ).rstrip("/")
        self.api_key = api_key or os.getenv("EPISTEMICOS_API_KEY", "")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_client(self) -> httpx.AsyncClient:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
        )

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = self._build_client()
        return self._client

    async def close(self) -> None:
        """Release underlying HTTP connections."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return *True* if EpistemicOS is reachable, *False* otherwise.

        Uses a short timeout so callers are not blocked for long when the
        service is down.
        """
        client = self._build_client()
        client.timeout = httpx.Timeout(3.0)
        try:
            response = await client.get("/health")
            await client.aclose()
            return response.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.warning("EpistemicOS health check failed: %s", exc)
            await client.aclose()
            return False

    async def get_zone(
        self,
        zone_id: str,
        *,
        include_cxus: bool = True,
        include_swarm_metrics: bool = True,
    ) -> Dict[str, Any]:
        """Fetch zone data including optional CXU and swarm metric details.

        Args:
            zone_id: Identifier of the EpistemicOS zone to query.
            include_cxus: When *True* the response contains CXU sub-objects.
            include_swarm_metrics: When *True* the response contains swarm
                aggregated metrics.

        Returns:
            Zone payload dict as returned by EpistemicOS.

        Raises:
            EpistemicOSClientError: On timeout, network error, or HTTP error.
        """
        try:
            client = self._get_client()
            response = await client.get(
                f"/v1/zones/{zone_id}",
                params={
                    "include_cxus": str(include_cxus).lower(),
                    "include_swarm_metrics": str(include_swarm_metrics).lower(),
                },
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
            logger.info("epistemicos get_zone(%s) → success", zone_id)
            return data
        except httpx.TimeoutException as exc:
            raise EpistemicOSClientError(
                f"Timeout fetching zone '{zone_id}': {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise EpistemicOSClientError(
                f"HTTP {exc.response.status_code} fetching zone '{zone_id}': {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise EpistemicOSClientError(
                f"Network error fetching zone '{zone_id}': {exc}"
            ) from exc

    async def search_precedent(
        self,
        query: str,
        *,
        embedding_lane: str = "formulation",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search for similar formulation precedents.

        Args:
            query: Natural-language description of the formulation (e.g.
                ``"sustained release SC peptide PLGA depot"``).
            embedding_lane: EpistemicOS embedding lane to search in.
            limit: Maximum number of precedent records to return.

        Returns:
            List of precedent dicts; each matches ``PrecedentRecord`` schema.

        Raises:
            EpistemicOSClientError: On timeout, network error, or HTTP error.
        """
        try:
            client = self._get_client()
            response = await client.post(
                "/v1/precedents/search",
                json={
                    "query": query,
                    "embedding_lane": embedding_lane,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            payload: Dict[str, Any] = response.json()
            records: List[Dict[str, Any]] = payload.get("results", [])
            logger.info(
                "epistemicos search_precedent(%r) → %d results", query, len(records)
            )
            return records
        except httpx.TimeoutException as exc:
            raise EpistemicOSClientError(
                f"Timeout searching precedents for '{query}': {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise EpistemicOSClientError(
                f"HTTP {exc.response.status_code} searching precedents: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise EpistemicOSClientError(
                f"Network error searching precedents: {exc}"
            ) from exc

    async def post_formulation_result(
        self,
        zone_id: str,
        simulation_id: str,
        *,
        asset_id: Optional[str] = None,
        overall_score: int,
        epistemicos_status: str,
        scorecard_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Post a completed ChronoThera simulation result to EpistemicOS.

        This closes the feedback loop: EpistemicOS can use the outcome to
        update zone knowledge and improve future precedent searches.

        Args:
            zone_id: Target EpistemicOS zone to receive the result.
            simulation_id: ChronoThera simulation identifier.
            asset_id: Optional asset identifier for provenance tagging.
            overall_score: Overall ChronoThera readiness score (0–100).
            epistemicos_status: Query status string (``"success"`` |
                ``"fallback"`` | ``"unavailable"``).
            scorecard_summary: Optional dict of dimension → score pairs.

        Returns:
            Confirmation payload from EpistemicOS.

        Raises:
            EpistemicOSClientError: On timeout, network error, or HTTP error.
        """
        try:
            client = self._get_client()
            body: Dict[str, Any] = {
                "zone_id": zone_id,
                "simulation_id": simulation_id,
                "asset_id": asset_id,
                "overall_score": overall_score,
                "epistemicos_status": epistemicos_status,
                "source": "chronothera",
            }
            if scorecard_summary:
                body["scorecard_summary"] = scorecard_summary
            response = await client.post("/v1/formulation-results", json=body)
            response.raise_for_status()
            result: Dict[str, Any] = response.json()
            logger.info(
                "epistemicos post_formulation_result(%s) → success", simulation_id
            )
            return result
        except httpx.TimeoutException as exc:
            raise EpistemicOSClientError(
                f"Timeout posting result for '{simulation_id}': {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise EpistemicOSClientError(
                f"HTTP {exc.response.status_code} posting result: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise EpistemicOSClientError(
                f"Network error posting result: {exc}"
            ) from exc
