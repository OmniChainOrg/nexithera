# tests/test_guardian.py
"""Tests for the Guardian review system (PR #5)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.guardian_service import guardian_service


def _build_db_mock(mock_db, fetchrow_side_effect=None, fetch_return=None,
                   fetchval_return=None):
    """Wire up an async-aware mock for `db` so that:

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchrow(...)
            await conn.fetch(...)
            await conn.execute(...)

    works under unittest.mock.  Mirrors the helper in
    tests/test_hypothesis_candidate.py.
    """
    mock_conn = AsyncMock()
    if fetchrow_side_effect is not None:
        mock_conn.fetchrow.side_effect = fetchrow_side_effect
    if fetch_return is not None:
        mock_conn.fetch.return_value = fetch_return
    if fetchval_return is not None:
        mock_conn.fetchval.return_value = fetchval_return

    mock_pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=acquire_cm)

    mock_db.get_pool = AsyncMock(return_value=mock_pool)
    return mock_conn


# ---------------------------------------------------------------------------
# Review creation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_review_approve_hypothesis():
    """Approving a hypothesis records the review and updates entity status."""
    with patch("app.services.guardian_service.db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {
                    "id": "rev_1",
                    "review_type": "hypothesis_review",
                    "entity_id": "hyp_1",
                    "entity_type": "hypothesis",
                    "decision": "approve",
                    "decision_rationale": "Strong supporting evidence.",
                    "reviewer_id": "user_1",
                    "is_final": True,
                    "superseded_by": None,
                },
            ],
        )

        result = await guardian_service.create_review(
            review_type="hypothesis_review",
            entity_id="hyp_1",
            entity_type="hypothesis",
            reviewer_id="user_1",
            decision="approve",
            decision_rationale="Strong supporting evidence.",
        )

        assert result["decision"] == "approve"
        assert result["entity_type"] == "hypothesis"
        # Verify the entity-status UPDATE was issued (INSERT + UPDATE hypothesis).
        executed_sql = [c.args[0] for c in mock_conn.execute.await_args_list]
        assert any("INSERT INTO guardian_reviews" in s for s in executed_sql)
        assert any(
            "UPDATE hypotheses" in s and "status" in s for s in executed_sql
        )


@pytest.mark.asyncio
async def test_kill_candidate_via_review_requires_rationale():
    """A 'kill' decision without rationale is rejected before any DB write."""
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(mock_db)

        with pytest.raises(ValueError, match="Kill rationale required"):
            await guardian_service.create_review(
                review_type="candidate_review",
                entity_id="cand_1",
                entity_type="candidate",
                reviewer_id="user_1",
                decision="kill",
                decision_rationale="",
            )


@pytest.mark.asyncio
async def test_create_review_rejects_invalid_decision():
    """Decisions outside the allowed enum are rejected."""
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(mock_db)

        with pytest.raises(ValueError, match="Invalid decision"):
            await guardian_service.create_review(
                review_type="candidate_review",
                entity_id="cand_1",
                entity_type="candidate",
                reviewer_id="user_1",
                decision="not_a_real_decision",
                decision_rationale="Some text.",
            )


@pytest.mark.asyncio
async def test_create_review_rejects_invalid_review_type():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(mock_db)

        with pytest.raises(ValueError, match="Invalid review_type"):
            await guardian_service.create_review(
                review_type="bogus_type",
                entity_id="cand_1",
                entity_type="candidate",
                reviewer_id="user_1",
                decision="approve",
                decision_rationale="ok",
            )


@pytest.mark.asyncio
async def test_kill_candidate_via_review_sets_kill_metadata():
    """Killing a candidate via a review writes kill_rationale/killed_by/killed_at."""
    with patch("app.services.guardian_service.db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {
                    "id": "rev_2",
                    "review_type": "candidate_review",
                    "entity_id": "cand_1",
                    "entity_type": "candidate",
                    "decision": "kill",
                    "decision_rationale": "Failed safety signal",
                    "reviewer_id": "user_1",
                    "is_final": True,
                    "superseded_by": None,
                },
            ],
        )

        await guardian_service.create_review(
            review_type="candidate_review",
            entity_id="cand_1",
            entity_type="candidate",
            reviewer_id="user_1",
            decision="kill",
            decision_rationale="Failed safety signal",
        )

        executed_sql = [c.args[0] for c in mock_conn.execute.await_args_list]
        assert any(
            "UPDATE candidates" in s and "kill_rationale" in s
            for s in executed_sql
        )


@pytest.mark.asyncio
async def test_promote_to_epistemicos_updates_candidate():
    """promote_to_epistemicos drives the candidate to 'promoted'."""
    with patch("app.services.guardian_service.db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {
                    "id": "rev_3",
                    "decision": "promote_to_epistemicos",
                    "entity_type": "candidate",
                },
            ],
        )

        await guardian_service.create_review(
            review_type="epistemicos_promotion",
            entity_id="cand_1",
            entity_type="candidate",
            reviewer_id="user_1",
            decision="promote_to_epistemicos",
            decision_rationale="Ready for recursive reasoning.",
        )

        executed_sql = [c.args[0] for c in mock_conn.execute.await_args_list]
        update_stmts = [s for s in executed_sql if "UPDATE candidates" in s]
        assert update_stmts, "Expected candidate status update"


# ---------------------------------------------------------------------------
# Immutability / supersede flow
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_submit_decision_supersedes_original_review():
    """A new decision supersedes the original via a fresh review row."""
    with patch("app.services.guardian_service.db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                # original review lookup
                {
                    "id": "rev_orig",
                    "review_type": "candidate_review",
                    "entity_id": "cand_1",
                    "entity_type": "candidate",
                    "is_final": True,
                    "superseded_by": None,
                },
                # final SELECT of the new review
                {
                    "id": "rev_new",
                    "decision": "approve",
                    "review_type": "candidate_review",
                    "entity_id": "cand_1",
                    "entity_type": "candidate",
                    "is_final": True,
                    "superseded_by": None,
                },
            ],
        )

        new_review = await guardian_service.submit_decision(
            review_id="rev_orig",
            decision="approve",
            decision_rationale="Revised view: evidence now sufficient.",
            reviewer_id="user_1",
        )

        assert new_review["id"] == "rev_new"
        executed_sql = [c.args[0] for c in mock_conn.execute.await_args_list]
        # We must INSERT a new review row...
        assert any("INSERT INTO guardian_reviews" in s for s in executed_sql)
        # ...and mark the original as superseded.
        assert any(
            "UPDATE guardian_reviews" in s
            and "is_final = FALSE" in s
            and "superseded_by" in s
            for s in executed_sql
        )


@pytest.mark.asyncio
async def test_submit_decision_rejects_already_superseded():
    """Cannot supersede an already-superseded review."""
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {
                    "id": "rev_orig",
                    "review_type": "candidate_review",
                    "entity_id": "cand_1",
                    "entity_type": "candidate",
                    "is_final": False,
                    "superseded_by": "rev_other",
                },
            ],
        )

        with pytest.raises(ValueError, match="already been superseded"):
            await guardian_service.submit_decision(
                review_id="rev_orig",
                decision="approve",
                decision_rationale="Try again.",
                reviewer_id="user_1",
            )


@pytest.mark.asyncio
async def test_submit_decision_review_not_found():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(mock_db, fetchrow_side_effect=[None])

        with pytest.raises(ValueError, match="Review not found"):
            await guardian_service.submit_decision(
                review_id="missing",
                decision="approve",
                decision_rationale="Has rationale.",
                reviewer_id="user_1",
            )


# ---------------------------------------------------------------------------
# Checklists
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_checklist_returns_items():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetch_return=[
                {
                    "id": "chk_1",
                    "review_type": "candidate_review",
                    "criterion": "Target engagement",
                    "order_index": 1,
                },
                {
                    "id": "chk_2",
                    "review_type": "candidate_review",
                    "criterion": "Safety profile",
                    "order_index": 2,
                },
            ],
        )

        items = await guardian_service.get_checklist("candidate_review")
        assert len(items) == 2
        assert items[0]["criterion"] == "Target engagement"


@pytest.mark.asyncio
async def test_get_checklist_rejects_invalid_type():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(mock_db)
        with pytest.raises(ValueError, match="Invalid review_type"):
            await guardian_service.get_checklist("bogus_type")


@pytest.mark.asyncio
async def test_add_checklist_response_inserts_new():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                # review lookup
                {"is_final": True, "superseded_by": None},
                # existing response check
                None,
                # final SELECT of inserted response
                {
                    "id": "resp_1",
                    "review_id": "rev_1",
                    "checklist_item_id": "chk_1",
                    "passed": True,
                    "notes": "ok",
                },
            ],
        )

        result = await guardian_service.add_checklist_response(
            review_id="rev_1",
            checklist_item_id="chk_1",
            passed=True,
            notes="ok",
        )
        assert result["passed"] is True


@pytest.mark.asyncio
async def test_add_checklist_response_blocks_on_superseded_review():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {"is_final": False, "superseded_by": "rev_new"},
            ],
        )
        with pytest.raises(ValueError, match="superseded"):
            await guardian_service.add_checklist_response(
                review_id="rev_old",
                checklist_item_id="chk_1",
                passed=True,
            )


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_add_comment_returns_row():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                {
                    "id": "cmt_1",
                    "review_id": "rev_1",
                    "user_id": "user_1",
                    "comment_text": "Looks good.",
                    "parent_comment_id": None,
                },
            ],
        )

        result = await guardian_service.add_comment(
            review_id="rev_1",
            user_id="user_1",
            comment_text="Looks good.",
        )
        assert result["comment_text"] == "Looks good."


@pytest.mark.asyncio
async def test_add_comment_rejects_empty_text():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(mock_db)
        with pytest.raises(ValueError, match="Comment text"):
            await guardian_service.add_comment(
                review_id="rev_1",
                user_id="user_1",
                comment_text="   ",
            )


# ---------------------------------------------------------------------------
# Signed report
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_report_creates_signed_artifact():
    """Generating a report stores an artifact with checksum + signed URI."""
    with patch("app.services.guardian_service.db") as mock_db:
        mock_conn = _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                # get_review: review row
                {
                    "id": "rev_1",
                    "decision": "approve",
                    "decision_rationale": "Solid.",
                    "review_type": "candidate_review",
                    "entity_id": "cand_1",
                    "entity_type": "candidate",
                },
                # final SELECT of inserted artifact
                {
                    "id": "art_1",
                    "review_id": "rev_1",
                    "artifact_type": "report",
                    "artifact_uri": "s3://guardian-reports/rev_1/report-abc.pdf",
                    "checksum": "deadbeef" * 8,
                    "created_by": "user_1",
                },
            ],
            fetch_return=[],  # checklist / comments / artifacts / assignments
        )

        result = await guardian_service.generate_report(
            review_id="rev_1",
            created_by="user_1",
        )
        assert result["artifact_type"] == "report"
        assert result["checksum"]

        executed_sql = [c.args[0] for c in mock_conn.execute.await_args_list]
        assert any("INSERT INTO review_artifacts" in s for s in executed_sql)
        assert any(
            "UPDATE guardian_reviews" in s and "signed_artifact_uri" in s
            for s in executed_sql
        )


@pytest.mark.asyncio
async def test_generate_report_rejects_invalid_artifact_type():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(mock_db)
        with pytest.raises(ValueError, match="Invalid artifact_type"):
            await guardian_service.generate_report(
                review_id="rev_1",
                created_by="user_1",
                artifact_type="not_a_type",
            )


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_assign_reviewer_inserts_new_assignment():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(
            mock_db,
            fetchrow_side_effect=[
                None,  # no existing assignment
                {
                    "id": "asg_1",
                    "review_id": "rev_1",
                    "assignee_id": "user_2",
                    "assigned_by": "user_1",
                    "status": "pending",
                },
            ],
        )

        result = await guardian_service.assign_reviewer(
            review_id="rev_1",
            assignee_id="user_2",
            assigned_by="user_1",
        )
        assert result["status"] == "pending"
        assert result["assignee_id"] == "user_2"


@pytest.mark.asyncio
async def test_update_assignment_status_rejects_invalid():
    with patch("app.services.guardian_service.db") as mock_db:
        _build_db_mock(mock_db)
        with pytest.raises(ValueError, match="Invalid assignment status"):
            await guardian_service.update_assignment_status(
                assignment_id="asg_1",
                status="bogus",
            )
