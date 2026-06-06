# app/services/active_learning_service.py
"""Persistence + orchestration for PR #9 active-learning entities.

Wraps the Gap Analysis Agent, the Active Learning Agent, and the
``evidence_gaps`` / ``proposed_experiments`` / ``experiment_outcomes``
tables.  The service also closes the feedback loop: when an outcome is
recorded, hypothesis confidence is recomputed and ``pipeline_service``
is asked to re-evaluate the candidate's status.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from ..agents.active_learning_agent import (
    EXPERIMENT_TEMPLATES,
    ActiveLearningAgent,
)
from ..agents.gap_analysis_agent import GapAnalysisAgent
from ..core.database import db
from .pipeline_service import pipeline_service


_TEMPLATE_IDS = {t["id"] for t in EXPERIMENT_TEMPLATES}


class ActiveLearningService:
    """Service layer for evidence gaps + active-learning experiments."""

    # ------------------------------------------------------------------
    # Gap analysis
    # ------------------------------------------------------------------
    async def run_gap_analysis(
        self,
        program_id: str,
        low_confidence_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run the Gap Analysis Agent, persist gaps, return a summary."""
        agent_id = await _ensure_agent_record(
            "Gap Analysis Agent", "gap_analysis"
        )
        agent = GapAnalysisAgent(agent_id)
        result = await agent.run(
            program_id=program_id,
            inputs={
                "program_id": program_id,
                "low_confidence_threshold": low_confidence_threshold,
            },
            run_type="gap_analysis",
        )

        gaps_in = (
            (result.get("output") or {}).get("structure", {}) or {}
        ).get("gaps", [])
        run_id = result["run_id"]

        gaps_persisted: List[Dict[str, Any]] = []
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            for gap in gaps_in:
                gap_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO evidence_gaps
                            (id, program_id, entity_type, entity_id,
                             related_entity_id, hypothesis_id, gap_type,
                             description, severity,
                             estimated_information_gain, agent_run_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                    gap_id,
                    program_id,
                    gap.get("entity_type"),
                    _coerce_uuid(gap.get("entity_id")),
                    _coerce_uuid(gap.get("related_entity_id")),
                    _coerce_uuid(gap.get("hypothesis_id")),
                    gap["gap_type"],
                    gap.get("description"),
                    float(gap["severity"]),
                    None,  # information gain is filled by next-experiments
                    run_id,
                )
                stored = dict(gap)
                stored["id"] = gap_id
                gaps_persisted.append(stored)

        high = [g for g in gaps_persisted if g["severity"] >= 0.7]
        return {
            "run_id": run_id,
            "program_id": program_id,
            "gaps_found": len(gaps_persisted),
            "high_severity_gaps": len(high),
            "gaps": gaps_persisted,
            "summary": (result.get("output") or {}).get("summary"),
            "recommended_next_step": (
                (result.get("output") or {}).get("recommended_next_step")
            ),
        }

    # ------------------------------------------------------------------
    # Active learning
    # ------------------------------------------------------------------
    async def propose_next_experiments(
        self,
        program_id: str,
        max_experiments: int = 10,
        include_cost: bool = True,
        gaps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run the Active Learning Agent, persist experiments, return rows."""
        # Pull unresolved persisted gaps when none were supplied.
        if gaps is None:
            gaps = await self.list_open_gaps(program_id)

        agent_id = await _ensure_agent_record(
            "Active Learning Agent", "active_learning"
        )
        agent = ActiveLearningAgent(agent_id)
        result = await agent.run(
            program_id=program_id,
            inputs={
                "program_id": program_id,
                "max_experiments": max_experiments,
                "include_cost": include_cost,
                "gaps": gaps,
            },
            run_type="active_learning",
        )
        experiments = (
            (result.get("output") or {}).get("structure", {}) or {}
        ).get("experiments", [])
        run_id = result["run_id"]

        # Hard guard: no experiment may slip through without a registered
        # template id (acceptance criterion: no hallucinated experiments).
        for exp in experiments:
            if exp.get("template_id") not in _TEMPLATE_IDS:
                raise ValueError(
                    f"Active Learning Agent emitted an unknown template "
                    f"id: {exp.get('template_id')!r}"
                )

        persisted: List[Dict[str, Any]] = []
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            for exp in experiments:
                exp_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO proposed_experiments
                            (id, program_id, hypothesis_id, gap_id,
                             agent_run_id, experiment_type, template_id,
                             description, expected_outcomes,
                             prior_entropy, expected_posterior_entropy,
                             information_gain, cost_estimate,
                             duration_days, value_per_unit_cost,
                             priority, status)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                               $13,$14,$15,$16,'proposed')""",
                    exp_id,
                    program_id,
                    _coerce_uuid(exp.get("hypothesis_id")),
                    _coerce_uuid(exp.get("gap_id")),
                    run_id,
                    exp["experiment_type"],
                    exp["template_id"],
                    exp["description"],
                    json.dumps(exp.get("expected_outcomes", {})),
                    exp.get("prior_entropy"),
                    exp.get("expected_posterior_entropy"),
                    float(exp["information_gain"]),
                    exp.get("cost_estimate"),
                    exp.get("duration_days"),
                    exp.get("value_per_unit_cost"),
                    int(exp["priority"]),
                )
                stored = dict(exp)
                stored["id"] = exp_id
                stored["status"] = "proposed"
                persisted.append(stored)

        return {
            "run_id": run_id,
            "program_id": program_id,
            "experiments": persisted,
            "ranking_mode": (
                "value_per_unit_cost" if include_cost else "information_gain"
            ),
            "summary": (result.get("output") or {}).get("summary"),
            "recommended_next_step": (
                (result.get("output") or {}).get("recommended_next_step")
            ),
        }

    # ------------------------------------------------------------------
    # Outcome recording (closes the active-learning loop)
    # ------------------------------------------------------------------
    async def record_outcome(
        self,
        experiment_id: str,
        result_summary: Optional[str],
        result_data: Optional[Dict[str, Any]],
        updated_confidence: Optional[float],
        conducted_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record the outcome of a proposed experiment and update beliefs.

        * Inserts an ``experiment_outcomes`` row.
        * Updates the linked hypothesis' confidence (if any).
        * Marks any linked gap as ``resolved``.
        * Re-evaluates pipeline status for any candidates linked via
          ``candidate_hypotheses`` so promotion/kill thresholds fire.
        """
        if updated_confidence is not None:
            updated_confidence = max(0.0, min(1.0, float(updated_confidence)))

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            experiment = await conn.fetchrow(
                "SELECT * FROM proposed_experiments WHERE id = $1",
                experiment_id,
            )
            if not experiment:
                raise ValueError(f"Proposed experiment not found: {experiment_id}")

            prior_confidence: Optional[float] = None
            hypothesis_id = experiment["hypothesis_id"]
            if hypothesis_id:
                row = await conn.fetchrow(
                    "SELECT confidence FROM hypotheses WHERE id = $1",
                    hypothesis_id,
                )
                if row:
                    prior_confidence = (
                        float(row["confidence"])
                        if row["confidence"] is not None
                        else None
                    )

            information_gain_observed: Optional[float] = None
            if (
                prior_confidence is not None
                and updated_confidence is not None
            ):
                # Reduction in Bernoulli entropy is the realised info gain.
                from ..agents.active_learning_agent import binary_entropy

                information_gain_observed = round(
                    max(
                        0.0,
                        binary_entropy(prior_confidence)
                        - binary_entropy(updated_confidence),
                    ),
                    4,
                )

            outcome_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO experiment_outcomes
                        (id, proposed_experiment_id, conducted_by,
                         result_summary, result_data, prior_confidence,
                         updated_confidence, information_gain_observed)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                outcome_id,
                experiment_id,
                _coerce_uuid(conducted_by),
                result_summary,
                json.dumps(result_data or {}),
                prior_confidence,
                updated_confidence,
                information_gain_observed,
            )

            await conn.execute(
                "UPDATE proposed_experiments SET status = 'completed' "
                "WHERE id = $1",
                experiment_id,
            )

            if hypothesis_id and updated_confidence is not None:
                await conn.execute(
                    "UPDATE hypotheses SET confidence = $1 WHERE id = $2",
                    round(updated_confidence, 3),
                    hypothesis_id,
                )

            if experiment["gap_id"]:
                await conn.execute(
                    """UPDATE evidence_gaps
                          SET resolved = TRUE,
                              resolved_at = NOW()
                        WHERE id = $1""",
                    experiment["gap_id"],
                )

            # Re-evaluate candidate pipeline status for any candidates
            # linked to this hypothesis (auto-promote / auto-kill).
            candidate_ids: List[str] = []
            if hypothesis_id:
                rows = await conn.fetch(
                    """SELECT candidate_id FROM candidate_hypotheses
                            WHERE hypothesis_id = $1""",
                    hypothesis_id,
                )
                candidate_ids = [str(r["candidate_id"]) for r in rows]

        pipeline_results: List[Dict[str, Any]] = []
        for cand_id in candidate_ids:
            try:
                pipeline_results.append(
                    await pipeline_service.auto_advance(cand_id)
                )
            except Exception:  # noqa: BLE001 — best-effort, sanitize to client
                pipeline_results.append(
                    {
                        "candidate_id": cand_id,
                        "error": "pipeline_auto_advance_failed",
                    }
                )

        return {
            "outcome_id": outcome_id,
            "experiment_id": experiment_id,
            "hypothesis_id": (
                str(hypothesis_id) if hypothesis_id is not None else None
            ),
            "prior_confidence": prior_confidence,
            "updated_confidence": updated_confidence,
            "information_gain_observed": information_gain_observed,
            "pipeline_updates": pipeline_results,
        }

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    async def list_open_gaps(self, program_id: str) -> List[Dict[str, Any]]:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM evidence_gaps
                        WHERE program_id = $1 AND resolved = FALSE
                        ORDER BY severity DESC""",
                program_id,
            )
            return [dict(r) for r in rows]

    async def list_experiments(
        self,
        program_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """SELECT * FROM proposed_experiments
                            WHERE program_id = $1 AND status = $2
                            ORDER BY priority ASC, information_gain DESC
                            LIMIT $3""",
                    program_id,
                    status,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """SELECT * FROM proposed_experiments
                            WHERE program_id = $1
                            ORDER BY priority ASC, information_gain DESC
                            LIMIT $2""",
                    program_id,
                    limit,
                )
            return [dict(r) for r in rows]

    async def get_belief_timeline(
        self, hypothesis_id: str
    ) -> List[Dict[str, Any]]:
        """Return belief-update events for a hypothesis (oldest first)."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT eo.id, eo.proposed_experiment_id,
                          eo.prior_confidence, eo.updated_confidence,
                          eo.information_gain_observed,
                          eo.conducted_at, eo.result_summary,
                          pe.template_id, pe.description
                   FROM experiment_outcomes eo
                   JOIN proposed_experiments pe
                        ON pe.id = eo.proposed_experiment_id
                  WHERE pe.hypothesis_id = $1
               ORDER BY eo.conducted_at ASC""",
                hypothesis_id,
            )
            return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _ensure_agent_record(name: str, role: str) -> str:
    """Look up (or insert) an agents row and return its id as a str."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM agents WHERE name = $1", name
        )
        if row:
            return str(row["id"])
        new_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO agents (id, name, role, is_active)
               VALUES ($1, $2, $3, TRUE)
               ON CONFLICT (name) DO NOTHING""",
            new_id,
            name,
            role,
        )
        row = await conn.fetchrow(
            "SELECT id FROM agents WHERE name = $1", name
        )
        return str(row["id"]) if row else new_id


def _coerce_uuid(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


active_learning_service = ActiveLearningService()
