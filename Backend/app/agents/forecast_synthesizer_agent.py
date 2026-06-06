# app/agents/forecast_synthesizer_agent.py
"""Forecast Synthesizer (PR #11 — Clinical Forecaster).

Combines sub-agent outputs into the final P(success) with:

    * decomposition  -- per-factor contribution to the probability,
    * sensitivity    -- tornado plot data (delta probability for +/-10%),
    * scenarios      -- optimistic / pessimistic / what-if alternatives,
    * confidence interval propagated from the precedent CI.

The combination formula (PR #11 spec)::

    P(success) = sum_i  w_i * factor_i

where ``w_i`` are calibrated factor weights (initially equal-ish, then
Bayesianly updated -- see :func:`bayesian_update_weights`).
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from .base_agent import BaseAgent


FACTOR_NAMES: Tuple[str, ...] = (
    "biology", "safety", "design", "competition", "precedent",
)

# Default seed weights (kept in sync with migration 011 seed).
DEFAULT_WEIGHTS: Dict[str, float] = {
    "biology": 0.30,
    "safety": 0.20,
    "design": 0.15,
    "competition": 0.10,
    "precedent": 0.25,
}


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Return a copy of ``weights`` rescaled so the values sum to 1."""
    filtered = {k: max(0.0, float(v)) for k, v in weights.items()
                if k in FACTOR_NAMES}
    total = sum(filtered.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: round(v / total, 6) for k, v in filtered.items()}


