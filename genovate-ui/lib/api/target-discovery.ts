import { api } from './client';
import type { DiscoverTargetsRequest, DiscoverTargetsResponse } from '@/lib/types/genovate';

export const targetDiscoveryApi = {
  discover: (input: DiscoverTargetsRequest) =>
    api.post<DiscoverTargetsResponse>('/agents/discover-targets', input),
};
