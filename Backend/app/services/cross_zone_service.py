# app/services/cross_zone_service.py
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from ..core.database import db
from .epistemicos_client import epistemicos_client

class CrossZoneService:
    """Manage cross-zone simulations."""
    
    async def register_coupling(
        self,
        source_zone_type: str,
        target_zone_type: str,
        coupling_name: str,
        coupling_map: Dict[str, str],
        is_bidirectional: bool = False,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a reusable zone coupling."""
        pool = await db.get_pool()
        coupling_id = str(uuid.uuid4())
        
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO zone_couplings 
                   (id, source_zone_type, target_zone_type, coupling_name, coupling_map, is_bidirectional, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                coupling_id, source_zone_type, target_zone_type, coupling_name,
                coupling_map, is_bidirectional, created_by
            )
            
            row = await conn.fetchrow("SELECT * FROM zone_couplings WHERE id = $1", coupling_id)
            return dict(row)
    
    async def run_cross_zone_simulation(
        self,
        name: Optional[str],
        source_zone_id: str,
        target_zone_id: str,
        input_state: Dict[str, Any],
        program_id: str,
        coupling_id: Optional[str] = None,
        coupling_map_override: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Run a coupled simulation across two zones."""
        pool = await db.get_pool()
        run_id = str(uuid.uuid4())
        
        async with pool.acquire() as conn:
            # Get zone references
            source_zone = await conn.fetchrow(
                "SELECT epistemicos_zone_id, zone_type FROM zones WHERE id = $1",
                source_zone_id
            )
            target_zone = await conn.fetchrow(
                "SELECT epistemicos_zone_id, zone_type FROM zones WHERE id = $1",
                target_zone_id
            )
            
            if not source_zone or not target_zone:
                raise ValueError("One or both zones not found")
            
            # Get coupling map
            coupling_map = coupling_map_override
            if coupling_id and not coupling_map:
                coupling = await conn.fetchrow(
                    "SELECT coupling_map FROM zone_couplings WHERE id = $1",
                    coupling_id
                )
                if coupling:
                    coupling_map = coupling['coupling_map']
            
            if not coupling_map:
                raise ValueError("No coupling map provided or found")
            
            # Create cross-zone run record
            await conn.execute(
                """INSERT INTO cross_zone_runs 
                   (id, name, source_zone_id, target_zone_id, coupling_id, coupling_map, 
                    input_state, status, program_id, started_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'running', $8, NOW())""",
                run_id, name, source_zone_id, target_zone_id, coupling_id,
                coupling_map, input_state, program_id
            )
            
            # Execute in EpistemicOS
            eos_result = await epistemicos_client.cross_zone_simulate(
                source_zone_id=source_zone['epistemicos_zone_id'],
                target_zone_id=target_zone['epistemicos_zone_id'],
                coupling_map=coupling_map,
                inputs=input_state,
                program_id=program_id
            )
            
            # Update with results
            await conn.execute(
                """UPDATE cross_zone_runs 
                   SET output_state = $1, status = 'completed', epistemicos_run_id = $2, 
                       trace_id = $3, completed_at = NOW()
                   WHERE id = $4""",
                eos_result.get('results'), eos_result.get('run_id'),
                eos_result.get('trace_id'), run_id
            )
            
            return {
                "run_id": run_id,
                "status": "completed",
                "output_state": eos_result.get('results'),
                "trace_id": eos_result.get('trace_id')
            }
    
    async def get_cross_zone_run(self, run_id: str) -> Optional[Dict]:
        """Get cross-zone simulation results."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT czr.*, 
                          sz.zone_type as source_zone_type,
                          tz.zone_type as target_zone_type
                   FROM cross_zone_runs czr
                   JOIN zones sz ON czr.source_zone_id = sz.id
                   JOIN zones tz ON czr.target_zone_id = tz.id
                   WHERE czr.id = $1""",
                run_id
            )
            return dict(row) if row else None
    
    async def list_couplings(self, source_zone_type: Optional[str] = None) -> List[Dict]:
        """List registered zone couplings."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            if source_zone_type:
                rows = await conn.fetch(
                    "SELECT * FROM zone_couplings WHERE source_zone_type = $1 ORDER BY coupling_name",
                    source_zone_type
                )
            else:
                rows = await conn.fetch("SELECT * FROM zone_couplings ORDER BY source_zone_type, coupling_name")
            return [dict(row) for row in rows]

cross_zone_service = CrossZoneService()
