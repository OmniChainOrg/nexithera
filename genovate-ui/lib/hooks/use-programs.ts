'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { programsApi, type CreateProgramInput } from '@/lib/api/programs';
import { queryKeys } from './query-keys';

export function usePrograms() {
  return useQuery({
    queryKey: queryKeys.programs.all,
    queryFn: ({ signal }) => programsApi.list(signal),
    staleTime: 30_000,
  });
}

export function useProgram(id: string | null | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.programs.detail(id) : ['programs', 'disabled'],
    queryFn: ({ signal }) => programsApi.get(id as string, signal),
    enabled: !!id,
  });
}

export function useCreateProgram() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateProgramInput) => programsApi.create(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.programs.all }),
  });
}
