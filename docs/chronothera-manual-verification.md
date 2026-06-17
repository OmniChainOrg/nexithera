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
