"""evidence graph

Revision ID: 002
Revises: 001
Create Date: 2026-01-20 10:00:00.000000

Adds the biomedical evidence graph tables: bio_entities, references, claims,
and evidence_edges, plus supporting indexes. Mirrors the idempotent schema
created in `app/core/database.py::_init_schema`.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bio entities (nodes in the evidence graph)
    op.execute(
        """
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
        """
    )

    # References (provenance)
    op.execute(
        """
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
        """
    )

    # Claims (atomic statements extracted from references)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS claims (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            reference_id UUID NOT NULL
                REFERENCES "references"(id) ON DELETE CASCADE,
            claim_text TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            confidence REAL,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    # Evidence edges (relationships between bio_entities)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_edges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id UUID NOT NULL
                REFERENCES bio_entities(id) ON DELETE CASCADE,
            target_id UUID NOT NULL
                REFERENCES bio_entities(id) ON DELETE CASCADE,
            predicate TEXT NOT NULL,
            confidence REAL NOT NULL
                CHECK (confidence >= 0 AND confidence <= 1),
            is_contradiction BOOLEAN NOT NULL DEFAULT FALSE,
            claim_id UUID REFERENCES claims(id),
            reference_id UUID NOT NULL
                REFERENCES "references"(id) ON DELETE CASCADE,
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
        """
    )

    # Indexes for graph queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_bio_entities_name "
        "ON bio_entities(name)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_bio_entities_type "
        "ON bio_entities(entity_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_source "
        "ON evidence_edges(source_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_target "
        "ON evidence_edges(target_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_predicate "
        "ON evidence_edges(predicate)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_confidence "
        "ON evidence_edges(confidence DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_reference "
        "ON evidence_edges(reference_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_claims_reference "
        "ON claims(reference_id)"
    )

    # GIN indexes for JSONB queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_bio_entities_metadata "
        "ON bio_entities USING GIN(metadata)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_edges_metadata "
        "ON evidence_edges USING GIN(metadata)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS evidence_edges CASCADE")
    op.execute("DROP TABLE IF EXISTS claims CASCADE")
    op.execute('DROP TABLE IF EXISTS "references" CASCADE')
    op.execute("DROP TABLE IF EXISTS bio_entities CASCADE")
