'use client';

import { useQuery } from '@tanstack/react-query';
import { hypothesesApi } from '@/lib/api/hypotheses';
import { queryKeys } from './query-keys';

export function useHypotheses(programId: string | null | undefined) {
  return useQuery({
    queryKey: programId
      ? queryKeys.hypotheses.forProgram(programId)
      : ['hypotheses', 'program', 'disabled'],
    queryFn: ({ signal }) => hypothesesApi.listForProgram(programId as string, signal),
    enabled: !!programId,
  });
}

export function useHypothesis(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.hypotheses.detail(id) : ['hypotheses', 'disabled'],
    queryFn: ({ signal }) => hypothesesApi.get(id as string, signal),
    enabled: !!id,
  });
}

export function useHypothesisVersions(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.hypotheses.versions(id) : ['hypotheses', 'versions', 'disabled'],
    queryFn: ({ signal }) => hypothesesApi.versions(id as string, signal),
    enabled: !!id,
  });
}
