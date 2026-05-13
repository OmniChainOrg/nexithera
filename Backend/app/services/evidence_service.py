# app/services/evidence_service.py
import uuid
from typing import List, Dict, Any, Optional
from ..core.database import db

class EvidenceService:
    """Manage bio entities and evidence edges."""

    async def create_entity(
        self,
        entity_type: str,
        name: str,
        external_id: Optional[str] = None,
        external_db: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create or retrieve a bio entity."""
        pool = await db.get_pool()
        entity_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            # Check if exists (upsert pattern)
            existing = await conn.fetchrow(
                """SELECT id FROM bio_entities 
                   WHERE entity_type = $1 AND name = $2 
                   AND (external_id IS NOT DISTINCT FROM $3)""",
                entity_type, name, external_id
            )
            if existing:
                row = await conn.fetchrow(
                    "SELECT * FROM bio_entities WHERE id = $1", existing['id']
                )
                return dict(row)

            await conn.execute(
                """INSERT INTO bio_entities 
                   (id, entity_type, name, external_id, external_db, description, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                entity_id, entity_type, name, external_id, external_db, description,
                json.dumps(metadata or {})
            )

            row = await conn.fetchrow("SELECT * FROM bio_entities WHERE id = $1", entity_id)
            return dict(row)

    async def add_evidence(
        self,
        source_name: str,
        source_type: str,
        target_name: str,
        target_type: str,
        predicate: str,
        confidence: float,
        reference_id: str,
        is_contradiction: bool = False,
        evidence_strength: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add an evidence edge between two entities (create entities if missing)."""
        # Create/retrieve both entities
        source = await self.create_entity(source_type, source_name)
        target = await self.create_entity(target_type, target_name)

        pool = await db.get_pool()
        edge_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            # Check if edge already exists
            existing = await conn.fetchrow(
                """SELECT id FROM evidence_edges 
                   WHERE source_id = $1 AND target_id = $2 AND predicate = $3 AND reference_id = $4""",
                source['id'], target['id'], predicate, reference_id
            )
            if existing:
                row = await conn.fetchrow("SELECT * FROM evidence_edges WHERE id = $1", existing['id'])
                return dict(row)

            await conn.execute(
                """INSERT INTO evidence_edges 
                   (id, source_id, target_id, predicate, confidence, is_contradiction, 
                    reference_id, evidence_strength, notes)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                edge_id, source['id'], target['id'], predicate, confidence,
                is_contradiction, reference_id, evidence_strength, notes
            )

            row = await conn.fetchrow("SELECT * FROM evidence_edges WHERE id = $1", edge_id)
            return dict(row)

    async def get_entity_evidence(
        self,
        entity_name: str,
        direction: str = "outgoing"  # 'outgoing', 'incoming', 'both'
    ) -> List[Dict]:
        """Get all evidence for a given entity."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            entity = await conn.fetchrow(
                "SELECT id FROM bio_entities WHERE name = $1", entity_name
            )
            if not entity:
                return []

            if direction in ("outgoing", "both"):
                outgoing = await conn.fetch(
                    """SELECT e.*, 
                              s.name as source_name, s.entity_type as source_type,
                              t.name as target_name, t.entity_type as target_type
                       FROM evidence_edges e
                       JOIN bio_entities s ON e.source_id = s.id
                       JOIN bio_entities t ON e.target_id = t.id
                       WHERE e.source_id = $1
                       ORDER BY e.confidence DESC""",
                    entity['id']
                )
            else:
                outgoing = []

            if direction in ("incoming", "both"):
                incoming = await conn.fetch(
                    """SELECT e.*,
                              s.name as source_name, s.entity_type as source_type,
                              t.name as target_name, t.entity_type as target_type
                       FROM evidence_edges e
                       JOIN bio_entities s ON e.source_id = s.id
                       JOIN bio_entities t ON e.target_id = t.id
                       WHERE e.target_id = $1
                       ORDER BY e.confidence DESC""",
                    entity['id']
                )
            else:
                incoming = []

            results = [dict(row) for row in outgoing] + [dict(row) for row in incoming]
            return results

    async def find_path(
        self,
        source_name: str,
        target_name: str,
        max_depth: int = 3
    ) -> List[Dict]:
        """Find paths between two entities using recursive CTE."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            source = await conn.fetchrow("SELECT id FROM bio_entities WHERE name = $1", source_name)
            target = await conn.fetchrow("SELECT id FROM bio_entities WHERE name = $1", target_name)
            if not source or not target:
                return []

            # Recursive CTE to find paths
            rows = await conn.fetch(
                """
                WITH RECURSIVE path_cte AS (
                    -- Start at source
                    SELECT 
                        source_id, target_id, predicate, confidence,
                        ARRAY[source_id] as visited,
                        ARRAY[source_id, target_id] as path_nodes,
                        ARRAY[predicate] as predicates,
                        1 as depth
                    FROM evidence_edges
                    WHERE source_id = $1 AND NOT is_contradiction
                    
                    UNION ALL
                    
                    -- Recursive step
                    SELECT 
                        e.source_id, e.target_id, e.predicate, e.confidence,
                        p.visited || e.source_id,
                        p.path_nodes || e.target_id,
                        p.predicates || e.predicate,
                        p.depth + 1
                    FROM evidence_edges e
                    JOIN path_cte p ON e.source_id = p.target_id
                    WHERE depth < $2
                      AND NOT (e.source_id = ANY(p.visited))
                      AND NOT e.is_contradiction
                )
                SELECT * FROM path_cte 
                WHERE target_id = $3
                ORDER BY depth, confidence DESC
                LIMIT 10
                """,
                source['id'], max_depth, target['id']
            )

            return [dict(row) for row in rows]

evidence_service = EvidenceService()
