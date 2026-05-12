import uuid
import json
from typing import Dict, Any, Optional
import httpx
from ..core.config import settings

class EpistemicOSClient:
    """
    Client for EpistemicOS – handles ingestion, embedding, simulation.
    MVP uses mock mode; real calls when EPISTEMICOS_MOCK_MODE=false.
    """
    
    def __init__(self):
        self.base_url = settings.EPISTEMICOS_URL
        self.mock_mode = settings.EPISTEMICOS_MOCK_MODE
    
    async def ingest_document(
        self,
        document_uri: str,
        file_type: str,
        program_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send document to EpistemicOS for chunking + embedding.
        Returns collection ID and chunk references.
        """
        if self.mock_mode:
            # Mock response for MVP
            return {
                "embedding_collection_id": f"emb_{uuid.uuid4().hex[:12]}",
                "chunk_ids": [f"chunk_{i}_{uuid.uuid4().hex[:6]}" for i in range(5)],
                "vector_count": 5,
                "status": "completed",
                "trace_id": f"trace_{uuid.uuid4().hex[:8]}"
            }
        
        # Real EpistemicOS call
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/ingest",
                json={
                    "document_uri": document_uri,
                    "file_type": file_type,
                    "metadata": program_context
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def create_zone(
        self,
        program_id: str,
        zone_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request EpistemicOS to create a new zone."""
        if self.mock_mode:
            return {
                "epistemicos_zone_id": f"zone_{uuid.uuid4().hex[:12]}",
                "status": "created",
                "zone_type": zone_type
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/zones",
                json={
                    "program_id": program_id,
                    "zone_type": zone_type,
                    "config": config
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def simulate(
        self,
        zone_id: str,
        simulation_type: str,
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request EpistemicOS to run a simulation in a zone."""
        if self.mock_mode:
            return {
                "run_id": f"sim_{uuid.uuid4().hex[:12]}",
                "status": "completed",
                "results": {"mock_output": "simulation result placeholder"},
                "confidence": 0.85
            }
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/simulate",
                json={
                    "zone_id": zone_id,
                    "simulation_type": simulation_type,
                    "inputs": inputs
                }
            )
            response.raise_for_status()
            return response.json()

# Singleton instance
epistemicos_client = EpistemicOSClient()