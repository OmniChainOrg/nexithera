# app/agents/partnerability_agent.py
"""Partnerability Agent (PR #10) — orchestrator.

Synthesizes the outputs of the three upstream agents
(Competitive Landscape, IP Position, IND Readiness) plus a
program-level "unmet need" estimate into a single composite
partnerability score.

Formula (per spec)::

    partnerability = 0.30 * competitive_moat
                   + 0.25 * ip_strength
                   + 0.25 * unmet_need
                   + 0.20 * ind_readiness

All sub-scores are 0..10, the composite is also 0..10.

The agent also ranks a small library of pharma partners by strategic
fit, using a heuristic that boosts fit when the partner's therapeutic
focus overlaps with the candidate's therapeutic area.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.database import db
from .base_agent import BaseAgent


# ---------------------------------------------------------------------------
# Composite score weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "competitive_moat": 0.30,
    "ip_strength": 0.25,
    "unmet_need": 0.25,
    "ind_readiness": 0.20,
}


# Small library of partnerable pharma companies tagged with focus areas.
# Used as a deterministic fallback when external BD data is unavailable.
_PARTNER_LIBRARY: List[Dict[str, Any]] = [
    {
        "name": "Pfizer",
        "focus_areas": {"oncology", "rare_disease", "vaccines"},
        "base_fit": 6.5,
    },
    {
        "name": "Roche",
        "focus_areas": {"oncology", "neuroscience", "ophthalmology"},
        "base_fit": 6.8,
    },
    {
        "name": "Merck",
        "focus_areas": {"oncology", "infectious_disease", "vaccines"},
        "base_fit": 6.4,
    },
    {
        "name": "Novartis",
        "focus_areas": {"oncology", "cardiovascular", "immunology"},
        "base_fit": 6.2,
    },
    {
        "name": "Bristol Myers Squibb",
        "focus_areas": {"oncology", "immunology", "hematology"},
        "base_fit": 6.5,
    },
    {
        "name": "Eli Lilly",
        "focus_areas": {"diabetes", "oncology", "neuroscience"},
        "base_fit": 6.0,
    },
]


def composite_partnerability(
    competitive_moat: float,
    ip_strength: float,
    unmet_need: float,
    ind_readiness: float,
) -> float:
    """Weighted composite (0..10) — the canonical PR #10 formula."""
    parts = {
        "competitive_moat": competitive_moat,
        "ip_strength": ip_strength,
        "unmet_need": unmet_need,
        "ind_readiness": ind_readiness,
    }
    score = 0.0
    for key, weight in WEIGHTS.items():
        sub = max(0.0, min(10.0, float(parts[key])))
        score += weight * sub
    return round(max(0.0, min(10.0, score)), 2)


