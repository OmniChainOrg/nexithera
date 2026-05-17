'use client';

import { useQuery } from '@tanstack/react-query';
import { evidenceApi } from '@/lib/api/evidence';
import { queryKeys } from './query-keys';

export function useEvidenceGraph(programId: string | null | undefined) {
  return useQuery({
    queryKey: programId ? queryKeys.evidence.graph(programId) : ['evidence', 'graph', 'disabled'],
    queryFn: ({ signal }) => evidenceApi.graph(programId as string, signal),
    enabled: !!programId,
  });
}

export function useEvidenceEntity(entityId: string | null) {
  return useQuery({
    queryKey: entityId ? queryKeys.evidence.entity(entityId) : ['evidence', 'entity', 'disabled'],
    queryFn: ({ signal }) => evidenceApi.entity(entityId as string, signal),
    enabled: !!entityId,
  });
}

export function useEvidenceEdges(entityId: string | null) {
  return useQuery({
    queryKey: entityId ? queryKeys.evidence.edges(entityId) : ['evidence', 'edges', 'disabled'],
    queryFn: ({ signal }) => evidenceApi.edgesFor(entityId as string, signal),
    enabled: !!entityId,
  });
}
