# app/api/evidence.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from ..services.evidence_service import evidence_service

router = APIRouter(prefix="/evidence", tags=["evidence"])

class EntityCreate(BaseModel):
    entity_type: str
    name: str
    external_id: Optional[str] = None
    external_db: Optional[str] = None
    description: Optional[str] = None

class EvidenceCreate(BaseModel):
    source_name: str
    source_type: str
    target_name: str
    target_type: str
    predicate: str
    confidence: float
    reference_id: str
    is_contradiction: bool = False
    evidence_strength: Optional[str] = None
    notes: Optional[str] = None

@router.post("/entities")
async def create_entity(entity: EntityCreate):
    """Create or retrieve a bio entity."""
    result = await evidence_service.create_entity(
        entity_type=entity.entity_type,
        name=entity.name,
        external_id=entity.external_id,
        external_db=entity.external_db,
        description=entity.description
    )
    return result

@router.post("/edges")
async def add_evidence(evidence: EvidenceCreate):
    """Add an evidence edge between two entities."""
    result = await evidence_service.add_evidence(
        source_name=evidence.source_name,
        source_type=evidence.source_type,
        target_name=evidence.target_name,
        target_type=evidence.target_type,
        predicate=evidence.predicate,
        confidence=evidence.confidence,
        reference_id=evidence.reference_id,
        is_contradiction=evidence.is_contradiction,
        evidence_strength=evidence.evidence_strength,
        notes=evidence.notes
    )
    return result

@router.get("/entities/{entity_name}/evidence")
async def get_entity_evidence(
    entity_name: str,
    direction: str = Query("both", regex="^(outgoing|incoming|both)$")
):
    """Get all evidence for an entity."""
    results = await evidence_service.get_entity_evidence(entity_name, direction)
    return {"entity": entity_name, "evidence_count": len(results), "evidence": results}

@router.get("/paths")
async def find_path(
    source: str,
    target: str,
    max_depth: int = Query(3, ge=1, le=5)
):
    """Find paths between two entities."""
    results = await evidence_service.find_path(source, target, max_depth)
    return {"source": source, "target": target, "paths": results}

@router.get("/entities")
async def list_entities(
    entity_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List bio entities with optional type filter."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        if entity_type:
            rows = await conn.fetch(
                "SELECT * FROM bio_entities WHERE entity_type = $1 ORDER BY name LIMIT $2 OFFSET $3",
                entity_type, limit, offset
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM bio_entities ORDER BY name LIMIT $1 OFFSET $2",
                limit, offset
            )
        total = await conn.fetchval("SELECT COUNT(*) FROM bio_entities")
        return {"entities": [dict(r) for r in rows], "total": total}
