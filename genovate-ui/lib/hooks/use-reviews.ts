'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  guardianApi,
  type ListReviewsParams,
  type SubmitReviewDecisionInput,
} from '@/lib/api/guardian';
import { queryKeys } from './query-keys';

export function useReviews(params: ListReviewsParams = {}) {
  return useQuery({
    queryKey: queryKeys.guardian.reviews(params as Record<string, unknown>),
    queryFn: ({ signal }) => guardianApi.listReviews(params, signal),
  });
}

export function useReview(id: string | null) {
  return useQuery({
    queryKey: id ? queryKeys.guardian.review(id) : ['guardian', 'review', 'disabled'],
    queryFn: ({ signal }) => guardianApi.getReview(id as string, signal),
    enabled: !!id,
  });
}

export function useSubmitReviewDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; input: SubmitReviewDecisionInput }) =>
      guardianApi.submitDecision(vars.id, vars.input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['guardian'] }),
  });
}
