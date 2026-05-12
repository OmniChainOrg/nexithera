from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import uuid
from ..core.database import db

router = APIRouter(prefix="/programs", tags=["programs"])

class ProgramCreate(BaseModel):
    name: str
    therapeutic_area: str
    description: Optional[str] = None

class ProgramResponse(BaseModel):
    id: str
    name: str
    therapeutic_area: str
    description: Optional[str]
    status: str
    created_at: str

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