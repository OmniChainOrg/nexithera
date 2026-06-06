'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { targetDiscoveryApi } from '@/lib/api/target-discovery';
import type { DiscoverTargetsRequest } from '@/lib/types/genovate';
import { queryKeys } from './query-keys';

export function useTargetDiscovery(input: DiscoverTargetsRequest | null) {
  return useQuery({
    queryKey: input ? queryKeys.targets.discover(input.program_id) : ['targets', 'discover', 'disabled'],
    queryFn: () => targetDiscoveryApi.discover(input as DiscoverTargetsRequest),
    enabled: false,
    staleTime: 60 * 60 * 1000,
  });
}

export function useDiscoverTargets(programId: string | null | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: DiscoverTargetsRequest) => targetDiscoveryApi.discover(input),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.targets.discover(data.program_id), data);
      qc.invalidateQueries({ queryKey: queryKeys.targets.discover(data.program_id) });
    },
    gcTime: 60 * 60 * 1000,
    meta: { programId },
  });
}
