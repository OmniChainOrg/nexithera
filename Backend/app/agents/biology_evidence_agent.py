# app/agents/biology_evidence_agent.py
"""Biology Evidence Agent (PR #11 — Clinical Forecaster).

Scores the strength of biological evidence supporting a candidate's
target-disease pair on a 0..1 scale.  The score is derived from
``evidence_edges`` linked to the candidate's target plus any prior
``Target Biology Agent`` runs.  When the evidence graph is empty the
agent falls back to a mid-range prior (0.5) rather than fabricating
supporting evidence.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.database import db
from .base_agent import BaseAgent


def _normalize_score(supporting: int, contradicting: int) -> float:
    """Smoothed (Laplace) win-rate of supporting vs contradicting edges."""
    total = supporting + contradicting
    if total == 0:
        return 0.5
    return round((supporting + 1) / (total + 2), 4)


class BiologyEvidenceAgent(BaseAgent):
    """Score biology evidence strength for a candidate-disease pair."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id, "Biology Evidence Agent", "clinical_biology"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "Biology Evidence Agent requires candidate_id input"
            )

        supporting = 0
        contradicting = 0
        target_label: Optional[str] = inputs.get("target_label")
        evidence_examples: List[Dict[str, Any]] = []

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT target_id FROM candidates WHERE id = $1",
                candidate_id,
            )
            if not row:
                raise ValueError(f"Candidate not found: {candidate_id}")
            target_id = row["target_id"]

            if target_id is not None:
                edges = await conn.fetch(
                    """SELECT relation_type, confidence
                       FROM evidence_edges
                       WHERE source_id = $1 OR target_id = $1
                       LIMIT 200""",
                    target_id,
                )
                for edge in edges:
                    relation = (edge["relation_type"] or "").lower()
                    if "support" in relation or "associated" in relation:
                        supporting += 1
                    elif "contradict" in relation or "refute" in relation:
                        contradicting += 1
                    if len(evidence_examples) < 5:
                        evidence_examples.append(
                            {
                                "relation": edge["relation_type"],
                                "confidence": edge["confidence"],
                            }
                        )

            if target_label is None and target_id is not None:
                trow = await conn.fetchrow(
                    "SELECT name FROM bio_entities WHERE id = $1",
                    target_id,
                )
                target_label = trow["name"] if trow else None

        score = _normalize_score(supporting, contradicting)
        confidence = round(
            0.4 + min(0.5, 0.02 * (supporting + contradicting)), 3
        )
        rationale = (
            f"{supporting} supporting vs {contradicting} contradicting "
            f"evidence edges for target {target_label or 'unknown'} -> "
            f"biology_score={score}."
        )

        return {
            "summary": rationale,
            "structure": {
                "candidate_id": candidate_id,
                "target_label": target_label,
                "biology_score": score,
                "supporting_edges": supporting,
                "contradicting_edges": contradicting,
                "evidence_examples": evidence_examples,
            },
            "confidence": confidence,
            "uncertainty_reason": (
                None
                if (supporting + contradicting) >= 5
                else "Sparse evidence graph; biology score is a weak prior"
            ),
            "recommended_next_step": (
                "Strengthen biology evidence via additional literature "
                "mining or mechanistic in vitro work."
                if score < 0.6
                else "Biology evidence is sufficient to support next phase."
            ),
            "trace_summary": rationale,
        }
