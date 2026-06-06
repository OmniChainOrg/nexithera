import { api } from './client';
import type { GuardianBulkRequest, GuardianBulkResponse } from '@/lib/types/genovate';

export const guardianBulkApi = {
  bulk: (input: GuardianBulkRequest) => api.post<GuardianBulkResponse>('/guardian/bulk', input),
};
