# tests/test_agents.py
import pytest
from unittest.mock import AsyncMock, patch
from app.agents.target_biology_agent import TargetBiologyAgent
from app.agents.simulation_critic_agent import SimulationCriticAgent

@pytest.mark.asyncio
async def test_target_biology_agent():
    """Test target biology agent evaluation."""
    agent = TargetBiologyAgent("test_agent_id")

    llm_response = {
        "summary": "BRCA1 is highly relevant to Breast Cancer with strong pathway evidence.",
        "confidence": 0.85,
        "uncertainty_reason": None,
        "recommended_next_step": "Promote to candidate generation",
        "trace_summary": "LLM assessed BRCA1 vs Breast Cancer using 2 evidence edges.",
        "structure": {
            "target": "BRCA1",
            "disease": "Breast Cancer",
            "confidence": 0.85,
            "direct_evidence_count": 1,
            "total_target_evidence": 2,
            "target_plausibility_score": 0.85,
            "pathway_assessment": "Strong DNA repair pathway link",
            "disease_fit": "High",
        },
    }

    with patch.object(agent, '_query_evidence_graph', new_callable=AsyncMock) as mock_query, \
         patch.object(agent, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_query.return_value = [
            {'target_name': 'Breast Cancer', 'confidence': 0.85},
            {'source_name': 'BRCA1', 'target_name': 'DNA Repair', 'confidence': 0.9}
        ]
        mock_llm.return_value = llm_response

        result = await agent.execute({
            "target_name": "BRCA1",
            "disease_name": "Breast Cancer"
        })

        assert result['confidence'] >= 0.7
        assert 'BRCA1' in result['summary']
        assert result['recommended_next_step'] == "Promote to candidate generation"
        mock_llm.assert_called_once()

@pytest.mark.asyncio
async def test_simulation_critic_agent():
    """Test simulation critic identifies weaknesses."""
    agent = SimulationCriticAgent("test_agent_id")

    llm_response = {
        "summary": "⚠️ Simulation plan has 3 critical weaknesses. Requires revision before proceeding.",
        "confidence": 0.55,
        "uncertainty_reason": "Simulation plan has gaps",
        "recommended_next_step": "Revise simulation plan to address critical gaps",
        "trace_summary": "Critiqued simulation for BRCA1. Found 3 weaknesses.",
        "structure": {
            "target": "BRCA1",
            "candidate": None,
            "weaknesses": [
                "No positive control defined",
                "No negative control defined",
                "Low replication: 1 replicates (recommend ≥3)",
            ],
            "missing_controls": ["Missing positive control", "Missing negative control"],
            "assumptions": ["Assumptions not explicitly stated"],
            "passes_critique": False,
            "weakness_count": 3,
            "improvement_suggestions": ["Add positive control", "Add negative control", "Increase replicates to ≥3"],
        },
    }

    with patch.object(agent, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = llm_response

        result = await agent.execute({
            "simulation_plan": {
                "replicates": 1,
                "positive_control": None,
                "negative_control": None
            },
            "target_name": "BRCA1"
        })

        assert result['structure']['weakness_count'] >= 2
        assert result['confidence'] < 0.7
        assert "Missing positive control" in result['structure']['missing_controls']
        mock_llm.assert_called_once()

@pytest.mark.asyncio
async def test_oncology_agent():
    """Test oncology agent immune relevance scoring."""
    from app.agents.oncology_agent import OncologyImmunotherapyAgent

    agent = OncologyImmunotherapyAgent("test_agent_id")

    llm_response = {
        "summary": "PD-L1 shows strong immune relevance in solid_tumor with checkpoint pathway evidence.",
        "confidence": 0.75,
        "uncertainty_reason": None,
        "recommended_next_step": "Advance to candidate design with immunotherapy focus",
        "trace_summary": "Assessed PD-L1 in solid_tumor with 1 immune evidence edge.",
        "structure": {
            "target": "PD-L1",
            "tumor_type": "solid_tumor",
            "biomarker": None,
            "immune_relevance_score": 0.65,
            "biomarker_availability_score": 0.3,
            "tumor_suitability_score": 0.7,
            "overall_oncology_confidence": 0.75,
            "immune_evidence_count": 1,
            "biomarker_evidence_count": 0,
            "tme_assessment": "Moderate immune infiltration expected",
            "immunotherapy_fit": "Strong checkpoint inhibitor candidate",
        },
    }

    with patch.object(agent, '_query_evidence_graph', new_callable=AsyncMock) as mock_query, \
         patch.object(agent, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_query.return_value = [
            {'source_name': 'PD-1', 'target_name': 'T Cell', 'confidence': 0.9}
        ]
        mock_llm.return_value = llm_response

        result = await agent.execute({
            "target_name": "PD-L1",
            "tumor_type": "solid_tumor"
        })

        assert result['structure']['immune_relevance_score'] > 0
        assert result['confidence'] >= 0.5
        mock_llm.assert_called_once()
