# app/agents/active_learning_agent.py
"""Active Learning Agent (PR #9 — Active Learning + Evidence Gap Analysis).

For each evidence gap or active hypothesis the agent enumerates a fixed
catalog of experiment templates and computes::

    information_gain = prior_entropy − E[posterior_entropy]

with per-template, per-outcome posterior beliefs.  Every emitted
experiment is anchored to a template id (no free-form / hallucinated
experiments).  The agent supports cost-weighted ranking via::

    value_per_unit_cost = information_gain / cost_estimate

and exposes both the unweighted and cost-weighted ranking so callers
can choose the appropriate priority order.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ..core.database import db
from .base_agent import BaseAgent


# ---------------------------------------------------------------------------
# Experiment template library (preclinical only — no clinical trials).
# ---------------------------------------------------------------------------
# Each template defines two hypothetical outcomes.  ``p_positive`` is the
# prior probability of the "positive" branch (defaults to current
# hypothesis confidence at evaluation time when omitted), and the
# ``posterior_*`` fields encode the *updated* belief assuming each
# branch.  Costs are unit-less 1–10 (smaller = cheaper).
EXPERIMENT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "lit_mining_v1",
        "experiment_type": "literature_mining",
        "label": "Targeted literature mining",
        "description_template": (
            "Mine PubMed/preprints for {entity} in the context of "
            "{disease}; extract supporting/contradicting claims."
        ),
        "cost_estimate": 1.0,
        "duration_days": 3,
        "posterior_if_positive": 0.75,
        "posterior_if_negative": 0.25,
    },
    {
        "id": "in_silico_pathway_sim_v1",
        "experiment_type": "in_silico_simulation",
        "label": "In-silico pathway simulation (EpistemicOS CXU)",
        "description_template": (
            "Run an EpistemicOS pathway-signaling CXU on {entity} to "
            "predict downstream effect in {disease}."
        ),
        "cost_estimate": 2.0,
        "duration_days": 5,
        "posterior_if_positive": 0.78,
        "posterior_if_negative": 0.30,
    },
    {
        "id": "crispr_ko_panel_v1",
        "experiment_type": "in_vitro_assay",
        "label": "CRISPR knockout assay (3-cell-line panel)",
        "description_template": (
            "CRISPR knockout of {entity} in 3 disease-relevant cell "
            "lines with proliferation + apoptosis readouts."
        ),
        "cost_estimate": 3.0,
        "duration_days": 14,
        "posterior_if_positive": 0.88,
        "posterior_if_negative": 0.12,
    },
    {
        "id": "dose_response_v1",
        "experiment_type": "in_vitro_assay",
        "label": "Dose-response IC50 curve",
        "description_template": (
            "Generate an 8-point dose-response curve for {entity} in "
            "the lead {disease} cell line."
        ),
        "cost_estimate": 2.5,
        "duration_days": 10,
        "posterior_if_positive": 0.82,
        "posterior_if_negative": 0.20,
    },
    {
        "id": "in_vivo_pdx_v1",
        "experiment_type": "in_vivo_model",
        "label": "PDX in-vivo efficacy study",
        "description_template": (
            "Run a patient-derived xenograft efficacy study for "
            "{entity} in a {disease} model."
        ),
        "cost_estimate": 8.0,
        "duration_days": 60,
        "posterior_if_positive": 0.92,
        "posterior_if_negative": 0.10,
    },
    {
        "id": "biomarker_strat_v1",
        "experiment_type": "biomarker_analysis",
        "label": "Biomarker stratification analysis",
        "description_template": (
            "Stratify existing {disease} datasets by a candidate "
            "biomarker linked to {entity} and re-evaluate response."
        ),
        "cost_estimate": 2.0,
        "duration_days": 7,
        "posterior_if_positive": 0.80,
        "posterior_if_negative": 0.25,
    },
    {
        "id": "omics_profiling_v1",
        "experiment_type": "omics_profiling",
        "label": "Bulk RNA-seq + proteomics profiling",
        "description_template": (
            "Profile {entity}-related expression and pathway activity "
            "across a {disease} sample cohort."
        ),
        "cost_estimate": 5.0,
        "duration_days": 21,
        "posterior_if_positive": 0.85,
        "posterior_if_negative": 0.20,
    },
]


def binary_entropy(p: Optional[float]) -> float:
    """Shannon entropy (bits) of a Bernoulli belief.

    Returns ``1.0`` when ``p`` is ``None`` (maximum uncertainty); clamps
    inputs to ``[0, 1]``; returns ``0.0`` at the boundaries.
    """
    if p is None:
        return 1.0
    p = max(0.0, min(1.0, float(p)))
    if p in (0.0, 1.0):
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def expected_posterior_entropy(
    p_positive: float,
    posterior_if_positive: float,
    posterior_if_negative: float,
) -> float:
    """Expected posterior entropy averaged over the two branches.

    ``p_positive`` is the prior probability of the "positive" branch;
    ``posterior_if_*`` are the updated beliefs in each branch.  All
    inputs are clamped to ``[0, 1]``.
    """
    p = max(0.0, min(1.0, float(p_positive)))
    return (
        p * binary_entropy(posterior_if_positive)
        + (1.0 - p) * binary_entropy(posterior_if_negative)
    )


def information_gain(
    prior: Optional[float],
    posterior_if_positive: float,
    posterior_if_negative: float,
    p_positive: Optional[float] = None,
) -> float:
    """Expected information gain (in bits) of running an experiment.

    ``information_gain = H(prior) − E[H(posterior)]``.  When
    ``p_positive`` is omitted it defaults to ``prior`` (the canonical
    Bayes-optimal proposal distribution under no other information).
    Always returns a non-negative value, clamped to ``[0, 1]``.
    """
    prior_p = 0.5 if prior is None else max(0.0, min(1.0, float(prior)))
    if p_positive is None:
        p_positive = prior_p
    prior_h = binary_entropy(prior_p)
    expected_h = expected_posterior_entropy(
        p_positive, posterior_if_positive, posterior_if_negative
    )
    gain = prior_h - expected_h
    # Numerical safety: never let small float artifacts push us negative.
    return max(0.0, min(1.0, gain))


class ActiveLearningAgent(BaseAgent):
    """Rank experiments by information gain (and information gain per cost)."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id,
            "Active Learning Agent",
            "active_learning",
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        program_id: Optional[str] = inputs.get("program_id")
        if not program_id:
            raise ValueError(
                "Active Learning Agent requires program_id input"
            )
        max_experiments: int = int(inputs.get("max_experiments") or 10)
        include_cost: bool = bool(inputs.get("include_cost", True))
        gaps: List[Dict[str, Any]] = list(inputs.get("gaps") or [])
        # Optionally restrict to a subset of templates (e.g. for cost
        # ceilings).  When empty, use the full library.
        allowed_types = set(inputs.get("allowed_experiment_types") or [])

        templates = EXPERIMENT_TEMPLATES
        if allowed_types:
            templates = [
                t for t in templates if t["experiment_type"] in allowed_types
            ]

        pool = await db.get_pool()
        async with pool.acquire() as conn:
            program = await conn.fetchrow(
                "SELECT id, therapeutic_area FROM programs WHERE id = $1",
                program_id,
            )
            if not program:
                raise ValueError(f"Program not found: {program_id}")
            disease_name = (
                inputs.get("disease_name") or program["therapeutic_area"]
            )

            hypotheses = await conn.fetch(
                """SELECT id, hypothesis_text, confidence
                       FROM hypotheses
                       WHERE program_id = $1
                         AND status NOT IN ('refuted', 'deprecated')
                       ORDER BY COALESCE(confidence, 0.5) ASC""",
                program_id,
            )

        # Build (entity_label, prior_confidence, hypothesis_id) "targets"
        # to evaluate experiments against.  Each gap with a linked
        # hypothesis produces one target; otherwise we fall back to
        # iterating over hypotheses.
        targets: List[Dict[str, Any]] = []
        for gap in gaps:
            targets.append(
                {
                    "label": gap.get("description") or "evidence gap",
                    "entity": gap.get("description")
                    or "graph entity"
                    if not gap.get("entity_id")
                    else gap.get("entity_id"),
                    "prior": _gap_prior_confidence(gap),
                    "hypothesis_id": gap.get("hypothesis_id"),
                    "gap_id": gap.get("id"),
                }
            )
        if not targets:
            for hyp in hypotheses:
                targets.append(
                    {
                        "label": hyp["hypothesis_text"][:100],
                        "entity": hyp["hypothesis_text"][:60],
                        "prior": hyp["confidence"],
                        "hypothesis_id": str(hyp["id"]),
                        "gap_id": None,
                    }
                )
        if not targets:
            return _empty_result(program_id, disease_name)

        proposed: List[Dict[str, Any]] = []
        for target in targets:
            prior = target["prior"]
            prior_h = binary_entropy(prior if prior is not None else 0.5)
            for tmpl in templates:
                gain = information_gain(
                    prior=prior,
                    posterior_if_positive=tmpl["posterior_if_positive"],
                    posterior_if_negative=tmpl["posterior_if_negative"],
                )
                cost = float(tmpl["cost_estimate"])
                value_per_cost = gain / cost if cost > 0 else gain
                expected_h = expected_posterior_entropy(
                    p_positive=prior if prior is not None else 0.5,
                    posterior_if_positive=tmpl["posterior_if_positive"],
                    posterior_if_negative=tmpl["posterior_if_negative"],
                )
                proposed.append(
                    {
                        "template_id": tmpl["id"],
                        "experiment_type": tmpl["experiment_type"],
                        "description": tmpl["description_template"].format(
                            entity=target["entity"],
                            disease=disease_name,
                        ),
                        "expected_outcomes": {
                            "if_positive": (
                                f"posterior confidence ≈ "
                                f"{tmpl['posterior_if_positive']:.2f}"
                            ),
                            "if_negative": (
                                f"posterior confidence ≈ "
                                f"{tmpl['posterior_if_negative']:.2f}"
                            ),
                        },
                        "prior_entropy": round(prior_h, 4),
                        "expected_posterior_entropy": round(expected_h, 4),
                        "information_gain": round(gain, 4),
                        "cost_estimate": cost,
                        "duration_days": int(tmpl["duration_days"]),
                        "value_per_unit_cost": round(value_per_cost, 4),
                        "hypothesis_id": target.get("hypothesis_id"),
                        "gap_id": target.get("gap_id"),
                        "target_label": target["label"],
                    }
                )

        # Cost-weighted vs raw ranking.
        sort_key = "value_per_unit_cost" if include_cost else "information_gain"
        proposed.sort(key=lambda e: e[sort_key], reverse=True)
        proposed = proposed[:max_experiments]
        for idx, exp in enumerate(proposed):
            exp["priority"] = min(10, idx + 1)

        if proposed:
            top = proposed[0]
            summary = (
                f"Proposed {len(proposed)} experiment(s); top: "
                f"{top['template_id']} (info gain={top['information_gain']:.2f}"
                + (
                    f", {top['value_per_unit_cost']:.2f}/cost-unit"
                    if include_cost
                    else ""
                )
                + ")."
            )
            recommended = (
                f"Run experiment '{top['description']}' first; expected "
                f"information gain {top['information_gain']:.2f} bits."
            )
            confidence = round(0.5 + 0.4 * top["information_gain"], 3)
        else:
            summary = (
                "No experiments could be ranked — template library or "
                "targets list was empty."
            )
            recommended = (
                "Run the Gap Analysis Agent first or expand the template "
                "library."
            )
            confidence = 0.3

        trace_summary = (
            f"Evaluated {len(templates)} templates × "
            f"{len(targets)} targets = "
            f"{len(templates) * len(targets)} candidate experiments; "
            f"returned top {len(proposed)}."
        )

        heuristic_result = {
            "summary": summary,
            "structure": {
                "program_id": program_id,
                "disease_name": disease_name,
                "experiments": proposed,
                "ranking_mode": (
                    "value_per_unit_cost" if include_cost else "information_gain"
                ),
                "templates_evaluated": len(templates),
                "targets_evaluated": len(targets),
            },
            "confidence": confidence,
            "uncertainty_reason": (
                None
                if proposed and proposed[0]["information_gain"] >= 0.2
                else "Low information gain across template library"
            ),
            "recommended_next_step": recommended,
            "trace_summary": trace_summary,
        }

        # Enhance with LLM if available
        from ..core.config import settings
        if not settings.OPENAI_API_KEY or not proposed:
            return heuristic_result

        top_experiments = [
            {
                "type": e["experiment_type"],
                "description": e["description"],
                "info_gain": e["information_gain"],
                "cost": e["cost_estimate"],
                "priority": e["priority"],
            }
            for e in proposed[:5]
        ]
        system_prompt = (
            "You are the Active Learning Agent for a drug discovery platform. "
            "Review information-gain-ranked experiments and provide expert prioritization guidance. "
            "Return a JSON object with exactly these keys: "
            "summary (string — expert 2-sentence narrative), confidence (float 0-1), "
            "uncertainty_reason (null or string), recommended_next_step (string), "
            "trace_summary (string), structure (object — pass through unchanged)."
        )
        user_prompt = (
            f"Disease: {disease_name}\n"
            f"Proposed experiments (ranked by information gain / cost):\n{top_experiments}\n"
            f"Ranking mode: {'value_per_unit_cost' if include_cost else 'information_gain'}\n"
            f"Total experiments ranked: {len(proposed)}\n\n"
            "Provide an expert narrative on experiment prioritization and rationale. "
            f"Return the structure field as: {heuristic_result['structure']!r}"
        )

        llm_result = await self._call_llm(system_prompt, user_prompt)
        if isinstance(llm_result, dict) and "summary" in llm_result:
            heuristic_result["summary"] = llm_result.get("summary", summary)
            heuristic_result["recommended_next_step"] = llm_result.get(
                "recommended_next_step", recommended
            )
            heuristic_result["trace_summary"] = llm_result.get("trace_summary", trace_summary)
            if llm_result.get("confidence") is not None:
                heuristic_result["confidence"] = llm_result["confidence"]
            heuristic_result["uncertainty_reason"] = llm_result.get(
                "uncertainty_reason", heuristic_result["uncertainty_reason"]
            )
        return heuristic_result


