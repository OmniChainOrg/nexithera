# app/agents/ind_readiness_agent.py
"""IND Readiness Agent (PR #10).

Compares a candidate against the ``ind_readiness_items`` checklist
(seeded by migration 010) and returns::

    * per-item statuses (pulled from ``candidate_ind_readiness``;
      defaults to ``not_started`` when no row exists),
    * the overall readiness fraction = complete / required,
    * the list of critical gaps (required items that are not yet
      ``complete`` or ``waived``),
    * an estimated timeline-to-IND in months (heuristic: 2 months per
      open critical item, capped at 36).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.database import db
from .base_agent import BaseAgent


_COMPLETE_STATUSES = {"complete", "waived"}


def _estimate_timeline_months(open_required: int) -> int:
    return min(36, max(0, 2 * open_required))


def _readiness_score(fraction: float) -> float:
    """Map a readiness fraction (0..1) to a 0..10 score."""
    return round(max(0.0, min(10.0, 10.0 * fraction)), 2)


class INDReadinessAgent(BaseAgent):
    """Assess progress toward an IND filing."""

    def __init__(self, agent_id: str):
        super().__init__(agent_id, "IND Readiness Agent", "ind_readiness")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "IND Readiness Agent requires candidate_id input"
            )

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            candidate = await conn.fetchrow(
                "SELECT id, name FROM candidates WHERE id = $1",
                candidate_id,
            )
            if not candidate:
                raise ValueError(f"Candidate not found: {candidate_id}")

            rows = await conn.fetch(
                """
                SELECT i.id AS item_id,
                       i.category,
                       i.item,
                       i.description,
                       i.is_required,
                       cir.status,
                       cir.evidence_uri,
                       cir.notes,
                       cir.updated_at
                  FROM ind_readiness_items i
             LEFT JOIN candidate_ind_readiness cir
                    ON cir.checklist_item_id = i.id
                   AND cir.candidate_id = $1
              ORDER BY i.category, i.item
                """,
                candidate_id,
            )

        items: List[Dict[str, Any]] = []
        items_complete = 0
        items_total = 0
        critical_gaps: List[str] = []
        by_category: Dict[str, Dict[str, int]] = {}

        for row in rows:
            status = row["status"] or "not_started"
            is_required = bool(row["is_required"])
            cat = row["category"]
            cat_bucket = by_category.setdefault(
                cat, {"total": 0, "complete": 0, "required": 0}
            )
            cat_bucket["total"] += 1
            if is_required:
                cat_bucket["required"] += 1
                items_total += 1
                if status in _COMPLETE_STATUSES:
                    items_complete += 1
                    cat_bucket["complete"] += 1
                else:
                    critical_gaps.append(f"{cat}: {row['item']}")
            elif status in _COMPLETE_STATUSES:
                cat_bucket["complete"] += 1
            items.append(
                {
                    "item_id": str(row["item_id"]),
                    "category": cat,
                    "item": row["item"],
                    "description": row["description"],
                    "is_required": is_required,
                    "status": status,
                    "evidence_uri": row["evidence_uri"],
                    "notes": row["notes"],
                    "updated_at": (
                        row["updated_at"].isoformat()
                        if row["updated_at"] is not None
                        else None
                    ),
                }
            )

        overall_readiness = (
            items_complete / items_total if items_total else 0.0
        )
        score = _readiness_score(overall_readiness)
        timeline_months = _estimate_timeline_months(
            items_total - items_complete
        )

        if not items:
            summary = (
                "IND checklist is empty — run migration 010 to seed "
                "ind_readiness_items."
            )
            recommended = "Seed the IND checklist before assessment."
            confidence = 0.3
        elif critical_gaps:
            summary = (
                f"IND readiness {overall_readiness:.0%} "
                f"({items_complete}/{items_total} required items complete); "
                f"{len(critical_gaps)} critical gap(s); "
                f"~{timeline_months} months to IND."
            )
            recommended = (
                "Address critical gaps in priority order: "
                + "; ".join(critical_gaps[:3])
            )
            confidence = round(0.4 + 0.5 * overall_readiness, 3)
        else:
            summary = (
                f"All {items_total} required IND items complete — "
                "candidate is IND-ready."
            )
            recommended = "Schedule pre-IND meeting and assemble IND package."
            confidence = 0.9

        return {
            "summary": summary,
            "structure": {
                "candidate_id": candidate_id,
                "overall_readiness": round(overall_readiness, 3),
                "ind_readiness_score": score,
                "items_complete": items_complete,
                "items_total": items_total,
                "critical_gaps": critical_gaps,
                "estimated_timeline_months": timeline_months,
                "by_category": by_category,
                "items": items,
            },
            "confidence": confidence,
            "uncertainty_reason": (
                "Critical gaps remain in the IND checklist"
                if critical_gaps
                else None
            ),
            "recommended_next_step": recommended,
            "trace_summary": (
                f"Reviewed {len(items)} checklist items; "
                f"{items_complete}/{items_total} required complete; "
                f"{len(critical_gaps)} gap(s)."
            ),
        }
