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

        system_prompt = (
            "You are the Simulation Critic Agent for a drug discovery platform. "
            "Critically review simulation plans and outputs. Identify weaknesses, missing controls, "
            "unstated assumptions, and fragile logic. Suggest concrete improvements. "
            "Return a JSON object with exactly these keys: "
            "summary (string), confidence (float 0-1, higher = more robust plan), "
            "uncertainty_reason (null or string), recommended_next_step (string), "
            "trace_summary (string), structure (object with: "
            "target, candidate, weaknesses (list of strings), missing_controls (list), "
            "assumptions (list), passes_critique (bool), weakness_count (int), "
            "improvement_suggestions (list of strings))."
        )
        user_prompt = (
            f"Target: {target_name}\n"
            f"Candidate: {candidate_name or 'not specified'}\n"
            f"Simulation plan:\n{simulation_plan}\n\n"
            "Critique this simulation plan rigorously. "
            "Check for: missing positive/negative controls, insufficient replication (recommend ≥3), "
            "undocumented statistical tests, unstated assumptions, and model fragility. "
            "Set confidence based on plan robustness (0.9+ = very robust, 0.3 = major gaps)."
        )

        return await self._call_llm(system_prompt, user_prompt)
