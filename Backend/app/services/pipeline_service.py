# app/services/pipeline_service.py
"""Candidate-pipeline automation (PR #8 — Genovate Precog).

Implements the auto-advance state machine described in PR #8:

    Current Status      Condition to Advance                    Next Status
    --------------      --------------------                    -----------
    idea                Has at least one hypothesis linked       evidence_map
    evidence_map        Evidence support score
                            > program.auto_promote_threshold     hypothesis
    hypothesis          Agent confidence > 0.7
                            AND Guardian approves                candidate
    candidate           Scorecard overall
                            > program.auto_promote_threshold     simulation
    simulation          Simulation critic passes
                            (no high-severity issues)            guardian_review
    guardian_review     Guardian approves                        promoted
    Any status          Score < program.auto_kill_threshold      killed (auto)

Every transition (auto or manual) is logged in ``candidate_transitions``
with a trigger_type so the pipeline is fully auditable.  Auto-transitions
also broadcast a ``candidate_status_changed`` WebSocket event on the
``/ws/program/{program_id}`` channel so the dashboard updates in
real-time.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from ..core.database import db
from .websocket_manager import program_event_broadcaster


# Pipeline order — index reflects how far a candidate has progressed.
_PIPELINE_ORDER: List[str] = [
    "idea",
    "evidence_map",
    "hypothesis",
    "candidate",
    "simulation",
    "guardian_review",
    "promoted",
]
_TERMINAL_STATUSES = {"promoted", "killed", "parked"}


# Scorecards use a 0-10 axis; programs.auto_*_threshold use 0-1.
# Map a 0-10 overall_score onto the 0-1 axis when comparing.
def _normalise_score(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value > 1.0:
        return float(value) / 10.0
    return float(value)


class PipelineService:
    """Auto-advance candidates and log every transition."""

    # ------------------------------------------------------------------
    # Transition logging
    # ------------------------------------------------------------------
    async def log_transition(
        self,
        candidate_id: str,
        from_status: Optional[str],
        to_status: str,
        trigger_type: str,
        trigger_id: Optional[str] = None,
        rationale: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append a row to ``candidate_transitions``."""
        valid_triggers = {"agent", "guardian", "threshold", "manual"}
        if trigger_type not in valid_triggers:
            raise ValueError(
                f"trigger_type must be one of {sorted(valid_triggers)}; "
                f"got {trigger_type!r}"
            )

        pool = await db.get_pool()
        transition_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO candidate_transitions
                       (id, candidate_id, from_status, to_status,
                        trigger_type, trigger_id, rationale, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                transition_id,
                candidate_id,
                from_status,
                to_status,
                trigger_type,
                trigger_id,
                rationale,
                created_by,
            )
            row = await conn.fetchrow(
                "SELECT * FROM candidate_transitions WHERE id = $1",
                transition_id,
            )
            return dict(row)

    async def list_transitions(
        self, candidate_id: str
    ) -> List[Dict[str, Any]]:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM candidate_transitions
                       WHERE candidate_id = $1
                       ORDER BY created_at ASC""",
                candidate_id,
            )
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Auto-advance state machine
    # ------------------------------------------------------------------
    async def auto_advance(
        self, candidate_id: str
    ) -> Dict[str, Any]:
        """Evaluate auto-advance / auto-kill rules for ``candidate_id``.

        Returns a structured decision describing whether the candidate
        was moved, the new status, the reason it was (or wasn't) moved,
        and the trigger type.  Idempotent for terminal candidates.
        """
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            candidate = await conn.fetchrow(
                "SELECT * FROM candidates WHERE id = $1", candidate_id
            )
            if not candidate:
                raise ValueError(f"Candidate not found: {candidate_id}")

            current_status: str = candidate["status"]
            program_id: str = str(candidate["program_id"])

            if current_status in _TERMINAL_STATUSES:
                return {
                    "candidate_id": candidate_id,
                    "moved": False,
                    "from_status": current_status,
                    "to_status": current_status,
                    "reason": (
                        f"Candidate is in terminal status '{current_status}'."
                    ),
                }

            program = await conn.fetchrow(
                """SELECT id, auto_promote_threshold, auto_kill_threshold
                       FROM programs WHERE id = $1""",
                program_id,
            )
            promote_thr = float(
                (program and program["auto_promote_threshold"]) or 0.7
            )
            kill_thr = float(
                (program and program["auto_kill_threshold"]) or 0.3
            )

            # ---- Latest scorecard (used for kill check + 'candidate' gate)
            scorecard = await conn.fetchrow(
                """SELECT * FROM scorecards
                       WHERE candidate_id = $1
                       ORDER BY version DESC
                       LIMIT 1""",
                candidate_id,
            )
            normalised_overall = _normalise_score(
                scorecard["overall_score"] if scorecard else None
            )

            # ---- Auto-kill takes priority over advance
            if (
                normalised_overall is not None
                and normalised_overall < kill_thr
            ):
                rationale = (
                    f"Latest scorecard normalised score "
                    f"{normalised_overall:.2f} fell below "
                    f"auto_kill_threshold ({kill_thr:.2f})."
                )
                return await self._transition(
                    conn,
                    candidate_id=candidate_id,
                    from_status=current_status,
                    to_status="killed",
                    trigger_type="threshold",
                    rationale=rationale,
                    program_id=program_id,
                    extra_kill_rationale=rationale,
                )

            # ---- Per-stage advancement rules
            decision = await self._evaluate_advance_rules(
                conn,
                candidate_id=candidate_id,
                current_status=current_status,
                promote_thr=promote_thr,
                scorecard=scorecard,
                normalised_overall=normalised_overall,
            )
            if decision is None:
                return {
                    "candidate_id": candidate_id,
                    "moved": False,
                    "from_status": current_status,
                    "to_status": current_status,
                    "reason": (
                        "Advance condition for "
                        f"'{current_status}' not yet met."
                    ),
                }

            next_status, trigger_type, rationale = decision
            return await self._transition(
                conn,
                candidate_id=candidate_id,
                from_status=current_status,
                to_status=next_status,
                trigger_type=trigger_type,
                rationale=rationale,
                program_id=program_id,
            )

    async def _evaluate_advance_rules(
        self,
        conn,
        *,
        candidate_id: str,
        current_status: str,
        promote_thr: float,
        scorecard: Optional[Any],
        normalised_overall: Optional[float],
    ) -> Optional[tuple]:
        """Return ``(next_status, trigger_type, rationale)`` or ``None``."""
        if current_status == "idea":
            count = await conn.fetchval(
                """SELECT COUNT(*) FROM candidate_hypotheses
                       WHERE candidate_id = $1""",
                candidate_id,
            )
            if count and count > 0:
                return (
                    "evidence_map",
                    "agent",
                    f"Candidate has {count} linked hypothesis(es).",
                )
            return None

        if current_status == "evidence_map":
            evidence_score = await conn.fetchval(
                """SELECT AVG(h.confidence)
                       FROM candidate_hypotheses ch
                       JOIN hypotheses h ON h.id = ch.hypothesis_id
                       WHERE ch.candidate_id = $1""",
                candidate_id,
            )
            if evidence_score is not None and float(evidence_score) > promote_thr:
                return (
                    "hypothesis",
                    "threshold",
                    (
                        f"Mean linked-hypothesis confidence "
                        f"{float(evidence_score):.2f} exceeds "
                        f"auto_promote_threshold ({promote_thr:.2f})."
                    ),
                )
            return None

        if current_status == "hypothesis":
            # Best agent confidence linked to this candidate.
            agent_conf = await conn.fetchval(
                """SELECT MAX(confidence) FROM agent_runs
                       WHERE candidate_id = $1 AND status = 'completed'""",
                candidate_id,
            )
            # Latest non-superseded Guardian decision on this candidate.
            guardian_decision = await conn.fetchval(
                """SELECT decision FROM guardian_reviews
                       WHERE entity_type = 'candidate'
                         AND entity_id = $1
                         AND is_final = TRUE
                         AND superseded_by IS NULL
                       ORDER BY reviewed_at DESC
                       LIMIT 1""",
                candidate_id,
            )
            if (
                agent_conf is not None
                and float(agent_conf) > 0.7
                and guardian_decision in ("approve", "promote_to_epistemicos")
            ):
                return (
                    "candidate",
                    "guardian",
                    (
                        f"Agent confidence {float(agent_conf):.2f} > 0.7 and "
                        f"Guardian decision '{guardian_decision}'."
                    ),
                )
            return None

        if current_status == "candidate":
            if (
                normalised_overall is not None
                and normalised_overall > promote_thr
            ):
                return (
                    "simulation",
                    "threshold",
                    (
                        f"Scorecard overall {normalised_overall:.2f} > "
                        f"auto_promote_threshold ({promote_thr:.2f})."
                    ),
                )
            return None

        if current_status == "simulation":
            # Simulation critic passes when there are no high-severity
            # critiques on any simulation_critique run for this candidate.
            high_severity = await conn.fetchval(
                """SELECT COUNT(*)
                       FROM agent_critiques c
                       JOIN agent_runs r ON r.id = c.agent_run_id
                       WHERE r.candidate_id = $1
                         AND r.run_type = 'simulation_critique'
                         AND c.severity = 'high'""",
                candidate_id,
            )
            had_critic = await conn.fetchval(
                """SELECT COUNT(*) FROM agent_runs
                       WHERE candidate_id = $1
                         AND run_type = 'simulation_critique'
                         AND status = 'completed'""",
                candidate_id,
            )
            if had_critic and not high_severity:
                return (
                    "guardian_review",
                    "agent",
                    "Simulation critic passed with no high-severity issues.",
                )
            return None

        if current_status == "guardian_review":
            decision = await conn.fetchval(
                """SELECT decision FROM guardian_reviews
                       WHERE entity_type = 'candidate'
                         AND entity_id = $1
                         AND is_final = TRUE
                         AND superseded_by IS NULL
                       ORDER BY reviewed_at DESC
                       LIMIT 1""",
                candidate_id,
            )
            if decision in ("approve", "promote_to_epistemicos"):
                return (
                    "promoted",
                    "guardian",
                    f"Guardian decision '{decision}'.",
                )
            return None

        return None

    async def _transition(
        self,
        conn,
        *,
        candidate_id: str,
        from_status: str,
        to_status: str,
        trigger_type: str,
        rationale: str,
        program_id: str,
        extra_kill_rationale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply a transition: update candidate, log it, broadcast it."""
        if to_status == "killed":
            await conn.execute(
                """UPDATE candidates
                       SET status = 'killed',
                           kill_rationale = COALESCE($2, kill_rationale),
                           killed_at = NOW(),
                           updated_at = NOW()
                       WHERE id = $1""",
                candidate_id,
                extra_kill_rationale or rationale,
            )
        else:
            await conn.execute(
                """UPDATE candidates
                       SET status = $1, updated_at = NOW()
                       WHERE id = $2""",
                to_status,
                candidate_id,
            )

        transition_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO candidate_transitions
                   (id, candidate_id, from_status, to_status,
                    trigger_type, rationale)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            transition_id,
            candidate_id,
            from_status,
            to_status,
            trigger_type,
            rationale,
        )

        # Best-effort fan-out; never let a websocket failure kill a transition.
        try:
            await program_event_broadcaster.broadcast_candidate_status_changed(
                program_id=program_id,
                candidate_id=candidate_id,
                old_status=from_status,
                new_status=to_status,
                trigger_type=trigger_type,
                rationale=rationale,
            )
        except Exception:  # pragma: no cover
            pass

        return {
            "candidate_id": candidate_id,
            "moved": True,
            "from_status": from_status,
            "to_status": to_status,
            "trigger_type": trigger_type,
            "rationale": rationale,
            "transition_id": transition_id,
        }

    # ------------------------------------------------------------------
    # Pipeline view
    # ------------------------------------------------------------------
    async def get_program_pipeline(
        self, program_id: str
    ) -> Dict[str, Any]:
        """Return all candidates with current status, latest scorecard,
        pending Guardian actions, and a recommended next step."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            program = await conn.fetchrow(
                """SELECT id, name, therapeutic_area,
                          auto_promote_threshold, auto_kill_threshold
                   FROM programs WHERE id = $1""",
                program_id,
            )
            if not program:
                raise ValueError(f"Program not found: {program_id}")

            rows = await conn.fetch(
                """
                SELECT c.id, c.name, c.candidate_type, c.status,
                       c.therapeutic_area, c.created_at, c.updated_at,
                       s.overall_score, s.version AS scorecard_version,
                       gr.id AS pending_review_id,
                       gr.decision AS pending_review_decision
                  FROM candidates c
                  LEFT JOIN LATERAL (
                      SELECT * FROM scorecards
                       WHERE candidate_id = c.id
                       ORDER BY version DESC LIMIT 1
                  ) s ON TRUE
                  LEFT JOIN LATERAL (
                      SELECT id, decision FROM guardian_reviews
                       WHERE entity_type = 'candidate'
                         AND entity_id = c.id
                         AND is_final = TRUE
                         AND superseded_by IS NULL
                       ORDER BY reviewed_at DESC LIMIT 1
                  ) gr ON TRUE
                  WHERE c.program_id = $1
                  ORDER BY c.created_at DESC
                """,
                program_id,
            )

        candidates: List[Dict[str, Any]] = []
        stage_counts: Dict[str, int] = {s: 0 for s in _PIPELINE_ORDER}
        stage_counts.update({"killed": 0, "parked": 0})
        for r in rows:
            d = dict(r)
            stage_counts[d["status"]] = stage_counts.get(d["status"], 0) + 1
            d["next_recommended_step"] = _next_recommended_step(d["status"])
            d["pending_guardian_decision"] = (
                d["status"] in ("hypothesis", "guardian_review")
                and d.get("pending_review_decision") not in (
                    "approve",
                    "promote_to_epistemicos",
                )
            )
            candidates.append(d)

        return {
            "program": dict(program),
            "candidates": candidates,
            "stage_counts": stage_counts,
            "total": len(candidates),
        }


def _next_recommended_step(status: str) -> str:
    """User-facing recommendation matching the auto-advance rules."""
    return {
        "idea": "Link a hypothesis to begin evidence mapping.",
        "evidence_map": "Strengthen evidence to exceed auto_promote_threshold.",
        "hypothesis": "Run agent assessment and request Guardian approval.",
        "candidate": "Score the candidate so it can advance to simulation.",
        "simulation": "Run the Simulation Critic; resolve high-severity issues.",
        "guardian_review": "Awaiting Guardian decision (approve / kill / park).",
        "promoted": "Candidate promoted — no further automation.",
        "killed": "Candidate killed — no further automation.",
        "parked": "Candidate parked — resume by manual status update.",
    }.get(status, "No recommendation.")


pipeline_service = PipelineService()
