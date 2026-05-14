# tests/test_agents.py
import pytest
from unittest.mock import AsyncMock, patch
from app.agents.target_biology_agent import TargetBiologyAgent
from app.agents.simulation_critic_agent import SimulationCriticAgent

@pytest.mark.asyncio
async def test_target_biology_agent():
    """Test target biology agent evaluation."""
    agent = TargetBiologyAgent("test_agent_id")
    
    # Mock evidence graph query
    with patch.object(agent, '_query_evidence_graph', new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {'target_name': 'Breast Cancer', 'confidence': 0.85},
            {'source_name': 'BRCA1', 'target_name': 'DNA Repair', 'confidence': 0.9}
        ]
        
        result = await agent.execute({
            "target_name": "BRCA1",
            "disease_name": "Breast Cancer"
        })
        
        assert result['confidence'] >= 0.7
        assert 'BRCA1' in result['summary']
        assert result['recommended_next_step'] == "Promote to candidate generation"

@pytest.mark.asyncio
async def test_simulation_critic_agent():
    """Test simulation critic identifies weaknesses."""
    agent = SimulationCriticAgent("test_agent_id")
    
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

@pytest.mark.asyncio
async def test_oncology_agent():
    """Test oncology agent immune relevance scoring."""
    from app.agents.oncology_agent import OncologyImmunotherapyAgent
    
    agent = OncologyImmunotherapyAgent("test_agent_id")
    
    with patch.object(agent, '_query_evidence_graph', new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {'source_name': 'PD-1', 'target_name': 'T Cell', 'confidence': 0.9}
        ]
        
        result = await agent.execute({
            "target_name": "PD-L1",
            "tumor_type": "solid_tumor"
        })
        
        assert result['structure']['immune_relevance_score'] > 0
        assert result['confidence'] >= 0.5
