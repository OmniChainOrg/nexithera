# app/agents/evidence_synthesizer_agent.py
from typing import Dict, Any, List
from .base_agent import BaseAgent

class EvidenceSynthesizerAgent(BaseAgent):
    """Produces ranked recommendations from multiple agent outputs."""
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "Evidence Synthesizer Agent", "evidence_synthesis")
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
            - agent_outputs: List[Dict] - outputs from other agents
            - candidate_name: str (optional)
            - hypothesis_id: str (optional)
        """
        agent_outputs = inputs.get("agent_outputs", [])
        candidate_name = inputs.get("candidate_name")
        synthesis_focus = inputs.get("synthesis_focus", "")

        if not agent_outputs and not candidate_name:
            return {
                "summary": "No agent outputs or candidate name provided to synthesize.",
                "structure": {"recommendation": "insufficient_data", "ranked_reasons": []},
                "confidence": 0.0,
                "uncertainty_reason": "No inputs provided",
                "recommended_next_step": "Run individual agents first or provide a candidate name",
                "trace_summary": "Synthesis aborted: empty input",
            }

        system_prompt = (
            "You are the Evidence Synthesizer Agent for a drug discovery platform. "
            "Synthesize multi-source evidence and agent outputs into a unified structured assessment. "
            "Return a JSON object with exactly these keys: "
            "summary (string), confidence (float 0-1), uncertainty_reason (null or string), "
            "recommended_next_step (string), trace_summary (string), structure (object with: "
            "candidate, overall_confidence, recommendation, agent_count, ranked_reasons, "
            "key_evidence_claims, synthesis_notes)."
        )

        agent_summaries = [
            {
                "agent": o.get("agent_name", "unknown") if isinstance(o, dict) else "unknown",
                "summary": o.get("summary", "") if isinstance(o, dict) else "",
                "confidence": o.get("confidence", 0.5) if isinstance(o, dict) else 0.5,
                "recommended_next_step": o.get("recommended_next_step", "") if isinstance(o, dict) else "",
            }
            for o in agent_outputs
        ]

        user_prompt = (
            f"Candidate / target: {candidate_name or 'not specified'}\n"
            f"Synthesis focus: {synthesis_focus or 'general'}\n"
            f"Number of agent outputs to synthesize: {len(agent_outputs)}\n"
            f"Agent outputs:\n{agent_summaries}\n\n"
            "Synthesize these agent outputs into a unified recommendation. "
            "Weigh each agent's confidence and recommendation. "
            "Provide a clear overall recommendation (e.g., 'Promote to Guardian Review', "
            "'Gather additional evidence', or 'Consider alternatives')."
        )

        return await self._call_llm(system_prompt, user_prompt)
