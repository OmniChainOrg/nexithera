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
