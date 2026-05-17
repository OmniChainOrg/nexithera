import { api } from './client';
import type {
  Candidate,
  CandidateStatus,
  CandidateType,
  Scorecard,
} from '@/lib/types/genovate';

export interface CreateCandidateInput {
  program_id: string;
  name: string;
  candidate_type: CandidateType;
  target_id?: string | null;
  mechanism_of_action?: string | null;
  therapeutic_area: string;
}

export interface UpdateCandidateStatusInput {
  status: CandidateStatus;
  kill_rationale?: string;
}

export const candidatesApi = {
  listForProgram: (programId: string, signal?: AbortSignal) =>
    api.get<Candidate[]>(`/candidates/program/${encodeURIComponent(programId)}`, { signal }),
  get: (id: string, signal?: AbortSignal) =>
    api.get<Candidate>(`/candidates/${encodeURIComponent(id)}`, { signal }),
  create: (input: CreateCandidateInput) => api.post<Candidate>('/candidates', input),
  updateStatus: (id: string, input: UpdateCandidateStatusInput) =>
    api.patch<Candidate>(`/candidates/${encodeURIComponent(id)}/status`, input),
  scorecards: (id: string, signal?: AbortSignal) =>
    api.get<Scorecard[]>(`/candidates/${encodeURIComponent(id)}/scorecards`, { signal }),
  latestScorecard: (id: string, signal?: AbortSignal) =>
    api.get<Scorecard>(`/candidates/${encodeURIComponent(id)}/scorecards/latest`, { signal }),
  promoteToEpistemicOS: (id: string) =>
    api.post<Candidate>(`/candidates/${encodeURIComponent(id)}/promote`),
};
