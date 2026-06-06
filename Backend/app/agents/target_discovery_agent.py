# app/agents/target_discovery_agent.py
"""Target Discovery Agent (PR #8 — Genovate Precog).

Scans the program's evidence graph for genes/proteins that look biologically
plausible for the program's disease area but are *under-supported* by
existing evidence (i.e. opportunity gaps).  For each candidate target we
compute::

    opportunity_score = (potential_impact * novelty) - evidence_strength

Where:

    * ``potential_impact`` is a proxy for pathway centrality / druggability,
      derived from the entity's outgoing/incoming edge count.
    * ``novelty`` rewards entities that are *not* yet strongly linked to the
      disease (low evidence_strength).
    * ``evidence_strength`` is the mean confidence of edges directly
      connecting the entity to the disease (0 when none exist).

The agent emits a ranked list of novel targets, each with a proposed
mechanistic hypothesis and a recommended next experiment.  It deliberately
does **not** reason about clinical trials, asset outcomes, or forecasting:
this is a preclinical-only signal.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.database import db
from .base_agent import BaseAgent


# Entity types we treat as druggable preclinical targets.
_TARGETABLE_ENTITY_TYPES = ("gene", "protein")


class TargetDiscoveryAgent(BaseAgent):
    """Find novel high-potential targets currently under-supported by evidence."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id,
            "Target Discovery Agent",
            "target_discovery",
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
            - program_id:    str (used to scope the disease and existing pipeline)
            - disease_name:  str (optional — defaults to program.therapeutic_area)
            - top_k:         int (max number of targets to rank, default 10)
        """
        program_id: Optional[str] = inputs.get("program_id")
        disease_name: Optional[str] = inputs.get("disease_name")
        top_k: int = int(inputs.get("top_k") or 10)

        if not program_id:
            raise ValueError("Target Discovery Agent requires program_id input")

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            program = await conn.fetchrow(
                "SELECT id, therapeutic_area FROM programs WHERE id = $1",
                program_id,
            )
            if not program:
                raise ValueError(f"Program not found: {program_id}")

            disease_name = disease_name or program["therapeutic_area"]

            # Targets already in the candidate pipeline — we exclude these from
            # discovery (we want *novel* opportunities).
            in_pipeline_rows = await conn.fetch(
                """SELECT DISTINCT target_id
                       FROM candidates
                       WHERE program_id = $1 AND target_id IS NOT NULL""",
                program_id,
            )
            in_pipeline_ids = {r["target_id"] for r in in_pipeline_rows}

            # Resolve the disease entity (if it exists in the graph).
            disease_entity = await conn.fetchrow(
                "SELECT id FROM bio_entities WHERE name = $1 LIMIT 1",
                disease_name,
            )
            disease_id = disease_entity["id"] if disease_entity else None

            # Pull all candidate targetable entities with a per-entity edge
            # count (proxy for pathway centrality / impact).
            candidate_rows = await conn.fetch(
                """
                SELECT b.id, b.name, b.entity_type,
                       COALESCE(out_edges.cnt, 0) + COALESCE(in_edges.cnt, 0)
                           AS edge_count
                FROM bio_entities b
                LEFT JOIN (
                    SELECT source_id, COUNT(*) AS cnt
                    FROM evidence_edges
                    WHERE NOT is_contradiction
                    GROUP BY source_id
                ) out_edges ON out_edges.source_id = b.id
                LEFT JOIN (
                    SELECT target_id, COUNT(*) AS cnt
                    FROM evidence_edges
                    WHERE NOT is_contradiction
                    GROUP BY target_id
                ) in_edges ON in_edges.target_id = b.id
                WHERE b.entity_type = ANY($1::text[])
                ORDER BY edge_count DESC
                LIMIT 200
                """,
                list(_TARGETABLE_ENTITY_TYPES),
            )

            # For each candidate target compute its evidence strength to the
            # disease (mean edge confidence; 0 when no direct edge exists).
            ranked: List[Dict[str, Any]] = []
            for row in candidate_rows:
                if row["id"] in in_pipeline_ids:
                    continue

                evidence_strength = 0.0
                supporting_edges: List[Dict[str, Any]] = []
                if disease_id is not None:
                    edge_rows = await conn.fetch(
                        """SELECT id, predicate, confidence
                               FROM evidence_edges
                               WHERE NOT is_contradiction
                                 AND ((source_id = $1 AND target_id = $2)
                                      OR (source_id = $2 AND target_id = $1))""",
                        row["id"],
                        disease_id,
                    )
                    if edge_rows:
                        evidence_strength = sum(
                            float(e["confidence"]) for e in edge_rows
                        ) / len(edge_rows)
                        supporting_edges = [
                            {
                                "edge_id": str(e["id"]),
                                "predicate": e["predicate"],
                                "confidence": float(e["confidence"]),
                            }
                            for e in edge_rows
                        ]

                # Normalise edge_count into a [0, 1] potential-impact proxy.
                # Edge counts in real biology are heavy-tailed; clip at 50.
                potential_impact = min(1.0, float(row["edge_count"]) / 50.0)

                # Novelty rewards weak existing disease-evidence (1.0 = no
                # direct evidence, 0.0 = already strongly established).
                novelty = 1.0 - evidence_strength

                opportunity_score = (
                    potential_impact * novelty
                ) - evidence_strength
                # Confidence in the *recommendation itself* — high when we
                # have some evidence to ground it but not so much that the
                # target is already established.
                confidence = round(
                    max(
                        0.0,
                        min(
                            1.0,
                            0.4 + 0.4 * potential_impact - 0.2 * evidence_strength,
                        ),
                    ),
                    3,
                )

                proposed_hypothesis = (
                    f"{row['name']} modulates a pathway implicated in "
                    f"{disease_name}; existing graph evidence is weak "
                    f"({evidence_strength:.2f}) despite high pathway "
                    f"centrality ({potential_impact:.2f})."
                )

                if potential_impact >= 0.6:
                    recommended_experiment = (
                        f"In-vitro knockdown of {row['name']} in a "
                        f"{disease_name} cell-line panel with phenotypic readout."
                    )
                elif potential_impact >= 0.3:
                    recommended_experiment = (
                        f"Pathway-enrichment analysis linking {row['name']} "
                        f"to known {disease_name} mechanisms, then a small "
                        f"CRISPR screen."
                    )
                else:
                    recommended_experiment = (
                        f"Literature mining + co-expression analysis to "
                        f"establish a baseline {row['name']}–{disease_name} link."
                    )

                ranked.append(
                    {
                        "target_id": str(row["id"]),
                        "target_name": row["name"],
                        "entity_type": row["entity_type"],
                        "score": round(opportunity_score, 3),
                        "potential_impact": round(potential_impact, 3),
                        "novelty": round(novelty, 3),
                        "evidence_strength": round(evidence_strength, 3),
                        "confidence": confidence,
                        "proposed_hypothesis": proposed_hypothesis,
                        "supporting_evidence": supporting_edges,
                        "recommended_next_experiment": recommended_experiment,
                    }
                )

        ranked.sort(key=lambda t: t["score"], reverse=True)
        ranked = ranked[:top_k]

        if ranked:
            top = ranked[0]
            summary = (
                f"Identified {len(ranked)} novel target candidate(s) for "
                f"{disease_name}; top opportunity: "
                f"{top['target_name']} (score={top['score']:.2f})."
            )
            recommended_next_step = (
                f"Promote {top['target_name']} to hypothesis stage and run "
                f"a Target Biology assessment."
            )
            confidence = max(t["confidence"] for t in ranked)
            uncertainty_reason = None
        else:
            summary = (
                f"No under-supported targetable entities found for "
                f"{disease_name}. Consider expanding the evidence graph "
                f"(e.g. ingest new literature) or relaxing entity-type filter."
            )
            recommended_next_step = (
                "Ingest additional evidence sources for this program."
            )
            confidence = 0.2
            uncertainty_reason = "Empty or sparse evidence graph for program"

        trace_summary = (
            f"Scanned {len(candidate_rows)} targetable entities; "
            f"excluded {len(in_pipeline_ids)} already in pipeline; "
            f"returned top {len(ranked)} by opportunity score."
        )

        return {
            "summary": summary,
            "structure": {
                "program_id": program_id,
                "disease_name": disease_name,
                "ranked_targets": ranked,
                "scanned_entities": len(candidate_rows),
                "excluded_in_pipeline": len(in_pipeline_ids),
            },
            "confidence": confidence,
            "uncertainty_reason": uncertainty_reason,
            "recommended_next_step": recommended_next_step,
            "trace_summary": trace_summary,
        }
