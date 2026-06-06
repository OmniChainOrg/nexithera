"""preclinical pipeline automation + target discovery (PR #8)

Revision ID: 008
Revises: 007
Create Date: 2026-06-06 12:00:00.000000

Adds the PR #8 (Genovate Precog) tables and configuration:

    * ``candidate_transitions``  — pipeline state-transition log (every
                                   automated/manual move is auditable)
    * ``target_discoveries``     — output bundles from the Target
                                   Discovery Agent
    * ``programs.auto_promote_threshold`` / ``auto_kill_threshold``
                                  — per-program automation thresholds
    * ``idx_hypotheses_parent``  — fast lookup for hypothesis-versioning
                                   timelines

Mirrors the idempotent schema created in
``app/core/database.py::_init_schema``.  All statements are ``IF NOT
EXISTS`` so the migration is safe to re-run.

This migration introduces no clinical-trial or forecasting structures;
it is preclinical-only.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Per-program automation thresholds
    op.execute(
        "ALTER TABLE programs "
        "ADD COLUMN IF NOT EXISTS auto_promote_threshold REAL DEFAULT 0.7"
    )
    op.execute(
        "ALTER TABLE programs "
        "ADD COLUMN IF NOT EXISTS auto_kill_threshold REAL DEFAULT 0.3"
    )

    # Hypothesis-versioning lookup index (parent -> child)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hypotheses_parent "
        "ON hypotheses(parent_hypothesis_id)"
    )

    # Pipeline state-transition log
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_transitions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL
                REFERENCES candidates(id) ON DELETE CASCADE,
            from_status TEXT,
            to_status TEXT NOT NULL,
            trigger_type TEXT NOT NULL CHECK (trigger_type IN (
                'agent', 'guardian', 'threshold', 'manual'
            )),
            trigger_id UUID,
            rationale TEXT,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Target Discovery Agent output bundles
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS target_discoveries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_run_id UUID REFERENCES agent_runs(id),
            program_id UUID NOT NULL
                REFERENCES programs(id) ON DELETE CASCADE,
            ranked_targets JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidate_transitions_candidate "
        "ON candidate_transitions(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidate_transitions_created "
        "ON candidate_transitions(created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_target_discoveries_program "
        "ON target_discoveries(program_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS target_discoveries CASCADE")
    op.execute("DROP TABLE IF EXISTS candidate_transitions CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_hypotheses_parent")
    op.execute("ALTER TABLE programs DROP COLUMN IF EXISTS auto_kill_threshold")
    op.execute("ALTER TABLE programs DROP COLUMN IF EXISTS auto_promote_threshold")
