# app/services/hypothesis_service.py
import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..core.database import db

class HypothesisService:
    """Manage hypotheses and their evidence links."""

    async def create_hypothesis(
        self,
        hypothesis_text: str,
        claim_type: str,
        program_id: str,
        created_by: Optional[str] = None,
        confidence: Optional[float] = None,
        uncertainty_reason: Optional[str] = None,
        parent_hypothesis_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new hypothesis (version 1)."""
        pool = await db.get_pool()
        hypothesis_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            # Check if similar hypothesis exists (optional: prevent duplicates)
            existing = await conn.fetchrow(
                """SELECT id, version FROM hypotheses 
                   WHERE hypothesis_text = $1 AND program_id = $2 
                   AND status NOT IN ('refuted', 'deprecated')
                   LIMIT 1""",
                hypothesis_text, program_id
            )
            if existing:
                # Return existing hypothesis instead of duplicate
                row = await conn.fetchrow(
                    "SELECT * FROM hypotheses WHERE id = $1", existing['id']
                )
                return dict(row)

            await conn.execute(
                """INSERT INTO hypotheses 
                   (id, hypothesis_text, claim_type, program_id, created_by, 
                    confidence, uncertainty_reason, parent_hypothesis_id, status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'draft')""",
                hypothesis_id, hypothesis_text, claim_type, program_id,
                created_by, confidence, uncertainty_reason, parent_hypothesis_id
            )

            row = await conn.fetchrow("SELECT * FROM hypotheses WHERE id = $1", hypothesis_id)
            return dict(row)

    async def add_evidence_to_hypothesis(
        self,
        hypothesis_id: str,
        evidence_edge_id: str,
        supports: bool = True,
        weight: float = 1.0,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Link evidence to a hypothesis."""
        pool = await db.get_pool()
        link_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            # Check if already linked
            existing = await conn.fetchrow(
                """SELECT id FROM hypothesis_evidence 
                   WHERE hypothesis_id = $1 AND evidence_edge_id = $2""",
                hypothesis_id, evidence_edge_id
            )
            if existing:
                row = await conn.fetchrow(
                    "SELECT * FROM hypothesis_evidence WHERE id = $1", existing['id']
                )
                return dict(row)

            await conn.execute(
                """INSERT INTO hypothesis_evidence 
                   (id, hypothesis_id, evidence_edge_id, supports, weight, note)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                link_id, hypothesis_id, evidence_edge_id, supports, weight, note
            )

            # Update hypothesis confidence based on evidence (simple average for MVP)
            await self._recalculate_hypothesis_confidence(hypothesis_id)

            row = await conn.fetchrow("SELECT * FROM hypothesis_evidence WHERE id = $1", link_id)
            return dict(row)

    async def _recalculate_hypothesis_confidence(self, hypothesis_id: str) -> None:
        """Recalculate hypothesis confidence from supporting/contradicting evidence."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Get all evidence for this hypothesis
            rows = await conn.fetch(
                """SELECT supports, weight, e.confidence as edge_confidence
                   FROM hypothesis_evidence he
                   JOIN evidence_edges e ON he.evidence_edge_id = e.id
                   WHERE he.hypothesis_id = $1""",
                hypothesis_id
            )

            if not rows:
                return

            support_sum = 0.0
            total_weight = 0.0
            for row in rows:
                weight = row['weight']
                edge_conf = row['edge_confidence']
                if row['supports']:
                    support_sum += edge_conf * weight
                else:
                    support_sum += (1 - edge_conf) * weight  # Contradicting evidence reduces confidence
                total_weight += weight

            if total_weight > 0:
                new_confidence = support_sum / total_weight
                await conn.execute(
                    "UPDATE hypotheses SET confidence = $1 WHERE id = $2",
                    round(new_confidence, 3), hypothesis_id
                )

    async def get_hypothesis_with_evidence(
        self,
        hypothesis_id: str
    ) -> Dict[str, Any]:
        """Get hypothesis with all supporting and contradicting evidence."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            hypothesis = await conn.fetchrow(
                "SELECT * FROM hypotheses WHERE id = $1", hypothesis_id
            )
            if not hypothesis:
                return {}

            supporting = await conn.fetch(
                """SELECT he.*, e.predicate, e.confidence as edge_confidence,
                          s.name as source_name, t.name as target_name
                   FROM hypothesis_evidence he
                   JOIN evidence_edges e ON he.evidence_edge_id = e.id
                   JOIN bio_entities s ON e.source_id = s.id
                   JOIN bio_entities t ON e.target_id = t.id
                   WHERE he.hypothesis_id = $1 AND he.supports = TRUE""",
                hypothesis_id
            )

            contradicting = await conn.fetch(
                """SELECT he.*, e.predicate, e.confidence as edge_confidence,
                          s.name as source_name, t.name as target_name
                   FROM hypothesis_evidence he
                   JOIN evidence_edges e ON he.evidence_edge_id = e.id
                   JOIN bio_entities s ON e.source_id = s.id
                   JOIN bio_entities t ON e.target_id = t.id
                   WHERE he.hypothesis_id = $1 AND he.supports = FALSE""",
                hypothesis_id
            )

            return {
                "hypothesis": dict(hypothesis),
                "supporting_evidence": [dict(r) for r in supporting],
                "contradicting_evidence": [dict(r) for r in contradicting]
            }

    # ------------------------------------------------------------------
    # PR #8: Hypothesis versioning
    # ------------------------------------------------------------------
    async def create_version(
        self,
        parent_hypothesis_id: str,
        hypothesis_text: str,
        created_by: Optional[str] = None,
        confidence: Optional[float] = None,
        uncertainty_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new child version of an existing hypothesis.

        The child preserves ``parent_hypothesis_id``, inherits
        ``program_id`` and ``claim_type`` from the parent, and bumps
        ``version`` to ``parent.version + 1``.  Older versions are kept
        intact so the timeline is auditable.
        """
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            parent = await conn.fetchrow(
                "SELECT * FROM hypotheses WHERE id = $1",
                parent_hypothesis_id,
            )
            if not parent:
                raise ValueError(
                    f"Parent hypothesis not found: {parent_hypothesis_id}"
                )

            new_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO hypotheses
                       (id, version, hypothesis_text, claim_type, program_id,
                        parent_hypothesis_id, created_by, confidence,
                        uncertainty_reason, status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'draft')""",
                new_id,
                int(parent["version"] or 1) + 1,
                hypothesis_text,
                parent["claim_type"],
                parent["program_id"],
                parent_hypothesis_id,
                created_by,
                confidence,
                uncertainty_reason,
            )

            # Mark the parent as deprecated so consumers know a child
            # version supersedes it; older versions remain queryable.
            await conn.execute(
                """UPDATE hypotheses
                       SET status = 'deprecated'
                       WHERE id = $1
                         AND status NOT IN ('refuted', 'deprecated')""",
                parent_hypothesis_id,
            )

            row = await conn.fetchrow(
                "SELECT * FROM hypotheses WHERE id = $1", new_id
            )
            return dict(row)

    async def get_version_timeline(
        self, hypothesis_id: str
    ) -> List[Dict[str, Any]]:
        """Return the full version timeline (root → leaves) for a hypothesis."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH RECURSIVE up AS (
                    SELECT * FROM hypotheses WHERE id = $1
                    UNION
                    SELECT h.* FROM hypotheses h
                      JOIN up ON h.id = up.parent_hypothesis_id
                ),
                root AS (
                    SELECT id FROM up
                     WHERE parent_hypothesis_id IS NULL
                     LIMIT 1
                ),
                tree AS (
                    SELECT * FROM hypotheses
                      WHERE id = (SELECT id FROM root)
                    UNION
                    SELECT h.* FROM hypotheses h
                      JOIN tree ON h.parent_hypothesis_id = tree.id
                )
                SELECT * FROM tree
                ORDER BY version ASC, created_at ASC
                """,
                hypothesis_id,
            )
            return [dict(r) for r in rows]

hypothesis_service = HypothesisService()
