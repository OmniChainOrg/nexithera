"""PK parameter precedent adapter for ChronoThera release curve modulation.

Looks up pharmacokinetic (PK) parameters for a given API from EpistemicOS
formulation precedents, then falls back to deterministic heuristic defaults
when no precedent is available.

PK parameters returned:
- ``CL``    – clearance (L/h)
- ``V``     – volume of distribution (L)
- ``Tmax``  – time to peak concentration (h)
- ``F``     – bioavailability fraction (0–1)
- ``ka``    – absorption rate constant (h⁻¹)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..clients.epistemicos_client import EpistemicOSClient, EpistemicOSClientError
from ..schemas.calibration import PrecedentRecord

logger = logging.getLogger(__name__)

_DEFAULT_PK: Dict[str, float] = {
    "CL": 1.0,
    "V": 50.0,
    "Tmax": 2.0,
    "F": 0.8,
    "ka": 0.5,
}


class PKPrecedentAdapter:
    """Adapter that sources PK parameters from EpistemicOS precedents.

    Args:
        epistemicos_client: Optional ``EpistemicOSClient`` instance.  When
            *None* the adapter always falls back to heuristic defaults.
    """

    def __init__(
        self,
        epistemicos_client: Optional[EpistemicOSClient] = None,
    ) -> None:
        self._client = epistemicos_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def lookup_pk_parameters(
        self,
        api_name: str,
        formulation_objective: str,
        route: str,
    ) -> Dict[str, float]:
        """Return PK parameters for the given API / objective / route combination.

        Logic:
        1. If an EpistemicOS client is configured, perform a semantic search
           for similar formulation precedents.
        2. Average PK params across the top-3 precedents (by confidence).
        3. If no usable precedent is found, fall back to heuristic defaults.

        Args:
            api_name: Active pharmaceutical ingredient name.
            formulation_objective: ChronoThera objective key (e.g.
                ``"depot_formulation"``).
            route: Route of administration (e.g. ``"SC"``).

        Returns:
            Dict with keys ``CL``, ``V``, ``Tmax``, ``F``, ``ka``.
        """
        if self._client is None:
            return self._heuristic_pk_parameters(formulation_objective, route)

        query = (
            f"{api_name} {formulation_objective.replace('_', ' ')} "
            f"{route} formulation PK parameters"
        )
        try:
            raw_records = await self._client.search_precedent(
                query, embedding_lane="formulation", limit=5
            )
        except EpistemicOSClientError as exc:
            logger.warning(
                "PK precedent lookup failed (%s); using heuristic defaults.", exc
            )
            return self._heuristic_pk_parameters(formulation_objective, route)

        precedents = self._parse_precedents(raw_records)
        if not precedents:
            logger.info(
                "No PK precedents found for '%s'; using heuristic defaults.",
                api_name,
            )
            return self._heuristic_pk_parameters(formulation_objective, route)

        # Take top 3 by confidence and average their PK params
        top3 = sorted(precedents, key=lambda p: p.confidence, reverse=True)[:3]
        return self._average_pk_params([p.pk_parameters for p in top3])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_precedents(raw: List[Dict[str, Any]]) -> List[PrecedentRecord]:
        """Parse raw EpistemicOS search results into ``PrecedentRecord`` objects."""
        records: List[PrecedentRecord] = []
        for item in raw:
            try:
                rec = PrecedentRecord.model_validate(item)
                if rec.pk_parameters:
                    records.append(rec)
            except Exception:  # noqa: BLE001
                pass
        return records

    @staticmethod
    def _average_pk_params(
        param_list: List[Dict[str, float]],
    ) -> Dict[str, float]:
        """Average PK parameters across a list of parameter dicts."""
        if not param_list:
            return dict(_DEFAULT_PK)
        keys = ["CL", "V", "Tmax", "F", "ka"]
        result: Dict[str, float] = {}
        for k in keys:
            values = [p[k] for p in param_list if k in p]
            result[k] = sum(values) / len(values) if values else _DEFAULT_PK[k]
        return result

    def _heuristic_pk_parameters(
        self,
        formulation_objective: str,
        route: str,
    ) -> Dict[str, float]:
        """Return route/objective-adjusted heuristic PK defaults.

        Adjustments applied on top of ``_DEFAULT_PK``:
        - Depot / sustained release → delayed Tmax (slower absorption)
        - Half-life extension / pegylation → reduced CL (longer t½)
        - IV route → instant absorption (F=1, Tmax≈0)
        - Oral delayed release → slower absorption onset
        """
        params = dict(_DEFAULT_PK)

        if formulation_objective in {"depot_formulation", "sustained_release"}:
            params["Tmax"] = 6.0   # delayed peak
            params["ka"] = 0.2     # slow absorption

        if formulation_objective in {"half_life_extension", "pegylation_strategy"}:
            params["CL"] = 0.4     # reduced clearance → extended t½

        if route == "IV":
            params["F"] = 1.0      # complete bioavailability
            params["Tmax"] = 0.0   # bolus / infusion → instant
            params["ka"] = 10.0    # effectively instantaneous

        if formulation_objective == "oral_delayed_release":
            params["Tmax"] = 4.0   # delayed GI absorption
            params["ka"] = 0.3

        logger.info(
            "Heuristic PK parameters for objective='%s', route='%s': %s",
            formulation_objective,
            route,
            params,
        )
        return params
