# tests/test_evidence_graph.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.evidence_service import evidence_service

@pytest.mark.asyncio
async def test_create_entity():
    """Test creating a bio entity."""
    with patch('app.services.evidence_service.db') as mock_db:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_db.get_pool.return_value = mock_pool
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        
        mock_conn.fetchrow.side_effect = [
            None,  # no existing entity
            {'id': '123', 'name': 'BRCA1', 'entity_type': 'gene'}  # after insert
        ]
        
        result = await evidence_service.create_entity('gene', 'BRCA1')
        assert result['name'] == 'BRCA1'

@pytest.mark.asyncio
async def test_add_evidence():
    """Test adding evidence edge."""
    with patch('app.services.evidence_service.db') as mock_db:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_db.get_pool.return_value = mock_pool
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        
        # Mock create_entity calls
        mock_conn.fetchrow.side_effect = [
            {'id': 'src_id', 'name': 'BRCA1'},  # source exists
            {'id': 'tgt_id', 'name': 'Breast Cancer'},  # target exists
            None,  # no existing edge
            {'id': 'edge_id', 'confidence': 0.95}  # after insert
        ]
        
        result = await evidence_service.add_evidence(
            source_name='BRCA1',
            source_type='gene',
            target_name='Breast Cancer',
            target_type='disease',
            predicate='associated_with',
            confidence=0.95,
            reference_id='ref_123'
        )
        assert result['confidence'] == 0.95
