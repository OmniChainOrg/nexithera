"""guardian review system

Revision ID: 005
Revises: 004
Create Date: 2026-04-20 10:00:00.000000

Adds The Guardian — the human-in-the-loop governance layer.  Creates the
guardian_reviews, review_assignments, review_checklists,
review_checklist_responses, review_comments, and review_artifacts tables,
plus supporting indexes and seed checklist criteria.  Mirrors the
idempotent schema created in ``app/core/database.py::_init_schema``.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guardian reviews (the core decision record)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guardian_reviews (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            review_type TEXT NOT NULL CHECK (review_type IN (
                'hypothesis_review',
                'candidate_review',
                'simulation_review',
                'program_gate_review',
                'epistemicos_promotion'
            )),
            entity_id UUID NOT NULL,
            entity_type TEXT NOT NULL CHECK (entity_type IN (
                'hypothesis', 'candidate', 'simulation', 'program'
            )),
            decision TEXT NOT NULL CHECK (decision IN (
                'approve',
                'request_revision',
                'escalate',
                'park',
                'kill',
                'promote_to_epistemicos'
            )),
            decision_rationale TEXT NOT NULL,
            risk_flags JSONB DEFAULT '[]',
            reviewer_id UUID NOT NULL REFERENCES users(id),
            reviewer_notes TEXT,
            review_deadline TIMESTAMPTZ,
            reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_final BOOLEAN DEFAULT TRUE,
            superseded_by UUID REFERENCES guardian_reviews(id),
            signed_artifact_uri TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Review assignments (who is on the hook to review what)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS review_assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            review_id UUID NOT NULL
                REFERENCES guardian_reviews(id) ON DELETE CASCADE,
            assignee_id UUID NOT NULL REFERENCES users(id),
            assigned_by UUID NOT NULL REFERENCES users(id),
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            status TEXT DEFAULT 'pending' CHECK (status IN (
                'pending', 'accepted', 'declined', 'completed'
            )),
            UNIQUE(review_id, assignee_id)
        )
        """
    )

    # Review checklists (structured criteria per review type)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS review_checklists (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            review_type TEXT NOT NULL,
            criterion TEXT NOT NULL,
            criterion_description TEXT,
            order_index INTEGER DEFAULT 0,
            is_required BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Checklist responses (the Guardian's answers to each criterion)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS review_checklist_responses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            review_id UUID NOT NULL
                REFERENCES guardian_reviews(id) ON DELETE CASCADE,
            checklist_item_id UUID NOT NULL
                REFERENCES review_checklists(id),
            passed BOOLEAN NOT NULL,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(review_id, checklist_item_id)
        )
        """
    )

    # Threaded review discussion
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS review_comments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            review_id UUID NOT NULL
                REFERENCES guardian_reviews(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            parent_comment_id UUID REFERENCES review_comments(id),
            comment_text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            edited_at TIMESTAMPTZ
        )
        """
    )

    # Signed artifacts produced from a review
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS review_artifacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            review_id UUID NOT NULL
                REFERENCES guardian_reviews(id) ON DELETE CASCADE,
            artifact_type TEXT NOT NULL CHECK (artifact_type IN (
                'report', 'certificate', 'evidence_package', 'decision_letter'
            )),
            artifact_uri TEXT NOT NULL,
            checksum TEXT,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_entity "
        "ON guardian_reviews(entity_id, entity_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_reviewer "
        "ON guardian_reviews(reviewer_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_decision "
        "ON guardian_reviews(decision)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reviews_reviewed_at "
        "ON guardian_reviews(reviewed_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignments_review "
        "ON review_assignments(review_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignments_assignee "
        "ON review_assignments(assignee_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_comments_review "
        "ON review_comments(review_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_artifacts_review "
        "ON review_artifacts(review_id)"
    )

    # Seed default review checklists.  We deduplicate on (review_type,
    # criterion) so re-running the migration is safe even though we cannot
    # add a UNIQUE constraint after the fact without losing idempotence.
    op.execute(
        """
        INSERT INTO review_checklists
            (review_type, criterion, criterion_description, order_index)
        SELECT v.review_type, v.criterion, v.criterion_description, v.order_index
        FROM (VALUES
            -- Hypothesis review
            ('hypothesis_review', 'Biological plausibility',
             'Is the hypothesis biologically plausible based on current evidence?', 1),
            ('hypothesis_review', 'Evidence strength',
             'Does supporting evidence outweigh contradicting evidence?', 2),
            ('hypothesis_review', 'Testability',
             'Can this hypothesis be experimentally tested?', 3),
            ('hypothesis_review', 'Novelty',
             'Is this hypothesis sufficiently novel?', 4),
            ('hypothesis_review', 'Clinical relevance',
             'Does this hypothesis address a meaningful clinical need?', 5),

            -- Candidate review
            ('candidate_review', 'Target engagement',
             'Is there evidence the candidate engages the intended target?', 1),
            ('candidate_review', 'Safety profile',
             'Are safety concerns adequately addressed?', 2),
            ('candidate_review', 'Developability',
             'Is the candidate developable (formulation, stability, manufacturing)?', 3),
            ('candidate_review', 'Differentiation',
             'Does this candidate offer meaningful differentiation from standard of care?', 4),
            ('candidate_review', 'Program fit',
             'Does this candidate align with program strategy?', 5),

            -- Simulation review
            ('simulation_review', 'Model validity',
             'Are simulation assumptions justified and documented?', 1),
            ('simulation_review', 'Controls',
             'Are appropriate positive/negative controls included?', 2),
            ('simulation_review', 'Reproducibility',
             'Can the simulation be reproduced with documented parameters?', 3),
            ('simulation_review', 'Uncertainty quantification',
             'Are confidence intervals and uncertainty properly characterized?', 4),
            ('simulation_review', 'Clinical translation',
             'Do simulation results translate to clinical predictions?', 5),

            -- Program gate review
            ('program_gate_review', 'Scientific rationale',
             'Is the overall scientific rationale sound?', 1),
            ('program_gate_review', 'Resource availability',
             'Are resources sufficient for next stage?', 2),
            ('program_gate_review', 'Risk assessment',
             'Have risks been identified and mitigation plans developed?', 3),
            ('program_gate_review', 'Timeline feasibility',
             'Is the proposed timeline realistic?', 4),
            ('program_gate_review', 'Strategic alignment',
             'Does this program align with NexiThera strategic priorities?', 5),

            -- EpistemicOS promotion
            ('epistemicos_promotion', 'Reasoning completeness',
             'Has reasoning reached sufficient depth for EpistemicOS?', 1),
            ('epistemicos_promotion', 'Data quality',
             'Is underlying data of sufficient quality for recursive reasoning?', 2),
            ('epistemicos_promotion', 'Business value',
             'Does promotion to EpistemicOS create incremental value?', 3),
            ('epistemicos_promotion', 'Readiness',
             'Is the candidate/hypothesis mature enough for EpistemicOS?', 4)
        ) AS v(review_type, criterion, criterion_description, order_index)
        WHERE NOT EXISTS (
            SELECT 1 FROM review_checklists rc
            WHERE rc.review_type = v.review_type
              AND rc.criterion = v.criterion
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS review_artifacts CASCADE")
    op.execute("DROP TABLE IF EXISTS review_comments CASCADE")
    op.execute("DROP TABLE IF EXISTS review_checklist_responses CASCADE")
    op.execute("DROP TABLE IF EXISTS review_checklists CASCADE")
    op.execute("DROP TABLE IF EXISTS review_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS guardian_reviews CASCADE")
