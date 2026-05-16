# app/services/cxu_service.py
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..core.database import db
from .epistemicos_client import epistemicos_client

class CXUService:
    """Manage CXU (Causal Experience Unit) lifecycle."""
    
    async def create_cxu(
        self,
        name: str,
        cxu_type: str,
        zone_id: str,
        configuration: Dict[str, Any],
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new CXU in a zone."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            # Get zone reference
            zone = await conn.fetchrow(
                "SELECT epistemicos_zone_id FROM zones WHERE id = $1",
                zone_id
            )
            if not zone:
                raise ValueError(f"Zone {zone_id} not found")
            
            # Create CXU in EpistemicOS
            eos_result = await epistemicos_client.create_cxu(
                zone_id=zone['epistemicos_zone_id'],
                cxu_type=cxu_type,
                configuration=configuration,
                program_id=None  # Will be derived from zone
            )
            
            # Store in Genovate
            cxu_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO cxus 
                   (id, name, cxu_type, zone_id, epistemicos_cxu_id, configuration, status, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, 'created', $7)""",
                cxu_id, name, cxu_type, zone_id, eos_result.get('cxu_id'),
                configuration, created_by
            )
            
            row = await conn.fetchrow("SELECT * FROM cxus WHERE id = $1", cxu_id)
            return dict(row)
    
    async def start_cxu(self, cxu_id: str, initial_state: Optional[Dict] = None) -> Dict[str, Any]:
        """Start a CXU execution."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            cxu = await conn.fetchrow("SELECT * FROM cxus WHERE id = $1", cxu_id)
            if not cxu:
                raise ValueError(f"CXU {cxu_id} not found")
            
            # Start in EpistemicOS
            eos_result = await epistemicos_client.start_cxu(
                cxu_id=cxu['epistemicos_cxu_id'],
                initial_state=initial_state or {}
            )
            
            await conn.execute(
                """UPDATE cxus 
                   SET status = 'running', updated_at = NOW()
                   WHERE id = $1""",
                cxu_id
            )
            
            # Record first iteration
            iteration_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO cxu_iterations 
                   (id, cxu_id, iteration_number, input_state, trace_id)
                   VALUES ($1, $2, 1, $3, $4)""",
                iteration_id, cxu_id, initial_state or {}, eos_result.get('trace_id')
            )
            
            return {"cxu_id": cxu_id, "status": "running", "trace_id": eos_result.get('trace_id')}
    
    async def get_cxu_status(self, cxu_id: str) -> Dict[str, Any]:
        """Get current CXU status with latest iteration."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            cxu = await conn.fetchrow("SELECT * FROM cxus WHERE id = $1", cxu_id)
            if not cxu:
                raise ValueError(f"CXU {cxu_id} not found")
            
            latest_iteration = await conn.fetchrow(
                """SELECT * FROM cxu_iterations 
                   WHERE cxu_id = $1 
                   ORDER BY iteration_number DESC LIMIT 1""",
                cxu_id
            )
            
            return {
                "cxu": dict(cxu),
                "latest_iteration": dict(latest_iteration) if latest_iteration else None
            }
    
    async def pause_cxu(self, cxu_id: str) -> Dict[str, Any]:
        """Pause a running CXU."""
        await epistemicos_client.pause_cxu(cxu_id)
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE cxus SET status = 'paused', updated_at = NOW() WHERE id = $1",
                cxu_id
            )
        return {"cxu_id": cxu_id, "status": "paused"}
    
    async def terminate_cxu(self, cxu_id: str) -> Dict[str, Any]:
        """Terminate a CXU."""
        await epistemicos_client.terminate_cxu(cxu_id)
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE cxus 
                   SET status = 'terminated', terminated_at = NOW(), updated_at = NOW()
                   WHERE id = $1""",
                cxu_id
            )
        return {"cxu_id": cxu_id, "status": "terminated"}

cxu_service = CXUService()
