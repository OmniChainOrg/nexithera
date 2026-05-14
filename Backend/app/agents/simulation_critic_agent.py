# app/agents/simulation_critic_agent.py
from typing import Dict, Any, List
from .base_agent import BaseAgent

class SimulationCriticAgent(BaseAgent):
    """Challenges assumptions, checks model fragility, identifies missing controls."""
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "Simulation Critic Agent", "simulation_critique")
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
            - simulation_plan: Dict (simulation description)
            - simulation_results: Dict (optional)
            - target_name: str
            - candidate_name: str (optional)
        """
        simulation_plan = inputs.get("simulation_plan", {})
        target_name = inputs.get("target_name", "unknown")
        candidate_name = inputs.get("candidate_name")
        
        # Generate critiques based on simulation plan completeness
        weaknesses = []
        missing_controls = []
        assumptions = []
        
        # Check for common missing elements
        if not simulation_plan.get("positive_control"):
            missing_controls.append("Missing positive control")
            weaknesses.append("No positive control defined")
        
        if not simulation_plan.get("negative_control"):
            missing_controls.append("Missing negative control")
            weaknesses.append("No negative control defined")
        
        if not simulation_plan.get("replicates", 0) >= 3:
            weaknesses.append(f"Low replication: {simulation_plan.get('replicates', 0)} replicates (recommend ≥3)")
        
        if not simulation_plan.get("statistical_test"):
            weaknesses.append("No statistical test specified")
        
        # Identify assumptions
        if simulation_plan.get("assumptions"):
            assumptions = simulation_plan.get("assumptions", [])
        else:
            assumptions = ["Assumptions not explicitly stated - this is a red flag"]
            weaknesses.append("Assumptions not documented")
        
        confidence = 0.9 if len(weaknesses) == 0 else max(0.3, 1.0 - (len(weaknesses) * 0.15))
        
        if len(weaknesses) >= 3:
            recommended_next_step = "Revise simulation plan to address critical gaps"
            summary = f"⚠️ Simulation plan has {len(weaknesses)} critical weaknesses. Requires revision before proceeding."
        elif len(weaknesses) >= 1:
            recommended_next_step = "Address identified weaknesses and re-run critic"
            summary = f"Simulation plan has {len(weaknesses)} weaknesses. Acceptable with revisions."
        else:
            recommended_next_step = "Proceed with simulation execution"
            summary = f"Simulation plan is robust. No critical weaknesses identified."
        
        trace_summary = f"Critiqued simulation for {target_name}. Found {len(weaknesses)} weaknesses. "
        trace_summary += f"Missing controls: {len(missing_controls)}. Assumptions: {len(assumptions)}."
        
        return {
            "summary": summary,
            "structure": {
                "target": target_name,
                "candidate": candidate_name,
                "weaknesses": weaknesses,
                "missing_controls": missing_controls,
                "assumptions": assumptions,
                "passes_critique": len(weaknesses) == 0,
                "weakness_count": len(weaknesses)
            },
            "confidence": confidence,
            "uncertainty_reason": None if len(weaknesses) == 0 else "Simulation plan has gaps",
            "recommended_next_step": recommended_next_step,
            "trace_summary": trace_summary
        }
