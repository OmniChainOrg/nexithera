import { api } from './client';
import type { Program } from '@/lib/types/genovate';

export interface CreateProgramInput {
  name: string;
  therapeutic_area: string;
  description?: string | null;
}

export const programsApi = {
  list: (signal?: AbortSignal) => api.get<Program[]>('/programs', { signal }),
  get: (id: string, signal?: AbortSignal) =>
    api.get<Program>(`/programs/${encodeURIComponent(id)}`, { signal }),
  create: (input: CreateProgramInput) => api.post<Program>('/programs', input),
  archive: (id: string) =>
    api.patch<Program>(`/programs/${encodeURIComponent(id)}`, { status: 'archived' }),
};
