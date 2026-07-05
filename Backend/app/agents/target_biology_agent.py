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

        # Gather evidence context
        target_evidence = await self._query_evidence_graph(target_name)
        disease_evidence = await self._query_evidence_graph(disease_name)
        direct_evidence = [
            e for e in target_evidence
            if e.get('target_name') == disease_name or e.get('source_name') == disease_name
        ]

        system_prompt = (
            "You are the Target Biology Agent for a drug discovery platform. "
            "Evaluate target relevance, pathway plausibility, and disease fit based on "
            "the evidence graph data provided. "
            "Return a JSON object with exactly these keys: "
            "summary (string), confidence (float 0-1), uncertainty_reason (null or string), "
            "recommended_next_step (string), trace_summary (string), structure (object with: "
            "target, disease, confidence, direct_evidence_count, total_target_evidence, "
            "target_plausibility_score, pathway_assessment, disease_fit)."
        )
        user_prompt = (
            f"Target: {target_name} (type: {target_type})\n"
            f"Disease: {disease_name}\n"
            f"Evidence graph:\n"
            f"- Total target evidence edges: {len(target_evidence)}\n"
            f"- Total disease evidence edges: {len(disease_evidence)}\n"
            f"- Direct target-disease associations: {len(direct_evidence)}\n"
            f"Sample direct evidence: {direct_evidence[:3] if direct_evidence else 'None'}\n\n"
            "Assess this target's relevance to the disease. "
            "Set confidence 0.7+ if strong evidence, 0.4-0.7 if moderate, below 0.4 if weak."
        )

        return await self._call_llm(system_prompt, user_prompt)
