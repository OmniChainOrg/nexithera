# app/agents/target_biology_agent.py
from typing import Dict, Any, List
from .base_agent import BaseAgent

class TargetBiologyAgent(BaseAgent):
    """Evaluates target relevance, pathway plausibility, and disease fit."""
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "Target Biology Agent", "target_biology")
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
            - target_name: str
            - disease_name: str
            - target_type: str (gene, protein, etc.)
        """
        target_name = inputs.get("target_name")
        disease_name = inputs.get("disease_name")
        target_type = inputs.get("target_type", "gene")
        
        # Query evidence graph for target-disease associations
        target_evidence = await self._query_evidence_graph(target_name)
        disease_evidence = await self._query_evidence_graph(disease_name)
        
        # Find direct target-disease evidence
        direct_evidence = [
            e for e in target_evidence 
            if e.get('target_name') == disease_name or e.get('source_name') == disease_name
        ]
        
        # Calculate confidence based on evidence
        confidence = 0.3  # baseline
        if direct_evidence:
            avg_conf = sum(e.get('confidence', 0.5) for e in direct_evidence) / len(direct_evidence)
            confidence = min(0.9, avg_conf + 0.2)
        elif target_evidence or disease_evidence:
            confidence = 0.5
        
        # Generate trace summary
        trace_summary = f"Target '{target_name}' has {len(target_evidence)} evidence edges. "
        trace_summary += f"Disease '{disease_name}' has {len(disease_evidence)} evidence edges. "
        trace_summary += f"Direct associations: {len(direct_evidence)}."
        
        # Determine recommendation
        if confidence >= 0.7:
            recommended_next_step = "Promote to candidate generation"
        elif confidence >= 0.4:
            recommended_next_step = "Gather additional evidence for this target"
        else:
            recommended_next_step = "Consider alternative targets"
        
        uncertainty_reason = None
        if confidence < 0.7:
            uncertainty_reason = f"Limited direct evidence connecting {target_name} to {disease_name}"
        
        return {
            "summary": f"Target '{target_name}' is {'highly' if confidence >= 0.7 else 'moderately' if confidence >= 0.4 else 'weakly'} relevant to {disease_name} (confidence: {confidence:.2f}).",
            "structure": {
                "target": target_name,
                "disease": disease_name,
                "confidence": confidence,
                "direct_evidence_count": len(direct_evidence),
                "total_target_evidence": len(target_evidence),
                "target_plausibility_score": confidence
            },
            "confidence": confidence,
            "uncertainty_reason": uncertainty_reason,
            "recommended_next_step": recommended_next_step,
            "trace_summary": trace_summary
        }
