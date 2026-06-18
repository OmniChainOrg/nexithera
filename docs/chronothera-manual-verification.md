# ChronoThera Manual Verification Checklist

ChronoThera is now an internal NexiThera platform module in the React dashboard, not a public static page.

1. Start the backend API and the Genovate UI.
2. Open `http://localhost:3000/platform/chronothera` from an internal dashboard session.
3. Confirm the page displays the internal-use banner and compact scientific cockpit layout.
4. Confirm the public homepage does not include a ChronoThera navigation item or public “Open ChronoThera” CTA.
5. Confirm the route has `noindex` metadata through the Next.js page metadata.
6. Exercise the ChronoThera API calls:
   - `GET /api/v1/chronothera/catalog`
   - `POST /api/v1/chronothera/simulations`
   - `GET /api/v1/chronothera/simulations`
   - `GET /api/v1/chronothera/simulations/{simulation_id}`
   - `GET /api/v1/chronothera/simulations?asset_id={asset_id}`
   - `POST /api/v1/chronothera/simulations/{simulation_id}/guardian-review`
7. Run a simulation and verify the release profile, readiness scorecard, EpistemicOS trace, Guardian review, history list, and JSON export.

## Manual visual QA checklist

- Asset context is visible above the fold.
- Formulation strategy inputs are grouped by workflow stage rather than presented as a marketing hero.
- Release/exposure chart is labeled as a decision-support output.
- Scorecard includes rationale, assumptions, uncertainty, and next-best action.
- EpistemicOS trace shows zones, CXUs, swarm consensus, engine version, and provenance hashes.
- Guardian panel clearly communicates required/not-required state and trigger reasons.
- JSON export is positioned as a dossier artifact, not a public simulator download.

---

## EpistemicOS Integration Verification (v0.3+)

### EpistemicOS Connectivity Test

1. With EpistemicOS running at `EPISTEMICOS_API_URL`:
   - Open DevTools → Network tab, filter by `/v1/zones`.
   - Run a ChronoThera simulation.
   - Confirm a `GET /v1/zones/ChronoThera-Formulation-Cluster` request is made.
   - Verify JSON response field `epistemicos_query_status` equals `"success"`.
   - Verify `epistemic_trace.provenance.epistemicos_status` equals `"success"`.

2. With EpistemicOS stopped:
   - Run a simulation.
   - Confirm `epistemicos_query_status` equals `"fallback"`.
   - Confirm the simulation still completes (no 500 error).
   - Confirm 7 synthetic CXUs are present in `epistemic_trace.cxus`.

### PK Precedent Lookup Verification

- With EpistemicOS running and a precedent record seeded for the API under test:
  - Check that `release_profile.datasets[0].pk_precedent_used` is `true`.
  - Compare release curve shape against the no-precedent baseline — it should differ for depot/half-life objectives.
- With no matching precedents:
  - Confirm `pk_precedent_used` is `false`.
  - Confirm simulation still completes with heuristic defaults.

### Confidence Interval Validation

- In the simulation JSON export, verify every scorecard dimension includes:
  ```json
  "confidence": {
    "lower": <float>,
    "mean": <float>,
    "upper": <float>
  }
  ```
- Verify `lower ≤ mean ≤ upper` for all entries.
- Verify `overall_confidence` is present at the result root level.

### Risk-Stratified Guardian Triggers

- Run a simulation for a **Category A** asset (e.g. `peg-insulin-glargine-citrate`) with overall score 68:
  - Confirm `guardian_review.required` is `true`.
  - Confirm `guardian_review.risk_tier` equals `"category_a"`.
- Run the same simulation parameters with a **Category C** asset:
  - Confirm `guardian_review.required` is `false` (score 68 > Cat C threshold 50).
  - Confirm `guardian_review.risk_tier` equals `"category_c"`.
- Run for a **Rapid Response** asset:
  - Confirm `guardian_review.required` is `true` (always escalates).
  - Confirm `"Rapid Response Program"` appears in `guardian_review.reasons`.

### Graceful Degradation Testing

- Stop the EpistemicOS service while the backend is running.
- Submit a simulation request.
- Verify the API returns HTTP 200 (not 500).
- Verify `epistemicos_query_status` is `"fallback"`.
- Restart EpistemicOS.
- Submit a new simulation.
- Verify `epistemicos_query_status` reverts to `"success"`.

### API Contract Tests

Verify these fields exist in the `POST /api/v1/chronothera/simulations` JSON response:

| Field | Expected |
|---|---|
| `epistemicos_query_status` | `"success"` \| `"fallback"` \| `"unavailable"` |
| `overall_confidence.lower` | float 0–100 |
| `overall_confidence.mean` | float 0–100 |
| `overall_confidence.upper` | float 0–100 |
| `guardian_review.risk_tier` | `"category_a"` \| `"category_b"` \| `"category_c"` \| `"rapid_response"` |
| `release_profile.datasets[*].pk_precedent_used` | boolean |
| `scorecard[*].confidence` | `{lower, mean, upper}` |
| `epistemic_trace.provenance.epistemicos_status` | string |

### JSON Export Structure Verification

- Download the simulation JSON dossier.
- Confirm `provenance.model_engine_version` equals `"chronothera-platform-engine-v0.3"`.
- Confirm `provenance.epistemicos_status` is present.

### Performance Benchmarks

| Scenario | Target |
|---|---|
| Simulation with EpistemicOS live | < 2 s end-to-end |
| Simulation in fallback mode | < 1 s end-to-end |
| Simulation no EpistemicOS configured | < 0.5 s end-to-end |

Measure with: `time curl -X POST .../simulations -d @payload.json`