def _gap_prior_confidence(gap: Dict[str, Any]) -> float:
    """Derive a prior confidence for a gap.

    Low-confidence edges expose their confidence directly; missing edges
    and unresolved contradictions default to ``0.5`` (maximum
    ambiguity).
    """
    if "confidence" in gap and gap["confidence"] is not None:
        return float(gap["confidence"])
    gap_type = gap.get("gap_type")
    if gap_type == "missing_edge":
        return 0.5
    if gap_type == "contradiction_unresolved":
        return 0.5
    if gap_type == "low_confidence":
        # Use uncertainty proxy if we have it.
        uncertainty = gap.get("uncertainty")
        if uncertainty is not None:
            # Map uncertainty back to a confidence near 0.5
            return 0.5
    return 0.5


def _empty_result(program_id: str, disease_name: str) -> Dict[str, Any]:
    return {
        "summary": "No active hypotheses or gaps available; nothing to plan.",
        "structure": {
            "program_id": program_id,
            "disease_name": disease_name,
            "experiments": [],
            "ranking_mode": "value_per_unit_cost",
            "templates_evaluated": 0,
            "targets_evaluated": 0,
        },
        "confidence": 0.2,
        "uncertainty_reason": "No targets to plan against",
        "recommended_next_step": (
            "Create at least one hypothesis or run the Gap Analysis Agent."
        ),
        "trace_summary": "Active Learning Agent exited early — no targets.",
    }
