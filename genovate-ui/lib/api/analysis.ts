import { api } from './client';
import type {
  BeliefTimeline,
  EvidenceGap,
  ExperimentOutcome,
  GapAnalysisRequest,
  GapAnalysisResponse,
  NextExperimentsRequest,
  ProposedExperiment,
  ProposedExperimentStatus,
} from '@/lib/types/genovate';

export const analysisApi = {
  gapAnalysis: (input: GapAnalysisRequest) =>
    api.post<GapAnalysisResponse>('/analysis/gap-analysis', input),
  nextExperiments: (input: NextExperimentsRequest) =>
    api.post<ProposedExperiment[]>('/analysis/next-experiments', input),
  beliefTimeline: (entityId: string, signal?: AbortSignal) =>
    api.get<BeliefTimeline>(`/analysis/belief-timeline/${encodeURIComponent(entityId)}`, { signal }),
  conductExperiment: (id: string, outcome: ExperimentOutcome) =>
    api.post<ProposedExperiment>(`/analysis/experiments/${encodeURIComponent(id)}/outcome`, outcome),
  updateExperimentStatus: (id: string, status: ProposedExperimentStatus) =>
    api.patch<ProposedExperiment>(`/analysis/experiments/${encodeURIComponent(id)}/status`, { status }),
};

export type { EvidenceGap };
