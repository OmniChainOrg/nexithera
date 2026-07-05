# app/agents/oncology_agent.py
from typing import Dict, Any, List
from .base_agent import BaseAgent

class OncologyImmunotherapyAgent(BaseAgent):
    """Focuses on tumor biology, immune mechanisms, biomarkers, and response hypotheses."""
    
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "Oncology & Immunotherapy Agent", "oncology_immunotherapy")
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inputs expected:
            - target_name: str
            - tumor_type: str
            - biomarker: str (optional)
        """
        target_name = inputs.get("target_name")
        tumor_type = inputs.get("tumor_type", "solid_tumor")
        biomarker = inputs.get("biomarker")

        # Gather evidence context
        target_evidence = await self._query_evidence_graph(target_name)
        immune_keywords = ['immune', 't cell', 'pd-1', 'pd-l1', 'checkpoint', 'infiltration', 'cytokine']
        immune_evidence = [
            e for e in target_evidence
            if any(keyword in str(e.get('source_name', '')).lower() or
                   keyword in str(e.get('target_name', '')).lower()
                   for keyword in immune_keywords)
        ]
        biomarker_evidence = []
        if biomarker:
            biomarker_evidence = await self._query_evidence_graph(biomarker)

        system_prompt = (
            "You are the Oncology & Immunotherapy Agent for a drug discovery platform. "
            "Evaluate oncology-specific therapeutic context, tumor microenvironment (TME), "
            "and immunotherapy landscape for a target. "
            "Return a JSON object with exactly these keys: "
            "summary (string), confidence (float 0-1), uncertainty_reason (null or string), "
            "recommended_next_step (string), trace_summary (string), structure (object with: "
            "target, tumor_type, biomarker, immune_relevance_score, biomarker_availability_score, "
            "tumor_suitability_score, overall_oncology_confidence, immune_evidence_count, "
            "biomarker_evidence_count, tme_assessment, immunotherapy_fit)."
        )
        user_prompt = (
            f"Target: {target_name}\n"
            f"Tumor type: {tumor_type}\n"
            f"Biomarker: {biomarker or 'not specified'}\n"
            f"Evidence graph:\n"
            f"- Total target evidence edges: {len(target_evidence)}\n"
            f"- Immune-related evidence edges: {len(immune_evidence)}\n"
            f"- Biomarker evidence edges: {len(biomarker_evidence)}\n"
            f"Sample immune evidence: {immune_evidence[:3] if immune_evidence else 'None'}\n\n"
            "Evaluate the oncology/immunotherapy fit. Consider TME, checkpoint pathways, "
            "biomarker availability, and tumor type suitability."
        )

        return await self._call_llm(system_prompt, user_prompt)
