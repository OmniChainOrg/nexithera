# ChronoThera Manual Verification Checklist

Use this checklist when reviewing the ChronoThera platform module locally.

## Static app smoke test

1. Run `npm start` from the repository root.
2. Open `http://localhost:3000/chronothera.html`.
3. Confirm the page uses the NexiThera dark visual system and displays the ChronoThera™ headline:
   "ChronoThera™ optimizes how therapeutic candidates become viable medicines."
4. Select an asset preset, formulation goal, APIs, excipients, release duration, regulatory body, route, and optimization toggle.
5. Run a simulation and confirm the release profile chart, scorecard, EpistemicOS trace, CXU list, swarm panel, Guardian review panel, simulation history, and JSON export are visible.

## FastAPI platform API smoke test

1. From the repository root, run `cd Backend && uvicorn app.main:app --reload`.
2. Open `http://localhost:8000/docs`.
3. Exercise:
   - `GET /api/v1/chronothera/catalog`
   - `POST /api/v1/chronothera/simulations`
   - `GET /api/v1/chronothera/simulations`
   - `GET /api/v1/chronothera/simulations/{simulation_id}`
   - `GET /api/v1/chronothera/assets/{asset_id}/formulation-profile`
   - `POST /api/v1/chronothera/simulations/{simulation_id}/guardian-review`
4. Confirm each result contains score rationales, assumptions, uncertainty, recommendations, next-best steps, EpistemicOS zones, CXUs, swarm consensus, provenance hashes, and Guardian review state.

## Local screenshot capture

If a headless browser is available locally, capture screenshots with one of these commands:

```bash
chromium --headless --disable-gpu --window-size=1440,1200 --screenshot=chronothera.png http://localhost:3000/chronothera.html
```

or:

```bash
google-chrome --headless --disable-gpu --window-size=1440,1200 --screenshot=chronothera.png http://localhost:3000/chronothera.html
```

This environment did not provide `chromium`, `chromium-browser`, `google-chrome`, or `playwright`, so automated screenshot capture could not be completed here.
