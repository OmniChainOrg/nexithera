# app/services/partnerability_service.py
"""Persistence + orchestration for PR #10 partnerability / IND readiness.

Wires together the Competitive Landscape, IP Position, IND Readiness,
and Partnerability agents and writes their outputs to the PR #10
tables (``competitive_assets``, ``ip_positions``, ``partnerability_scores``,
``candidate_ind_readiness``).

The service is intentionally tolerant of missing tables / agents: each
upstream agent run is wrapped so a single sub-agent failure does not
abort the orchestrator (it falls back to neutral mid-range sub-scores
and surfaces the failure in the response payload).
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from ..agents.competitive_landscape_agent import CompetitiveLandscapeAgent
from ..agents.ind_readiness_agent import INDReadinessAgent
from ..agents.ip_position_agent import IPPositionAgent
from ..agents.partnerability_agent import PartnerabilityAgent
from ..core.database import db


_VALID_IND_STATUSES = {
    "not_started",
    "in_progress",
    "complete",
    "waived",
    "failed",
}


class PartnerabilityService:
    """Service layer for PR #10 partnerability / IND readiness."""

    # ------------------------------------------------------------------
    # Competitive landscape
    # ------------------------------------------------------------------
    async def run_competitive_landscape(
        self, candidate_id: str
    ) -> Dict[str, Any]:
        agent_id = await _ensure_agent_record(
            "Competitive Landscape Agent", "competitive_landscape"
        )
        agent = CompetitiveLandscapeAgent(agent_id)
        program_id = await _candidate_program_id(candidate_id)
        result = await agent.run(
            program_id=program_id,
            inputs={"candidate_id": candidate_id},
            candidate_id=candidate_id,
            run_type="competitive_landscape",
        )
        structure = (result.get("output") or {}).get("structure", {}) or {}
        competitors = structure.get("competitors", []) or []
        run_id = result["run_id"]

        persisted: List[Dict[str, Any]] = []
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            for comp in competitors:
                row_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO competitive_assets
                            (id, candidate_id, asset_name, developer,
                             phase, modality, mechanism,
                             estimated_launch_year, differentiation,
                             threat_level, source, source_ref,
                             confidence, agent_run_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                               $13,$14)""",
                    row_id,
                    candidate_id,
                    comp.get("asset_name") or "Unknown",
                    comp.get("developer"),
                    comp.get("phase"),
                    comp.get("modality"),
                    comp.get("mechanism"),
                    comp.get("estimated_launch_year"),
                    comp.get("differentiation"),
                    comp.get("threat_level"),
                    comp.get("source"),
                    comp.get("source_ref"),
                    comp.get("confidence"),
                    run_id,
                )
                stored = dict(comp)
                stored["id"] = row_id
                persisted.append(stored)

        return {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "competitors": persisted,
            "competitive_moat_score": structure.get(
                "competitive_moat_score"
            ),
            "summary": (result.get("output") or {}).get("summary"),
            "recommended_next_step": (
                (result.get("output") or {}).get("recommended_next_step")
            ),
        }

    # ------------------------------------------------------------------
    # IP position
    # ------------------------------------------------------------------
    async def run_ip_position(self, candidate_id: str) -> Dict[str, Any]:
        agent_id = await _ensure_agent_record(
            "IP Position Agent", "ip_position"
        )
        agent = IPPositionAgent(agent_id)
        program_id = await _candidate_program_id(candidate_id)
        result = await agent.run(
            program_id=program_id,
            inputs={"candidate_id": candidate_id},
            candidate_id=candidate_id,
            run_type="ip_position",
        )
        structure = (result.get("output") or {}).get("structure", {}) or {}
        positions = structure.get("positions", []) or []
        run_id = result["run_id"]

        persisted: List[Dict[str, Any]] = []
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            for pos in positions:
                row_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO ip_positions
                            (id, candidate_id, patent_number, patent_family,
                             assignee, expiry_year, jurisdiction, claims,
                             is_blocking, freedom_to_operate_estimate,
                             agent_run_id)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                    row_id,
                    candidate_id,
                    pos.get("patent_number"),
                    pos.get("patent_family"),
                    pos.get("assignee"),
                    pos.get("expiry_year"),
                    pos.get("jurisdiction"),
                    pos.get("claims"),
                    bool(pos.get("is_blocking")),
                    pos.get("freedom_to_operate_estimate"),
                    run_id,
                )
                stored = dict(pos)
                stored["id"] = row_id
                persisted.append(stored)

        return {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "positions": persisted,
            "ip_strength_score": structure.get("ip_strength_score"),
            "freedom_to_operate_estimate": structure.get(
                "freedom_to_operate_estimate"
            ),
            "blocking_count": structure.get("blocking_count"),
            "white_space_count": structure.get("white_space_count"),
            "summary": (result.get("output") or {}).get("summary"),
            "recommended_next_step": (
                (result.get("output") or {}).get("recommended_next_step")
            ),
        }

    # ------------------------------------------------------------------
    # IND readiness
    # ------------------------------------------------------------------
    async def run_ind_readiness(self, candidate_id: str) -> Dict[str, Any]:
        agent_id = await _ensure_agent_record(
            "IND Readiness Agent", "ind_readiness"
        )
        agent = INDReadinessAgent(agent_id)
        program_id = await _candidate_program_id(candidate_id)
        result = await agent.run(
            program_id=program_id,
            inputs={"candidate_id": candidate_id},
            candidate_id=candidate_id,
            run_type="ind_readiness",
        )
        structure = (result.get("output") or {}).get("structure", {}) or {}
        return {
            "run_id": result["run_id"],
            "candidate_id": candidate_id,
            "overall_readiness": structure.get("overall_readiness"),
            "ind_readiness_score": structure.get("ind_readiness_score"),
            "items_complete": structure.get("items_complete"),
            "items_total": structure.get("items_total"),
            "critical_gaps": structure.get("critical_gaps", []),
            "estimated_timeline_months": structure.get(
                "estimated_timeline_months"
            ),
            "by_category": structure.get("by_category", {}),
            "items": structure.get("items", []),
            "summary": (result.get("output") or {}).get("summary"),
            "recommended_next_step": (
                (result.get("output") or {}).get("recommended_next_step")
            ),
        }

    async def update_checklist_item(
        self,
        candidate_id: str,
        item_id: str,
        status: str,
        evidence_uri: Optional[str] = None,
        notes: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        if status not in _VALID_IND_STATUSES:
            raise ValueError(
                f"Invalid IND checklist status: {status!r}. "
                f"Allowed: {sorted(_VALID_IND_STATUSES)}"
            )
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            candidate = await conn.fetchrow(
                "SELECT id FROM candidates WHERE id = $1", candidate_id
            )
            if not candidate:
                raise ValueError(f"Candidate not found: {candidate_id}")
            item = await conn.fetchrow(
                "SELECT id FROM ind_readiness_items WHERE id = $1", item_id
            )
            if not item:
                raise ValueError(f"Checklist item not found: {item_id}")
            row = await conn.fetchrow(
                """
                INSERT INTO candidate_ind_readiness
                    (id, candidate_id, checklist_item_id, status,
                     evidence_uri, notes, updated_by, updated_at)
                VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (candidate_id, checklist_item_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        evidence_uri = EXCLUDED.evidence_uri,
                        notes = EXCLUDED.notes,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW()
                RETURNING id, candidate_id, checklist_item_id, status,
                          evidence_uri, notes, updated_at
                """,
                candidate_id,
                item_id,
                status,
                evidence_uri,
                notes,
                _coerce_uuid(updated_by),
            )
        return dict(row) if row else {}

    # ------------------------------------------------------------------
    # Partnerability (orchestrator)
    # ------------------------------------------------------------------
    async def assess_partnerability(
        self,
        candidate_id: str,
        assessed_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run all sub-agents (best-effort) and persist a composite score."""
        sub_errors: Dict[str, str] = {}

        try:
            comp = await self.run_competitive_landscape(candidate_id)
            competitive_moat = float(
                comp.get("competitive_moat_score") or 5.0
            )
        except Exception as exc:  # noqa: BLE001
            sub_errors["competitive_landscape"] = str(exc)
            competitive_moat = 5.0
            comp = {"competitive_moat_score": 5.0, "competitors": []}

        try:
            ip = await self.run_ip_position(candidate_id)
            ip_strength = float(ip.get("ip_strength_score") or 5.0)
        except Exception as exc:  # noqa: BLE001
            sub_errors["ip_position"] = str(exc)
            ip_strength = 5.0
            ip = {"ip_strength_score": 5.0, "positions": []}

        try:
            ind = await self.run_ind_readiness(candidate_id)
            ind_readiness = float(ind.get("ind_readiness_score") or 0.0)
        except Exception as exc:  # noqa: BLE001
            sub_errors["ind_readiness"] = str(exc)
            ind_readiness = 0.0
            ind = {
                "ind_readiness_score": 0.0,
                "items_complete": 0,
                "items_total": 0,
            }

        agent_id = await _ensure_agent_record(
            "Partnerability Agent", "partnerability"
        )
        agent = PartnerabilityAgent(agent_id)
        program_id = await _candidate_program_id(candidate_id)
        result = await agent.run(
            program_id=program_id,
            inputs={
                "candidate_id": candidate_id,
                "competitive_moat": competitive_moat,
                "ip_strength": ip_strength,
                "ind_readiness": ind_readiness,
            },
            candidate_id=candidate_id,
            run_type="partnerability",
        )
        structure = (result.get("output") or {}).get("structure", {}) or {}
        run_id = result["run_id"]

        score_id = str(uuid.uuid4())
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO partnerability_scores
                        (id, candidate_id, overall_score,
                         competitive_moat_score, ip_strength_score,
                         unmet_need_score, ind_readiness_score,
                         bd_interest_estimate, potential_partners,
                         rationale, agent_run_id, assessed_by)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                score_id,
                candidate_id,
                float(structure.get("overall_score") or 0.0),
                structure.get("competitive_moat_score"),
                structure.get("ip_strength_score"),
                structure.get("unmet_need_score"),
                structure.get("ind_readiness_score"),
                structure.get("bd_interest_estimate"),
                json.dumps(structure.get("potential_partners") or []),
                (result.get("output") or {}).get("recommended_next_step"),
                run_id,
                _coerce_uuid(assessed_by),
            )

        return {
            "id": score_id,
            "run_id": run_id,
            "candidate_id": candidate_id,
            "overall_score": structure.get("overall_score"),
            "competitive_moat": structure.get("competitive_moat_score"),
            "ip_strength": structure.get("ip_strength_score"),
            "unmet_need": structure.get("unmet_need_score"),
            "ind_readiness": structure.get("ind_readiness_score"),
            "bd_interest_estimate": structure.get("bd_interest_estimate"),
            "potential_partners": structure.get("potential_partners", []),
            "verdict": structure.get("verdict"),
            "summary": (result.get("output") or {}).get("summary"),
            "recommended_next_step": (
                (result.get("output") or {}).get("recommended_next_step")
            ),
            "sub_errors": sub_errors,
            "competitive_landscape": comp,
            "ip_position": ip,
            "ind_readiness_assessment": ind,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _ensure_agent_record(name: str, role: str) -> str:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM agents WHERE name = $1", name
        )
        if row:
            return str(row["id"])
        new_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO agents (id, name, role, is_active)
               VALUES ($1, $2, $3, TRUE)
               ON CONFLICT (name) DO NOTHING""",
            new_id,
            name,
            role,
        )
        row = await conn.fetchrow(
            "SELECT id FROM agents WHERE name = $1", name
        )
        return str(row["id"]) if row else new_id


async def _candidate_program_id(candidate_id: str) -> str:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT program_id FROM candidates WHERE id = $1", candidate_id
        )
        if not row:
            raise ValueError(f"Candidate not found: {candidate_id}")
        return str(row["program_id"])


def _coerce_uuid(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


partnerability_service = PartnerabilityService()
