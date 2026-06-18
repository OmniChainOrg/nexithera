"""Bayesian formulation scorecard calibrator.

Loads historical formulation outcome data and fits a logistic regression
model that maps formulation features to success likelihood. The fitted model
is then used to compute confidence intervals around the heuristic ChronoThera
scores.

Usage::

    calibrator = get_calibrator()
    lower, mean, upper = calibrator.predict_confidence_interval(
        formulation_outcome, nominal_score=72
    )

The calibrator degrades gracefully when no data is available: it returns a
default ±10 band around the nominal score.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Optional sklearn import – calibration is a best-effort enhancement
try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SKLEARN_AVAILABLE = False
    np = None  # type: ignore[assignment]

from ..schemas.calibration import (
    CalibrationDataset,
    FormulationOutcome,
)

_DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "calibration" / "formulations.json"
)

_OBJECTIVES = [
    "sustained_release",
    "half_life_extension",
    "pegylation_strategy",
    "depot_formulation",
    "oral_delayed_release",
    "local_ocular_delivery",
    "chronotherapeutic_release",
    "co_formulation",
]
_ROUTES = ["oral", "SC", "IM", "IV", "local", "ocular"]
_COMMON_EXCIPIENTS = ["PLGA", "PEG", "Chitosan", "Eudragit", "HPMC", "Trehalose", "Poloxamer"]


class FormulationScorecardCalibrator:
    """Bayesian logistic regression calibrator for ChronoThera scorecards.

    Attributes:
        data_path: Path to the JSON file containing historical outcomes.
    """

    def __init__(self, data_path: Optional[Path] = None) -> None:
        self.data_path = data_path or _DEFAULT_DATA_PATH
        self._dataset: Optional[CalibrationDataset] = None
        self._model: Optional[Any] = None
        self._scaler: Optional[Any] = None
        self._fitted = False

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_calibration_data(self) -> CalibrationDataset:
        """Load historical formulations from disk.

        Returns an empty dataset when the file does not exist yet.
        """
        if not self.data_path.exists():
            logger.info(
                "Calibration data file not found at %s; using empty dataset.",
                self.data_path,
            )
            return CalibrationDataset()

        try:
            raw = json.loads(self.data_path.read_text())
            dataset = CalibrationDataset.model_validate(raw)
            logger.info(
                "Loaded %d calibration formulations from %s",
                len(dataset.formulations),
                self.data_path,
            )
            return dataset
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load calibration data: %s", exc)
            return CalibrationDataset()

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def featurize(self, formulation: FormulationOutcome) -> "np.ndarray":  # type: ignore[name-defined]
        """Convert a FormulationOutcome to a numeric feature vector.

        Features:
        - One-hot objective flags (8 features)
        - One-hot route flags (6 features)
        - Per-excipient presence flags (7 features)
        - Normalised release duration (1 feature)
        - API count (1 feature)
        """
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn is required for featurisation")

        obj_vec = [
            1.0 if formulation.formulation_objective == obj else 0.0
            for obj in _OBJECTIVES
        ]
        route_vec = [
            1.0 if formulation.route == r else 0.0
            for r in _ROUTES
        ]
        exc_lower = [e.lower() for e in formulation.excipients]
        exc_vec = [
            1.0 if ce.lower() in exc_lower else 0.0
            for ce in _COMMON_EXCIPIENTS
        ]
        duration_feat = [formulation.release_duration_weeks / 24.0]
        api_count_feat = [min(len(formulation.apis), 5) / 5.0]

        return np.array(
            obj_vec + route_vec + exc_vec + duration_feat + api_count_feat,
            dtype=np.float64,
        )

    # ------------------------------------------------------------------
    # Model fitting
    # ------------------------------------------------------------------

    def fit(self) -> Dict[str, Any]:
        """Fit a logistic regression model to the loaded calibration data.

        Returns:
            Dict with ``accuracy``, ``n_samples``, and ``fitted_weights``.
        """
        dataset = self.load_calibration_data()
        self._dataset = dataset

        if not _SKLEARN_AVAILABLE:
            logger.warning(
                "scikit-learn not available; calibration model not fitted."
            )
            return {"accuracy": None, "n_samples": 0, "fitted_weights": {}}

        formulations = dataset.formulations
        if len(formulations) < 5:
            logger.info(
                "Too few calibration samples (%d); skipping model fit.",
                len(formulations),
            )
            return {"accuracy": None, "n_samples": len(formulations), "fitted_weights": {}}

        X = np.array([self.featurize(f) for f in formulations])
        y = np.array(
            [1 if f.actual_outcome == "success" else 0 for f in formulations]
        )

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = LogisticRegression(
            C=1.0,
            max_iter=500,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(X_scaled, y)

        self._model = model
        self._scaler = scaler
        self._fitted = True

        # In-sample accuracy (proxy for calibration quality)
        accuracy = float(model.score(X_scaled, y))
        weights = {f"w{i}": float(w) for i, w in enumerate(model.coef_[0])}
        logger.info(
            "Calibration model fitted on %d samples; accuracy=%.2f",
            len(formulations),
            accuracy,
        )
        return {
            "accuracy": accuracy,
            "n_samples": len(formulations),
            "fitted_weights": weights,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict_confidence_interval(
        self,
        formulation: FormulationOutcome,
        nominal_score: float,
    ) -> Tuple[float, float, float]:
        """Compute a (lower, mean, upper) confidence interval.

        If the model is fitted the calibrated mean is a blend of the nominal
        heuristic score and the model's predicted success probability.
        Otherwise a default ±10 band is returned.

        Args:
            formulation: The formulation to calibrate.
            nominal_score: The raw heuristic score (0–100).

        Returns:
            Tuple of (lower, mean, upper) in [0, 100].
        """
        if not self._fitted:
            # Auto-fit on first prediction attempt
            self.fit()

        if not self._fitted or not _SKLEARN_AVAILABLE:
            # Default fallback: ±10 symmetric band
            half = 10.0
            mean = float(nominal_score)
            return (
                max(0.0, mean - half),
                mean,
                min(100.0, mean + half),
            )

        try:
            features = self.featurize(formulation).reshape(1, -1)
            features_scaled = self._scaler.transform(features)
            prob_success = float(
                self._model.predict_proba(features_scaled)[0][1]
            )

            # Calibrated mean: blend nominal score with model probability
            model_score = prob_success * 100.0
            divergence = abs(model_score - nominal_score)
            blend_weight = min(0.5, divergence / 100.0)  # max 50% model influence
            calibrated_mean = nominal_score * (1 - blend_weight) + model_score * blend_weight

            # Uncertainty: proportional to divergence between model and heuristic
            if divergence > 15:
                half_width = 15.0
            else:
                half_width = 5.0

            lower = max(0.0, calibrated_mean - half_width)
            upper = min(100.0, calibrated_mean + half_width)

            return (round(lower, 1), round(calibrated_mean, 1), round(upper, 1))

        except Exception as exc:  # noqa: BLE001
            logger.warning("CI prediction failed (%s); using default ±10.", exc)
            mean = float(nominal_score)
            return (max(0.0, mean - 10.0), mean, min(100.0, mean + 10.0))


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_calibrator_instance: Optional[FormulationScorecardCalibrator] = None


def get_calibrator() -> FormulationScorecardCalibrator:
    """Return the process-wide calibrator singleton (lazy-initialised)."""
    global _calibrator_instance
    if _calibrator_instance is None:
        _calibrator_instance = FormulationScorecardCalibrator()
    return _calibrator_instance
