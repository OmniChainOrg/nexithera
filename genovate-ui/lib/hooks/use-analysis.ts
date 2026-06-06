'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { analysisApi } from '@/lib/api/analysis';
import type {
  ExperimentOutcome,
  GapAnalysisRequest,
  NextExperimentsRequest,
  ProposedExperimentStatus,
} from '@/lib/types/genovate';
import { queryKeys } from './query-keys';

export function useGapAnalysis(input: GapAnalysisRequest | null) {
  return useQuery({
    queryKey: input ? queryKeys.analysis.gaps(input.program_id) : ['analysis', 'gaps', 'disabled'],
    queryFn: () => analysisApi.gapAnalysis(input as GapAnalysisRequest),
    enabled: !!input?.program_id,
    staleTime: 30 * 60 * 1000,
  });
}

export function useNextExperiments(input: NextExperimentsRequest | null) {
  return useQuery({
    queryKey: input ? queryKeys.analysis.experiments(input.program_id) : ['analysis', 'experiments', 'disabled'],
    queryFn: () => analysisApi.nextExperiments(input as NextExperimentsRequest),
    enabled: !!input?.program_id,
    staleTime: 5 * 60 * 1000,
  });
}

export function useBeliefTimeline(entityId: string | null | undefined) {
  return useQuery({
    queryKey: entityId ? queryKeys.analysis.beliefTimeline(entityId) : ['analysis', 'belief', 'disabled'],
    queryFn: ({ signal }) => analysisApi.beliefTimeline(entityId as string, signal),
    enabled: !!entityId,
  });
}

export function useConductExperiment(programId: string | null | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, outcome }: { id: string; outcome: ExperimentOutcome }) =>
      analysisApi.conductExperiment(id, outcome),
    onSuccess: (experiment) => {
      const pid = experiment.program_id ?? programId;
      if (pid) qc.invalidateQueries({ queryKey: queryKeys.analysis.experiments(pid) });
      if (experiment.hypothesis_id) {
        qc.invalidateQueries({ queryKey: queryKeys.analysis.beliefTimeline(experiment.hypothesis_id) });
      }
      if (experiment.id) qc.invalidateQueries({ queryKey: queryKeys.analysis.beliefTimeline(experiment.id) });
    },
  });
}

export function useUpdateExperimentStatus(programId: string | null | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: ProposedExperimentStatus }) =>
      analysisApi.updateExperimentStatus(id, status),
    onSuccess: (experiment) => {
      const pid = experiment.program_id ?? programId;
      if (pid) qc.invalidateQueries({ queryKey: queryKeys.analysis.experiments(pid) });
    },
  });
}
