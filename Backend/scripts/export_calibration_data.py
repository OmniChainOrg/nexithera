#!/usr/bin/env python
"""Export ChronoThera simulation history to calibration dataset format.

Reads all saved simulations from ``data/chronothera/simulations.json`` and
writes them as ``FormulationOutcome`` records to
``data/calibration/formulations.json``.

The exported records are in the schema expected by
``FormulationScorecardCalibrator``.  After export, manually tag each record
with a real ``actual_outcome`` value (``"success"`` | ``"partial_success"`` |
``"failure"``) before running ``calibrator.fit()``.

Usage::

    python Backend/scripts/export_calibration_data.py

Output::

    Exported 42 formulations to data/calibration/formulations.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make sure the Backend package is importable
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from app.schemas.calibration import CalibrationDataset, FormulationOutcome  # noqa: E402

_SIMULATIONS_PATH = _BACKEND_ROOT.parent / "data" / "chronothera" / "simulations.json"
_CALIBRATION_PATH = _BACKEND_ROOT.parent / "data" / "calibration" / "formulations.json"


def main() -> None:
    if not _SIMULATIONS_PATH.exists():
        print(f"No simulation data found at {_SIMULATIONS_PATH}")
        sys.exit(0)

    raw = json.loads(_SIMULATIONS_PATH.read_text())
    simulations = raw.get("simulations", [])

    outcomes: list[FormulationOutcome] = []
    for sim in simulations:
        sim_id = sim.get("id", "unknown")
        inp = sim.get("input", {})
        overall = sim.get("overall_chronothera_score", 50)
        guardian = sim.get("guardian_review", {})
        guardian_status = guardian.get("status", "pending")

        # Map guardian decision to a provisional outcome label
        if guardian_status == "approved":
            provisional_outcome = "success"
        elif guardian_status in ("needs-revision",):
            provisional_outcome = "partial_success"
        elif guardian_status == "rejected":
            provisional_outcome = "failure"
        else:
            # Not yet reviewed – use score as proxy
            provisional_outcome = (
                "success" if overall >= 70 else
                "partial_success" if overall >= 55 else
                "failure"
            )

        outcomes.append(
            FormulationOutcome(
                id=sim_id,
                asset_id=sim.get("asset_id"),
                formulation_objective=inp.get("formulation_objective", "unknown"),
                route=inp.get("route_of_administration", "unknown"),
                release_duration_weeks=inp.get("release_duration_weeks", 0),
                apis=[a.get("name", "") for a in inp.get("apis", [])],
                excipients=[e.get("name", "") for e in inp.get("excipients", [])],
                predicted_score=float(overall),
                actual_outcome=provisional_outcome,
                notes=(
                    "Auto-exported from simulation history. "
                    "Please verify actual_outcome before using for calibration."
                ),
            )
        )

    dataset = CalibrationDataset(
        formulations=outcomes,
        sample_count=len(outcomes),
    )

    _CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CALIBRATION_PATH.write_text(dataset.model_dump_json(indent=2))
    print(f"Exported {len(outcomes)} formulations to {_CALIBRATION_PATH}")


if __name__ == "__main__":
    main()
