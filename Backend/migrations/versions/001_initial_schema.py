"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-15 10:00:00.000000

Creates the foundational Genovate tables: organizations, users, programs,
zones, epistemicos_runs, data_assets. Mirrors the idempotent schema in
`app/core/database.py::_init_schema`.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE NOT NULL,
            organization_id UUID NOT NULL
                REFERENCES organizations(id) ON DELETE CASCADE,
            role TEXT NOT NULL
                CHECK (role IN ('admin', 'scientist', 'guardian', 'viewer')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS programs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            therapeutic_area TEXT NOT NULL,
            description TEXT,
            organization_id UUID NOT NULL
                REFERENCES organizations(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'archived')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS zones (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            program_id UUID NOT NULL
                REFERENCES programs(id) ON DELETE CASCADE,
            epistemicos_zone_id TEXT NOT NULL,
            zone_type TEXT NOT NULL,
            config JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS epistemicos_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            run_type TEXT NOT NULL
                CHECK (run_type IN ('ingest', 'embed', 'simulate', 'swarm')),
            request_payload JSONB NOT NULL,
            response_payload JSONB,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'completed', 'failed')),
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS data_assets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            filename TEXT NOT NULL,
            s3_uri TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'ingested', 'failed')),
            program_id UUID NOT NULL
                REFERENCES programs(id) ON DELETE CASCADE,
            epistemicos_run_id UUID REFERENCES epistemicos_runs(id),
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_assets_program_id "
        "ON data_assets(program_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_assets_status ON data_assets(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_runs_status "
        "ON epistemicos_runs(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_zones_program_id ON zones(program_id)"
    )

    op.execute(
        """
        INSERT INTO organizations (id, name)
        VALUES ('11111111-1111-1111-1111-111111111111', 'NexiThera')
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS data_assets CASCADE")
    op.execute("DROP TABLE IF EXISTS epistemicos_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS zones CASCADE")
    op.execute("DROP TABLE IF EXISTS programs CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS organizations CASCADE")
