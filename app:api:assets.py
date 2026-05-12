from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
from typing import Optional
from ..services.asset_service import asset_service
from ..core.database import db

router = APIRouter(prefix="/programs/{program_id}/assets", tags=["assets"])

class AssetResponse(BaseModel):
    asset_id: str
    filename: str
    status: str
    epistemicos_run_id: Optional[str]
    embedding_collection_id: Optional[str]
    chunk_count: Optional[int]

@router.post("", response_model=AssetResponse)
async def upload_asset(
    program_id: str,
    file: UploadFile = File(...)
):
    """Upload a data asset to a program."""
    # Verify program exists
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        program = await conn.fetchrow("SELECT id FROM programs WHERE id = $1", program_id)
        if not program:
            raise HTTPException(status_code=404, detail="Program not found")
    
    # Read file content
    content = await file.read()
    
    # Determine file type
    file_type = file.content_type or "application/octet-stream"
    if file.filename.endswith(".pdf"):
        file_type = "application/pdf"
    elif file.filename.endswith(".csv"):
        file_type = "text/csv"
    elif file.filename.endswith(".json"):
        file_type = "application/json"
    
    # Create asset (sync - will trigger EpistemicOS ingestion)
    result = await asset_service.create_asset(
        program_id=program_id,
        filename=file.filename,
        file_content=content,
        file_type=file_type
    )
    
    return result

@router.get("")
async def list_assets(program_id: str):
    """List all assets for a program."""
    assets = await asset_service.list_assets(program_id)
    return {"assets": assets}