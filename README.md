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


## Custom domain + SSL troubleshooting (Render)
If you see `ERR_SSL_VERSION_OR_CIPHER_MISMATCH` for `https://www.nexithera.com`, this is not an app-code issue. It usually means DNS and certificate provisioning are not fully aligned yet.

1. In Render service settings, add both domains:
   - `nexithera.com`
   - `www.nexithera.com`
2. In DNS, point records exactly as Render instructs (typically `CNAME` for `www`, and `ALIAS/ANAME/A` for apex).
3. Wait for TLS certificate status to become **Issued** in Render before testing HTTPS.
4. Keep Cloudflare/registrar SSL mode on **Full** (or equivalent) and avoid proxy/edge SSL modes that can conflict during issuance.
5. After issuance, verify:
   - `https://nexithera.com`
   - `https://www.nexithera.com`

You can confirm certificate visibility with:
- `openssl s_client -connect www.nexithera.com:443 -servername www.nexithera.com`
