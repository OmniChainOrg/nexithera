# app/services/swarm_service.py
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..core.database import db
from .epistemicos_client import epistemicos_client

class SwarmService:
    """Orchestrate swarms of CXUs."""
    
    async def create_swarm(
        self,
        name: str,
        swarm_type: str,
        objective: str,
        configuration: Dict[str, Any],
        program_id: str,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new swarm."""
        pool = await db.get_pool()
        swarm_id = str(uuid.uuid4())
        
        async with pool.acquire() as conn:
            # Create swarm in EpistemicOS
            eos_result = await epistemicos_client.create_swarm(
                swarm_config=configuration,
                program_id=program_id,
                objective=objective
            )
            
            await conn.execute(
                """INSERT INTO swarms 
                   (id, name, swarm_type, objective, configuration, status, 
                    epistemicos_swarm_id, program_id, created_by)
                   VALUES ($1, $2, $3, $4, $5, 'created', $6, $7, $8)""",
                swarm_id, name, swarm_type, objective, configuration,
                eos_result.get('swarm_id'), program_id, created_by
            )
            
            row = await conn.fetchrow("SELECT * FROM swarms WHERE id = $1", swarm_id)
            return dict(row)
    
    async def add_member(
        self,
        swarm_id: str,
        cxu_id: str,
        role: str = "worker",
        weight: float = 1.0
    ) -> Dict[str, Any]:
        """Add a CXU as a member of a swarm."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Get member index
            member_count = await conn.fetchval(
                "SELECT COUNT(*) FROM swarm_members WHERE swarm_id = $1",
                swarm_id
            )
            
            await conn.execute(
                """INSERT INTO swarm_members (swarm_id, cxu_id, member_index, role, weight)
                   VALUES ($1, $2, $3, $4, $5)""",
                swarm_id, cxu_id, member_count + 1, role, weight
            )
            
            return {"swarm_id": swarm_id, "cxu_id": cxu_id, "role": role}
    
    async def start_swarm(self, swarm_id: str) -> Dict[str, Any]:
        """Start swarm execution."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            swarm = await conn.fetchrow("SELECT * FROM swarms WHERE id = $1", swarm_id)
            if not swarm:
                raise ValueError(f"Swarm {swarm_id} not found")
            
            # Get all members
            members = await conn.fetch(
                """SELECT m.*, c.cxu_type, c.configuration 
                   FROM swarm_members m
                   JOIN cxus c ON m.cxu_id = c.id
                   WHERE m.swarm_id = $1""",
                swarm_id
            )
            
            # Start swarm in EpistemicOS
            eos_result = await epistemicos_client.start_swarm(
                swarm_id=swarm['epistemicos_swarm_id'],
                members=[dict(m) for m in members]
            )
            
            await conn.execute(
                "UPDATE swarms SET status = 'running' WHERE id = $1",
                swarm_id
            )
            
            return {"swarm_id": swarm_id, "status": "running", "trace_id": eos_result.get('trace_id')}
    
    async def get_swarm_results(self, swarm_id: str) -> Dict[str, Any]:
        """Get aggregated swarm results."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            swarm = await conn.fetchrow("SELECT * FROM swarms WHERE id = $1", swarm_id)
            if not swarm:
                raise ValueError(f"Swarm {swarm_id} not found")
            
            # Get results from EpistemicOS
            eos_result = await epistemicos_client.get_swarm_results(swarm['epistemicos_swarm_id'])
            
            # Store aggregated results
            result_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO swarm_results 
                   (id, swarm_id, aggregation_method, aggregated_output, consensus_score, 
                    best_cxu_id, diversity_metric, trace_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                result_id, swarm_id, eos_result.get('aggregation_method', 'consensus'),
                eos_result.get('aggregated_output'), eos_result.get('consensus_score'),
                eos_result.get('best_cxu_id'), eos_result.get('diversity_metric'),
                eos_result.get('trace_id')
            )
            
            await conn.execute(
                "UPDATE swarms SET status = 'completed', completed_at = NOW() WHERE id = $1",
                swarm_id
            )
            
            return {
                "swarm_id": swarm_id,
                "status": "completed",
                "results": eos_result,
                "consensus_score": eos_result.get('consensus_score'),
                "diversity_metric": eos_result.get('diversity_metric')
            }
    
    async def list_swarms(self, program_id: str) -> List[Dict]:
        """List all swarms for a program."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT s.*, 
                          COUNT(DISTINCT sm.cxu_id) as member_count,
                          COALESCE(sr.consensus_score, 0) as consensus_score
                   FROM swarms s
                   LEFT JOIN swarm_members sm ON s.id = sm.swarm_id
                   LEFT JOIN swarm_results sr ON s.id = sr.swarm_id
                   WHERE s.program_id = $1
                   GROUP BY s.id, sr.consensus_score
                   ORDER BY s.created_at DESC""",
                program_id
            )
            return [dict(row) for row in rows]

swarm_service = SwarmService()
