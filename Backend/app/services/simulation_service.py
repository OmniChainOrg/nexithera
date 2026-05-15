# app/services/simulation_service.py — NEW: Orchestrate EpistemicOS simulations
from typing import Dict, Any, Optional, List
import uuid
from ..core.database import db
from .epistemicos_client import epistemicos_client

class SimulationService:
    """Orchestrate simulations via EpistemicOS — Genovate only manages metadata."""
    
    async def create_zone(
        self,
        program_id: str,
        zone_type: str,
        config: Dict[str, Any],
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new zone in EpistemicOS for simulation."""
        result = await epistemicos_client.create_zone(
            program_id=program_id,
            zone_type=zone_type,
            config=config,
            name=name
        )
        return result
    
    async def run_simulation(
        self,
        zone_id: str,
        simulation_type: str,
        inputs: Dict[str, Any],
        program_id: str,
        candidate_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a simulation in an existing zone."""
        # Get zone from DB to get epistemicos_zone_id
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            zone = await conn.fetchrow(
                "SELECT epistemicos_zone_id FROM zones WHERE id = $1",
                zone_id
            )
            if not zone:
                raise ValueError(f"Zone {zone_id} not found")
            
            epistemicos_zone_id = zone['epistemicos_zone_id']
        
        result = await epistemicos_client.simulate(
            zone_id=epistemicos_zone_id,
            simulation_type=simulation_type,
            inputs=inputs,
            program_id=program_id,
            candidate_id=candidate_id
        )
        
        # Store simulation result in candidate_simulations
        if candidate_id:
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE candidate_simulations 
                       SET results = $1, status = 'completed', completed_at = NOW()
                       WHERE candidate_id = $2 AND epistemicos_run_id = $3""",
                    result.get("results"),
                    candidate_id,
                    result.get("run_id")
                )
        
        return result
    
    async def create_cxu(
        self,
        zone_id: str,
        cxu_type: str,
        configuration: Dict[str, Any],
        program_id: str
    ) -> Dict[str, Any]:
        """Create a CXU inside a zone."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            zone = await conn.fetchrow(
                "SELECT epistemicos_zone_id FROM zones WHERE id = $1",
                zone_id
            )
            if not zone:
                raise ValueError(f"Zone {zone_id} not found")
        
        return await epistemicos_client.create_cxu(
            zone_id=zone['epistemicos_zone_id'],
            cxu_type=cxu_type,
            configuration=configuration,
            program_id=program_id
        )
    
    async def run_swarm(
        self,
        swarm_config: Dict[str, Any],
        program_id: str,
        objective: str
    ) -> Dict[str, Any]:
        """Run a swarm of CXUs."""
        return await epistemicos_client.create_swarm(
            swarm_config=swarm_config,
            program_id=program_id,
            objective=objective
        )
    
    async def cross_zone_simulate(
        self,
        source_zone_id: str,
        target_zone_id: str,
        coupling_map: Dict[str, str],
        inputs: Dict[str, Any],
        program_id: str
    ) -> Dict[str, Any]:
        """Run coupled simulation across two zones."""
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            source = await conn.fetchrow(
                "SELECT epistemicos_zone_id FROM zones WHERE id = $1",
                source_zone_id
            )
            target = await conn.fetchrow(
                "SELECT epistemicos_zone_id FROM zones WHERE id = $1",
                target_zone_id
            )
            if not source or not target:
                raise ValueError("One or both zones not found")
        
        return await epistemicos_client.cross_zone_simulate(
            source_zone_id=source['epistemicos_zone_id'],
            target_zone_id=target['epistemicos_zone_id'],
            coupling_map=coupling_map,
            inputs=inputs,
            program_id=program_id
        )
    
    async def get_verifiable_trace(self, trace_id: str) -> Dict[str, Any]:
        """Get verifiable trace for audit."""
        return await epistemicos_client.get_trace(trace_id)

simulation_service = SimulationService()
