import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.database import db
from ..schemas.program import ProgramCreate, ProgramResponse
from ..services.pipeline_service import pipeline_service

router = APIRouter(prefix="/programs", tags=["programs"])

@router.post("", response_model=ProgramResponse)
async def create_program(program: ProgramCreate):
    """Create a new drug discovery program."""
    pool = await db.get_pool()
    program_id = str(uuid.uuid4())
    
    async with pool.acquire() as conn:
        # Default organization for MVP
        org_id = "11111111-1111-1111-1111-111111111111"
        
        row = await conn.fetchrow("""
            INSERT INTO programs (id, name, therapeutic_area, description, organization_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, name, therapeutic_area, description, status, created_at
        """, program_id, program.name, program.therapeutic_area, program.description, org_id)
    
    return dict(row)

@router.get("", response_model=list[ProgramResponse])
async def list_programs():
    """List all programs for the default organization."""
    pool = await db.get_pool()

    async with pool.acquire() as conn:
        # Default organization for MVP
        org_id = "11111111-1111-1111-1111-111111111111"
        rows = await conn.fetch("""
            SELECT id, name, therapeutic_area, description, status, created_at
            FROM programs
            WHERE organization_id = $1
            ORDER BY created_at DESC
        """, org_id)

    return [dict(row) for row in rows]

@router.get("/{program_id}", response_model=ProgramResponse)
async def get_program(program_id: str):
    """Get program details."""
    pool = await db.get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT id, name, therapeutic_area, description, status, created_at
            FROM programs
            WHERE id = $1
        """, program_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Program not found")
    
    return dict(row)


class ProgramStatusUpdate(BaseModel):
    status: str


@router.patch("/{program_id}", response_model=ProgramResponse)
async def update_program(program_id: str, payload: ProgramStatusUpdate):
    """Update program status (e.g. archive)."""
    allowed = ("active", "archived")
    if payload.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {allowed}",
        )

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE programs
               SET status = $2, updated_at = NOW()
             WHERE id = $1
            RETURNING id, name, therapeutic_area, description, status, created_at
        """, program_id, payload.status)

    if not row:
        raise HTTPException(status_code=404, detail="Program not found")

    return dict(row)


# ---------------------------------------------------------------------------
# PR #8: Pipeline view + threshold configuration
# ---------------------------------------------------------------------------
class PipelineThresholdsUpdate(BaseModel):
    auto_promote_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    auto_kill_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)


@router.get("/{program_id}/pipeline")
async def get_program_pipeline(program_id: str):
    """Return all candidates in a program with status, latest scorecard,
    pending Guardian actions, and recommended next step (PR #8)."""
    try:
        return await pipeline_service.get_program_pipeline(program_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{program_id}/thresholds")
async def update_pipeline_thresholds(
    program_id: str, payload: PipelineThresholdsUpdate
):
    """Configure auto_promote / auto_kill thresholds for a program."""
    if (
        payload.auto_promote_threshold is None
        and payload.auto_kill_threshold is None
    ):
        raise HTTPException(
            status_code=400,
            detail="At least one threshold must be provided.",
        )
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE programs
                   SET auto_promote_threshold =
                           COALESCE($2, auto_promote_threshold),
                       auto_kill_threshold =
                           COALESCE($3, auto_kill_threshold),
                       updated_at = NOW()
                   WHERE id = $1
               RETURNING id, name, auto_promote_threshold, auto_kill_threshold""",
            program_id,
            payload.auto_promote_threshold,
            payload.auto_kill_threshold,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Program not found")
    return dict(row)
