# ChronoThera ↔ EpistemicOS Integration: Architecture & Design

## Overview

This document describes the live integration between **ChronoThera** (NexiThera's formulation and delivery intelligence layer) and **EpistemicOS** (the epistemic kernel). The integration was introduced as part of the Priority 1–3 corrective actions following the ChronoThera assessment (PR #30).

The goal is to move ChronoThera from a self-contained deterministic engine to a bidirectionally-connected system that queries live EpistemicOS data, uses PK-informed release curves, calibrates scorecard weights against historical outcomes, and adapts Guardian triggers per asset risk tier.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  ChronoThera Service                    │
│  ┌──────────────────┐  ┌──────────────────────────┐    │
│  │ Release Profile  │  │       Scorecard           │    │
│  │  (PK-informed)   │  │  (Bayesian CI calibrated) │    │
│  └────────┬─────────┘  └────────────┬─────────────┘    │
│           │                         │                   │
│  ┌────────▼──────────────────────────▼──────────────┐  │
│  │           run_simulation() orchestrator           │  │
│  └────────┬──────────────────────────┬──────────────┘  │
│           │                          │                  │
│  ┌────────▼────────┐  ┌──────────────▼──────────────┐  │
│  │  Epistemic Trace │  │  Guardian Review (risk-tier) │  │
│  │  (live or synth) │  │  Category A / B / C / Rapid  │  │
│  └────────┬────────┘  └──────────────────────────────┘  │
│           │                                              │
│  ┌────────▼────────┐                                    │
│  │  Feedback Loop   │                                    │
│  │ (post to EOS)    │                                    │
│  └─────────────────┘                                    │
└─────────────────────────────────────────────────────────┘
           │              ▲
    write  │              │ read
           ▼              │
┌──────────────────────────────────────┐
│           EpistemicOS                │
│  /v1/zones/{id}  – CXU/swarm data   │
│  /v1/precedents/search – PK lookup  │
│  /v1/formulation-results – feedback │
└──────────────────────────────────────┘
```

---

## Data Flows

### Read Path (simulation inputs)

1. `ChronoTheraService.run_simulation()` calls `_build_epistemic_trace()`
2. `_build_epistemic_trace()` calls `EpistemicOSClient.get_zone("ChronoThera-Formulation-Cluster")`
3. On success: live CXU/swarm data is embedded in the epistemic trace.
4. On `EpistemicOSClientError`: synthetic CXU/swarm data generated deterministically.

### PK Lookup Path

1. `_generate_release_profile()` iterates over APIs in the request.
2. For each API: `PKPrecedentAdapter.lookup_pk_parameters()` queries `EpistemicOSClient.search_precedent()`.
3. Top-3 precedents are averaged to derive PK parameters.
4. `_release_curve_with_pk()` modulates the base release curve using `CL` and `Tmax`.
5. On failure/no results: `_heuristic_pk_parameters()` provides deterministic defaults.

### Write / Feedback Path

1. After `save_simulation()`, `_post_to_epistemicos()` posts the result back.
2. Payload includes: simulation ID, asset ID, overall score, scorecard summary.
3. Errors in this step are logged but **never propagate** to the caller (fire-and-forget).

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `EPISTEMICOS_API_URL` | `http://localhost:8000` | EpistemicOS base URL |
| `EPISTEMICOS_API_KEY` | _(empty)_ | Optional bearer token |

### Feature Flags

The EpistemicOS client is initialized in `main.py` during FastAPI startup. A health check is performed; if EpistemicOS is unreachable, the service starts without the live client and uses synthetic/heuristic fallbacks throughout.

---

## Risk-Stratified Guardian Triggers

Guardian escalation thresholds vary by asset category:

| Category | Overall Score Min | Duration Max (w) | Mfg Min | Reg Min | Stab Min | Auto-escalate |
|---|---|---|---|---|---|---|
| Category A | 70 | 16 | 65 | 65 | 65 | No |
| Category B | 60 | 20 | 55 | 55 | 55 | No |
| Category C | 50 | 24 | 45 | 45 | 45 | No |
| Rapid Response | 40 | 12 | 50 | 50 | 50 | **Yes** |

Configuration is defined in `Backend/app/services/guardian_trigger_config.py`.

---

## Calibration Workflow

1. **Export**: Run `python Backend/scripts/export_calibration_data.py` to export simulation history.
2. **Label**: Open `data/calibration/formulations.json` and tag each record with a real `actual_outcome` value (`"success"` | `"partial_success"` | `"failure"`).
3. **Fit**: The `FormulationScorecardCalibrator` auto-fits on the next simulation request (lazy initialisation), or call `calibrator.fit()` directly.
4. **Predict**: All scorecard dimensions and the overall score now carry a `ConfidenceInterval` (lower / mean / upper).

The model uses logistic regression (scikit-learn) with Bayesian-inspired balanced class weights. With fewer than 5 labelled samples, the calibrator degrades gracefully to a default ±10 band.

---

## Error Handling & Fallbacks

| Failure Scenario | Behaviour | Status Field |
|---|---|---|
| EpistemicOS unreachable at startup | Service starts in synthetic mode | N/A (startup warning) |
| `get_zone()` timeout/error | Synthetic CXUs generated | `epistemicos_query_status: "fallback"` |
| `search_precedent()` error | Heuristic PK parameters used | `pk_precedent_used: false` |
| `post_formulation_result()` error | Logged, simulation still returns | `epistemicos_query_status` unchanged |
| Calibration data missing | Default ±10 CI band used | N/A |

---

## Testing Strategy

1. **Unit Tests** – `test_chronothera_epistemicos_integration.py`: 17 test cases covering all components in isolation with mocked dependencies.
2. **Existing Tests** – `test_chronothera_service.py`: 9 tests confirm backward compatibility (no breaking changes).
3. **Manual QA** – See `docs/chronothera-manual-verification.md` for live scenario checklists.
4. **Performance** – Target: < 2s with EpistemicOS live, < 1s in fallback mode.

---

## Observability & Metrics

- All epistemicos interactions log at INFO (success) or WARNING (fallback).
- `result.epistemicos_query_status` field: `"success"` | `"fallback"` | `"unavailable"`.
- `result.epistemic_trace.provenance.epistemicos_status` mirrors the field above.
- `result.overall_confidence` contains (lower, mean, upper) for the overall ChronoThera score.
- Each scorecard dimension in `result.scorecard[key].confidence` carries a per-dimension CI.

---

## Future Enhancement Roadmap

- [ ] Persistent confidence interval tracking across simulation history.
- [ ] Active learning: surface low-confidence simulations for manual outcome labelling.
- [ ] EpistemicOS zone subscription: push updates when zone data changes.
- [ ] Multi-zone PK coupling: cross-zone simulation for PK/PD ↔ formulation interactions.
- [ ] Calibration decay: reduce confidence when model is stale (> 30 days without new labels).
