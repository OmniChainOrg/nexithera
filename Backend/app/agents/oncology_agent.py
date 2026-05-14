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
        
        # Query evidence for tumor microenvironment context
        target_evidence = await self._query_evidence_graph(target_name)
        
        # Check for immune-related evidence
        immune_keywords = ['immune', 't cell', 'pd-1', 'pd-l1', 'checkpoint', 'infiltration', 'cytokine']
        immune_evidence = [
            e for e in target_evidence 
            if any(keyword in str(e.get('source_name', '')).lower() or 
                   keyword in str(e.get('target_name', '')).lower() 
                   for keyword in immune_keywords)
        ]
        
        # Check for biomarker evidence
        biomarker_evidence = []
        if biomarker:
            biomarker_evidence = await self._query_evidence_graph(biomarker)
        
        # Calculate scores.  Any immune-relevant evidence establishes a
        # non-trivial baseline (0.5) plus a per-edge bonus, so a single strong
        # immune signal is not penalised down to noise.
        if immune_evidence:
            immune_relevance = min(1.0, 0.5 + len(immune_evidence) * 0.15)
        else:
            immune_relevance = 0.0
        biomarker_availability = 0.8 if biomarker and len(biomarker_evidence) > 0 else 0.3

        # Only average in biomarker availability when a biomarker was actually
        # requested.  Otherwise the score reflects immune relevance alone and
        # we don't punish callers for omitting an optional input.
        if biomarker:
            overall_confidence = (immune_relevance + biomarker_availability) / 2
        else:
            overall_confidence = immune_relevance if immune_relevance > 0 else 0.3
        
        # Determine tumor type suitability
        tumor_suitability = 0.7  # baseline for solid tumors
        if tumor_type == "liquid_tumor":
            tumor_suitability = 0.5  # immunotherapy often different in liquid tumors
        
        trace_summary = f"Target '{target_name}' in {tumor_type}. "
        trace_summary += f"Immune evidence: {len(immune_evidence)} edges. "
        if biomarker:
            trace_summary += f"Biomarker '{biomarker}': {len(biomarker_evidence)} edges."
        
        if overall_confidence >= 0.7:
            recommended_next_step = "Advance to candidate design with immunotherapy focus"
            summary = f"Target '{target_name}' shows strong immune relevance in {tumor_type}. "
        elif overall_confidence >= 0.4:
            recommended_next_step = "Explore additional immune mechanisms for this target"
            summary = f"Target '{target_name}' has moderate immune relevance in {tumor_type}. "
        else:
            recommended_next_step = "Reconsider target or tumor type selection"
            summary = f"Target '{target_name}' shows weak immune relevance in {tumor_type}. "
        
        if biomarker:
            summary += f"Biomarker {'available' if biomarker_availability >= 0.7 else 'limited'}."
        
        return {
            "summary": summary,
            "structure": {
                "target": target_name,
                "tumor_type": tumor_type,
                "biomarker": biomarker,
                "immune_relevance_score": immune_relevance,
                "biomarker_availability_score": biomarker_availability,
                "tumor_suitability_score": tumor_suitability,
                "overall_oncology_confidence": overall_confidence,
                "immune_evidence_count": len(immune_evidence),
                "biomarker_evidence_count": len(biomarker_evidence) if biomarker else 0
            },
            "confidence": overall_confidence,
            "uncertainty_reason": None if overall_confidence >= 0.6 else "Limited immune mechanism evidence",
            "recommended_next_step": recommended_next_step,
            "trace_summary": trace_summary
        }
