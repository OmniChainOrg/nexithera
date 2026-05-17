import { api } from './client';
import type { CXU, SimulationRun, SimulationRunStatus } from '@/lib/types/genovate';

export interface ListSimulationRunsParams {
  program_id?: string;
  status?: SimulationRunStatus;
  limit?: number;
}

export interface CreateCXUInput {
  name: string;
  zone_id: string;
  program_id: string;
}

export const simulationsApi = {
  listRuns: (params: ListSimulationRunsParams = {}, signal?: AbortSignal) =>
    api.get<SimulationRun[]>('/simulations/runs', { query: params as Record<string, unknown>, signal }),
  getRun: (id: string, signal?: AbortSignal) =>
    api.get<SimulationRun>(`/simulations/runs/${encodeURIComponent(id)}`, { signal }),
  zones: (programId: string, signal?: AbortSignal) =>
    api.get<Array<{ id: string; name: string; status: string }>>(
      `/simulations/program/${encodeURIComponent(programId)}/zones`,
      { signal },
    ),
  listCXUs: (programId: string, signal?: AbortSignal) =>
    api.get<CXU[]>(`/simulations/program/${encodeURIComponent(programId)}/cxus`, { signal }),
  createCXU: (input: CreateCXUInput) => api.post<CXU>('/simulations/cxus', input),
  startCXU: (id: string) => api.post<CXU>(`/simulations/cxus/${encodeURIComponent(id)}/start`),
  pauseCXU: (id: string) => api.post<CXU>(`/simulations/cxus/${encodeURIComponent(id)}/pause`),
  terminateCXU: (id: string) =>
    api.post<CXU>(`/simulations/cxus/${encodeURIComponent(id)}/terminate`),
  trace: (runId: string, signal?: AbortSignal) =>
    api.get<{ steps: Array<{ step: number; description: string; timestamp: string }> }>(
      `/simulations/runs/${encodeURIComponent(runId)}/trace`,
      { signal },
    ),
};
