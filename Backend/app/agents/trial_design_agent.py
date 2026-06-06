# app/agents/trial_design_agent.py
"""Trial Design Agent (PR #11 — Clinical Forecaster).

Scores a planned trial design (enrollment, duration, statistical power,
alpha, endpoint choice) on a 0..1 scale.  The score multiplicatively
combines a power factor, an enrollment-vs-phase factor, a duration
sanity factor and an endpoint-quality factor.

The intent is *not* to recompute a power calculation but to penalize
designs that are obviously underpowered, too short, or use weak
endpoints (e.g. retrospective biomarker change in Phase III).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base_agent import BaseAgent


_PHASE_MIN_ENROLL = {"I": 12, "II": 60, "III": 200}
_PHASE_TYPICAL_DURATION = {"I": 12, "II": 18, "III": 30}  # months

# Endpoint quality (0..1).  Hard endpoints (OS, MACE) > response > PFS >
# biomarker > QoL.
_ENDPOINT_QUALITY = {
    "overall survival": 1.00,
    "os": 1.00,
    "mace": 1.00,
    "overall response rate": 0.85,
    "orr": 0.85,
    "complete response": 0.85,
    "progression-free survival": 0.75,
    "pfs": 0.75,
    "disease-free survival": 0.75,
    "dfs": 0.75,
    "objective response": 0.80,
    "hba1c reduction": 0.70,
    "ldl reduction": 0.70,
    "biomarker": 0.55,
    "quality of life": 0.50,
    "qol": 0.50,
    "pharmacokinetics": 0.60,
    "pk": 0.60,
    "safety": 0.65,
}


def _endpoint_quality(name: Optional[str]) -> float:
    if not name:
        return 0.65
    key = name.strip().lower()
    if key in _ENDPOINT_QUALITY:
        return _ENDPOINT_QUALITY[key]
    for token, q in _ENDPOINT_QUALITY.items():
        if token in key:
            return q
    return 0.65


def _power_factor(power: Optional[float], alpha: Optional[float]) -> float:
    p = 0.8 if power is None else float(power)
    a = 0.05 if alpha is None else float(alpha)
    # Reward power >= 0.8; penalize lower; penalize alpha > 0.05.
    pf = max(0.4, min(1.0, p))
    af = max(0.6, min(1.0, 1.0 - (a - 0.05) * 4)) if a > 0.05 else 1.0
    return round(pf * af, 4)


def _enrollment_factor(phase: str, enrollment: Optional[int]) -> float:
    if enrollment is None:
        return 0.7
    minimum = _PHASE_MIN_ENROLL.get(phase, 60)
    ratio = float(enrollment) / float(minimum)
    return round(max(0.4, min(1.0, 0.5 + 0.5 * min(1.0, ratio))), 4)


def _duration_factor(phase: str, months: Optional[int]) -> float:
    if months is None:
        return 0.8
    typical = _PHASE_TYPICAL_DURATION.get(phase, 18)
    ratio = float(months) / float(typical)
    if ratio < 0.4:
        return 0.5
    if ratio > 2.5:
        return 0.7
    return round(min(1.0, 0.7 + 0.3 * min(1.0, ratio)), 4)


def design_score(
    phase: str,
    *,
    enrollment: Optional[int] = None,
    duration_months: Optional[int] = None,
    statistical_power: Optional[float] = None,
    alpha: Optional[float] = None,
    primary_endpoint: Optional[str] = None,
) -> Dict[str, float]:
    pf = _power_factor(statistical_power, alpha)
    ef = _enrollment_factor(phase, enrollment)
    df = _duration_factor(phase, duration_months)
    eq = _endpoint_quality(primary_endpoint)
    total = round(pf * ef * df * eq, 4)
    return {
        "design_score": max(0.0, min(1.0, total)),
        "power_factor": pf,
        "enrollment_factor": ef,
        "duration_factor": df,
        "endpoint_quality": eq,
    }


class TrialDesignAgent(BaseAgent):
    """Score quality of a planned trial design."""

    def __init__(self, agent_id: str):
        super().__init__(
            agent_id, "Trial Design Agent", "clinical_trial_design"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id: Optional[str] = inputs.get("candidate_id")
        if not candidate_id:
            raise ValueError(
                "Trial Design Agent requires candidate_id input"
            )
        phase = str(inputs.get("phase") or "II").upper()
        design = inputs.get("trial_design") or {}

        parts = design_score(
            phase,
            enrollment=design.get("enrollment"),
            duration_months=design.get("duration_months"),
            statistical_power=design.get("statistical_power"),
            alpha=design.get("alpha"),
            primary_endpoint=inputs.get("primary_endpoint"),
        )
        score = parts["design_score"]

        risks = []
        if parts["power_factor"] < 0.8:
            risks.append("Statistical power below 0.8 — under-powered.")
        if parts["enrollment_factor"] < 0.7:
            risks.append("Enrollment below phase-appropriate minimum.")
        if parts["duration_factor"] < 0.7:
            risks.append("Trial duration too short or excessively long.")
        if parts["endpoint_quality"] < 0.7:
            risks.append("Primary endpoint is weaker than typical for phase.")

        summary = (
            f"Phase {phase} design_score={score} "
            f"(power={parts['power_factor']}, "
            f"enrollment={parts['enrollment_factor']}, "
            f"duration={parts['duration_factor']}, "
            f"endpoint={parts['endpoint_quality']})."
        )
        return {
            "summary": summary,
            "structure": {
                "candidate_id": candidate_id,
                "phase": phase,
                **parts,
                "risks": risks,
                "trial_design": design,
                "primary_endpoint": inputs.get("primary_endpoint"),
            },
            "confidence": round(0.55 + 0.05 * (1 if not risks else 0), 3),
            "uncertainty_reason": (
                None if not risks else "; ".join(risks)
            ),
            "recommended_next_step": (
                "Strengthen design (increase power / enrollment / harden "
                "endpoint) before submitting protocol."
                if risks
                else "Design is adequate to proceed to protocol finalization."
            ),
            "trace_summary": summary,
        }
