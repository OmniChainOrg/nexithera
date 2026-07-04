'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  simulationsApi,
  type CreateCXUInput,
  type CreateSwarmInput,
  type CreateZoneInput,
  type ListSimulationRunsParams,
  type RunCrossZoneInput,
} from '@/lib/api/simulations';
import { queryKeys } from './query-keys';

export function useSimulationRuns(params: ListSimulationRunsParams = {}) {
  return useQuery({
    queryKey: queryKeys.simulations.runs(params as Record<string, unknown>),
    queryFn: ({ signal }) => simulationsApi.listRuns(params, signal),
  });
}

export function useSimulationRun(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.simulations.run(id) : ['simulations', 'run', 'disabled'],
    queryFn: ({ signal }) => simulationsApi.getRun(id as string, signal),
    enabled: !!id,
  });
}

export function useZones(programId: string | null | undefined) {
  return useQuery({
    queryKey: programId ? queryKeys.simulations.zones(programId) : ['simulations', 'zones', 'disabled'],
    queryFn: ({ signal }) => simulationsApi.zones(programId as string, signal),
    enabled: !!programId,
  });
}

export function useCXUs(programId: string | null | undefined) {
  return useQuery({
    queryKey: programId ? queryKeys.simulations.cxus(programId) : ['simulations', 'cxus', 'disabled'],
    queryFn: ({ signal }) => simulationsApi.listCXUs(programId as string, signal),
    enabled: !!programId,
  });
}

export function useSimulationTrace(runId: string | null) {
  return useQuery({
    queryKey: runId ? queryKeys.simulations.trace(runId) : ['simulations', 'trace', 'disabled'],
    queryFn: ({ signal }) => simulationsApi.trace(runId as string, signal),
    enabled: !!runId,
  });
}

export function useCreateZone(programId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateZoneInput) => simulationsApi.createZone(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.simulations.zones(programId) }),
  });
}

export function useCreateCXU(programId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateCXUInput) => simulationsApi.createCXU(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.simulations.cxus(programId) }),
  });
}

export function useCreateSwarm(programId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateSwarmInput) => simulationsApi.createSwarm(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.simulations.cxus(programId) }),
  });
}

export function useRunCrossZone(programId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: RunCrossZoneInput) => simulationsApi.runCrossZone(input),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: queryKeys.simulations.runs({ program_id: programId }),
      }),
  });
}