def combine_probability(
    factors: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Weighted sum of factors -> 0..1 probability."""
    w = normalize_weights(weights or DEFAULT_WEIGHTS)
    p = 0.0
    for name in FACTOR_NAMES:
        f = float(factors.get(name, 0.5))
        f = max(0.0, min(1.0, f))
        p += w.get(name, 0.0) * f
    return round(max(0.0, min(1.0, p)), 4)


def decompose_contributions(
    factors: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Return per-factor contribution ``w_i * f_i`` (sums to probability)."""
    w = normalize_weights(weights or DEFAULT_WEIGHTS)
    out = {}
    for name in FACTOR_NAMES:
        f = max(0.0, min(1.0, float(factors.get(name, 0.5))))
        out[f"{name}_contribution"] = round(w.get(name, 0.0) * f, 4)
    return out


def tornado_sensitivity(
    factors: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
    delta: float = 0.10,
) -> Dict[str, Any]:
    """Vary each factor by ±delta and report the resulting probability swing.

    Returns ``{"tornado_data": [...], "most_influential_factor": name}``
    sorted by absolute swing descending.
    """
    base = combine_probability(factors, weights)
    rows = []
    for name in FACTOR_NAMES:
        f = factors.get(name, 0.5)
        hi_factors = dict(factors)
        lo_factors = dict(factors)
        hi_factors[name] = max(0.0, min(1.0, float(f) + delta))
        lo_factors[name] = max(0.0, min(1.0, float(f) - delta))
        p_hi = combine_probability(hi_factors, weights)
        p_lo = combine_probability(lo_factors, weights)
        swing = round(abs(p_hi - p_lo), 4)
        rows.append(
            {
                "factor": name,
                "low_value": round(lo_factors[name], 4),
                "high_value": round(hi_factors[name], 4),
                "p_low": p_lo,
                "p_high": p_hi,
                "swing": swing,
            }
        )
    rows.sort(key=lambda r: r["swing"], reverse=True)
    return {
        "base_probability": base,
        "delta": delta,
        "tornado_data": rows,
        "most_influential_factor": (
            f"{rows[0]['factor']}_score" if rows else None
        ),
    }


def scenario_explorer(
    factors: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
    overrides: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run a set of named scenario overrides and return their probabilities.

    ``overrides`` is a list of ``{"name": str, "factors": {...}}`` dicts.
    Two canonical scenarios (``optimistic`` / ``pessimistic``) are
    always included alongside any caller-supplied scenarios.
    """
    out: Dict[str, Any] = {}
    canonical = [
        ("optimistic", {k: min(1.0, v + 0.15) for k, v in factors.items()}),
        ("pessimistic", {k: max(0.0, v - 0.15) for k, v in factors.items()}),
    ]
    for name, scen in canonical:
        out[name] = combine_probability(scen, weights)

    custom = []
    for spec in overrides or []:
        name = spec.get("name") or "scenario"
        merged = dict(factors)
        merged.update(spec.get("factors") or {})
        p = combine_probability(merged, weights)
        custom.append(
            {"name": name, "factors": merged, "probability": p}
        )
        out[name] = p
    out["_custom"] = custom
    return out


def bayesian_update_weights(
    weights: Dict[str, float],
    observed_outcome: bool,
    factor_likelihoods: Dict[str, float],
    learning_rate: float = 0.10,
) -> Dict[str, float]:
    """Update ``weights`` from one observed outcome.

    ``factor_likelihoods[factor]`` is the probability the agent assigned
    to the *observed* outcome conditional on that factor alone.  Factors
    whose prediction aligns with reality get up-weighted; those that
    disagreed get down-weighted.  ``learning_rate`` caps the per-update
    movement so a single observation never collapses the weights.
    """
    updated = {}
    for name in FACTOR_NAMES:
        w = max(0.0, float(weights.get(name, DEFAULT_WEIGHTS[name])))
        likelihood = float(
            factor_likelihoods.get(name, 0.5 if observed_outcome else 0.5)
        )
        likelihood = max(0.05, min(0.95, likelihood))
        # Multiplicative update toward likelihood ratio vs 0.5, clamped.
        ratio = likelihood / 0.5
        ratio = max(1.0 - learning_rate, min(1.0 + learning_rate, ratio))
        updated[name] = w * ratio
    return normalize_weights(updated)


def confidence_interval(
    probability: float,
    precedent_ci: Optional[Tuple[float, float]],
    factor_confidences: Dict[str, float],
) -> Tuple[float, float]:
    """Combine precedent CI with agent confidences into a final CI."""
    # Width grows with low agent confidence; centred on the probability.
    avg_conf = (
        sum(max(0.0, min(1.0, c)) for c in factor_confidences.values())
        / max(1, len(factor_confidences))
    )
    half_width = (1.0 - avg_conf) * 0.25
    if precedent_ci is not None:
        lo_p, hi_p = precedent_ci
        lo_p = max(0.0, min(1.0, float(lo_p)))
        hi_p = max(0.0, min(1.0, float(hi_p)))
        # Average our own half-width with precedent half-width.
        prec_half = max(0.0, (hi_p - lo_p) / 2.0)
        half_width = (half_width + prec_half) / 2.0
    lo = max(0.0, round(probability - half_width, 4))
    hi = min(1.0, round(probability + half_width, 4))
    if lo > hi:
        lo, hi = hi, lo
    return (lo, hi)


class ForecastSynthesizerAgent(BaseAgent):
    """Combine ensemble outputs into the final forecast."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id, "Forecast Synthesizer", "clinical_forecast"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "Forecast Synthesizer requires candidate_id input"
            )
        factors: Dict[str, float] = dict(inputs.get("factors") or {})
        weights: Dict[str, float] = (
            inputs.get("weights") or dict(DEFAULT_WEIGHTS)
        )
        precedent_ci = inputs.get("precedent_confidence_interval")
        factor_confidences = inputs.get("factor_confidences") or {}
        scenario_overrides = inputs.get("scenarios") or []

        probability = combine_probability(factors, weights)
        decomposition = decompose_contributions(factors, weights)
        sensitivity = tornado_sensitivity(factors, weights)
        scenarios = scenario_explorer(factors, weights, scenario_overrides)
        ci_lo, ci_hi = confidence_interval(
            probability,
            tuple(precedent_ci) if precedent_ci else None,
            factor_confidences,
        )

        verdict = (
            "Go" if probability >= 0.65
            else "Conditional" if probability >= 0.45
            else "No-Go"
        )
        summary = (
            f"P(success)={probability} CI=[{ci_lo}, {ci_hi}] ({verdict}). "
            f"Most influential factor: {sensitivity['most_influential_factor']}."
        )
        return {
            "summary": summary,
            "structure": {
                "candidate_id": candidate_id,
                "probability": probability,
                "confidence_interval": [ci_lo, ci_hi],
                "decomposition": decomposition,
                "sensitivity": sensitivity,
                "scenarios": scenarios,
                "factors": factors,
                "weights": normalize_weights(weights),
                "verdict": verdict,
            },
            "confidence": round(
                0.5 + 0.4 * (
                    sum(factor_confidences.values())
                    / max(1, len(factor_confidences))
                ),
                3,
            ),
            "uncertainty_reason": (
                None if probability >= 0.6 else "Low or borderline probability"
            ),
            "recommended_next_step": {
                "Go": "Proceed to phase planning and IRB submission.",
                "Conditional": (
                    "Run highest-info experiments to reduce uncertainty on "
                    f"{sensitivity['most_influential_factor']}."
                ),
                "No-Go": "Reconsider endpoint / population enrichment / dose.",
            }[verdict],
            "trace_summary": summary,
        }
