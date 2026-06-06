'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { guardianApi } from '@/lib/api/guardian';
import type { GuardianBulkRequest } from '@/lib/types/genovate';
import { queryKeys } from './query-keys';

export function useGuardianBulk(programId: string | null | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: GuardianBulkRequest) => guardianApi.bulk(input),
    onSuccess: () => {
      if (programId) {
        qc.invalidateQueries({ queryKey: queryKeys.guardian.reviews({ program_id: programId }) });
        qc.invalidateQueries({ queryKey: queryKeys.candidates.forProgram(programId) });
      }
      qc.invalidateQueries({ queryKey: ['guardian'] });
    },
  });
}
