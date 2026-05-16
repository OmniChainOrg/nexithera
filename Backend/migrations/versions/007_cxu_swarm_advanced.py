"""cxu, swarm, cross-zone simulation tables

Revision ID: 007
Revises: 005
Create Date: 2026-05-16 00:00:00.000000

Adds the advanced EpistemicOS workflow surface used by PR #7:

    * ``cxus`` and ``cxu_iterations``       — Causal Experience Unit lifecycle
    * ``swarms`` / ``swarm_members`` / ``swarm_results``
                                            — swarm orchestration + aggregation
    * ``zone_couplings``                    — reusable coupling-map registry
    * ``cross_zone_runs``                   — coupled cross-zone simulations
    * ``simulation_pipelines`` / ``pipeline_executions``
                                            — multi-step simulation workflows

Mirrors the idempotent schema created in
``app/core/database.py::_init_schema``.  All statements are ``IF NOT EXISTS``
so the migration is safe to re-run.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "007"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CXU instances (Causal Experience Units)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cxus (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            cxu_type TEXT NOT NULL CHECK (cxu_type IN (
                'tumor_microenvironment', 'pkpd', 'pathway_signaling',
                'immune_response', 'resistance_evolution', 'dose_response'
            )),
            zone_id UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
            epistemicos_cxu_id TEXT NOT NULL,
            configuration JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'created' CHECK (status IN (
                'created', 'initializing', 'running', 'paused',
                'completed', 'failed', 'terminated'
            )),
            current_iteration INTEGER DEFAULT 0,
            last_checkpoint JSONB,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            terminated_at TIMESTAMPTZ
        )
        """
    )

    # CXU execution history (checkpoints / iterations)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cxu_iterations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cxu_id UUID NOT NULL REFERENCES cxus(id) ON DELETE CASCADE,
            iteration_number INTEGER NOT NULL,
            input_state JSONB,
            output_state JSONB,
            metrics JSONB DEFAULT '{}',
            trace_id TEXT,
            duration_ms INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(cxu_id, iteration_number)
        )
        """
    )

    # Swarm definitions
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS swarms (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            swarm_type TEXT NOT NULL CHECK (swarm_type IN (
                'cooperative', 'competitive', 'ensemble', 'adversarial'
            )),
            objective TEXT NOT NULL,
            configuration JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'created' CHECK (status IN (
                'created', 'provisioning', 'running', 'aggregating',
                'completed', 'failed'
            )),
            epistemicos_swarm_id TEXT,
            program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )

    # Swarm members
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_members (
            swarm_id UUID NOT NULL REFERENCES swarms(id) ON DELETE CASCADE,
            cxu_id UUID NOT NULL REFERENCES cxus(id) ON DELETE CASCADE,
            member_index INTEGER NOT NULL,
            role TEXT DEFAULT 'worker' CHECK (role IN (
                'worker', 'leader', 'critic', 'arbiter'
            )),
            weight REAL DEFAULT 1.0,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (swarm_id, cxu_id)
        )
        """
    )

    # Swarm results (aggregated outputs)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS swarm_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            swarm_id UUID NOT NULL REFERENCES swarms(id) ON DELETE CASCADE,
            aggregation_method TEXT NOT NULL CHECK (aggregation_method IN (
                'consensus', 'weighted_average', 'best_of',
                'voting', 'meta_learner'
            )),
            aggregated_output JSONB,
            consensus_score REAL,
            best_cxu_id UUID REFERENCES cxus(id),
            diversity_metric REAL,
            trace_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Zone coupling registry (reusable coupling maps)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS zone_couplings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_zone_type TEXT NOT NULL,
            target_zone_type TEXT NOT NULL,
            coupling_name TEXT NOT NULL,
            coupling_map JSONB NOT NULL,
            is_bidirectional BOOLEAN DEFAULT FALSE,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(source_zone_type, target_zone_type, coupling_name)
        )
        """
    )

    # Cross-zone simulation runs
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cross_zone_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT,
            source_zone_id UUID NOT NULL REFERENCES zones(id),
            target_zone_id UUID NOT NULL REFERENCES zones(id),
            coupling_id UUID REFERENCES zone_couplings(id),
            coupling_map JSONB,
            input_state JSONB,
            output_state JSONB,
            status TEXT DEFAULT 'pending',
            epistemicos_run_id TEXT,
            trace_id TEXT,
            program_id UUID NOT NULL REFERENCES programs(id),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Simulation pipelines
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_pipelines (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            description TEXT,
            program_id UUID NOT NULL REFERENCES programs(id),
            steps JSONB NOT NULL,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Pipeline executions
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_executions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pipeline_id UUID NOT NULL REFERENCES simulation_pipelines(id),
            execution_id TEXT NOT NULL,
            current_step INTEGER DEFAULT 0,
            step_results JSONB DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            trace_id TEXT,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_cxus_zone ON cxus(zone_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cxus_status ON cxus(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cxus_type ON cxus(cxu_type)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cxu_iterations_cxu ON cxu_iterations(cxu_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_swarms_program ON swarms(program_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_swarms_status ON swarms(status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_swarm_members_swarm ON swarm_members(swarm_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_cross_zone_runs_zones "
        "ON cross_zone_runs(source_zone_id, target_zone_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pipeline_executions_pipeline "
        "ON pipeline_executions(pipeline_id)"
    )

    # Seed default zone couplings (idempotent: skip pre-existing rows).
    op.execute(
        """
        INSERT INTO zone_couplings
            (source_zone_type, target_zone_type, coupling_name,
             coupling_map, is_bidirectional)
        SELECT v.source_zone_type, v.target_zone_type, v.coupling_name,
               v.coupling_map::jsonb, v.is_bidirectional
        FROM (VALUES
            ('tumor_microenvironment', 'pkpd', 'TME_to_PKPD',
             '{"tumor_volume": "initial_tumor_volume", '
             '"immune_infiltration": "clearance_factor"}', FALSE),
            ('pkpd', 'tumor_microenvironment', 'PKPD_to_TME',
             '{"drug_concentration": "drug_exposure", '
             '"exposure_time": "treatment_duration"}', FALSE),
            ('pathway_signaling', 'immune_response', 'Signaling_to_Immune',
             '{"pathway_activity": "immune_activation_signal"}', TRUE)
        ) AS v(source_zone_type, target_zone_type, coupling_name,
               coupling_map, is_bidirectional)
        WHERE NOT EXISTS (
            SELECT 1 FROM zone_couplings zc
            WHERE zc.source_zone_type = v.source_zone_type
              AND zc.target_zone_type = v.target_zone_type
              AND zc.coupling_name = v.coupling_name
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pipeline_executions CASCADE")
    op.execute("DROP TABLE IF EXISTS simulation_pipelines CASCADE")
    op.execute("DROP TABLE IF EXISTS cross_zone_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS zone_couplings CASCADE")
    op.execute("DROP TABLE IF EXISTS swarm_results CASCADE")
    op.execute("DROP TABLE IF EXISTS swarm_members CASCADE")
    op.execute("DROP TABLE IF EXISTS swarms CASCADE")
    op.execute("DROP TABLE IF EXISTS cxu_iterations CASCADE")
    op.execute("DROP TABLE IF EXISTS cxus CASCADE")
