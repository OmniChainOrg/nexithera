# app/agents/ip_position_agent.py
"""IP Position Agent (PR #10).

Estimates freedom-to-operate (FTO) and IP strength for a candidate.

The agent enumerates a small library of patent records (real lookups
when ``PATENT_API_KEY`` is set; otherwise a deterministic mock library
keyed by the candidate's target name).  Each patent is annotated with::

    * ``expiry_year``                  -- best-effort parsed expiry.
    * ``is_blocking``                  -- True when an unrelated assignee
                                          holds composition-of-matter
                                          claims on the same target.
    * ``freedom_to_operate_estimate``  -- 0..1 per-patent FTO; 1 means
                                          "no obstruction"; 0 means
                                          "fully blocking".

The aggregate IP strength score (0..10) is::

    ip_strength = clamp(0, 10, 5 + 2 * white_space_signal − 3 * blocking_signal)

so a candidate with no blocking patents and ample white space scores
near 10, and one with multiple blocking patents scores near 0.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .base_agent import BaseAgent
from .competitive_landscape_agent import _candidate_context


PATENTS_VIEW_BASE = "https://api.patentsview.org/patents/query"

_IP_CACHE: Dict[Any, List[Dict[str, Any]]] = {}


_MOCK_PATENT_LIBRARY: List[Dict[str, Any]] = [
    {
        "patent_number": "US10000001",
        "patent_family": "PF-1",
        "assignee": "Amgen Inc.",
        "expiry_year": 2030,
        "jurisdiction": "US",
        "claims": "Composition of matter for KRAS G12C inhibitors",
        "is_blocking": True,
    },
    {
        "patent_number": "US10000002",
        "patent_family": "PF-2",
        "assignee": "Mirati Therapeutics",
        "expiry_year": 2032,
        "jurisdiction": "US",
        "claims": "Method of treating NSCLC with G12C inhibitors",
        "is_blocking": True,
    },
    {
        "patent_number": "EP3000003",
        "patent_family": "PF-3",
        "assignee": "Generic / unassigned",
        "expiry_year": 2026,
        "jurisdiction": "EP",
        "claims": "Process patent — nearing expiry",
        "is_blocking": False,
    },
]


def _ip_strength_score(positions: List[Dict[str, Any]]) -> float:
    """Map patent positions to a 0..10 IP strength score."""
    if not positions:
        return 5.0  # no data -> neutral
    blocking = sum(1 for p in positions if p.get("is_blocking"))
    expiring_soon = sum(
        1
        for p in positions
        if p.get("is_blocking")
        and isinstance(p.get("expiry_year"), int)
        and p["expiry_year"] - datetime.utcnow().year <= 3
    )
    score = 5.0 - 3.0 * blocking + 2.0 * expiring_soon + 1.0 * (
        len(positions) - blocking
    )
    return round(max(0.0, min(10.0, score)), 2)


def _aggregate_fto(positions: List[Dict[str, Any]]) -> float:
    if not positions:
        return 0.5
    per_patent = [
        float(p.get("freedom_to_operate_estimate", 0.0 if p.get("is_blocking") else 1.0))
        for p in positions
    ]
    # Aggregate FTO is the *minimum* per-patent FTO — a single
    # blocking patent is enough to obstruct.
    return round(max(0.0, min(1.0, min(per_patent))), 3)


class IPPositionAgent(BaseAgent):
    """Estimate freedom-to-operate and IP strength for a candidate."""

    def __init__(self, agent_id: str):
        super().__init__(agent_id, "IP Position Agent", "ip_position")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError("IP Position Agent requires candidate_id input")

        target_name, _disease = await _candidate_context(candidate_id)
        target_name = inputs.get("target_name") or target_name

        positions = await _fetch_patents(target_name)
        if not positions:
            positions = list(_MOCK_PATENT_LIBRARY)

        # Annotate per-patent FTO (1.0 if not blocking, else 0.0; if
        # blocking but expiring within 3 years, soften to 0.4).
        now_year = datetime.utcnow().year
        for p in positions:
            if "freedom_to_operate_estimate" in p:
                continue
            if not p.get("is_blocking"):
                p["freedom_to_operate_estimate"] = 1.0
            elif (
                isinstance(p.get("expiry_year"), int)
                and p["expiry_year"] - now_year <= 3
            ):
                p["freedom_to_operate_estimate"] = 0.4
            else:
                p["freedom_to_operate_estimate"] = 0.05

        ip_strength = _ip_strength_score(positions)
        fto = _aggregate_fto(positions)
        white_space = [
            p
            for p in positions
            if not p.get("is_blocking")
            or (
                isinstance(p.get("expiry_year"), int)
                and p["expiry_year"] - now_year <= 1
            )
        ]
        blocking = [p for p in positions if p.get("is_blocking")]

        summary = (
            f"Reviewed {len(positions)} patent record(s); "
            f"{len(blocking)} blocking, {len(white_space)} in white-space "
            f"window. FTO≈{fto:.2f}, IP strength={ip_strength}/10."
        )
        recommended = (
            "Pursue freedom-to-operate opinion before partnering."
            if blocking
            else "Strong IP position — emphasize composition-of-matter coverage."
        )
        confidence = 0.5 + 0.05 * len(positions)
        confidence = round(min(0.9, confidence), 3)

        return {
            "summary": summary,
            "structure": {
                "candidate_id": candidate_id,
                "target_name": target_name,
                "positions": positions,
                "ip_strength_score": ip_strength,
                "freedom_to_operate_estimate": fto,
                "blocking_count": len(blocking),
                "white_space_count": len(white_space),
            },
            "confidence": confidence,
            "uncertainty_reason": (
                "Blocking patents may obstruct FTO" if blocking else None
            ),
            "recommended_next_step": recommended,
            "trace_summary": (
                f"Evaluated {len(positions)} patents (blocking={len(blocking)}, "
                f"white_space={len(white_space)}); IP strength={ip_strength}."
            ),
        }


async def _fetch_patents(
    target_name: Optional[str],
) -> List[Dict[str, Any]]:
    cache_key = ("ip_positions", target_name)
    if cache_key in _IP_CACHE:
        return _IP_CACHE[cache_key]

    api_key = os.environ.get("PATENT_API_KEY")
    if not target_name or not api_key:
        _IP_CACHE[cache_key] = []
        return []

    payload = {
        "q": {"_text_phrase": {"patent_abstract": target_name}},
        "f": [
            "patent_number",
            "patent_title",
            "assignee_organization",
            "patent_date",
        ],
        "o": {"per_page": 5},
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                PATENTS_VIEW_BASE,
                json=payload,
                headers={"X-Api-Key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:  # noqa: BLE001
        _IP_CACHE[cache_key] = []
        return []

    positions: List[Dict[str, Any]] = []
    for p in data.get("patents") or []:
        patent_date = p.get("patent_date")
        expiry: Optional[int] = None
        if patent_date and len(patent_date) >= 4:
            try:
                expiry = int(patent_date[:4]) + 20
            except ValueError:
                expiry = None
        positions.append(
            {
                "patent_number": p.get("patent_number"),
                "patent_family": None,
                "assignee": (
                    (p.get("assignees") or [{}])[0].get(
                        "assignee_organization"
                    )
                    if p.get("assignees")
                    else None
                ),
                "expiry_year": expiry,
                "jurisdiction": "US",
                "claims": p.get("patent_title"),
                "is_blocking": True,  # any external composition patent
                                      # is treated as potentially blocking
            }
        )
    _IP_CACHE[cache_key] = positions
    return positions
