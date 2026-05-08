# NexiThera

Autonomous Cognition for Next‑Generation Therapies.

## Project
This repository contains the initial public one-page website for **NexiThera.com**, built with vanilla HTML, CSS, and JavaScript.

## Local development
1. Open `index.html` directly in your browser, or
2. Run a lightweight static server (optional), for example:
   - `python -m http.server 8000`
   - Visit `http://localhost:8000`

## Deploy on Render
This repo includes a `render.yaml` Blueprint for a Node.js Web Service on Render.

### Steps
1. Push this repository to GitHub.
2. In Render, choose **New +** → **Blueprint**.
3. Connect your repository.
4. Render will detect `render.yaml` and provision the static service automatically.

Render runs `npm start`, which launches `server.js`. The server delivers static assets and falls back to `index.html` for route-safe navigation.
