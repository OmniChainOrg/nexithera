# app/services/guardian_service.py
"""Guardian review service (PR #5).

Implements the human-in-the-loop governance layer.  The Guardian can
approve, request revisions, escalate, park, kill, or promote candidates,
hypotheses, simulations, and programs to EpistemicOS.  Every decision is
immutable: once a review is final it can only be replaced via a new
review that supersedes it.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.database import db
from ..models.guardian import (
    ARTIFACT_TYPES,
    ASSIGNMENT_STATUSES,
    DECISIONS,
    ENTITY_TYPES,
    REVIEW_TYPES,
)


# Map a Guardian decision onto the resulting status for the reviewed entity.
# (Only ``hypothesis`` and ``candidate`` carry a status column in the
# current schema; ``simulation`` / ``program`` are no-ops here but the
# decision is still recorded immutably in ``guardian_reviews``.)
_HYPOTHESIS_STATUS_BY_DECISION = {
    "approve": "supported",
    "request_revision": "draft",
    "kill": "refuted",
    "park": "deprecated",
    "promote_to_epistemicos": "supported",
    # 'escalate' deliberately leaves the entity status untouched.
}

_CANDIDATE_STATUS_BY_DECISION = {
    "approve": "promoted",
    "request_revision": "guardian_review",
    "kill": "killed",
    "park": "parked",
    "promote_to_epistemicos": "promoted",
}


class GuardianService:
    """Manage guardian reviews, assignments, checklists, comments, artifacts."""

    # ------------------------------------------------------------------
    # Review lifecycle
    # ------------------------------------------------------------------
    async def create_review(
        self,
        review_type: str,
        entity_id: str,
        entity_type: str,
        reviewer_id: str,
        decision: str,
        decision_rationale: str,
        risk_flags: Optional[List[Dict[str, Any]]] = None,
        reviewer_notes: Optional[str] = None,
        review_deadline: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Create a new guardian review.

        ``decision`` is required at creation time because every review is
        an immutable decision record.  Use ``submit_decision`` on an
        existing review only when superseding it via a new review.
        """
        self._validate_review_type(review_type)
        self._validate_entity_type(entity_type)
        self._validate_decision(decision, decision_rationale)

        pool = await db.get_pool()
        review_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO guardian_reviews
                       (id, review_type, entity_id, entity_type, decision,
                        decision_rationale, risk_flags, reviewer_id,
                        reviewer_notes, review_deadline)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                review_id,
                review_type,
                entity_id,
                entity_type,
                decision,
                decision_rationale,
                risk_flags or [],
                reviewer_id,
                reviewer_notes,
                review_deadline,
            )

            # Propagate the decision to the underlying entity status.
            await self._apply_decision_to_entity(
                conn,
                entity_type=entity_type,
                entity_id=entity_id,
                decision=decision,
                reviewer_id=reviewer_id,
                decision_rationale=decision_rationale,
            )

            row = await conn.fetchrow(
                "SELECT * FROM guardian_reviews WHERE id = $1", review_id
            )
            return dict(row)

    async def submit_decision(
        self,
        review_id: str,
        decision: str,
        decision_rationale: str,
        reviewer_id: str,
        risk_flags: Optional[List[Dict[str, Any]]] = None,
        reviewer_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a (new) decision against an existing review.

        Reviews are immutable once final; a new decision is recorded as a
        fresh ``guardian_reviews`` row that supersedes the original.  The
        new review inherits review_type / entity_id / entity_type from
        the superseded one.
        """
        self._validate_decision(decision, decision_rationale)

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            original = await conn.fetchrow(
                "SELECT * FROM guardian_reviews WHERE id = $1", review_id
            )
            if not original:
                raise ValueError(f"Review not found: {review_id}")
            if original["superseded_by"] is not None:
                raise ValueError(
                    "Review has already been superseded by another review."
                )
            if not original["is_final"]:
                raise ValueError(
                    "Original review is not final; cannot supersede a draft."
                )

            new_review_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO guardian_reviews
                       (id, review_type, entity_id, entity_type, decision,
                        decision_rationale, risk_flags, reviewer_id,
                        reviewer_notes)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                new_review_id,
                original["review_type"],
                original["entity_id"],
                original["entity_type"],
                decision,
                decision_rationale,
                risk_flags or [],
                reviewer_id,
                reviewer_notes,
            )

            # Mark the original as superseded (preserving the audit trail).
            await conn.execute(
                """UPDATE guardian_reviews
                       SET is_final = FALSE,
                           superseded_by = $1
                       WHERE id = $2""",
                new_review_id,
                review_id,
            )

            await self._apply_decision_to_entity(
                conn,
                entity_type=original["entity_type"],
                entity_id=original["entity_id"],
                decision=decision,
                reviewer_id=reviewer_id,
                decision_rationale=decision_rationale,
            )

            row = await conn.fetchrow(
                "SELECT * FROM guardian_reviews WHERE id = $1", new_review_id
            )
            return dict(row)

    async def get_review(self, review_id: str) -> Dict[str, Any]:
        """Get a review with its checklist responses, comments, and artifacts."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            review = await conn.fetchrow(
                "SELECT * FROM guardian_reviews WHERE id = $1", review_id
            )
            if not review:
                return {}

            checklist = await conn.fetch(
                """SELECT r.*, c.criterion, c.criterion_description, c.order_index
                       FROM review_checklist_responses r
                       JOIN review_checklists c ON r.checklist_item_id = c.id
                       WHERE r.review_id = $1
                       ORDER BY c.order_index""",
                review_id,
            )
            comments = await conn.fetch(
                """SELECT * FROM review_comments
                       WHERE review_id = $1
                       ORDER BY created_at ASC""",
                review_id,
            )
            artifacts = await conn.fetch(
                """SELECT * FROM review_artifacts
                       WHERE review_id = $1
                       ORDER BY created_at DESC""",
                review_id,
            )
            assignments = await conn.fetch(
                """SELECT * FROM review_assignments
                       WHERE review_id = $1
                       ORDER BY assigned_at ASC""",
                review_id,
            )

            return {
                "review": dict(review),
                "checklist_responses": [dict(r) for r in checklist],
                "comments": [dict(r) for r in comments],
                "artifacts": [dict(r) for r in artifacts],
                "assignments": [dict(r) for r in assignments],
            }

    async def list_reviews(
        self,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        review_type: Optional[str] = None,
        decision: Optional[str] = None,
        only_final: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List reviews with simple filters."""
        clauses: List[str] = []
        args: List[Any] = []

        def _add(clause: str, value: Any) -> None:
            args.append(value)
            clauses.append(clause.replace("$?", f"${len(args)}"))

        if entity_id:
            _add("entity_id = $?", entity_id)
        if entity_type:
            _add("entity_type = $?", entity_type)
        if reviewer_id:
            _add("reviewer_id = $?", reviewer_id)
        if review_type:
            _add("review_type = $?", review_type)
        if decision:
            _add("decision = $?", decision)
        if only_final:
            clauses.append("is_final = TRUE")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.extend([limit, offset])
        sql = (
            f"SELECT * FROM guardian_reviews {where} "
            f"ORDER BY reviewed_at DESC "
            f"LIMIT ${len(args) - 1} OFFSET ${len(args)}"
        )

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------
    async def assign_reviewer(
        self,
        review_id: str,
        assignee_id: str,
        assigned_by: str,
    ) -> Dict[str, Any]:
        """Assign a guardian to review."""
        pool = await db.get_pool()
        assignment_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                """SELECT id FROM review_assignments
                       WHERE review_id = $1 AND assignee_id = $2""",
                review_id,
                assignee_id,
            )
            if existing:
                row = await conn.fetchrow(
                    "SELECT * FROM review_assignments WHERE id = $1",
                    existing["id"],
                )
                return dict(row)

            await conn.execute(
                """INSERT INTO review_assignments
                       (id, review_id, assignee_id, assigned_by)
                   VALUES ($1, $2, $3, $4)""",
                assignment_id,
                review_id,
                assignee_id,
                assigned_by,
            )
            row = await conn.fetchrow(
                "SELECT * FROM review_assignments WHERE id = $1",
                assignment_id,
            )
            return dict(row)

    async def update_assignment_status(
        self,
        assignment_id: str,
        status: str,
    ) -> Dict[str, Any]:
        """Move an assignment through pending → accepted/declined → completed."""
        if status not in ASSIGNMENT_STATUSES:
            raise ValueError(f"Invalid assignment status: {status}")
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE review_assignments
                       SET status = $1,
                           completed_at = CASE
                               WHEN $1 = 'completed' THEN NOW()
                               ELSE completed_at
                           END
                       WHERE id = $2""",
                status,
                assignment_id,
            )
            row = await conn.fetchrow(
                "SELECT * FROM review_assignments WHERE id = $1",
                assignment_id,
            )
            return dict(row) if row else {}

    # ------------------------------------------------------------------
    # Checklists
    # ------------------------------------------------------------------
    async def get_checklist(self, review_type: str) -> List[Dict[str, Any]]:
        """Return the structured checklist for a given review type."""
        self._validate_review_type(review_type)
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM review_checklists
                       WHERE review_type = $1
                       ORDER BY order_index""",
                review_type,
            )
            return [dict(r) for r in rows]

    async def add_checklist_response(
        self,
        review_id: str,
        checklist_item_id: str,
        passed: bool,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a guardian's answer for a single checklist criterion."""
        pool = await db.get_pool()
        response_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            # Reviews are immutable once final.  Allow checklist responses
            # only while the review has not been superseded.
            review = await conn.fetchrow(
                "SELECT is_final, superseded_by FROM guardian_reviews WHERE id = $1",
                review_id,
            )
            if not review:
                raise ValueError(f"Review not found: {review_id}")
            if review["superseded_by"] is not None:
                raise ValueError(
                    "Cannot modify checklist for a superseded review."
                )

            existing = await conn.fetchrow(
                """SELECT id FROM review_checklist_responses
                       WHERE review_id = $1 AND checklist_item_id = $2""",
                review_id,
                checklist_item_id,
            )
            if existing:
                await conn.execute(
                    """UPDATE review_checklist_responses
                           SET passed = $1, notes = $2
                           WHERE id = $3""",
                    passed,
                    notes,
                    existing["id"],
                )
                row = await conn.fetchrow(
                    "SELECT * FROM review_checklist_responses WHERE id = $1",
                    existing["id"],
                )
                return dict(row)

            await conn.execute(
                """INSERT INTO review_checklist_responses
                       (id, review_id, checklist_item_id, passed, notes)
                   VALUES ($1, $2, $3, $4, $5)""",
                response_id,
                review_id,
                checklist_item_id,
                passed,
                notes,
            )
            row = await conn.fetchrow(
                "SELECT * FROM review_checklist_responses WHERE id = $1",
                response_id,
            )
            return dict(row)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------
    async def add_comment(
        self,
        review_id: str,
        user_id: str,
        comment_text: str,
        parent_comment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a threaded comment to a review's discussion."""
        if not comment_text or not comment_text.strip():
            raise ValueError("Comment text cannot be empty")
        pool = await db.get_pool()
        comment_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO review_comments
                       (id, review_id, user_id, parent_comment_id, comment_text)
                   VALUES ($1, $2, $3, $4, $5)""",
                comment_id,
                review_id,
                user_id,
                parent_comment_id,
                comment_text,
            )
            row = await conn.fetchrow(
                "SELECT * FROM review_comments WHERE id = $1", comment_id
            )
            return dict(row)

    # ------------------------------------------------------------------
    # Artifacts / signed reports
    # ------------------------------------------------------------------
    async def generate_report(
        self,
        review_id: str,
        created_by: str,
        artifact_type: str = "report",
    ) -> Dict[str, Any]:
        """Generate a signed report for a review.

        For the MVP we generate a JSON evidence package, compute a SHA-256
        checksum over the canonical payload, and store the artifact's URI
        in ``review_artifacts`` + ``guardian_reviews.signed_artifact_uri``.
        Actual PDF rendering is a stub — the URI shape lets the frontend
        and downstream signers swap in real object storage later.
        """
        if artifact_type not in ARTIFACT_TYPES:
            raise ValueError(f"Invalid artifact_type: {artifact_type}")

        bundle = await self.get_review(review_id)
        if not bundle:
            raise ValueError(f"Review not found: {review_id}")

        canonical = json.dumps(
            bundle, sort_keys=True, default=str
        ).encode("utf-8")
        checksum = hashlib.sha256(canonical).hexdigest()
        artifact_uri = (
            f"s3://guardian-reports/{review_id}/{artifact_type}-{checksum[:12]}.pdf"
        )

        pool = await db.get_pool()
        artifact_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO review_artifacts
                       (id, review_id, artifact_type, artifact_uri,
                        checksum, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                artifact_id,
                review_id,
                artifact_type,
                artifact_uri,
                checksum,
                created_by,
            )
            await conn.execute(
                """UPDATE guardian_reviews
                       SET signed_artifact_uri = $1
                       WHERE id = $2""",
                artifact_uri,
                review_id,
            )
            row = await conn.fetchrow(
                "SELECT * FROM review_artifacts WHERE id = $1", artifact_id
            )
            return dict(row)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_review_type(review_type: str) -> None:
        if review_type not in REVIEW_TYPES:
            raise ValueError(f"Invalid review_type: {review_type}")

    @staticmethod
    def _validate_entity_type(entity_type: str) -> None:
        if entity_type not in ENTITY_TYPES:
            raise ValueError(f"Invalid entity_type: {entity_type}")

    @staticmethod
    def _validate_decision(decision: str, decision_rationale: str) -> None:
        if decision not in DECISIONS:
            raise ValueError(f"Invalid decision: {decision}")
        if not decision_rationale or not decision_rationale.strip():
            # Science advances because we murder bad hypotheses politely.
            if decision == "kill":
                raise ValueError(
                    "Kill rationale required: every kill must be explained."
                )
            raise ValueError("Decision rationale is required for all decisions.")

    # ------------------------------------------------------------------
    # Decision → entity status propagation
    # ------------------------------------------------------------------
    @staticmethod
    async def _apply_decision_to_entity(
        conn,
        *,
        entity_type: str,
        entity_id: str,
        decision: str,
        reviewer_id: str,
        decision_rationale: str,
    ) -> None:
        """Update the underlying entity to reflect the Guardian's decision."""
        if entity_type == "hypothesis":
            new_status = _HYPOTHESIS_STATUS_BY_DECISION.get(decision)
            if new_status is None:
                return
            await conn.execute(
                """UPDATE hypotheses
                       SET status = $1,
                           reviewed_by = $2,
                           reviewed_at = NOW(),
                           updated_at = NOW()
                       WHERE id = $3""",
                new_status,
                reviewer_id,
                entity_id,
            )
        elif entity_type == "candidate":
            new_status = _CANDIDATE_STATUS_BY_DECISION.get(decision)
            if new_status is None:
                return
            if new_status == "killed":
                await conn.execute(
                    """UPDATE candidates
                           SET status = 'killed',
                               kill_rationale = $1,
                               killed_at = NOW(),
                               killed_by = $2,
                               updated_at = NOW()
                           WHERE id = $3""",
                    decision_rationale,
                    reviewer_id,
                    entity_id,
                )
            else:
                await conn.execute(
                    """UPDATE candidates
                           SET status = $1,
                               updated_at = NOW()
                           WHERE id = $2""",
                    new_status,
                    entity_id,
                )
        # simulations / programs: decision recorded only in guardian_reviews


guardian_service = GuardianService()