def rank_partners(
    therapeutic_area: Optional[str],
    overall_score: float,
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    """Rank partners by therapeutic-area overlap and overall asset score."""
    ta = (therapeutic_area or "").lower().replace("-", "_").replace(" ", "_")
    ranked: List[Tuple[float, Dict[str, Any]]] = []
    for partner in _PARTNER_LIBRARY:
        overlap = any(area in ta for area in partner["focus_areas"]) or any(
            ta in area for area in partner["focus_areas"]
        )
        # Fit = base_fit + 1.5 if overlap + 0.2 * overall_score (caps at 10).
        fit = partner["base_fit"] + (1.5 if overlap else 0.0) + 0.2 * overall_score
        fit = round(min(10.0, max(0.0, fit)), 2)
        rationale = (
            f"{partner['name']} has focus overlap with '{therapeutic_area}' "
            if overlap
            else f"{partner['name']} is opportunistic for '{therapeutic_area}' "
        ) + (
            "and the asset's overall partnerability supports a strategic deal."
            if overall_score >= 6.0
            else "but the asset's partnerability score is still maturing."
        )
        ranked.append(
            (
                fit,
                {
                    "name": partner["name"],
                    "fit_score": fit,
                    "focus_overlap": overlap,
                    "rationale": rationale,
                },
            )
        )
    ranked.sort(key=lambda t: t[0], reverse=True)
    return [item for _, item in ranked[:top_n]]


def estimate_unmet_need(therapeutic_area: Optional[str]) -> float:
    """Return a 0..10 unmet-need estimate for a therapeutic area.

    Heuristic only — when external epidemiology data isn't connected we
    use a coarse mapping based on commonly-cited high-unmet-need
    indications.  Defaults to 6.0 (moderate) when unknown.
    """
    if not therapeutic_area:
        return 6.0
    ta = therapeutic_area.lower()
    high = (
        "pancreatic", "glioblastoma", "als", "ipf", "huntington",
        "ovarian", "rare", "orphan", "fibrosis",
    )
    medium = ("oncology", "nsclc", "breast", "colorectal", "melanoma")
    low = ("hypertension", "type 2 diabetes", "atopic dermatitis")
    if any(token in ta for token in high):
        return 9.0
    if any(token in ta for token in medium):
        return 7.0
    if any(token in ta for token in low):
        return 4.0
    return 6.0


class PartnerabilityAgent(BaseAgent):
    """Synthesize partnerability sub-scores into a composite score."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id, "Partnerability Agent", "partnerability"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "Partnerability Agent requires candidate_id input"
            )

        # Sub-scores may be passed in directly (orchestrator path) or
        # retrieved via a fresh agent run (callers usually compute them
        # in the service layer for full traceability — see
        # PartnerabilityService.assess()).
        competitive_moat = float(inputs.get("competitive_moat", 5.0))
        ip_strength = float(inputs.get("ip_strength", 5.0))
        ind_readiness = float(inputs.get("ind_readiness", 5.0))
        unmet_need = inputs.get("unmet_need")

        therapeutic_area: Optional[str] = inputs.get("therapeutic_area")
        if therapeutic_area is None:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT therapeutic_area FROM candidates WHERE id = $1",
                    candidate_id,
                )
                if not row:
                    raise ValueError(f"Candidate not found: {candidate_id}")
                therapeutic_area = row["therapeutic_area"]

        if unmet_need is None:
            unmet_need = estimate_unmet_need(therapeutic_area)
        unmet_need = float(unmet_need)

        overall_score = composite_partnerability(
            competitive_moat=competitive_moat,
            ip_strength=ip_strength,
            unmet_need=unmet_need,
            ind_readiness=ind_readiness,
        )
        partners = rank_partners(therapeutic_area, overall_score)
        # BD interest estimate scales with overall score (0..1).
        bd_interest = round(min(1.0, max(0.0, overall_score / 10.0)), 3)

        verdict = (
            "Highly Partnerable"
            if overall_score >= 7.5
            else "Conditionally Partnerable"
            if overall_score >= 5.0
            else "Not yet Partnerable"
        )

        summary = (
            f"Partnerability {overall_score}/10 ({verdict}). "
            f"moat={competitive_moat}, ip={ip_strength}, "
            f"unmet={unmet_need}, ind={ind_readiness}."
        )
        if overall_score >= 7.5:
            recommended = (
                "Initiate BD outreach to top-ranked partners; prepare "
                "data room with competitive + IP packages."
            )
        elif overall_score >= 5.0:
            recommended = (
                "Address weakest sub-score before partnering; revisit in "
                "60 days."
            )
        else:
            recommended = (
                "Strengthen IP and IND readiness before any BD outreach."
            )
        confidence = round(0.5 + 0.04 * overall_score, 3)

        return {
            "summary": summary,
            "structure": {
                "candidate_id": candidate_id,
                "therapeutic_area": therapeutic_area,
                "overall_score": overall_score,
                "competitive_moat_score": round(competitive_moat, 2),
                "ip_strength_score": round(ip_strength, 2),
                "unmet_need_score": round(unmet_need, 2),
                "ind_readiness_score": round(ind_readiness, 2),
                "bd_interest_estimate": bd_interest,
                "potential_partners": partners,
                "verdict": verdict,
                "weights": dict(WEIGHTS),
            },
            "confidence": confidence,
            "uncertainty_reason": (
                None
                if overall_score >= 7.0
                else "Sub-scores show meaningful gaps to address"
            ),
            "recommended_next_step": recommended,
            "trace_summary": (
                f"Composite of moat={competitive_moat}, ip={ip_strength}, "
                f"unmet={unmet_need}, ind={ind_readiness} -> "
                f"{overall_score}/10 ({verdict})."
            ),
        }
