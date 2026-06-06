"""active learning + evidence gap analysis (PR #9)

Revision ID: 009
Revises: 008
Create Date: 2026-06-06 12:30:00.000000

Adds the PR #9 (Genovate Precog) tables that enable proactive evidence
gap analysis and active-learning experiment recommendations:

    * ``evidence_gaps``        — systematically identified weaknesses in
                                 the evidence graph (missing edges,
                                 low-confidence edges, unresolved
                                 contradictions, missing dose/tissue/
                                 timecourse data).
    * ``proposed_experiments`` — ranked experiments produced by the
                                 Active Learning Agent, each tied to a
                                 template type (no hallucinated free-form
                                 experiments allowed).
    * ``experiment_outcomes``  — feedback loop closing the cycle:
                                 records what a conducted experiment
                                 found and the updated confidence.

The migration also extends the existing ``agent_runs.run_type`` CHECK
constraint with the two new agent types (``gap_analysis``,
``active_learning``) so the orchestrator can record traces without
having to widen the schema in ``app/core/database.py`` first.

All statements are idempotent (``IF NOT EXISTS`` / ``DO $$``) so the
migration is safe to re-run.  This migration introduces no clinical-
trial or forecasting structures; it is preclinical-only.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend agent_runs.run_type CHECK so gap_analysis / active_learning
    # traces can be persisted by BaseAgent.run().
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                 WHERE conname = 'agent_runs_run_type_check'
            ) THEN
                ALTER TABLE agent_runs
                    DROP CONSTRAINT agent_runs_run_type_check;
            END IF;
            ALTER TABLE agent_runs
                ADD CONSTRAINT agent_runs_run_type_check
                CHECK (run_type IN (
                    'target_assessment', 'evidence_synthesis',
                    'simulation_critique', 'literature_extraction',
                    'safety_check', 'formulation_analysis',
                    'gap_analysis', 'active_learning'
                ));
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_gaps (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            program_id UUID NOT NULL
                REFERENCES programs(id) ON DELETE CASCADE,
            entity_type TEXT,
            entity_id UUID REFERENCES bio_entities(id) ON DELETE SET NULL,
            related_entity_id UUID REFERENCES bio_entities(id) ON DELETE SET NULL,
            hypothesis_id UUID REFERENCES hypotheses(id) ON DELETE SET NULL,
            gap_type TEXT NOT NULL CHECK (gap_type IN (
                'missing_edge', 'low_confidence',
                'contradiction_unresolved', 'missing_dose_response',
                'missing_tissue_data', 'missing_timecourse'
            )),
            description TEXT,
            severity REAL NOT NULL CHECK (severity >= 0 AND severity <= 1),
            proposed_experiment TEXT,
            estimated_information_gain REAL,
            resolved BOOLEAN NOT NULL DEFAULT FALSE,
            agent_run_id UUID REFERENCES agent_runs(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposed_experiments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            program_id UUID REFERENCES programs(id) ON DELETE CASCADE,
            hypothesis_id UUID REFERENCES hypotheses(id) ON DELETE CASCADE,
            candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
            gap_id UUID REFERENCES evidence_gaps(id) ON DELETE SET NULL,
            agent_run_id UUID REFERENCES agent_runs(id),
            experiment_type TEXT NOT NULL CHECK (experiment_type IN (
                'literature_mining', 'in_silico_simulation',
                'in_vitro_assay', 'in_vivo_model',
                'biomarker_analysis', 'omics_profiling'
            )),
            template_id TEXT NOT NULL,
            description TEXT NOT NULL,
            expected_outcomes JSONB NOT NULL DEFAULT '{}',
            prior_entropy REAL,
            expected_posterior_entropy REAL,
            information_gain REAL NOT NULL,
            cost_estimate REAL,
            duration_days INTEGER,
            value_per_unit_cost REAL,
            priority INTEGER NOT NULL CHECK (priority >= 1 AND priority <= 10),
            status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN (
                'proposed', 'queued', 'running', 'completed',
                'cancelled', 'rejected'
            )),
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS experiment_outcomes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            proposed_experiment_id UUID NOT NULL
                REFERENCES proposed_experiments(id) ON DELETE CASCADE,
            conducted_by UUID REFERENCES users(id),
            conducted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            result_summary TEXT,
            result_data JSONB DEFAULT '{}',
            prior_confidence REAL,
            updated_confidence REAL,
            information_gain_observed REAL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_gaps_program "
        "ON evidence_gaps(program_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_gaps_severity "
        "ON evidence_gaps(severity DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_gaps_resolved "
        "ON evidence_gaps(resolved)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_proposed_experiments_program "
        "ON proposed_experiments(program_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_proposed_experiments_priority "
        "ON proposed_experiments(priority ASC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_proposed_experiments_info_gain "
        "ON proposed_experiments(information_gain DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_proposed_experiments_hypothesis "
        "ON proposed_experiments(hypothesis_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_experiment_outcomes_experiment "
        "ON experiment_outcomes(proposed_experiment_id)"
    )

    # Seed the two new agents (idempotent).
    op.execute(
        """
        INSERT INTO agents (name, role, description, system_prompt, is_active)
        VALUES
            ('Gap Analysis Agent', 'gap_analysis',
             'Systematically scans the evidence graph for missing edges, '
             'low-confidence edges, and unresolved contradictions; scores '
             'each gap by severity = impact × uncertainty.',
             'You are a rigorous evidence auditor. Identify weaknesses in '
             'the evidence graph that materially affect active hypotheses '
             'and candidates. Do not invent evidence. Do not reason about '
             'clinical trials or forecasting.', TRUE),
            ('Active Learning Agent', 'active_learning',
             'Proposes experiments that maximize information gain '
             '(prior_entropy − expected_posterior_entropy), supports '
             'cost-weighted ranking, and only emits experiments drawn '
             'from a fixed template library.',
             'You are an active-learning planner. For each gap or '
             'hypothesis, enumerate experiments from the template library '
             'and rank by information gain per unit cost. Never invent '
             'free-form experiments. Preclinical only.', TRUE)
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS experiment_outcomes CASCADE")
    op.execute("DROP TABLE IF EXISTS proposed_experiments CASCADE")
    op.execute("DROP TABLE IF EXISTS evidence_gaps CASCADE")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                 WHERE conname = 'agent_runs_run_type_check'
            ) THEN
                ALTER TABLE agent_runs
                    DROP CONSTRAINT agent_runs_run_type_check;
            END IF;
            ALTER TABLE agent_runs
                ADD CONSTRAINT agent_runs_run_type_check
                CHECK (run_type IN (
                    'target_assessment', 'evidence_synthesis',
                    'simulation_critique', 'literature_extraction',
                    'safety_check', 'formulation_analysis'
                ));
        END $$;
        """
    )
