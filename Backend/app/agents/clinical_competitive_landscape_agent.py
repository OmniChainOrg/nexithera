# app/agents/clinical_competitive_landscape_agent.py
"""Clinical Competitive Landscape Agent (PR #11 — Clinical Forecaster).

Variant of the PR #10 ``CompetitiveLandscapeAgent`` that focuses on the
*clinical* impact of competing assets and standard of care.  Returns a
0..1 ``competition_score`` (higher = less competitive threat to the
trial).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.database import db
from .base_agent import BaseAgent


_PHASE_WEIGHTS = {
    "approved": 1.0,
    "phase 3": 0.8,
    "phase iii": 0.8,
    "iii": 0.8,
    "phase 2": 0.5,
    "phase ii": 0.5,
    "ii": 0.5,
    "phase 1": 0.2,
    "phase i": 0.2,
    "i": 0.2,
}


def _phase_weight(phase: Optional[str]) -> float:
    if not phase:
        return 0.1
    return _PHASE_WEIGHTS.get(str(phase).strip().lower(), 0.3)


def competition_score(competitors: List[Dict[str, Any]]) -> float:
    """Return 0..1: 1 means no late-stage competition, 0 means crowded."""
    if not competitors:
        return 0.9
    pressure = 0.0
    for c in competitors:
        pressure += _phase_weight(c.get("phase"))
    # Map 0 pressure -> 1.0; pressure of 4 -> ~0.0.
    score = max(0.0, 1.0 - pressure / 4.0)
    return round(score, 4)


class ClinicalCompetitiveLandscapeAgent(BaseAgent):
    """Clinical-focused competitive landscape agent."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id,
            "Clinical Competitive Landscape Agent",
            "clinical_competitive_landscape",
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "Clinical Competitive Landscape Agent requires candidate_id"
            )

        competitors: List[Dict[str, Any]] = list(
            inputs.get("competitors") or []
        )

        if not competitors:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT asset_name, developer, phase, modality,
                              mechanism, threat_level
                         FROM competitive_assets
                         WHERE candidate_id = $1
                         ORDER BY created_at DESC LIMIT 50""",
                    candidate_id,
                )
                competitors = [dict(row) for row in rows]

        score = competition_score(competitors)
        summary = (
            f"competition_score={score} from {len(competitors)} "
            f"competing assets."
        )
        return {
            "summary": summary,
            "structure": {
                "candidate_id": candidate_id,
                "competition_score": score,
                "competitor_count": len(competitors),
                "competitors": competitors[:10],
            },
            "confidence": 0.6 if competitors else 0.45,
            "uncertainty_reason": (
                None
                if competitors
                else "No competitor data available; using optimistic prior"
            ),
            "recommended_next_step": (
                "Differentiate via biomarker / population enrichment to "
                "reduce clinical competition risk."
                if score < 0.5
                else "Competitive pressure is manageable for planned trial."
            ),
            "trace_summary": summary,
        }
