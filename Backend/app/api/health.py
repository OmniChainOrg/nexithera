from fastapi import APIRouter
from ..core.database import db

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status,
        "service": "genovate"
    }
