# app/services/candidate_service.py
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..core.database import db

class CandidateService:
    """Manage candidates and their scorecards."""

    async def create_candidate(
        self,
        name: str,
        candidate_type: str,
        therapeutic_area: str,
        program_id: str,
        target_id: Optional[str] = None,
        mechanism_of_action: Optional[str] = None,
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new candidate (status: idea)."""
        pool = await db.get_pool()
        candidate_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO candidates 
                   (id, name, candidate_type, therapeutic_area, program_id, 
                    target_id, mechanism_of_action, description, created_by, status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'idea')""",
                candidate_id, name, candidate_type, therapeutic_area, program_id,
                target_id, mechanism_of_action, description, created_by
            )

            row = await conn.fetchrow("SELECT * FROM candidates WHERE id = $1", candidate_id)
            return dict(row)

    async def update_candidate_status(
        self,
        candidate_id: str,
        new_status: str,
        user_id: Optional[str] = None,
        kill_rationale: Optional[str] = None,
        trigger_type: str = "manual",
        trigger_id: Optional[str] = None,
        rationale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Advance candidate through pipeline stages.

        Every status change is logged in ``candidate_transitions`` (PR #8)
        with a trigger_type so the pipeline is fully auditable.
        """
        valid_statuses = [
            'idea', 'evidence_map', 'hypothesis', 'candidate',
            'simulation', 'guardian_review', 'promoted', 'killed', 'parked'
        ]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}")

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # If killing, require rationale
            if new_status == 'killed' and not kill_rationale:
                raise ValueError("Kill rationale required when killing a candidate")

            previous = await conn.fetchrow(
                "SELECT status, program_id FROM candidates WHERE id = $1",
                candidate_id,
            )
            previous_status = previous["status"] if previous else None
            program_id = str(previous["program_id"]) if previous else None

            await conn.execute(
                """UPDATE candidates 
                   SET status = $1, 
                       kill_rationale = $2,
                       killed_at = CASE WHEN $1 = 'killed' THEN NOW() ELSE killed_at END,
                       killed_by = CASE WHEN $1 = 'killed' THEN $3 ELSE killed_by END,
                       updated_at = NOW()
                   WHERE id = $4""",
                new_status, kill_rationale, user_id, candidate_id
            )

            # Log the transition (PR #8) and broadcast a websocket event.
            if previous_status is not None and previous_status != new_status:
                await conn.execute(
                    """INSERT INTO candidate_transitions
                           (id, candidate_id, from_status, to_status,
                            trigger_type, trigger_id, rationale, created_by)
                       VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7)""",
                    candidate_id,
                    previous_status,
                    new_status,
                    trigger_type,
                    trigger_id,
                    rationale or kill_rationale,
                    user_id,
                )
                if program_id:
                    try:
                        from .websocket_manager import program_event_broadcaster
                        await program_event_broadcaster.broadcast_candidate_status_changed(
                            program_id=program_id,
                            candidate_id=candidate_id,
                            old_status=previous_status,
                            new_status=new_status,
                            trigger_type=trigger_type,
                            rationale=rationale or kill_rationale,
                        )
                    except Exception:  # pragma: no cover - defensive
                        pass

            row = await conn.fetchrow("SELECT * FROM candidates WHERE id = $1", candidate_id)
            return dict(row)

    async def add_scorecard(
        self,
        candidate_id: str,
        evidence_score: float,
        simulation_score: float,
        safety_score: float,
        formulation_score: float,
        translational_score: float,
        program_fit_score: float,
        scored_by: Optional[str] = None,
        scoring_rationale: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a new scorecard for a candidate (versioned)."""
        pool = await db.get_pool()
        scorecard_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            # Get current max version
            max_version = await conn.fetchval(
                "SELECT COALESCE(MAX(version), 0) FROM scorecards WHERE candidate_id = $1",
                candidate_id
            )
            new_version = max_version + 1

            await conn.execute(
                """INSERT INTO scorecards 
                   (id, candidate_id, evidence_score, simulation_score, safety_score,
                    formulation_score, translational_score, program_fit_score,
                    scoring_rationale, scored_by, version)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                scorecard_id, candidate_id, evidence_score, simulation_score,
                safety_score, formulation_score, translational_score, program_fit_score,
                scoring_rationale, scored_by, new_version
            )

            row = await conn.fetchrow("SELECT * FROM scorecards WHERE id = $1", scorecard_id)
            return dict(row)

    async def link_hypothesis_to_candidate(
        self,
        candidate_id: str,
        hypothesis_id: str
    ) -> Dict[str, Any]:
        """Link a hypothesis to a candidate."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO candidate_hypotheses (candidate_id, hypothesis_id)
                   VALUES ($1, $2)
                   ON CONFLICT DO NOTHING""",
                candidate_id, hypothesis_id
            )
            return {"candidate_id": candidate_id, "hypothesis_id": hypothesis_id}

    async def get_candidate_with_scorecard(
        self,
        candidate_id: str
    ) -> Dict[str, Any]:
        """Get candidate with latest scorecard."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            candidate = await conn.fetchrow(
                "SELECT * FROM candidates WHERE id = $1", candidate_id
            )
            if not candidate:
                return {}

            latest_scorecard = await conn.fetchrow(
                """SELECT * FROM scorecards 
                   WHERE candidate_id = $1 
                   ORDER BY version DESC LIMIT 1""",
                candidate_id
            )

            hypotheses = await conn.fetch(
                """SELECT h.* FROM hypotheses h
                   JOIN candidate_hypotheses ch ON h.id = ch.hypothesis_id
                   WHERE ch.candidate_id = $1""",
                candidate_id
            )

            return {
                "candidate": dict(candidate),
                "latest_scorecard": dict(latest_scorecard) if latest_scorecard else None,
                "supporting_hypotheses": [dict(h) for h in hypotheses]
            }

    async def list_candidates_by_program(
        self,
        program_id: str,
        status: Optional[str] = None
    ) -> List[Dict]:
        """List all candidates in a program, optionally filtered by status."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """SELECT c.*, 
                              COALESCE(s.overall_score, 0) as current_score
                       FROM candidates c
                       LEFT JOIN scorecards s ON c.id = s.candidate_id
                       WHERE c.program_id = $1 AND c.status = $2
                       ORDER BY c.created_at DESC""",
                    program_id, status
                )
            else:
                rows = await conn.fetch(
                    """SELECT c.*, 
                              COALESCE(s.overall_score, 0) as current_score
                       FROM candidates c
                       LEFT JOIN scorecards s ON c.id = s.candidate_id
                       WHERE c.program_id = $1
                       ORDER BY c.created_at DESC""",
                    program_id
                )
            return [dict(row) for row in rows]

candidate_service = CandidateService()
