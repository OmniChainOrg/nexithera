# tests/test_hypothesis_candidate.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.hypothesis_service import hypothesis_service
from app.services.candidate_service import candidate_service

@pytest.mark.asyncio
async def test_create_hypothesis():
    """Test creating a hypothesis."""
    with patch('app.services.hypothesis_service.db') as mock_db:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_db.get_pool.return_value = mock_pool
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_conn.fetchrow.side_effect = [
            None,  # no existing hypothesis
            {'id': 'hyp_123', 'hypothesis_text': 'Test hypothesis', 'version': 1}
        ]

        result = await hypothesis_service.create_hypothesis(
            hypothesis_text="BRCA1 mutations increase breast cancer risk",
            claim_type="target_disease_association",
            program_id="prog_123"
        )
        assert result['hypothesis_text'] == "BRCA1 mutations increase breast cancer risk"

@pytest.mark.asyncio
async def test_create_candidate():
    """Test creating a candidate."""
    with patch('app.services.candidate_service.db') as mock_db:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_db.get_pool.return_value = mock_pool
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        mock_conn.fetchrow.return_value = {
            'id': 'cand_123',
            'name': 'BRCA1 inhibitor',
            'candidate_type': 'small_molecule',
            'status': 'idea'
        }

        result = await candidate_service.create_candidate(
            name="BRCA1 inhibitor",
            candidate_type="small_molecule",
            therapeutic_area="oncology",
            program_id="prog_123"
        )
        assert result['name'] == "BRCA1 inhibitor"
        assert result['status'] == "idea"

@pytest.mark.asyncio
async def test_kill_candidate_requires_rationale():
    """Test that killing a candidate requires a rationale."""
    with patch('app.services.candidate_service.db') as mock_db:
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_db.get_pool.return_value = mock_pool
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with pytest.raises(ValueError, match="Kill rationale required"):
            await candidate_service.update_candidate_status(
                candidate_id="cand_123",
                new_status="killed",
                kill_rationale=None
            )
