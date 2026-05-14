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
        
        if not agent_outputs:
            return {
                "summary": "No agent outputs to synthesize.",
                "structure": {"recommendation": "insufficient_data", "ranked_reasons": []},
                "confidence": 0.0,
                "uncertainty_reason": "No agent outputs provided",
                "recommended_next_step": "Run individual agents first",
                "trace_summary": "Synthesis aborted: empty input"
            }
        
        # Aggregate confidence scores
        confidences = [o.get('confidence', 0.5) for o in agent_outputs if isinstance(o, dict)]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Extract key recommendations
        recommendations = []
        for output in agent_outputs:
            if isinstance(output, dict) and output.get('recommended_next_step'):
                recommendations.append(output['recommended_next_step'])
        
        # Synthesize final recommendation
        if any("promote" in r.lower() for r in recommendations):
            final_recommendation = "Promote candidate to Guardian Review"
        elif any("gather" in r.lower() or "additional" in r.lower() for r in recommendations):
            final_recommendation = "Gather additional evidence"
        else:
            final_recommendation = "Consider alternative candidates or targets"
        
        trace_summary = f"Synthesized {len(agent_outputs)} agent outputs. "
        trace_summary += f"Average confidence: {avg_confidence:.2f}. "
        trace_summary += f"Final recommendation: {final_recommendation}"
        
        return {
            "summary": f"After synthesizing {len(agent_outputs)} agent evaluations, the recommendation is: {final_recommendation}. Overall confidence: {avg_confidence:.2f}.",
            "structure": {
                "candidate": candidate_name,
                "overall_confidence": avg_confidence,
                "recommendation": final_recommendation,
                "agent_count": len(agent_outputs),
                "ranked_reasons": recommendations[:5]  # Top 5 recommendations
            },
            "confidence": avg_confidence,
            "uncertainty_reason": None if avg_confidence >= 0.6 else "Confidence across agents is low",
            "recommended_next_step": final_recommendation,
            "trace_summary": trace_summary
        }
