'use client';

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  partnerabilityApi,
  type INDChecklistItem,
  type INDReadinessResponse,
  type PartnerabilityResponse,
  type UpdateINDChecklistInput,
} from '@/lib/api/partnerability';
import { queryKeys } from './query-keys';

const ONE_HOUR = 60 * 60 * 1000;
const FIVE_MINUTES = 5 * 60 * 1000;
const ONE_DAY = 24 * 60 * 60 * 1000;

export function usePartnerability(candidateId: string | null | undefined) {
  return useQuery({
    queryKey: candidateId
      ? queryKeys.analysis.partnerability(candidateId)
      : ['analysis', 'partnerability', 'disabled'],
    queryFn: () => partnerabilityApi.partnerability(candidateId as string),
    enabled: !!candidateId,
    staleTime: ONE_HOUR,
    // Patent map shares this query but caches up to a day in-place — TanStack
    // Query will refetch on tab focus only after `staleTime`, so the one-hour
    // default is appropriate. The PatentMap tab also exposes a manual refresh.
    gcTime: ONE_DAY,
  });
}

export function useINDReadiness(candidateId: string | null | undefined) {
  return useQuery({
    queryKey: candidateId
      ? queryKeys.analysis.indReadiness(candidateId)
      : ['analysis', 'ind-readiness', 'disabled'],
    queryFn: () => partnerabilityApi.indReadiness(candidateId as string),
    enabled: !!candidateId,
    staleTime: FIVE_MINUTES,
  });
}

export function useUpdateINDChecklistItem(candidateId: string) {
  const qc = useQueryClient();
  const key = queryKeys.analysis.indReadiness(candidateId);

  return useMutation({
    mutationFn: ({
      itemId,
      input,
    }: {
      itemId: string;
      input: UpdateINDChecklistInput;
    }) => partnerabilityApi.updateChecklistItem(candidateId, itemId, input),

    // Optimistic update — flip the row state instantly and roll back on error.
    onMutate: async ({ itemId, input }) => {
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<INDReadinessResponse>(key);
      if (previous?.items) {
        const nextItems: INDChecklistItem[] = previous.items.map((i) =>
          i.item_id === itemId
            ? {
                ...i,
                status: input.status,
                evidence_uri: input.evidence_uri ?? i.evidence_uri,
                notes: input.notes ?? i.notes,
                updated_at: new Date().toISOString(),
              }
            : i,
        );
        qc.setQueryData<INDReadinessResponse>(key, {
          ...previous,
          items: nextItems,
        });
      }
      return { previous };
    },

    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(key, ctx.previous);
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey: key });
    },
  });
}

/**
 * Helper for callers that already hold a partnerability response and want
 * to seed the IND readiness cache without a second network round-trip
 * (the partnerability endpoint embeds `ind_readiness_assessment`).
 */
export function seedINDReadinessFromPartnerability(
  qc: ReturnType<typeof useQueryClient>,
  candidateId: string,
  data: PartnerabilityResponse,
) {
  if (data.ind_readiness_assessment) {
    qc.setQueryData(
      queryKeys.analysis.indReadiness(candidateId),
      data.ind_readiness_assessment,
    );
  }
}
