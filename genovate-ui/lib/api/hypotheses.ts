import { api } from './client';
import type { Hypothesis, HypothesisVersion } from '@/lib/types/genovate';

export interface CreateHypothesisInput {
  program_id: string;
  text: string;
  claim_type: string;
  initial_evidence_ids?: string[];
}

export const hypothesesApi = {
  listForProgram: (programId: string, signal?: AbortSignal) =>
    api.get<Hypothesis[]>(`/hypotheses/program/${encodeURIComponent(programId)}`, { signal }),
  get: (id: string, signal?: AbortSignal) =>
    api.get<Hypothesis>(`/hypotheses/${encodeURIComponent(id)}`, { signal }),
  create: (input: CreateHypothesisInput) => api.post<Hypothesis>('/hypotheses', input),
  versions: (id: string, signal?: AbortSignal) =>
    api.get<HypothesisVersion[]>(`/hypotheses/${encodeURIComponent(id)}/versions`, { signal }),
};
