# app/agents/historical_precedent_agent.py
"""Historical Precedent Agent (PR #11 — Clinical Forecaster).

Computes a similarity-weighted base rate (``precedent_prior``) from
``clinical_precedents`` for a given (target, disease, modality, phase)
tuple, plus a Wilson-style confidence interval and the top-5 most
similar trials.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..core.database import db
from .base_agent import BaseAgent


def _similarity(
    precedent: Dict[str, Any],
    *,
    target: Optional[str],
    disease: Optional[str],
    modality: Optional[str],
    phase: Optional[str],
) -> float:
    """Weighted Jaccard-style similarity in [0, 1]."""
    score = 0.0
    if target and precedent.get("target_label"):
        score += 0.4 if precedent["target_label"].lower() == target.lower() else 0.0
    if disease and precedent.get("disease_label"):
        if precedent["disease_label"].lower() == disease.lower():
            score += 0.3
        elif (
            disease.lower() in precedent["disease_label"].lower()
            or precedent["disease_label"].lower() in disease.lower()
        ):
            score += 0.15
    if modality and precedent.get("modality"):
        score += 0.15 if precedent["modality"] == modality else 0.0
    if phase and precedent.get("phase"):
        score += 0.15 if precedent["phase"] == phase else 0.0
    return round(score, 4)


def wilson_interval(
    successes: float, total: float, z: float = 1.96
) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion (supports
    fractional successes/totals coming from weighted aggregations)."""
    if total <= 0:
        return (0.0, 1.0)
    phat = successes / total
    denom = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denom
    margin = (
        z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total))
    ) / denom
    return (max(0.0, round(centre - margin, 4)),
            min(1.0, round(centre + margin, 4)))


def aggregate_precedent_prior(
    precedents: List[Dict[str, Any]],
    *,
    target: Optional[str],
    disease: Optional[str],
    modality: Optional[str],
    phase: Optional[str],
    top_k: int = 5,
) -> Dict[str, Any]:
    """Return precedent prior, CI and top-k similar trials."""
    if not precedents:
        return {
            "precedent_prior": 0.5,
            "confidence_interval": (0.2, 0.8),
            "top_precedents": [],
            "effective_n": 0,
        }
    ranked = []
    for p in precedents:
        sim = _similarity(
            p, target=target, disease=disease,
            modality=modality, phase=phase,
        )
        w = sim * float(p.get("weight") or 1.0)
        ranked.append((sim, w, p))
    ranked.sort(key=lambda t: t[0], reverse=True)

    total_w = sum(w for _, w, _ in ranked)
    if total_w <= 0:
        # Fall back to unweighted average over the most relevant slice.
        slice_ = [p for _, _, p in ranked[: max(10, top_k)]]
        succ = sum(1 for p in slice_ if p.get("met_primary_endpoint"))
        prior = round(succ / max(1, len(slice_)), 4)
        ci = wilson_interval(succ, max(1, len(slice_)))
    else:
        weighted_succ = sum(
            w for _, w, p in ranked if p.get("met_primary_endpoint")
        )
        prior = round(weighted_succ / total_w, 4)
        ci = wilson_interval(weighted_succ, total_w)

    top = [
        {
            "trial_id": p.get("trial_id"),
            "target": p.get("target_label"),
            "disease": p.get("disease_label"),
            "modality": p.get("modality"),
            "phase": p.get("phase"),
            "similarity": sim,
            "outcome": (
                "success" if p.get("met_primary_endpoint") else "failure"
            ),
        }
        for sim, _, p in ranked[:top_k]
        if sim > 0
    ]
    return {
        "precedent_prior": prior,
        "confidence_interval": ci,
        "top_precedents": top,
        "effective_n": round(total_w, 3),
    }


class HistoricalPrecedentAgent(BaseAgent):
    """Compute similarity-weighted base rate from historical trials."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id, "Historical Precedent Agent", "clinical_precedent"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "Historical Precedent Agent requires candidate_id input"
            )
        target = inputs.get("target_label")
        disease = inputs.get("disease_label")
        modality = inputs.get("modality")
        phase = inputs.get("phase")

        precedents: List[Dict[str, Any]] = list(
            inputs.get("precedents") or []
        )
        if not precedents:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT target_label, disease_label, modality, phase, "
                    "met_primary_endpoint, effect_size, p_value, trial_id, "
                    "weight FROM clinical_precedents LIMIT 1000"
                )
                precedents = [dict(r) for r in rows]

        agg = aggregate_precedent_prior(
            precedents,
            target=target, disease=disease,
            modality=modality, phase=phase,
        )
        lo, hi = agg["confidence_interval"]
        summary = (
            f"precedent_prior={agg['precedent_prior']} "
            f"[{lo}, {hi}] from {agg['effective_n']} "
            f"weighted matches."
        )
        return {
            "summary": summary,
            "structure": {
                "candidate_id": candidate_id,
                "precedent_prior": agg["precedent_prior"],
                "confidence_interval": [lo, hi],
                "top_precedents": agg["top_precedents"],
                "effective_n": agg["effective_n"],
                "query": {
                    "target": target, "disease": disease,
                    "modality": modality, "phase": phase,
                },
            },
            "confidence": round(
                0.5 + min(0.4, 0.05 * agg["effective_n"]), 3
            ),
            "uncertainty_reason": (
                None
                if agg["effective_n"] >= 3
                else "Few similar precedents; prior is weak"
            ),
            "recommended_next_step": (
                "Curate additional precedents to tighten the prior."
                if agg["effective_n"] < 3
                else "Prior is grounded in sufficient precedents."
            ),
            "trace_summary": summary,
        }
