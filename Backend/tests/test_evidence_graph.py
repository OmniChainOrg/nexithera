# tests/test_evidence_graph.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.evidence_service import evidence_service


def _build_db_mock(mock_db, fetchrow_side_effect):
    """Wire up an async-aware mock for `db` so that:

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchrow(...)
            await conn.execute(...)

    works under unittest.mock.
    """
    mock_conn = AsyncMock()
    mock_conn.fetchrow.side_effect = fetchrow_side_effect

    mock_pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=acquire_cm)

    mock_db.get_pool = AsyncMock(return_value=mock_pool)
    return mock_conn


@pytest.mark.asyncio
async def test_create_entity():
    """Test creating a bio entity."""
    with patch('app.services.evidence_service.db') as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                None,  # no existing entity
                {'id': '123', 'name': 'BRCA1', 'entity_type': 'gene'},  # after insert
            ],
        )

        result = await evidence_service.create_entity('gene', 'BRCA1')
        assert result['name'] == 'BRCA1'


@pytest.mark.asyncio
async def test_add_evidence():
    """Test adding evidence edge."""
    with patch('app.services.evidence_service.db') as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                # create_entity(source): existing check + SELECT by id
                {'id': 'src_id', 'name': 'BRCA1'},
                {'id': 'src_id', 'name': 'BRCA1', 'entity_type': 'gene'},
                # create_entity(target): existing check + SELECT by id
                {'id': 'tgt_id', 'name': 'Breast Cancer'},
                {'id': 'tgt_id', 'name': 'Breast Cancer', 'entity_type': 'disease'},
                # add_evidence: no existing edge
                None,
                # add_evidence: row after insert
                {'id': 'edge_id', 'confidence': 0.95},
            ],
        )

        result = await evidence_service.add_evidence(
            source_name='BRCA1',
            source_type='gene',
            target_name='Breast Cancer',
            target_type='disease',
            predicate='associated_with',
            confidence=0.95,
            reference_id='ref_123',
        )
        assert result['confidence'] == 0.95
