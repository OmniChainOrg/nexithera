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
