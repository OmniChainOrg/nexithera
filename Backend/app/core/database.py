import json

import asyncpg
from typing import Optional, Dict, Any
from .config import settings

class Database:
    """Direct PostgreSQL connection pool – no ORM."""
    
    _pool: Optional[asyncpg.Pool] = None
    
    @classmethod
    async def init(cls):
        """Create connection pool."""
        cls._pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            min_size=1,
            max_size=10,
            command_timeout=60,
            init=cls._init_connection,
        )
        
        # Initialize schema
        await cls._init_schema()
        return cls._pool

    @staticmethod
    async def _init_connection(conn: asyncpg.Connection) -> None:
        """Register a JSON/JSONB codec so dicts can be passed as parameters."""
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "json",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
    
    @classmethod
    async def _init_schema(cls):
        """Create tables if they don't exist."""
        async with cls._pool.acquire() as conn:
            # Organizations
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS organizations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            
            # Users
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email TEXT UNIQUE NOT NULL,
                    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'scientist', 'guardian', 'viewer')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            
            # Programs
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS programs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name TEXT NOT NULL,
                    therapeutic_area TEXT NOT NULL,
                    description TEXT,
                    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            # PR #8: pipeline-automation thresholds (per program)
            await conn.execute("""
                ALTER TABLE programs
                    ADD COLUMN IF NOT EXISTS auto_promote_threshold REAL DEFAULT 0.7
            """)
            await conn.execute("""
                ALTER TABLE programs
                    ADD COLUMN IF NOT EXISTS auto_kill_threshold REAL DEFAULT 0.3
            """)
            
            # Zones (epistemic zone references)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS zones (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                    epistemicos_zone_id TEXT NOT NULL,
                    zone_type TEXT NOT NULL,
                    config JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            
            # EpistemicOS runs (trace storage)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS epistemicos_runs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    run_type TEXT NOT NULL CHECK (run_type IN ('ingest', 'embed', 'simulate', 'swarm')),
                    request_payload JSONB NOT NULL,
                    response_payload JSONB,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
                    error_message TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """)
            
            # Data assets
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS data_assets (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    filename TEXT NOT NULL,
                    s3_uri TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    file_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'ingested', 'failed')),
                    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                    epistemicos_run_id UUID REFERENCES epistemicos_runs(id),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            
            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_program_id ON data_assets(program_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_status ON data_assets(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON epistemicos_runs(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_zones_program_id ON zones(program_id)")

            # ---------------- Evidence graph (PR #2) ----------------

            # Bio entities (nodes in the evidence graph)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bio_entities (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    entity_type TEXT NOT NULL CHECK (entity_type IN (
                        'gene', 'protein', 'disease', 'compound',
                        'pathway', 'assay', 'biomarker', 'cell_type', 'species'
                    )),
                    name TEXT NOT NULL,
                    external_id TEXT,
                    external_db TEXT,
                    description TEXT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(entity_type, name, external_id)
                )
            """)

            # References (provenance)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS "references" (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    ref_type TEXT NOT NULL CHECK (ref_type IN (
                        'pubmed', 'doi', 'internal_doc', 'dataset', 'clinical_trial'
                    )),
                    ref_id TEXT NOT NULL,
                    title TEXT,
                    authors JSONB DEFAULT '[]',
                    journal TEXT,
                    year INTEGER,
                    url TEXT,
                    UNIQUE(ref_type, ref_id)
                )
            """)

            # Claims (atomic statements extracted from references)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS claims (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    reference_id UUID NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
                    claim_text TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    confidence REAL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Evidence edges (relationships between bio_entities)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_edges (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    source_id UUID NOT NULL REFERENCES bio_entities(id) ON DELETE CASCADE,
                    target_id UUID NOT NULL REFERENCES bio_entities(id) ON DELETE CASCADE,
                    predicate TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                    is_contradiction BOOLEAN NOT NULL DEFAULT FALSE,
                    claim_id UUID REFERENCES claims(id),
                    reference_id UUID NOT NULL REFERENCES "references"(id) ON DELETE CASCADE,
                    direction TEXT DEFAULT 'directed',
                    evidence_strength TEXT CHECK (evidence_strength IN (
                        'strong', 'moderate', 'weak', 'predicted', 'contradicts'
                    )),
                    notes TEXT,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(source_id, target_id, predicate, reference_id)
                )
            """)

            # Indexes for graph queries
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_bio_entities_name ON bio_entities(name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_bio_entities_type ON bio_entities(entity_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON evidence_edges(source_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON evidence_edges(target_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_predicate ON evidence_edges(predicate)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_confidence ON evidence_edges(confidence DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_reference ON evidence_edges(reference_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_reference ON claims(reference_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_bio_entities_metadata ON bio_entities USING GIN(metadata)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_metadata ON evidence_edges USING GIN(metadata)")

            # ---------------- Hypothesis + Candidate registry (PR #3) ----------------

            # Hypotheses (versioned, evidence-backed)
            await conn.execute("""
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
                    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                    parent_hypothesis_id UUID REFERENCES hypotheses(id),
                    created_by UUID REFERENCES users(id),
                    reviewed_by UUID REFERENCES users(id),
                    reviewed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Evidence supporting or contradicting hypotheses
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS hypothesis_evidence (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
                    evidence_edge_id UUID NOT NULL REFERENCES evidence_edges(id) ON DELETE CASCADE,
                    supports BOOLEAN NOT NULL DEFAULT TRUE,
                    weight REAL DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 2.0),
                    note TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(hypothesis_id, evidence_edge_id)
                )
            """)

            # Candidates (what NexiThera might develop)
            await conn.execute("""
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
                    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                    created_by UUID REFERENCES users(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Scorecards (multi-dimensional candidate evaluation)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS scorecards (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                    evidence_score REAL CHECK (evidence_score >= 0 AND evidence_score <= 10),
                    simulation_score REAL CHECK (simulation_score >= 0 AND simulation_score <= 10),
                    safety_score REAL CHECK (safety_score >= 0 AND safety_score <= 10),
                    formulation_score REAL CHECK (formulation_score >= 0 AND formulation_score <= 10),
                    translational_score REAL CHECK (translational_score >= 0 AND translational_score <= 10),
                    program_fit_score REAL CHECK (program_fit_score >= 0 AND program_fit_score <= 10),
                    overall_score REAL GENERATED ALWAYS AS (
                        (evidence_score + simulation_score + safety_score +
                         formulation_score + translational_score + program_fit_score) / 6.0
                    ) STORED,
                    scoring_rationale TEXT,
                    scored_by UUID REFERENCES users(id),
                    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    version INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(candidate_id, version)
                )
            """)

            # Link hypotheses to candidates
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS candidate_hypotheses (
                    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                    hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
                    PRIMARY KEY (candidate_id, hypothesis_id)
                )
            """)

            # Simulation runs linked to candidates (prep for PR #4)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS candidate_simulations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                    simulation_plan_id UUID,
                    epistemicos_run_id UUID REFERENCES epistemicos_runs(id),
                    results JSONB DEFAULT '{}',
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """)

            # Indexes for hypothesis / candidate queries
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_hypotheses_program ON hypotheses(program_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON hypotheses(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_hypotheses_confidence ON hypotheses(confidence DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_program ON candidates(program_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_target ON candidates(target_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_scorecards_candidate ON scorecards(candidate_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_scorecards_overall ON scorecards(overall_score DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_candidate_simulations_candidate ON candidate_simulations(candidate_id)")
            # PR #8: index on hypothesis parent link (versioning)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_hypotheses_parent ON hypotheses(parent_hypothesis_id)")

            # Shared trigger function for updated_at maintenance
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
            """)

            # Recreate triggers idempotently
            await conn.execute("DROP TRIGGER IF EXISTS update_hypotheses_updated_at ON hypotheses")
            await conn.execute("""
                CREATE TRIGGER update_hypotheses_updated_at
                    BEFORE UPDATE ON hypotheses
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            """)
            await conn.execute("DROP TRIGGER IF EXISTS update_candidates_updated_at ON candidates")
            await conn.execute("""
                CREATE TRIGGER update_candidates_updated_at
                    BEFORE UPDATE ON candidates
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            """)

            # Create default organization for MVP
            await conn.execute("""
                INSERT INTO organizations (id, name) 
                VALUES ('11111111-1111-1111-1111-111111111111', 'NexiThera')
                ON CONFLICT (id) DO NOTHING
            """)

            # ---------------- Agentic orchestration (PR #4) ----------------

            # Agent registry
            await conn.execute("""
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
            """)

            # Agent runs (execution traces)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id UUID NOT NULL REFERENCES agents(id),
                    program_id UUID NOT NULL REFERENCES programs(id),
                    hypothesis_id UUID REFERENCES hypotheses(id),
                    candidate_id UUID REFERENCES candidates(id),
                    run_type TEXT NOT NULL CHECK (run_type IN (
                        'target_assessment', 'evidence_synthesis', 'simulation_critique',
                        'literature_extraction', 'safety_check', 'formulation_analysis',
                        'gap_analysis', 'active_learning'
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
            """)

            # Tool calls made by agents during a run
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_tool_calls (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                    tool_name TEXT NOT NULL,
                    tool_input JSONB NOT NULL,
                    tool_output JSONB,
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ,
                    duration_ms INTEGER,
                    status TEXT DEFAULT 'success'
                )
            """)

            # Agent critiques (self or cross-agent)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_critiques (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                    critic_agent_id UUID REFERENCES agents(id),
                    critique_text TEXT NOT NULL,
                    identifies_weakness BOOLEAN DEFAULT FALSE,
                    suggests_improvement TEXT,
                    severity TEXT CHECK (severity IN ('low', 'medium', 'high')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Evidence edges that informed an agent run
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_evidence_links (
                    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
                    evidence_edge_id UUID NOT NULL REFERENCES evidence_edges(id) ON DELETE CASCADE,
                    weight REAL DEFAULT 1.0,
                    PRIMARY KEY (agent_run_id, evidence_edge_id)
                )
            """)

            # Indexes for agent traces
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_program ON agent_runs(program_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_hypothesis ON agent_runs(hypothesis_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_candidate ON agent_runs(candidate_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_confidence ON agent_runs(confidence DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON agent_tool_calls(agent_run_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_critiques_run ON agent_critiques(agent_run_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_links_run ON agent_evidence_links(agent_run_id)")

            # Keep agents.updated_at fresh via the shared trigger function
            await conn.execute("DROP TRIGGER IF EXISTS update_agents_updated_at ON agents")
            await conn.execute("""
                CREATE TRIGGER update_agents_updated_at
                    BEFORE UPDATE ON agents
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            """)

            # Seed the four MVP agents.  ON CONFLICT keeps this idempotent.
            await conn.execute("""
                INSERT INTO agents (name, role, description, system_prompt, is_active)
                VALUES
                    ('Target Biology Agent', 'target_biology',
                     'Evaluates target relevance, pathway plausibility, and disease fit.',
                     'You are a computational biologist. Evaluate whether a given molecular target is biologically plausible for a specified disease. Consider: pathway position, genetic evidence, expression patterns, essentiality, and existing precedents. Output confidence scores and identify key evidence gaps.',
                     TRUE),
                    ('Oncology & Immunotherapy Agent', 'oncology_immunotherapy',
                     'Focuses on tumor biology, immune mechanisms, biomarkers, and response hypotheses.',
                     'You are a cancer biologist and immunologist. Analyze targets and candidates in the context of tumor microenvironment, immune evasion, checkpoint biology, and biomarker stratification. Prioritize mechanisms with translational potential.',
                     TRUE),
                    ('Evidence Synthesizer Agent', 'evidence_synthesis',
                     'Produces ranked recommendations and decision packages from multiple agent outputs.',
                     'You are a senior scientific reviewer. Synthesize outputs from multiple specialized agents into a coherent recommendation. Weigh confidence scores, identify consensus and disagreement, and produce a final ranked decision package with clear rationale.',
                     TRUE),
                    ('Simulation Critic Agent', 'simulation_critique',
                     'Challenges assumptions, checks model fragility, and identifies missing controls.',
                     'You are a rigorous simulation critic. Review simulation plans and results. Identify: unstated assumptions, model fragility, missing controls, alternative explanations, and overfitting risks. Be constructive but relentless. Science advances by killing bad ideas politely.',
                     TRUE)
                ON CONFLICT (name) DO NOTHING
            """)

            # PR #8: seed Target Discovery Agent for opportunity-gap scans
            await conn.execute("""
                INSERT INTO agents (name, role, description, system_prompt, is_active)
                VALUES
                    ('Target Discovery Agent', 'target_discovery',
                     'Scans the evidence graph for high-potential, under-supported preclinical targets and ranks them by opportunity gap.',
                     'You are a preclinical target-discovery scientist. Identify genes/proteins that are biologically plausible drivers of the disease but have weak existing evidence (high impact, high novelty, low evidence strength). Output a ranked list with proposed mechanistic hypotheses and a recommended next experiment. Do not reason about clinical trials, asset outcomes, or forecasting.',
                     TRUE)
                ON CONFLICT (name) DO NOTHING
            """)

            # ----------------------------------------------------------------
            # PR #8: Preclinical pipeline automation + target discovery
            # ----------------------------------------------------------------
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS candidate_transitions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
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
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS target_discoveries (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_run_id UUID REFERENCES agent_runs(id),
                    program_id UUID NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
                    ranked_targets JSONB NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_transitions_candidate "
                "ON candidate_transitions(candidate_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidate_transitions_created "
                "ON candidate_transitions(created_at DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_target_discoveries_program "
                "ON target_discoveries(program_id)"
            )

            # ----------------------------------------------------------------
            # PR #9: Active Learning + Evidence Gap Analysis
            # ----------------------------------------------------------------
            # Existing databases may have the older agent_runs.run_type CHECK
            # constraint; widen it to include the two new agent run types.
            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_gaps_program "
                "ON evidence_gaps(program_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_gaps_severity "
                "ON evidence_gaps(severity DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evidence_gaps_resolved "
                "ON evidence_gaps(resolved)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposed_experiments_program "
                "ON proposed_experiments(program_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposed_experiments_priority "
                "ON proposed_experiments(priority ASC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposed_experiments_info_gain "
                "ON proposed_experiments(information_gain DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proposed_experiments_hypothesis "
                "ON proposed_experiments(hypothesis_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_experiment_outcomes_experiment "
                "ON experiment_outcomes(proposed_experiment_id)"
            )

            # Reuse the shared updated_at trigger for proposed_experiments.
            await conn.execute(
                "DROP TRIGGER IF EXISTS update_proposed_experiments_updated_at "
                "ON proposed_experiments"
            )
            await conn.execute("""
                CREATE TRIGGER update_proposed_experiments_updated_at
                    BEFORE UPDATE ON proposed_experiments
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
            """)

            # Seed PR #9 agents (idempotent).
            await conn.execute("""
                INSERT INTO agents (name, role, description, system_prompt, is_active)
                VALUES
                    ('Gap Analysis Agent', 'gap_analysis',
                     'Systematically scans the evidence graph for missing edges, low-confidence edges, and unresolved contradictions; scores each gap by severity = impact × uncertainty.',
                     'You are a rigorous evidence auditor. Identify weaknesses in the evidence graph that materially affect active hypotheses and candidates. Do not invent evidence. Do not reason about clinical trials or forecasting.',
                     TRUE),
                    ('Active Learning Agent', 'active_learning',
                     'Proposes experiments that maximize information gain (prior_entropy − expected_posterior_entropy); supports cost-weighted ranking and only emits experiments drawn from a fixed template library.',
                     'You are an active-learning planner. For each gap or hypothesis, enumerate experiments from the template library and rank by information gain per unit cost. Never invent free-form experiments. Preclinical only.',
                     TRUE)
                ON CONFLICT (name) DO NOTHING
            """)


            # ----------------------------------------------------------------
            # Guardian review system (PR #5)
            # ----------------------------------------------------------------
            await conn.execute("""
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
                        'approve', 'request_revision', 'escalate',
                        'park', 'kill', 'promote_to_epistemicos'
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
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS review_assignments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    review_id UUID NOT NULL REFERENCES guardian_reviews(id) ON DELETE CASCADE,
                    assignee_id UUID NOT NULL REFERENCES users(id),
                    assigned_by UUID NOT NULL REFERENCES users(id),
                    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    status TEXT DEFAULT 'pending' CHECK (status IN (
                        'pending', 'accepted', 'declined', 'completed'
                    )),
                    UNIQUE(review_id, assignee_id)
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS review_checklists (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    review_type TEXT NOT NULL,
                    criterion TEXT NOT NULL,
                    criterion_description TEXT,
                    order_index INTEGER DEFAULT 0,
                    is_required BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS review_checklist_responses (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    review_id UUID NOT NULL REFERENCES guardian_reviews(id) ON DELETE CASCADE,
                    checklist_item_id UUID NOT NULL REFERENCES review_checklists(id),
                    passed BOOLEAN NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(review_id, checklist_item_id)
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS review_comments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    review_id UUID NOT NULL REFERENCES guardian_reviews(id) ON DELETE CASCADE,
                    user_id UUID NOT NULL REFERENCES users(id),
                    parent_comment_id UUID REFERENCES review_comments(id),
                    comment_text TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    edited_at TIMESTAMPTZ
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS review_artifacts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    review_id UUID NOT NULL REFERENCES guardian_reviews(id) ON DELETE CASCADE,
                    artifact_type TEXT NOT NULL CHECK (artifact_type IN (
                        'report', 'certificate', 'evidence_package', 'decision_letter'
                    )),
                    artifact_uri TEXT NOT NULL,
                    checksum TEXT,
                    created_by UUID NOT NULL REFERENCES users(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            # Guardian review indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_entity ON guardian_reviews(entity_id, entity_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON guardian_reviews(reviewer_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_decision ON guardian_reviews(decision)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_reviewed_at ON guardian_reviews(reviewed_at DESC)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_assignments_review ON review_assignments(review_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_assignments_assignee ON review_assignments(assignee_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_review ON review_comments(review_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_review ON review_artifacts(review_id)")

            # ===== PR #7: CXU + Swarm + Cross-Zone simulation =====

            # CXU instances (Causal Experience Units)
            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute("""
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
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS simulation_pipelines (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name TEXT NOT NULL,
                    description TEXT,
                    program_id UUID NOT NULL REFERENCES programs(id),
                    steps JSONB NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            await conn.execute("""
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
            """)

            # Advanced simulation indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cxus_zone ON cxus(zone_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cxus_status ON cxus(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cxus_type ON cxus(cxu_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cxu_iterations_cxu ON cxu_iterations(cxu_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_swarms_program ON swarms(program_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_swarms_status ON swarms(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_swarm_members_swarm ON swarm_members(swarm_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_cross_zone_runs_zones ON cross_zone_runs(source_zone_id, target_zone_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_executions_pipeline ON pipeline_executions(pipeline_id)")

            # Seed default zone couplings (idempotent: skip pre-existing rows)
            await conn.execute("""
                INSERT INTO zone_couplings
                    (source_zone_type, target_zone_type, coupling_name,
                     coupling_map, is_bidirectional)
                SELECT v.source_zone_type, v.target_zone_type, v.coupling_name,
                       v.coupling_map::jsonb, v.is_bidirectional
                FROM (VALUES
                    ('tumor_microenvironment', 'pkpd', 'TME_to_PKPD',
                     '{"tumor_volume": "initial_tumor_volume", "immune_infiltration": "clearance_factor"}', FALSE),
                    ('pkpd', 'tumor_microenvironment', 'PKPD_to_TME',
                     '{"drug_concentration": "drug_exposure", "exposure_time": "treatment_duration"}', FALSE),
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
            """)

            # Seed default review checklists (idempotent: skip pre-existing rows)
            await conn.execute("""
                INSERT INTO review_checklists
                    (review_type, criterion, criterion_description, order_index)
                SELECT v.review_type, v.criterion, v.criterion_description, v.order_index
                FROM (VALUES
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
            """)

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Get connection pool (initialized)."""
        if cls._pool is None:
            await cls.init()
        return cls._pool
    
    @classmethod
    async def close(cls):
        """Close connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

# Global instance access
db = Database()
