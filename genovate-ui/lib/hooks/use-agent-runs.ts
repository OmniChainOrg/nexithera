'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentsApi, type ListAgentRunsParams, type RunAgentInput } from '@/lib/api/agents';
import { queryKeys } from './query-keys';

export function useAgentRuns(params: ListAgentRunsParams = {}) {
  return useQuery({
    queryKey: queryKeys.agents.runs(params as Record<string, unknown>),
    queryFn: ({ signal }) => agentsApi.listRuns(params, signal),
  });
}

export function useAgentRun(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.agents.run(id) : ['agents', 'run', 'disabled'],
    queryFn: ({ signal }) => agentsApi.getRun(id as string, signal),
    enabled: !!id,
  });
}

export function useRunAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: RunAgentInput) => agentsApi.run(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents', 'runs'] }),
  });
}

export function useRerunAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => agentsApi.rerun(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agents', 'runs'] }),
  });
}
