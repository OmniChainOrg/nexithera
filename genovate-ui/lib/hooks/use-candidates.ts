'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  candidatesApi,
  type CreateCandidateInput,
  type UpdateCandidateStatusInput,
} from '@/lib/api/candidates';
import { queryKeys } from './query-keys';

export function useCandidates(programId: string | null | undefined) {
  return useQuery({
    queryKey: programId ? queryKeys.candidates.forProgram(programId) : ['candidates', 'disabled'],
    queryFn: ({ signal }) => candidatesApi.listForProgram(programId as string, signal),
    enabled: !!programId,
  });
}

export function useCandidate(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.candidates.detail(id) : ['candidates', 'disabled'],
    queryFn: ({ signal }) => candidatesApi.get(id as string, signal),
    enabled: !!id,
  });
}

export function useCandidateScorecards(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.candidates.scorecards(id) : ['candidates', 'scorecards', 'disabled'],
    queryFn: ({ signal }) => candidatesApi.scorecards(id as string, signal),
    enabled: !!id,
  });
}

export function useCreateCandidate(programId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateCandidateInput) => candidatesApi.create(input),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.candidates.forProgram(programId) }),
  });
}

export function useUpdateCandidateStatus(programId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; input: UpdateCandidateStatusInput }) =>
      candidatesApi.updateStatus(vars.id, vars.input),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.candidates.forProgram(programId) }),
  });
}
