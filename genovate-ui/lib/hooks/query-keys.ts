/**
 * Centralized query key factory.
 *
 * Using a single source of truth for query keys keeps invalidations,
 * prefetching, and devtools inspection consistent across the app.
 */
export const queryKeys = {
  programs: {
    all: ['programs'] as const,
    detail: (id: string) => ['programs', id] as const,
  },
  evidence: {
    graph: (programId: string) => ['evidence', 'graph', programId] as const,
    entity: (entityId: string) => ['evidence', 'entity', entityId] as const,
    edges: (entityId: string) => ['evidence', 'edges', entityId] as const,
  },
  hypotheses: {
    forProgram: (programId: string) => ['hypotheses', 'program', programId] as const,
    detail: (id: string) => ['hypotheses', id] as const,
    versions: (id: string) => ['hypotheses', id, 'versions'] as const,
  },
  candidates: {
    forProgram: (programId: string) => ['candidates', 'program', programId] as const,
    detail: (id: string) => ['candidates', id] as const,
    scorecards: (id: string) => ['candidates', id, 'scorecards'] as const,
    latestScorecard: (id: string) => ['candidates', id, 'scorecards', 'latest'] as const,
  },
  agents: {
    runs: (params: Record<string, unknown>) => ['agents', 'runs', params] as const,
    run: (id: string) => ['agents', 'runs', id] as const,
  },
  guardian: {
    reviews: (params: Record<string, unknown>) => ['guardian', 'reviews', params] as const,
    review: (id: string) => ['guardian', 'reviews', id] as const,
  },
  simulations: {
    runs: (params: Record<string, unknown>) => ['simulations', 'runs', params] as const,
    run: (id: string) => ['simulations', 'runs', id] as const,
    zones: (programId: string) => ['simulations', 'zones', programId] as const,
    cxus: (programId: string) => ['simulations', 'cxus', programId] as const,
    trace: (runId: string) => ['simulations', 'trace', runId] as const,
  },
} as const;
