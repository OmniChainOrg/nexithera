import { api } from './client';
import type { EvidenceEdge, EvidenceEntity, EvidenceGraph } from '@/lib/types/genovate';

export interface PathFindingResult {
  paths: Array<{
    entities: EvidenceEntity[];
    edges: EvidenceEdge[];
  }>;
}

export const evidenceApi = {
  graph: (programId: string, signal?: AbortSignal) =>
    api.get<EvidenceGraph>(`/evidence/program/${encodeURIComponent(programId)}/graph`, { signal }),
  entity: (entityId: string, signal?: AbortSignal) =>
    api.get<EvidenceEntity>(`/evidence/entities/${encodeURIComponent(entityId)}`, { signal }),
  edgesFor: (entityId: string, signal?: AbortSignal) =>
    api.get<EvidenceEdge[]>(`/evidence/entities/${encodeURIComponent(entityId)}/edges`, { signal }),
  findPaths: (programId: string, source: string, target: string, maxDepth = 3) =>
    api.get<PathFindingResult>(`/evidence/program/${encodeURIComponent(programId)}/paths`, {
      query: { source, target, max_depth: maxDepth },
    }),
};
