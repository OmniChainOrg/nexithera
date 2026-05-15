import uuid
import json
from typing import Dict, Any, Optional
from ..core.database import db
from ..core.storage import storage
from .epistemicos_client import epistemicos_client

class AssetService:
    """Handle data asset upload, metadata tracking, and EpistemicOS ingestion."""
    
    async def create_asset(
        self,
        program_id: str,
        filename: str,
        file_content: bytes,
        file_type: str
    ) -> Dict[str, Any]:
        """
        Upload file to S3, register in DB, trigger REAL EpistemicOS ingestion.
        """
        # 1. Upload to S3
        s3_uri = await storage.upload_file(
            bucket="genovate-assets",
            key=f"{program_id}/{uuid.uuid4()}/{filename}",
            content=file_content,
            content_type=file_type
        )
        
        file_size = len(file_content)
        
        # 2. Create EpistemicOS run record (pending)
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Create initial asset record
            asset_id = str(uuid.uuid4())
            
            # Create epistemicos run first (local UUID; EpistemicOS trace_id stored in response_payload)
            eos_run_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO epistemicos_runs (id, run_type, request_payload, status)
                VALUES ($1, $2, $3, $4)
            """, eos_run_id, "ingest", {"filename": filename, "program_id": program_id}, "pending")
            
            # Insert asset
            await conn.execute("""
                INSERT INTO data_assets (id, filename, s3_uri, size_bytes, file_type, status, program_id, epistemicos_run_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, asset_id, filename, s3_uri, file_size, file_type, "pending", program_id, eos_run_id)
        
        # 3. Call REAL EpistemicOS ingestion
        try:
            eos_result = await epistemicos_client.ingest_document(
                document_uri=s3_uri,
                file_type=file_type,
                program_context={
                    "program_id": program_id,
                    "filename": filename,
                    "asset_id": asset_id,
                },
                program_id=program_id,
            )
            
            # Update run with results
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE epistemicos_runs 
                    SET response_payload = $1, status = 'completed', completed_at = NOW()
                    WHERE id = $2
                """, eos_result, eos_run_id)
                
                # Update asset status + store embedding_collection_id + EpistemicOS trace_id in metadata
                asset_metadata = {
                    "embedding_collection_id": eos_result.get("embedding_collection_id"),
                    "epistemicos_trace_id": eos_result.get("trace_id"),
                    "vector_count": eos_result.get("vector_count", 0),
                }
                await conn.execute("""
                    UPDATE data_assets 
                    SET status = 'ingested',
                        metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                    WHERE id = $1
                """, asset_id, json.dumps(asset_metadata))
            
            return {
                "asset_id": asset_id,
                "filename": filename,
                "status": "ingested",
                "epistemicos_run_id": eos_run_id,
                "epistemicos_trace_id": eos_result.get("trace_id"),
                "embedding_collection_id": eos_result.get("embedding_collection_id"),
                "chunk_count": eos_result.get("vector_count", 0)
            }
            
        except Exception as e:
            # Mark as failed
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE epistemicos_runs 
                    SET status = 'failed', error_message = $1, completed_at = NOW()
                    WHERE id = $2
                """, str(e), eos_run_id)
                
                await conn.execute("""
                    UPDATE data_assets 
                    SET status = 'failed'
                    WHERE id = $1
                """, asset_id)
            raise
    
    async def list_assets(self, program_id: str) -> list:
        """List all assets for a program."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, filename, size_bytes, file_type, status, created_at
                FROM data_assets
                WHERE program_id = $1
                ORDER BY created_at DESC
            """, program_id)
            
            return [dict(row) for row in rows]

asset_service = AssetService()
