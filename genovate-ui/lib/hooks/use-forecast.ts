'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { forecastApi, type ForecastRequest, type GuardianSubmission } from '@/lib/api/forecast';
import { ApiError } from '@/lib/api/client';
import { queryKeys } from './query-keys';

const FIVE_MINUTES = 5 * 60 * 1000;
const ONE_HOUR = 60 * 60 * 1000;

/**
 * Fetches a clinical forecast. The `request` argument is included in the
 * query key so any change to `trial_design`, `phase`, or scenarios will
 * trigger a fresh fetch — matching the spec's "stale time 0 on param
 * change" behaviour while sharing the cache for identical parameters.
 */
export function useClinicalForecast(
  candidateId: string | null | undefined,
  request: Omit<ForecastRequest, 'candidate_id'> | null,
  options: { enabled?: boolean } = {},
) {
  const enabled = !!candidateId && !!request && options.enabled !== false;

  return useQuery({
    queryKey:
      candidateId && request
        ? queryKeys.forecast.clinical(candidateId, request)
        : ['forecast', 'clinical', 'disabled'],
    queryFn: () =>
      forecastApi.clinical({
        candidate_id: candidateId as string,
        ...(request as Omit<ForecastRequest, 'candidate_id'>),
      }),
    enabled,
    staleTime: 0,
    gcTime: FIVE_MINUTES,
  });
}

export function useForecastHistory(candidateId: string | null | undefined) {
  return useQuery({
    queryKey: candidateId
      ? queryKeys.forecast.history(candidateId)
      : ['forecast', 'history', 'disabled'],
    queryFn: () => forecastApi.history(candidateId as string),
    enabled: !!candidateId,
    staleTime: ONE_HOUR,
    // The endpoint is optional; suppress retry storms on 404 deployments.
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 1;
    },
  });
}

export function useSubmitForecastToGuardian(forecastId: string | null | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: GuardianSubmission) => {
      if (!forecastId) {
        return Promise.reject(new Error('Missing forecast_id'));
      }
      return forecastApi.submitGuardian(forecastId, input);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['forecast', 'clinical'] });
    },
  });
}
