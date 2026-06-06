# tests/test_hypothesis_candidate.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.hypothesis_service import hypothesis_service
from app.services.candidate_service import candidate_service


def _build_db_mock(mock_db, fetchrow_side_effect=None, fetchval_return=None):
    """Wire up an async-aware mock for `db` so that:

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchrow(...)
            await conn.execute(...)

    works under unittest.mock.
    """
    mock_conn = AsyncMock()
    if fetchrow_side_effect is not None:
        mock_conn.fetchrow.side_effect = fetchrow_side_effect
    if fetchval_return is not None:
        mock_conn.fetchval.return_value = fetchval_return

    mock_pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=acquire_cm)

    mock_db.get_pool = AsyncMock(return_value=mock_pool)
    return mock_conn


@pytest.mark.asyncio
async def test_create_hypothesis():
    """Test creating a hypothesis."""
    with patch('app.services.hypothesis_service.db') as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                None,  # no existing hypothesis
                {
                    'id': 'hyp_123',
                    'hypothesis_text': 'BRCA1 mutations increase breast cancer risk',
                    'version': 1,
                    'status': 'draft',
                },
            ],
        )

        result = await hypothesis_service.create_hypothesis(
            hypothesis_text="BRCA1 mutations increase breast cancer risk",
            claim_type="target_disease_association",
            program_id="prog_123",
        )
        assert result['hypothesis_text'] == "BRCA1 mutations increase breast cancer risk"
        assert result['status'] == "draft"


@pytest.mark.asyncio
async def test_create_candidate():
    """Test creating a candidate."""
    with patch('app.services.candidate_service.db') as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {
                    'id': 'cand_123',
                    'name': 'BRCA1 inhibitor',
                    'candidate_type': 'small_molecule',
                    'status': 'idea',
                },
            ],
        )

        result = await candidate_service.create_candidate(
            name="BRCA1 inhibitor",
            candidate_type="small_molecule",
            therapeutic_area="oncology",
            program_id="prog_123",
        )
        assert result['name'] == "BRCA1 inhibitor"
        assert result['status'] == "idea"


@pytest.mark.asyncio
async def test_kill_candidate_requires_rationale():
    """Test that killing a candidate requires a rationale."""
    with patch('app.services.candidate_service.db') as mock_db:
        _build_db_mock(mock_db)

        with pytest.raises(ValueError, match="Kill rationale required"):
            await candidate_service.update_candidate_status(
                candidate_id="cand_123",
                new_status="killed",
                kill_rationale=None,
            )


@pytest.mark.asyncio
async def test_update_candidate_status_rejects_invalid():
    """Invalid pipeline statuses are rejected before touching the DB."""
    with patch('app.services.candidate_service.db') as mock_db:
        _build_db_mock(mock_db)

        with pytest.raises(ValueError, match="Invalid status"):
            await candidate_service.update_candidate_status(
                candidate_id="cand_123",
                new_status="not_a_real_status",
            )


@pytest.mark.asyncio
async def test_kill_candidate_with_rationale():
    """Killing a candidate succeeds when a rationale is provided."""
    with patch('app.services.candidate_service.db') as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                # 1) lookup of previous status / program_id
                {
                    'status': 'candidate',
                    'program_id': 'prog_123',
                },
                # 2) final SELECT * after update
                {
                    'id': 'cand_123',
                    'name': 'BRCA1 inhibitor',
                    'status': 'killed',
                    'kill_rationale': 'Failed safety signal',
                },
            ],
        )

        result = await candidate_service.update_candidate_status(
            candidate_id="cand_123",
            new_status="killed",
            user_id="user_1",
            kill_rationale="Failed safety signal",
        )
        assert result['status'] == "killed"
        assert result['kill_rationale'] == "Failed safety signal"


@pytest.mark.asyncio
async def test_add_scorecard_increments_version():
    """Adding a scorecard bumps the version based on the current max."""
    with patch('app.services.candidate_service.db') as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {
                    'id': 'sc_1',
                    'candidate_id': 'cand_123',
                    'version': 2,
                    'overall_score': 7.5,
                },
            ],
            fetchval_return=1,
        )

        result = await candidate_service.add_scorecard(
            candidate_id="cand_123",
            evidence_score=8.0,
            simulation_score=7.0,
            safety_score=8.0,
            formulation_score=7.0,
            translational_score=7.0,
            program_fit_score=8.0,
        )
        assert result['version'] == 2
        # Ensure we queried for max version
        mock_conn.fetchval.assert_awaited()


@pytest.mark.asyncio
async def test_link_hypothesis_to_candidate():
    """Linking a hypothesis to a candidate returns the joined IDs."""
    with patch('app.services.candidate_service.db') as mock_db:
        _build_db_mock(mock_db)

        result = await candidate_service.link_hypothesis_to_candidate(
            candidate_id="cand_123",
            hypothesis_id="hyp_456",
        )
        assert result == {"candidate_id": "cand_123", "hypothesis_id": "hyp_456"}
