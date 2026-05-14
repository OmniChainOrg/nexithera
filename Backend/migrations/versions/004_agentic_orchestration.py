"""agentic orchestration

Revision ID: 004
Revises: 003
Create Date: 2026-03-15 10:00:00.000000

Adds the agentic orchestration tables: agents, agent_runs, agent_tool_calls,
agent_critiques, and agent_evidence_links, plus supporting indexes.  Seeds
the four MVP agents (Target Biology, Oncology & Immunotherapy, Evidence
Synthesizer, Simulation Critic).  Mirrors the idempotent schema created in
``app/core/database.py::_init_schema``.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agent registry (what agents exist)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            description TEXT,
            capabilities JSONB DEFAULT '[]',
            system_prompt TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Agent runs (execution traces)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id UUID NOT NULL REFERENCES agents(id),
            program_id UUID NOT NULL REFERENCES programs(id),
            hypothesis_id UUID REFERENCES hypotheses(id),
            candidate_id UUID REFERENCES candidates(id),
            run_type TEXT NOT NULL CHECK (run_type IN (
                'target_assessment', 'evidence_synthesis', 'simulation_critique',
                'literature_extraction', 'safety_check', 'formulation_analysis'
            )),
            input_bundle JSONB NOT NULL,
            output_summary TEXT,
            output_structure JSONB,
            confidence REAL CHECK (confidence >= 0 AND confidence <= 1),
            uncertainty_reason TEXT,
            recommended_next_step TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                'pending', 'running', 'completed', 'failed'
            )),
            error_message TEXT,
            trace_summary TEXT,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Tool calls made by agents during a run
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_tool_calls (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_run_id UUID NOT NULL
                REFERENCES agent_runs(id) ON DELETE CASCADE,
            tool_name TEXT NOT NULL,
            tool_input JSONB NOT NULL,
            tool_output JSONB,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            duration_ms INTEGER,
            status TEXT DEFAULT 'success'
        )
        """
    )

    # Critiques (agent self-critique or cross-agent critique)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_critiques (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_run_id UUID NOT NULL
                REFERENCES agent_runs(id) ON DELETE CASCADE,
            critic_agent_id UUID REFERENCES agents(id),
            critique_text TEXT NOT NULL,
            identifies_weakness BOOLEAN DEFAULT FALSE,
            suggests_improvement TEXT,
            severity TEXT CHECK (severity IN ('low', 'medium', 'high')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Evidence links from agent runs
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_evidence_links (
            agent_run_id UUID NOT NULL
                REFERENCES agent_runs(id) ON DELETE CASCADE,
            evidence_edge_id UUID NOT NULL
                REFERENCES evidence_edges(id) ON DELETE CASCADE,
            weight REAL DEFAULT 1.0,
            PRIMARY KEY (agent_run_id, evidence_edge_id)
        )
        """
    )

    # Indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent "
        "ON agent_runs(agent_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_program "
        "ON agent_runs(program_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_hypothesis "
        "ON agent_runs(hypothesis_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_candidate "
        "ON agent_runs(candidate_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_status "
        "ON agent_runs(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_runs_confidence "
        "ON agent_runs(confidence DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tool_calls_run "
        "ON agent_tool_calls(agent_run_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_critiques_run "
        "ON agent_critiques(agent_run_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_evidence_links_run "
        "ON agent_evidence_links(agent_run_id)"
    )

    # Trigger to keep agents.updated_at fresh (reuses shared function from 003)
    op.execute(
        "DROP TRIGGER IF EXISTS update_agents_updated_at ON agents"
    )
    op.execute(
        """
        CREATE TRIGGER update_agents_updated_at
            BEFORE UPDATE ON agents
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # Seed the four MVP agents.  Use ON CONFLICT to make the migration
    # idempotent if it is re-run against a partially-populated database.
    op.execute(
        """
        INSERT INTO agents (name, role, description, system_prompt, is_active)
        VALUES
            (
                'Target Biology Agent',
                'target_biology',
                'Evaluates target relevance, pathway plausibility, and disease fit.',
                'You are a computational biologist. Evaluate whether a given molecular target is biologically plausible for a specified disease. Consider: pathway position, genetic evidence, expression patterns, essentiality, and existing precedents. Output confidence scores and identify key evidence gaps.',
                TRUE
            ),
            (
                'Oncology & Immunotherapy Agent',
                'oncology_immunotherapy',
                'Focuses on tumor biology, immune mechanisms, biomarkers, and response hypotheses.',
                'You are a cancer biologist and immunologist. Analyze targets and candidates in the context of tumor microenvironment, immune evasion, checkpoint biology, and biomarker stratification. Prioritize mechanisms with translational potential.',
                TRUE
            ),
            (
                'Evidence Synthesizer Agent',
                'evidence_synthesis',
                'Produces ranked recommendations and decision packages from multiple agent outputs.',
                'You are a senior scientific reviewer. Synthesize outputs from multiple specialized agents into a coherent recommendation. Weigh confidence scores, identify consensus and disagreement, and produce a final ranked decision package with clear rationale.',
                TRUE
            ),
            (
                'Simulation Critic Agent',
                'simulation_critique',
                'Challenges assumptions, checks model fragility, and identifies missing controls.',
                'You are a rigorous simulation critic. Review simulation plans and results. Identify: unstated assumptions, model fragility, missing controls, alternative explanations, and overfitting risks. Be constructive but relentless. Science advances by killing bad ideas politely.',
                TRUE
            )
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_agents_updated_at ON agents")
    op.execute("DROP TABLE IF EXISTS agent_evidence_links CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_critiques CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_tool_calls CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS agents CASCADE")
