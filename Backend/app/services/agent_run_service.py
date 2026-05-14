# app/services/agent_run_service.py
from typing import List, Dict, Any, Optional
from ..core.database import db

class AgentRunService:
    """Service for querying agent runs and traces."""
    
    async def list_runs(
        self, 
        program_id: Optional[str] = None, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict]:
        """List agent runs with optional filters."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            if program_id:
                rows = await conn.fetch(
                    """SELECT ar.id, ar.run_type, ar.status, ar.confidence, 
                              ar.output_summary, ar.started_at, ar.completed_at,
                              a.name as agent_name
                       FROM agent_runs ar
                       JOIN agents a ON ar.agent_id = a.id
                       WHERE ar.program_id = $1
                       ORDER BY ar.created_at DESC
                       LIMIT $2 OFFSET $3""",
                    program_id, limit, offset
                )
            else:
                rows = await conn.fetch(
                    """SELECT ar.id, ar.run_type, ar.status, ar.confidence, 
                              ar.output_summary, ar.started_at, ar.completed_at,
                              a.name as agent_name
                       FROM agent_runs ar
                       JOIN agents a ON ar.agent_id = a.id
                       ORDER BY ar.created_at DESC
                       LIMIT $1 OFFSET $2""",
                    limit, offset
                )
            return [dict(row) for row in rows]
    
    async def get_run_details(self, run_id: str) -> Optional[Dict]:
        """Get complete run details including tool calls and critiques."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Get run
            run = await conn.fetchrow(
                """SELECT ar.*, a.name as agent_name, a.role as agent_role
                   FROM agent_runs ar
                   JOIN agents a ON ar.agent_id = a.id
                   WHERE ar.id = $1""",
                run_id
            )
            if not run:
                return None
            
            # Get tool calls
            tool_calls = await conn.fetch(
                "SELECT * FROM agent_tool_calls WHERE agent_run_id = $1 ORDER BY started_at",
                run_id
            )
            
            # Get critiques
            critiques = await conn.fetch(
                """SELECT ac.*, a.name as critic_name
                   FROM agent_critiques ac
                   LEFT JOIN agents a ON ac.critic_agent_id = a.id
                   WHERE ac.agent_run_id = $1
                   ORDER BY ac.created_at""",
                run_id
            )
            
            return {
                "run": dict(run),
                "tool_calls": [dict(tc) for tc in tool_calls],
                "critiques": [dict(c) for c in critiques]
            }

agent_run_service = AgentRunService()
