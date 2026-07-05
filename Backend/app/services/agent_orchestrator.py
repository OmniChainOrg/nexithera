# app/services/agent_orchestrator.py
import uuid
from typing import Dict, Any, List, Optional
from ..core.database import db
from ..agents.target_biology_agent import TargetBiologyAgent
from ..agents.oncology_agent import OncologyImmunotherapyAgent
from ..agents.evidence_synthesizer_agent import EvidenceSynthesizerAgent
from ..agents.simulation_critic_agent import SimulationCriticAgent
from ..agents.target_discovery_agent import TargetDiscoveryAgent
from ..agents.gap_analysis_agent import GapAnalysisAgent
from ..agents.active_learning_agent import ActiveLearningAgent
from ..agents.safety_toxicity_agent import SafetyToxicityAgent
from ..agents.competitive_landscape_agent import CompetitiveLandscapeAgent
from ..agents.forecast_synthesizer_agent import ForecastSynthesizerAgent
from ..agents.trial_design_agent import TrialDesignAgent
from ..agents.ip_position_agent import IPPositionAgent
from ..agents.historical_precedent_agent import HistoricalPrecedentAgent
from ..agents.ind_readiness_agent import INDReadinessAgent

# Agent instances (in production, these would be loaded from DB with prompts)
AGENTS = {}

async def get_or_create_agent(agent_name: str):
    """Get agent instance by name, creating DB record if needed."""
    if agent_name in AGENTS:
        return AGENTS[agent_name]
    
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM agents WHERE name = $1 AND is_active = TRUE",
            agent_name
        )
        if not row:
            # Create agent record
            agent_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO agents (id, name, role, is_active) 
                   VALUES ($1, $2, $3, TRUE)""",
                agent_id, agent_name, agent_name.lower().replace(' ', '_')
            )
        else:
            agent_id = row['id']
    
    # Instantiate appropriate agent class
    if agent_name == "Target Biology Agent":
        agent = TargetBiologyAgent(agent_id)
    elif agent_name == "Oncology & Immunotherapy Agent":
        agent = OncologyImmunotherapyAgent(agent_id)
    elif agent_name == "Evidence Synthesizer Agent":
        agent = EvidenceSynthesizerAgent(agent_id)
    elif agent_name == "Simulation Critic Agent":
        agent = SimulationCriticAgent(agent_id)
    elif agent_name == "Target Discovery Agent":
        agent = TargetDiscoveryAgent(agent_id)
    elif agent_name == "Gap Analysis Agent":
        agent = GapAnalysisAgent(agent_id)
    elif agent_name == "Active Learning Agent":
        agent = ActiveLearningAgent(agent_id)
    elif agent_name in ("Safety & Toxicity Agent", "Safety Toxicity Agent"):
        agent = SafetyToxicityAgent(agent_id)
    elif agent_name == "Competitive Landscape Agent":
        agent = CompetitiveLandscapeAgent(agent_id)
    elif agent_name in ("Clinical Forecaster Agent", "Forecast Synthesizer"):
        agent = ForecastSynthesizerAgent(agent_id)
    elif agent_name == "Trial Design Agent":
        agent = TrialDesignAgent(agent_id)
    elif agent_name == "IP Position Agent":
        agent = IPPositionAgent(agent_id)
    elif agent_name == "Historical Precedent Agent":
        agent = HistoricalPrecedentAgent(agent_id)
    elif agent_name == "IND Readiness Agent":
        agent = INDReadinessAgent(agent_id)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")
    
    AGENTS[agent_name] = agent
    return agent

class AgentOrchestrator:
    """Orchestrate multiple agents for a given task."""
    
    async def run_target_assessment(
        self,
        program_id: str,
        target_name: str,
        disease_name: str,
        tumor_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a full target assessment using multiple agents."""
        results = []
        
        # Run Target Biology Agent
        target_agent = await get_or_create_agent("Target Biology Agent")
        target_result = await target_agent.run(
            program_id=program_id,
            inputs={
                "target_name": target_name,
                "disease_name": disease_name,
                "target_type": "gene"
            },
            run_type="target_assessment"
        )
        results.append(target_result["output"])
        
        # Run Oncology Agent (if cancer context)
        if tumor_type or "cancer" in disease_name.lower():
            onco_agent = await get_or_create_agent("Oncology & Immunotherapy Agent")
            onco_result = await onco_agent.run(
                program_id=program_id,
                inputs={
                    "target_name": target_name,
                    "tumor_type": tumor_type or "solid_tumor",
                    "biomarker": None
                },
                run_type="target_assessment"
            )
            results.append(onco_result["output"])
        
        # Run Evidence Synthesizer
        synthesizer = await get_or_create_agent("Evidence Synthesizer Agent")
        synthesis = await synthesizer.run(
            program_id=program_id,
            inputs={
                "agent_outputs": results,
                "candidate_name": target_name
            },
            run_type="evidence_synthesis"
        )
        
        return {
            "target": target_name,
            "disease": disease_name,
            "agent_outputs": results,
            "synthesis": synthesis["output"],
            "overall_recommendation": synthesis["output"].get("recommended_next_step")
        }
    
    async def critique_simulation(
        self,
        program_id: str,
        target_name: str,
        simulation_plan: Dict[str, Any],
        candidate_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run simulation critic on a simulation plan."""
        critic = await get_or_create_agent("Simulation Critic Agent")
        result = await critic.run(
            program_id=program_id,
            candidate_id=candidate_id,
            inputs={
                "simulation_plan": simulation_plan,
                "target_name": target_name,
                "candidate_name": None
            },
            run_type="simulation_critique"
        )
        return result

    async def discover_targets(
        self,
        program_id: str,
        disease_name: Optional[str] = None,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """Run the Target Discovery Agent for a program and persist its
        ranked target list to ``target_discoveries`` (PR #8)."""
        import json

        agent = await get_or_create_agent("Target Discovery Agent")
        result = await agent.run(
            program_id=program_id,
            inputs={
                "program_id": program_id,
                "disease_name": disease_name,
                "top_k": top_k,
            },
            run_type="target_assessment",
        )

        ranked = (result.get("output", {}).get("structure", {}) or {}).get(
            "ranked_targets", []
        )

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            discovery_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO target_discoveries
                       (id, agent_run_id, program_id, ranked_targets)
                   VALUES ($1, $2, $3, $4)""",
                discovery_id,
                result["run_id"],
                program_id,
                json.dumps(ranked),
            )

        return {
            "discovery_id": discovery_id,
            "run_id": result["run_id"],
            "program_id": program_id,
            "targets": ranked,
            "summary": result.get("output", {}).get("summary"),
            "recommended_next_step": result.get("output", {}).get(
                "recommended_next_step"
            ),
        }

agent_orchestrator = AgentOrchestrator()
