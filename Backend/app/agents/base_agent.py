# app/agents/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import json
from ..core.database import db
from ..services.evidence_service import evidence_service
from ..services.hypothesis_service import hypothesis_service
from ..services.epistemicos_client import epistemicos_client

class BaseAgent(ABC):
    """Base class for all Genovate agents."""
    
    def __init__(self, agent_id: str, name: str, role: str):
        self.agent_id = agent_id
        self.name = name
        self.role = role
    
    @abstractmethod
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's core logic. Returns structured output."""
        pass
    
    async def run(
        self,
        program_id: str,
        inputs: Dict[str, Any],
        hypothesis_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
        run_type: str = "target_assessment"
    ) -> Dict[str, Any]:
        """Execute agent with full tracing and database logging."""
        run_id = str(uuid.uuid4())
        pool = await db.get_pool()
        
        # Record start
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO agent_runs 
                   (id, agent_id, program_id, hypothesis_id, candidate_id, 
                    run_type, input_bundle, status, started_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'running', NOW())""",
                run_id, self.agent_id, program_id, hypothesis_id, candidate_id,
                run_type, json.dumps(inputs)
            )
        
        try:
            # Execute agent logic
            output = await self.execute(inputs)
            
            # Record completion
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE agent_runs 
                       SET output_summary = $1,
                           output_structure = $2,
                           confidence = $3,
                           uncertainty_reason = $4,
                           recommended_next_step = $5,
                           trace_summary = $6,
                           status = 'completed',
                           completed_at = NOW()
                       WHERE id = $7""",
                    output.get('summary', ''),
                    json.dumps(output.get('structure', {})),
                    output.get('confidence'),
                    output.get('uncertainty_reason'),
                    output.get('recommended_next_step'),
                    output.get('trace_summary', ''),
                    run_id
                )
            
            return {
                "run_id": run_id,
                "agent_name": self.name,
                "output": output,
                "status": "completed"
            }
            
        except Exception as e:
            # Record failure
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE agent_runs 
                       SET status = 'failed', 
                           error_message = $1,
                           completed_at = NOW()
                       WHERE id = $2""",
                    str(e), run_id
                )
            raise
    
    async def _query_evidence_graph(
        self, 
        entity_name: str, 
        direction: str = "both"
    ) -> List[Dict]:
        """Tool: Query evidence graph for an entity."""
        return await evidence_service.get_entity_evidence(entity_name, direction)
    
    async def _get_hypothesis(self, hypothesis_id: str) -> Dict:
        """Tool: Get hypothesis with evidence."""
        return await hypothesis_service.get_hypothesis_with_evidence(hypothesis_id)
    
    async def _add_critique(
        self,
        run_id: str,
        critique_text: str,
        severity: str = "medium",
        identifies_weakness: bool = False,
        suggests_improvement: Optional[str] = None
    ) -> None:
        """Tool: Add a critique to the current run."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO agent_critiques 
                   (id, agent_run_id, critic_agent_id, critique_text, 
                    identifies_weakness, suggests_improvement, severity)
                   VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6)""",
                run_id, self.agent_id, critique_text, identifies_weakness,
                suggests_improvement, severity
            )

    async def _semantic_search(
        self,
        query: str,
        program_id: str,
        top_k: int = 5,
    ) -> List[Dict]:
        """Tool: Semantic search across program documents via EpistemicOS."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Get the most-recently-ingested asset's embedding collection.
            asset = await conn.fetchrow(
                """SELECT metadata->>'embedding_collection_id' AS collection_id
                   FROM data_assets
                   WHERE program_id = $1 AND status = 'ingested'
                   ORDER BY created_at DESC
                   LIMIT 1""",
                program_id,
            )
            if not asset or not asset["collection_id"]:
                return []

            collection_id = asset["collection_id"]

        result = await epistemicos_client.semantic_search(
            query=query,
            collection_id=collection_id,
            program_id=program_id,
            top_k=top_k,
        )
        return result.get("results", [])
