# app/agents/gap_analysis_agent.py
"""Gap Analysis Agent (PR #9 — Active Learning + Evidence Gap Analysis).

Systematically scans the evidence graph for weaknesses that materially
affect active hypotheses and candidates::

    * ``missing_edge``               — entity pairs implied by an active
                                       hypothesis that have no direct
                                       evidence edge in the graph.
    * ``low_confidence``             — evidence edges with
                                       ``confidence < 0.5``.
    * ``contradiction_unresolved``   — edges flagged
                                       ``is_contradiction = TRUE`` that
                                       have no superseding higher-
                                       confidence edge between the same
                                       endpoints.

Each gap is scored by::

    severity = impact × uncertainty

where ``impact`` reflects how many active hypotheses/candidates are
touched by the entities involved, and ``uncertainty`` is the entropy of
the current belief (1 − |2c − 1|, peaks at c=0.5).  Severity is clamped
to ``[0, 1]`` and the agent never invents evidence.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.database import db
from .base_agent import BaseAgent


_LOW_CONFIDENCE_THRESHOLD = 0.5


def _binary_entropy(p: Optional[float]) -> float:
    """Shannon entropy (bits) of a Bernoulli belief with probability ``p``.

    Returns 1.0 (maximum uncertainty) when ``p`` is ``None`` so that
    completely-unknown states are treated as maximum uncertainty.  Clamps
    inputs into ``[0, 1]`` defensively.
    """
    if p is None:
        return 1.0
    p = max(0.0, min(1.0, float(p)))
    if p in (0.0, 1.0):
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def _uncertainty_from_confidence(confidence: Optional[float]) -> float:
    """Map a [0, 1] confidence to a [0, 1] uncertainty proxy.

    Uses ``1 - |2c - 1|`` so that ``c = 0.5`` (max ambiguity) yields
    ``1.0`` and the boundaries (``c=0`` or ``c=1``) yield ``0.0``.
    """
    if confidence is None:
        return 1.0
    c = max(0.0, min(1.0, float(confidence)))
    return 1.0 - abs(2.0 * c - 1.0)


class GapAnalysisAgent(BaseAgent):
    """Identify and score weaknesses in the evidence graph."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id,
            "Gap Analysis Agent",
            "gap_analysis",
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        program_id: Optional[str] = inputs.get("program_id")
        if not program_id:
            raise ValueError("Gap Analysis Agent requires program_id input")

        low_confidence_threshold: float = float(
            inputs.get("low_confidence_threshold")
            or _LOW_CONFIDENCE_THRESHOLD
        )

        gaps: List[Dict[str, Any]] = []

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            program = await conn.fetchrow(
                "SELECT id, therapeutic_area FROM programs WHERE id = $1",
                program_id,
            )
            if not program:
                raise ValueError(f"Program not found: {program_id}")

            # Active hypotheses for the program (anything that hasn't been
            # refuted/deprecated counts as "active" for gap impact scoring).
            hypotheses = await conn.fetch(
                """SELECT id, hypothesis_text, claim_type, confidence, status
                       FROM hypotheses
                       WHERE program_id = $1
                         AND status NOT IN ('refuted', 'deprecated')""",
                program_id,
            )
            active_hypothesis_ids: Set[str] = {str(h["id"]) for h in hypotheses}
            n_active_hypotheses = max(1, len(active_hypothesis_ids))

            # Build per-entity "impact" = number of active hypotheses that
            # cite an evidence edge touching that entity.
            entity_impact: Dict[str, int] = {}
            if active_hypothesis_ids:
                impact_rows = await conn.fetch(
                    """SELECT DISTINCT he.hypothesis_id,
                              e.source_id, e.target_id
                           FROM hypothesis_evidence he
                           JOIN evidence_edges e ON he.evidence_edge_id = e.id
                          WHERE he.hypothesis_id = ANY($1::uuid[])""",
                    list(active_hypothesis_ids),
                )
                for row in impact_rows:
                    for ent_id in (row["source_id"], row["target_id"]):
                        if ent_id is None:
                            continue
                        key = str(ent_id)
                        entity_impact[key] = entity_impact.get(key, 0) + 1

            # ----------------------------------------------------------
            # 1) Low-confidence edges.
            # ----------------------------------------------------------
            low_conf_rows = await conn.fetch(
                """SELECT e.id, e.source_id, e.target_id, e.predicate,
                          e.confidence, e.is_contradiction,
                          s.name AS source_name, s.entity_type AS source_type,
                          t.name AS target_name, t.entity_type AS target_type
                       FROM evidence_edges e
                       JOIN bio_entities s ON s.id = e.source_id
                       JOIN bio_entities t ON t.id = e.target_id
                      WHERE e.confidence < $1
                        AND NOT e.is_contradiction""",
                low_confidence_threshold,
            )
            for row in low_conf_rows:
                impact = (
                    entity_impact.get(str(row["source_id"]), 0)
                    + entity_impact.get(str(row["target_id"]), 0)
                ) / (2.0 * n_active_hypotheses)
                impact = min(1.0, impact)
                uncertainty = _uncertainty_from_confidence(row["confidence"])
                severity = round(max(0.0, min(1.0, impact * uncertainty)), 3)
                gaps.append(
                    {
                        "gap_type": "low_confidence",
                        "entity_type": row["source_type"],
                        "entity_id": str(row["source_id"]),
                        "related_entity_id": str(row["target_id"]),
                        "description": (
                            f"Low-confidence edge "
                            f"{row['source_name']} —[{row['predicate']}]→ "
                            f"{row['target_name']} "
                            f"(confidence={row['confidence']:.2f})."
                        ),
                        "severity": severity,
                        "impact": round(impact, 3),
                        "uncertainty": round(uncertainty, 3),
                        "edge_id": str(row["id"]),
                    }
                )

            # ----------------------------------------------------------
            # 2) Unresolved contradictions: contradiction edges that have
            #    no superseding non-contradiction edge with confidence
            #    >= 0.7 between the same endpoints.
            # ----------------------------------------------------------
            contradiction_rows = await conn.fetch(
                """
                SELECT e.id, e.source_id, e.target_id, e.predicate,
                       e.confidence,
                       s.name AS source_name, s.entity_type AS source_type,
                       t.name AS target_name
                FROM evidence_edges e
                JOIN bio_entities s ON s.id = e.source_id
                JOIN bio_entities t ON t.id = e.target_id
                WHERE e.is_contradiction = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM evidence_edges e2
                       WHERE e2.is_contradiction = FALSE
                         AND e2.confidence >= 0.7
                         AND ((e2.source_id = e.source_id
                               AND e2.target_id = e.target_id)
                              OR (e2.source_id = e.target_id
                                  AND e2.target_id = e.source_id))
                  )
                """,
            )
            for row in contradiction_rows:
                impact = (
                    entity_impact.get(str(row["source_id"]), 0)
                    + entity_impact.get(str(row["target_id"]), 0)
                ) / (2.0 * n_active_hypotheses)
                impact = min(1.0, max(impact, 0.5))  # contradictions always non-trivial
                uncertainty = _uncertainty_from_confidence(row["confidence"])
                severity = round(max(0.0, min(1.0, impact * uncertainty)), 3)
                gaps.append(
                    {
                        "gap_type": "contradiction_unresolved",
                        "entity_type": row["source_type"],
                        "entity_id": str(row["source_id"]),
                        "related_entity_id": str(row["target_id"]),
                        "description": (
                            f"Unresolved contradiction "
                            f"{row['source_name']} ↮ {row['target_name']} "
                            f"({row['predicate']})."
                        ),
                        "severity": severity,
                        "impact": round(impact, 3),
                        "uncertainty": round(uncertainty, 3),
                        "edge_id": str(row["id"]),
                    }
                )

            # ----------------------------------------------------------
            # 3) Missing edges: hypotheses with low confidence whose
            #    primary entities have no supporting evidence yet.
            # ----------------------------------------------------------
            for hyp in hypotheses:
                hyp_conf = hyp["confidence"]
                if hyp_conf is not None and hyp_conf >= 0.7:
                    continue
                hyp_id = str(hyp["id"])
                support_count = await conn.fetchval(
                    """SELECT COUNT(*) FROM hypothesis_evidence
                            WHERE hypothesis_id = $1""",
                    hyp_id,
                )
                if support_count and int(support_count) > 0:
                    continue
                uncertainty = _uncertainty_from_confidence(hyp_conf)
                # Hypothesis-level missing-edge gaps always touch one
                # active hypothesis directly.
                impact = 1.0 / n_active_hypotheses
                severity = round(
                    max(0.0, min(1.0, max(impact, 0.4) * uncertainty)),
                    3,
                )
                gaps.append(
                    {
                        "gap_type": "missing_edge",
                        "entity_type": "hypothesis",
                        "entity_id": None,
                        "related_entity_id": None,
                        "hypothesis_id": hyp_id,
                        "description": (
                            f"Hypothesis '{hyp['hypothesis_text'][:80]}…' "
                            f"has no evidence edges in the graph yet."
                        ),
                        "severity": severity,
                        "impact": round(impact, 3),
                        "uncertainty": round(uncertainty, 3),
                    }
                )

        gaps.sort(key=lambda g: g["severity"], reverse=True)
        high_severity = [g for g in gaps if g["severity"] >= 0.7]

        if gaps:
            top = gaps[0]
            summary = (
                f"Identified {len(gaps)} evidence gap(s); "
                f"{len(high_severity)} high-severity. "
                f"Top: {top['gap_type']} (severity={top['severity']:.2f})."
            )
            recommended = (
                "Run the Active Learning Agent to propose experiments "
                "that resolve the highest-severity gaps first."
            )
            confidence = max(0.4, 1.0 - top["severity"] * 0.5)
        else:
            summary = "No evidence gaps detected for this program."
            recommended = (
                "Continue ingesting evidence; re-run gap analysis after "
                "new literature is loaded."
            )
            confidence = 0.9

        trace_summary = (
            f"Scanned {len(low_conf_rows)} low-confidence edges, "
            f"{len(contradiction_rows)} contradictions, "
            f"{len(hypotheses)} active hypotheses; "
            f"reported {len(gaps)} gaps."
        )

        return {
            "summary": summary,
            "structure": {
                "program_id": program_id,
                "gaps": gaps,
                "gap_counts_by_type": _count_by_type(gaps),
                "high_severity_count": len(high_severity),
            },
            "confidence": round(confidence, 3),
            "uncertainty_reason": (
                "High-severity evidence gaps remain unresolved"
                if high_severity
                else None
            ),
            "recommended_next_step": recommended,
            "trace_summary": trace_summary,
        }


def _count_by_type(gaps: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for g in gaps:
        counts[g["gap_type"]] = counts.get(g["gap_type"], 0) + 1
    return counts
