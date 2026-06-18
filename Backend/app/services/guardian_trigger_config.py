"""Risk-stratified Guardian trigger thresholds for ChronoThera.

Asset categories carry different risk profiles and therefore require
different Guardian escalation thresholds. This module provides:

- ``GuardianTriggerThresholds`` – per-category configuration dataclass
- ``GUARDIAN_TRIGGER_CONFIG`` – registry mapping category key → thresholds
- ``get_trigger_reasons()`` – compute escalation reasons for a simulation
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class GuardianTriggerThresholds:
    """Minimum/maximum score thresholds that trigger Guardian escalation."""

    overall_score_threshold: int
    """Guardian is triggered when overall score is *below* this value."""

    duration_weeks_max: int
    """Guardian is triggered when release duration *exceeds* this value."""

    manufacturability_min: int
    """Guardian is triggered when manufacturability score is *below* this."""

    regulatory_fit_min: int
    """Guardian is triggered when regulatory fit score is *below* this."""

    stability_min: int
    """Guardian is triggered when stability score is *below* this."""

    auto_escalate: bool = False
    """When *True* the category always triggers Guardian regardless of scores."""


# ---------------------------------------------------------------------------
# Per-category configuration
# ---------------------------------------------------------------------------

GUARDIAN_TRIGGER_CONFIG: Dict[str, GuardianTriggerThresholds] = {
    # Near-term revenue assets – tighter tolerances, faster timelines
    "category_a": GuardianTriggerThresholds(
        overall_score_threshold=70,
        duration_weeks_max=16,
        manufacturability_min=65,
        regulatory_fit_min=65,
        stability_min=65,
    ),
    # Differentiated assets – moderate tolerances
    "category_b": GuardianTriggerThresholds(
        overall_score_threshold=60,
        duration_weeks_max=20,
        manufacturability_min=55,
        regulatory_fit_min=55,
        stability_min=55,
    ),
    # Novel discovery programs – wider tolerances / exploratory
    "category_c": GuardianTriggerThresholds(
        overall_score_threshold=50,
        duration_weeks_max=24,
        manufacturability_min=45,
        regulatory_fit_min=45,
        stability_min=45,
    ),
    # Rapid response – always escalate; tightest duration window
    "rapid_response": GuardianTriggerThresholds(
        overall_score_threshold=40,
        duration_weeks_max=12,
        manufacturability_min=50,
        regulatory_fit_min=50,
        stability_min=50,
        auto_escalate=True,
    ),
}

_CATEGORY_KEY_MAP: Dict[str, str] = {
    "category a": "category_a",
    "near-term revenue": "category_a",
    "category b": "category_b",
    "differentiated": "category_b",
    "category c": "category_c",
    "novel discovery": "category_c",
    "rapid response": "rapid_response",
    "forge rapid response": "rapid_response",
}


def _resolve_category_key(category: str) -> str:
    """Map a free-form asset category string to a canonical config key."""
    lower = category.lower()
    for fragment, key in _CATEGORY_KEY_MAP.items():
        if fragment in lower:
            return key
    return "category_b"  # default to moderate tolerances


def get_trigger_reasons(
    category: str,
    overall_score: int,
    release_duration_weeks: int,
    scorecard: Dict[str, Any],
    *,
    is_rapid_response: bool = False,
) -> List[str]:
    """Return a list of escalation reasons for the given simulation context.

    An empty list means no Guardian escalation is required.

    Args:
        category: Asset category string (e.g. ``"Category A — Near-Term…"``).
        overall_score: Computed overall ChronoThera readiness score (0–100).
        release_duration_weeks: Planned release duration.
        scorecard: Dict mapping scorecard key → object with a ``score`` attr
            or plain ``int`` value.
        is_rapid_response: Explicit rapid-response flag (overrides category
            detection).

    Returns:
        List of human-readable escalation reason strings.
    """
    key = "rapid_response" if is_rapid_response else _resolve_category_key(category)
    cfg = GUARDIAN_TRIGGER_CONFIG[key]
    reasons: List[str] = []

    if cfg.auto_escalate:
        reasons.append("Rapid Response Program")

    if overall_score < cfg.overall_score_threshold:
        reasons.append(
            f"Overall ChronoThera score {overall_score} below threshold "
            f"{cfg.overall_score_threshold} for {key.replace('_', ' ').title()}"
        )

    if release_duration_weeks > cfg.duration_weeks_max:
        reasons.append(
            f"Release duration {release_duration_weeks}w exceeds maximum "
            f"{cfg.duration_weeks_max}w for {key.replace('_', ' ').title()}"
        )

    def _score(key_name: str) -> int:
        val = scorecard.get(key_name)
        if val is None:
            return 100  # no data → don't trigger
        if hasattr(val, "score"):
            return int(val.score)
        return int(val)

    mfg = _score("manufacturability")
    if mfg < cfg.manufacturability_min:
        reasons.append(
            f"Manufacturability score {mfg} below minimum "
            f"{cfg.manufacturability_min} for {key.replace('_', ' ').title()}"
        )

    reg = _score("regulatory_fit")
    if reg < cfg.regulatory_fit_min:
        reasons.append(
            f"Regulatory fit score {reg} below minimum "
            f"{cfg.regulatory_fit_min} for {key.replace('_', ' ').title()}"
        )

    stab = _score("stability")
    if stab < cfg.stability_min:
        reasons.append(
            f"Stability score {stab} below minimum "
            f"{cfg.stability_min} for {key.replace('_', ' ').title()}"
        )

    return reasons
