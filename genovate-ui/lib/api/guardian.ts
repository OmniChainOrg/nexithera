import { api } from './client';
import type {
  GuardianDecision,
  GuardianReview,
  GuardianReviewStatus,
  RiskFlag,
} from '@/lib/types/genovate';

export interface ListReviewsParams {
  program_id?: string;
  status?: GuardianReviewStatus;
  limit?: number;
  offset?: number;
}

export interface SubmitReviewDecisionInput {
  decision: GuardianDecision;
  decision_rationale: string;
  risk_flags?: RiskFlag[];
  checklist?: Array<{ item: string; passed: boolean }>;
}

export const guardianApi = {
  listReviews: (params: ListReviewsParams = {}, signal?: AbortSignal) =>
    api.get<GuardianReview[]>('/guardian/reviews', { query: params as Record<string, unknown>, signal }),
  getReview: (id: string, signal?: AbortSignal) =>
    api.get<GuardianReview>(`/guardian/reviews/${encodeURIComponent(id)}`, { signal }),
  submitDecision: (id: string, input: SubmitReviewDecisionInput) =>
    api.post<GuardianReview>(`/guardian/reviews/${encodeURIComponent(id)}/decision`, input),
  signedReport: (id: string, signal?: AbortSignal) =>
    api.get<{ url: string }>(`/guardian/reviews/${encodeURIComponent(id)}/signed-report`, {
      signal,
    }),
};
