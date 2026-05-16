# app/services/epistemicos_client.py — REPLACE stub with real implementation
import uuid
import json
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..core.config import settings
from ..core.database import db

class EpistemicOSClient:
    """
    Real client for EpistemicOS — handles ingestion, embedding, simulation, zones, CXUs, swarms.
    Proven integration (TensorMinded.com). Genovate calls, EpistemicOS computes.
    """
    
    def __init__(self):
        self.base_url = settings.EPISTEMICOS_URL
        self.mock_mode = settings.EPISTEMICOS_MOCK_MODE
        self.api_key = settings.EPISTEMICOS_API_KEY
        self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with auth."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.EPISTEMICOS_TIMEOUT_SIMULATE),
                headers=headers
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # ========== INGESTION & EMBEDDING ==========
    
    async def ingest_document(
        self,
        document_uri: str,
        file_type: str,
        program_context: Dict[str, Any],
        program_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send document to EpistemicOS for chunking + embedding.
        Returns collection_id, chunk_ids, vector_count, trace_id.
        """
        if self.mock_mode or not settings.EPISTEMICOS_ENABLE_INGEST:
            # Fallback to mock for testing
            return {
                "embedding_collection_id": f"emb_{uuid.uuid4().hex[:12]}",
                "chunk_ids": [f"chunk_{i}_{uuid.uuid4().hex[:6]}" for i in range(5)],
                "vector_count": 5,
                "status": "completed",
                "trace_id": f"trace_{uuid.uuid4().hex[:8]}",
                "mock": True
            }
        
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/ingest",
            json={
                "document_uri": document_uri,
                "file_type": file_type,
                "metadata": {
                    **program_context,
                    "program_id": program_id,
                    "source": "genovate"
                },
                "options": {
                    "chunk_size": 512,
                    "overlap": 64,
                    "embedding_model": "default"
                }
            }
        )
        response.raise_for_status()
        result = response.json()
        
        # Store trace reference in Genovate
        await self._store_trace_reference(
            run_type="ingest",
            epistemicos_run_id=result.get("trace_id"),
            request=program_context,
            response=result
        )
        
        return result
    
    # ========== SEMANTIC SEARCH ==========
    
    async def semantic_search(
        self,
        query: str,
        collection_id: str,
        program_id: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Search embedded documents via EpistemicOS.
        Returns relevant chunks with scores and provenance.
        """
        if self.mock_mode:
            return {
                "results": [
                    {"chunk_id": f"chunk_{i}", "score": 0.9 - i*0.1, "text": f"Mock result {i}"}
                    for i in range(min(top_k, 5))
                ],
                "trace_id": f"trace_{uuid.uuid4().hex[:8]}"
            }
        
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/search",
            json={
                "query": query,
                "collection_id": collection_id,
                "top_k": top_k,
                "program_id": program_id
            }
        )
        response.raise_for_status()
        return response.json()
    
    # ========== ZONE MANAGEMENT ==========
    
    async def create_zone(
        self,
        program_id: str,
        zone_type: str,
        config: Dict[str, Any],
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request EpistemicOS to create a new zone.
        Zone = bounded simulation + reasoning environment.
        """
        if self.mock_mode or not settings.EPISTEMICOS_ENABLE_CXU:
            return {
                "epistemicos_zone_id": f"zone_{uuid.uuid4().hex[:12]}",
                "status": "created",
                "zone_type": zone_type,
                "name": name or f"{zone_type}_zone"
            }
        
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/zones",
            json={
                "program_id": program_id,
                "zone_type": zone_type,
                "config": config,
                "name": name,
                "source": "genovate"
            }
        )
        response.raise_for_status()
        result = response.json()
        
        # Store zone reference in Genovate DB
        await self._store_zone_reference(program_id, result)
        
        return result
    
    async def _store_zone_reference(self, program_id: str, zone_data: Dict) -> None:
        """Store EpistemicOS zone reference in Genovate DB."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO zones (program_id, epistemicos_zone_id, zone_type, config)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (epistemicos_zone_id) DO NOTHING""",
                program_id,
                zone_data.get("epistemicos_zone_id"),
                zone_data.get("zone_type"),
                json.dumps(zone_data.get("config", {}))
            )
    
    # ========== SINGLE-ZONE SIMULATION ==========
    
    async def simulate(
        self,
        zone_id: str,
        simulation_type: str,
        inputs: Dict[str, Any],
        program_id: Optional[str] = None,
        candidate_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request EpistemicOS to run a simulation in a zone.
        Returns run_id, results, confidence, trace.
        """
        if self.mock_mode or not settings.EPISTEMICOS_ENABLE_SIMULATION:
            return {
                "run_id": f"sim_{uuid.uuid4().hex[:12]}",
                "status": "completed",
                "results": {"mock_output": "simulation result placeholder"},
                "confidence": 0.85,
                "trace_id": f"trace_{uuid.uuid4().hex[:8]}"
            }
        
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/simulate",
            json={
                "zone_id": zone_id,
                "simulation_type": simulation_type,
                "inputs": inputs,
                "program_id": program_id,
                "candidate_id": candidate_id,
                "source": "genovate"
            }
        )
        response.raise_for_status()
        result = response.json()
        
        # Link simulation to candidate if provided
        if candidate_id:
            await self._link_simulation_to_candidate(candidate_id, result.get("run_id"))
        
        return result
    
    async def _link_simulation_to_candidate(self, candidate_id: str, epistemicos_run_id: str) -> None:
        """Link a simulation run to a candidate."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO candidate_simulations (candidate_id, epistemicos_run_id, status)
                   VALUES ($1, $2, 'initiated')""",
                candidate_id, epistemicos_run_id
            )
    
    # ========== CXU (Causal Experience Unit) ==========
    
    async def create_cxu(
        self,
        zone_id: str,
        cxu_type: str,
        configuration: Dict[str, Any],
        program_id: str
    ) -> Dict[str, Any]:
        """
        Create a CXU (Causal Experience Unit) inside a zone.
        CXU = bounded simulation unit with causal reasoning.
        """
        if self.mock_mode:
            return {
                "cxu_id": f"cxu_{uuid.uuid4().hex[:12]}",
                "zone_id": zone_id,
                "status": "ready",
                "configuration": configuration
            }
        
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/cxus",
            json={
                "zone_id": zone_id,
                "cxu_type": cxu_type,
                "configuration": configuration,
                "program_id": program_id,
                "source": "genovate"
            }
        )
        response.raise_for_status()
        return response.json()
    
    # ========== SWARM ORCHESTRATION ==========
    
    async def create_swarm(
        self,
        swarm_config: Dict[str, Any],
        program_id: str,
        objective: str
    ) -> Dict[str, Any]:
        """
        Create a swarm of CXUs for cooperative/competitive simulation.
        Swarm = multiple CXUs working together.
        """
        if self.mock_mode:
            return {
                "swarm_id": f"swarm_{uuid.uuid4().hex[:12]}",
                "cxu_count": len(swarm_config.get("variations", [])),
                "status": "created",
                "objective": objective
            }
        
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/swarms",
            json={
                "swarm_config": swarm_config,
                "program_id": program_id,
                "objective": objective,
                "source": "genovate"
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_swarm_results(self, swarm_id: str) -> Dict[str, Any]:
        """Get aggregated results from a swarm."""
        if self.mock_mode:
            return {
                "swarm_id": swarm_id,
                "status": "completed",
                "aggregated_results": {"best_cxu": "cxu_1", "consensus_score": 0.92}
            }
        
        client = self._get_client()
        response = await client.get(f"{self.base_url}/v1/swarms/{swarm_id}/results")
        response.raise_for_status()
        return response.json()
    
    # ========== CROSS-ZONE SIMULATION ==========
    
    async def cross_zone_simulate(
        self,
        source_zone_id: str,
        target_zone_id: str,
        coupling_map: Dict[str, str],
        inputs: Dict[str, Any],
        program_id: str
    ) -> Dict[str, Any]:
        """
        Run simulation that spans multiple zones.
        Example: Tumour growth zone + Pharmacokinetics zone.
        """
        if self.mock_mode:
            return {
                "cross_simulation_id": f"cross_{uuid.uuid4().hex[:12]}",
                "status": "completed",
                "results": {"coupled_output": "mock cross-zone result"},
                "trace_id": f"trace_{uuid.uuid4().hex[:8]}"
            }
        
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/simulate/cross-zone",
            json={
                "source_zone_id": source_zone_id,
                "target_zone_id": target_zone_id,
                "coupling_map": coupling_map,
                "inputs": inputs,
                "program_id": program_id,
                "source": "genovate"
            }
        )
        response.raise_for_status()
        return response.json()
    
    # ========== CXU LIFECYCLE ==========

    async def start_cxu(
        self, cxu_id: str, initial_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Start a CXU in EpistemicOS."""
        if self.mock_mode:
            return {
                "cxu_id": cxu_id,
                "status": "running",
                "trace_id": f"trace_{uuid.uuid4().hex[:8]}",
            }
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/cxus/{cxu_id}/start",
            json={"initial_state": initial_state},
        )
        response.raise_for_status()
        return response.json()

    async def pause_cxu(self, cxu_id: str) -> Dict[str, Any]:
        """Pause a CXU."""
        if self.mock_mode:
            return {"cxu_id": cxu_id, "status": "paused"}
        client = self._get_client()
        response = await client.post(f"{self.base_url}/v1/cxus/{cxu_id}/pause")
        response.raise_for_status()
        return response.json()

    async def terminate_cxu(self, cxu_id: str) -> Dict[str, Any]:
        """Terminate a CXU."""
        if self.mock_mode:
            return {"cxu_id": cxu_id, "status": "terminated"}
        client = self._get_client()
        response = await client.post(f"{self.base_url}/v1/cxus/{cxu_id}/terminate")
        response.raise_for_status()
        return response.json()

    async def start_swarm(
        self, swarm_id: str, members: List[Dict]
    ) -> Dict[str, Any]:
        """Start a swarm."""
        if self.mock_mode:
            return {
                "swarm_id": swarm_id,
                "status": "running",
                "member_count": len(members),
                "trace_id": f"trace_{uuid.uuid4().hex[:8]}",
            }
        client = self._get_client()
        response = await client.post(
            f"{self.base_url}/v1/swarms/{swarm_id}/start",
            json={"members": members},
        )
        response.raise_for_status()
        return response.json()

    # ========== TRACE & VERIFIABILITY ==========
    
    async def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """
        Retrieve verifiable trace from EpistemicOS.
        Critical for audit, reproducibility, and regulatory readiness.
        """
        if self.mock_mode:
            return {
                "trace_id": trace_id,
                "steps": [
                    {"step": 1, "action": "ingest", "timestamp": "2024-01-01T00:00:00Z"},
                    {"step": 2, "action": "embed", "timestamp": "2024-01-01T00:00:01Z"}
                ],
                "verifiable_hash": f"hash_{trace_id}"
            }
        
        client = self._get_client()
        response = await client.get(f"{self.base_url}/v1/traces/{trace_id}")
        response.raise_for_status()
        return response.json()
    
    async def _store_trace_reference(
        self,
        run_type: str,
        epistemicos_run_id: str,
        request: Dict,
        response: Dict
    ) -> None:
        """Store EpistemicOS trace reference in Genovate DB."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO epistemicos_runs 
                   (id, run_type, request_payload, response_payload, status, completed_at)
                   VALUES ($1, $2, $3, $4, 'completed', NOW())
                   ON CONFLICT (id) DO NOTHING""",
                epistemicos_run_id,
                run_type,
                json.dumps(request),
                json.dumps(response)
            )

# Singleton instance
epistemicos_client = EpistemicOSClient()
