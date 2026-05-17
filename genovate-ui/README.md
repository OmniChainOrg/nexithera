# Genovate UI

Visualization dashboard for the **Genovate** scientific cognition engine — a Next.js 14 (App Router) TypeScript app that consumes the FastAPI backend in [`../Backend`](../Backend) and gives the NexiThera R&D team real-time visibility into programs, evidence graphs, hypotheses, candidates, agent runs, Guardian reviews, and CXU/swarm simulations.

This package is the **Dashboard PR #1 — UI Foundation**.

## Tech stack

| Category | Choice |
| --- | --- |
| Framework | Next.js 15 (App Router) — `15.5.18` |
| Language | TypeScript (strict mode) |
| Styling | Tailwind CSS + shadcn/ui-style primitives |
| Server state | TanStack Query v5 |
| Client state | Zustand |
| Forms | react-hook-form + zod |
| Graphs | React Flow (primary) + vis-network (fallback) |
| Charts | Recharts |
| Tables | TanStack Table v8 |
| Dates | date-fns |
| Tests | Vitest + React Testing Library |
| Lint/format | ESLint + Prettier |

## Getting started

```bash
cd genovate-ui
cp .env.example .env.local              # then edit NEXT_PUBLIC_API_URL if needed
npm install
npm run dev                             # http://localhost:3000
```

The dashboard expects the Genovate FastAPI backend to be reachable at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api/v1`). Start it with:

```bash
cd ../Backend
uvicorn app.main:app --reload
```

### Scripts

| Script | Purpose |
| --- | --- |
| `npm run dev` | Start the Next.js dev server on port 3000 |
| `npm run build` | Production build |
| `npm start` | Run the production build |
| `npm run lint` | ESLint (`next lint`) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest unit tests |
| `npm run format` | Prettier write |

## Project layout

```
genovate-ui/
├── app/
│   ├── (dashboard)/              # Authenticated dashboard route group
│   │   ├── layout.tsx            # Sidebar + header shell
│   │   ├── page.tsx              # Overview dashboard
│   │   ├── programs/             # Program list + per-program tabs
│   │   ├── evidence-graph/       # Global evidence graph explorer
│   │   ├── agent-runs/           # All agent runs history
│   │   └── settings/
│   ├── layout.tsx                # Root layout (QueryClient, fonts, dark mode root)
│   ├── providers.tsx             # TanStack Query provider
│   └── globals.css               # Tailwind + design tokens
├── components/                   # Reusable UI by domain (ui/, layout/, programs/, …)
├── lib/
│   ├── api/                      # Typed API client + per-resource modules
│   ├── hooks/                    # TanStack Query hooks + key factory
│   ├── stores/                   # Zustand stores (program / filter / ui)
│   ├── types/                    # Domain TypeScript types (matches FastAPI schemas)
│   └── utils/                    # Formatters, color tokens, confidence helpers
└── tests/                        # Vitest unit tests
```

## Pages & data sources

| Route | Description | Primary endpoints |
| --- | --- | --- |
| `/` | Overview: stats, candidate pipeline counts, recent runs, pending reviews | `GET /programs`, `GET /candidates/program/{id}`, `GET /agents/runs?limit=5`, `GET /guardian/reviews?status=pending`, `GET /simulations/runs?status=running` |
| `/programs` | All programs grid | `GET /programs` |
| `/programs/[id]/overview` | Program summary | `GET /candidates`, `GET /agents/runs`, `GET /guardian/reviews`, `GET /simulations/runs` |
| `/programs/[id]/evidence` | Interactive evidence graph (React Flow) with entity detail panel | `GET /evidence/program/{id}/graph` |
| `/programs/[id]/hypotheses` | Hypothesis workspace + create form | `GET /hypotheses/program/{id}`, `POST /hypotheses` |
| `/programs/[id]/candidates` | Kanban pipeline (drag-and-drop) + scorecard radar | `GET /candidates/program/{id}`, `PATCH /candidates/{id}/status` |
| `/programs/[id]/agents` | Run agents + history table | `GET /agents/runs`, `POST /agents/runs` |
| `/programs/[id]/guardian` | Guardian review queue + decision modal | `GET /guardian/reviews`, `POST /guardian/reviews/{id}/decision` |
| `/programs/[id]/simulations` | CXUs, zones, swarm consensus, cross-zone runs | `GET /simulations/program/{id}/cxus`, `GET /simulations/runs`, … |
| `/evidence-graph` | Global graph explorer (uses currently selected program) | as above |
| `/agent-runs` | All agent runs across programs | `GET /agents/runs` |
| `/settings` | Environment + theme | — |

## Design tokens

The color system lives in [`tailwind.config.js`](./tailwind.config.js) and exposes Tailwind utilities for the Genovate domain:

- **Status colors** (candidate pipeline): `idea`, `evidence-map`, `hypothesis`, `candidate`, `simulation`, `guardian-review`, `promoted`, `killed`, `parked`
- **Entity types** (evidence graph): `gene`, `disease`, `compound`, `pathway`, `assay`
- **Confidence**: `confidence-high`, `confidence-medium`, `confidence-low`

Semantic surface tokens (`background`, `foreground`, `card`, `primary`, …) are driven by CSS variables in [`app/globals.css`](./app/globals.css), enabling Tailwind's `dark` mode via the `class` strategy.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Genovate FastAPI base URL |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/ws` | WebSocket URL (reserved for Dashboard PR #9 — live updates) |

## API client

All requests flow through the type-safe client in [`lib/api/client.ts`](./lib/api/client.ts). For an OpenAPI-generated client, replace [`lib/types/genovate.ts`](./lib/types/genovate.ts) with the output of `openapi-typescript` against `${NEXT_PUBLIC_API_URL}/openapi.json` and update the per-resource modules accordingly.

## Acceptance criteria coverage (Dashboard PR #1)

- ✅ Next.js 14 app — `npm run dev` on `localhost:3000`
- ✅ API client connects to Genovate backend at `NEXT_PUBLIC_API_URL`
- ✅ Program selector in the header — switching updates all program-scoped views
- ✅ Interactive evidence graph (React Flow) with entity-type colors and confidence-weighted edges
- ✅ Candidate kanban with drag-and-drop status updates
- ✅ Agent run history table with confidence badges
- ✅ Guardian review queue with decision buttons & rationale modal
- ✅ `npm run build` compiles cleanly
- ✅ Responsive layout (sidebar collapses on mobile)
- ✅ Dark mode wired via the `class` strategy

## Security note

Pinned to **Next.js 15.5.18**, which patches the WebSocket-upgrade SSRF, Pages Router middleware/proxy i18n bypass, RSC HTTP request deserialization DoS, and segment-prefetch middleware bypass advisories that affected Next 14.x and earlier 15.x releases. Re-run `npm audit` after any future bump.
