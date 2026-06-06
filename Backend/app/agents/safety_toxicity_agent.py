# app/agents/safety_toxicity_agent.py
"""Safety & Toxicity Agent (PR #11 — Clinical Forecaster).

Returns a 0..1 ``safety_score`` (higher = safer) for the candidate.
Inputs come from:

    * the candidate's ``scorecards.safety_score`` (0..10) when present,
    * recent ``safety_check`` agent runs,
    * caller-provided ``known_safety_flags`` (list of strings).

The score is computed as a clamped affine combination of the scorecard
value and any explicit flags.  No flags + missing scorecard yields a
mid-range 0.6 prior (consistent with typical clinical safety attrition
of ~30-40% at Phase I).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.database import db
from .base_agent import BaseAgent


# Mechanism-based flags + their additive penalties (0..1 scale).
_FLAG_PENALTIES = {
    "herg_liability": 0.15,
    "genotoxicity": 0.20,
    "hepatotoxicity": 0.20,
    "cardiotoxicity": 0.15,
    "immunogenicity": 0.10,
    "cytokine_release": 0.15,
    "off_target_kinase": 0.10,
    "narrow_therapeutic_index": 0.15,
}


def _scorecard_to_safety(score_10: Optional[float]) -> float:
    if score_10 is None:
        return 0.6
    return round(max(0.0, min(1.0, float(score_10) / 10.0)), 4)


def _apply_flags(base: float, flags: List[str]) -> float:
    penalty = 0.0
    for flag in flags or []:
        penalty += _FLAG_PENALTIES.get(flag, 0.05)
    return round(max(0.0, min(1.0, base - penalty)), 4)


class SafetyToxicityAgent(BaseAgent):
    """Estimate probability of safety-related trial success."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id, "Safety Toxicity Agent", "clinical_safety"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "Safety Toxicity Agent requires candidate_id input"
            )
        flags: List[str] = list(inputs.get("known_safety_flags") or [])

        scorecard_score: Optional[float] = inputs.get("safety_scorecard")
        if scorecard_score is None:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT safety_score FROM scorecards
                        WHERE candidate_id = $1
                        ORDER BY scored_at DESC LIMIT 1""",
                    candidate_id,
                )
                if row and row["safety_score"] is not None:
                    scorecard_score = float(row["safety_score"])

        base = _scorecard_to_safety(scorecard_score)
        score = _apply_flags(base, flags)

        rationale = (
            f"Safety scorecard {scorecard_score!r} -> base {base}; "
            f"flags={flags} -> safety_score={score}."
        )
        return {
            "summary": rationale,
            "structure": {
                "candidate_id": candidate_id,
                "safety_score": score,
                "base_score": base,
                "flags": flags,
                "scorecard_safety": scorecard_score,
            },
            "confidence": round(0.5 + 0.05 * len(flags), 3) if flags else 0.55,
            "uncertainty_reason": (
                None
                if flags or scorecard_score is not None
                else "No scorecard or explicit safety flags; using prior"
            ),
            "recommended_next_step": (
                "Run additional in vitro / in vivo tox to retire flagged "
                "liabilities."
                if score < 0.6
                else "Safety profile is acceptable for the planned phase."
            ),
            "trace_summary": rationale,
        }
