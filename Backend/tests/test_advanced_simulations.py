# tests/test_advanced_simulations.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_cxu_lifecycle():
    """Test full CXU lifecycle."""
    with patch('app.services.cxu_service.epistemicos_client') as mock_eos:
        mock_eos.create_cxu = AsyncMock(return_value={'cxu_id': 'eos_cxu_123'})
        mock_eos.start_cxu = AsyncMock(return_value={'trace_id': 'trace_123'})
        
        # Create
        cxu = await cxu_service.create_cxu(
            name="Test CXU",
            cxu_type="tumor_microenvironment",
            zone_id="zone_123",
            configuration={"param": "value"}
        )
        assert cxu['status'] == 'created'
        
        # Start
        result = await cxu_service.start_cxu(cxu['id'])
        assert result['status'] == 'running'

@pytest.mark.asyncio
async def test_swarm_with_results():
    """Test swarm creation and result aggregation."""
    with patch('app.services.swarm_service.epistemicos_client') as mock_eos:
        mock_eos.create_swarm = AsyncMock(return_value={'swarm_id': 'eos_swarm_123'})
        mock_eos.get_swarm_results = AsyncMock(return_value={
            'aggregation_method': 'consensus',
            'consensus_score': 0.87,
            'diversity_metric': 0.42,
            'aggregated_output': {'recommendation': 'high_confidence'}
        })
        
        swarm = await swarm_service.create_swarm(
            name="Test Swarm",
            swarm_type="cooperative",
            objective="Find optimal dosing",
            configuration={},
            program_id="prog_123"
        )
        
        results = await swarm_service.get_swarm_results(swarm['id'])
        assert results['consensus_score'] == 0.87

@pytest.mark.asyncio
async def test_cross_zone_simulation():
    """Test cross-zone simulation."""
    with patch('app.services.cross_zone_service.epistemic
