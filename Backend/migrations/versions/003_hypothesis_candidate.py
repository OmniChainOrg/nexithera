"""hypothesis + candidate registry

Revision ID: 003
Revises: 002
Create Date: 2026-02-10 10:00:00.000000

Adds the hypothesis engine and candidate registry tables: hypotheses,
hypothesis_evidence, candidates, scorecards, candidate_hypotheses, and
candidate_simulations, plus supporting indexes and the shared
`update_updated_at_column` trigger function. Mirrors the idempotent schema
created in `app/core/database.py::_init_schema`.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hypotheses (versioned, evidence-backed)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hypotheses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            version INTEGER NOT NULL DEFAULT 1,
            hypothesis_text TEXT NOT NULL,
            claim_type TEXT NOT NULL CHECK (claim_type IN (
                'target_disease_association',
                'mechanism_of_action',
                'biomarker_stratification',
                'combination_synergy',
                'resistance_mechanism',
                'safety_signal'
            )),
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
                'draft', 'under_review', 'supported', 'refuted', 'deprecated'
            )),
            confidence REAL CHECK (confidence >= 0 AND confidence <= 1),
            uncertainty_reason TEXT,
            program_id UUID NOT NULL
                REFERENCES programs(id) ON DELETE CASCADE,
            parent_hypothesis_id UUID REFERENCES hypotheses(id),
            created_by UUID REFERENCES users(id),
            reviewed_by UUID REFERENCES users(id),
            reviewed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Evidence supporting or contradicting hypotheses
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hypothesis_evidence (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            hypothesis_id UUID NOT NULL
                REFERENCES hypotheses(id) ON DELETE CASCADE,
            evidence_edge_id UUID NOT NULL
                REFERENCES evidence_edges(id) ON DELETE CASCADE,
            supports BOOLEAN NOT NULL DEFAULT TRUE,
            weight REAL DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 2.0),
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(hypothesis_id, evidence_edge_id)
        )
        """
    )

    # Candidates (what NexiThera might develop)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            candidate_type TEXT NOT NULL CHECK (candidate_type IN (
                'small_molecule', 'biologic', 'vaccine', 'immunotherapy',
                'formulation', 'gene_target', 'protein_target',
                'synthetic_biology_construct', 'regenerative_intervention'
            )),
            target_id UUID REFERENCES bio_entities(id),
            mechanism_of_action TEXT,
            therapeutic_area TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'idea' CHECK (status IN (
                'idea', 'evidence_map', 'hypothesis', 'candidate',
                'simulation', 'guardian_review', 'promoted', 'killed', 'parked'
            )),
            kill_rationale TEXT,
            killed_at TIMESTAMPTZ,
            killed_by UUID REFERENCES users(id),
            program_id UUID NOT NULL
                REFERENCES programs(id) ON DELETE CASCADE,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Scorecards (multi-dimensional candidate evaluation)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scorecards (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL
                REFERENCES candidates(id) ON DELETE CASCADE,
            evidence_score REAL
                CHECK (evidence_score >= 0 AND evidence_score <= 10),
            simulation_score REAL
                CHECK (simulation_score >= 0 AND simulation_score <= 10),
            safety_score REAL
                CHECK (safety_score >= 0 AND safety_score <= 10),
            formulation_score REAL
                CHECK (formulation_score >= 0 AND formulation_score <= 10),
            translational_score REAL
                CHECK (translational_score >= 0 AND translational_score <= 10),
            program_fit_score REAL
                CHECK (program_fit_score >= 0 AND program_fit_score <= 10),
            overall_score REAL GENERATED ALWAYS AS (
                (evidence_score + simulation_score + safety_score +
                 formulation_score + translational_score + program_fit_score)
                / 6.0
            ) STORED,
            scoring_rationale TEXT,
            scored_by UUID REFERENCES users(id),
            scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            version INTEGER NOT NULL DEFAULT 1,
            UNIQUE(candidate_id, version)
        )
        """
    )

    # Link hypotheses to candidates
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_hypotheses (
            candidate_id UUID NOT NULL
                REFERENCES candidates(id) ON DELETE CASCADE,
            hypothesis_id UUID NOT NULL
                REFERENCES hypotheses(id) ON DELETE CASCADE,
            PRIMARY KEY (candidate_id, hypothesis_id)
        )
        """
    )

    # Simulation runs linked to candidates (prep for PR #4)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_simulations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID NOT NULL
                REFERENCES candidates(id) ON DELETE CASCADE,
            simulation_plan_id UUID,
            epistemicos_run_id UUID REFERENCES epistemicos_runs(id),
            results JSONB DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )

    # Indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hypotheses_program "
        "ON hypotheses(program_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hypotheses_status "
        "ON hypotheses(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hypotheses_confidence "
        "ON hypotheses(confidence DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidates_program "
        "ON candidates(program_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidates_status "
        "ON candidates(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidates_target "
        "ON candidates(target_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_scorecards_candidate "
        "ON scorecards(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_scorecards_overall "
        "ON scorecards(overall_score DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidate_simulations_candidate "
        "ON candidate_simulations(candidate_id)"
    )

    # Shared trigger function to keep updated_at fresh
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # Triggers (drop-then-create for idempotency)
    op.execute(
        "DROP TRIGGER IF EXISTS update_hypotheses_updated_at ON hypotheses"
    )
    op.execute(
        """
        CREATE TRIGGER update_hypotheses_updated_at
            BEFORE UPDATE ON hypotheses
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS update_candidates_updated_at ON candidates"
    )
    op.execute(
        """
        CREATE TRIGGER update_candidates_updated_at
            BEFORE UPDATE ON candidates
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS update_candidates_updated_at ON candidates"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS update_hypotheses_updated_at ON hypotheses"
    )
    op.execute("DROP TABLE IF EXISTS candidate_simulations CASCADE")
    op.execute("DROP TABLE IF EXISTS candidate_hypotheses CASCADE")
    op.execute("DROP TABLE IF EXISTS scorecards CASCADE")
    op.execute("DROP TABLE IF EXISTS candidates CASCADE")
    op.execute("DROP TABLE IF EXISTS hypothesis_evidence CASCADE")
    op.execute("DROP TABLE IF EXISTS hypotheses CASCADE")
    # Note: update_updated_at_column() is intentionally retained as it may
    # be used by future migrations.
