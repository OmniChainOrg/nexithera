import { api } from './client';
import type { CXU, SimulationRun, SimulationRunStatus } from '@/lib/types/genovate';

export interface ListSimulationRunsParams {
  program_id?: string;
  status?: SimulationRunStatus;
  limit?: number;
}

export interface CreateZoneInput {
  program_id: string;
  zone_type: string;
  config?: Record<string, unknown>;
  name?: string;
}

export interface CreateCXUInput {
  zone_id: string;
  cxu_type: string;
  configuration?: Record<string, unknown>;
  program_id: string;
}

export interface CreateSwarmInput {
  swarm_config: Record<string, unknown>;
  program_id: string;
  objective: string;
}

export interface RunCrossZoneInput {
  source_zone_id: string;
  target_zone_id: string;
  coupling_map: Record<string, string>;
  inputs: Record<string, unknown>;
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
  createZone: (input: CreateZoneInput) =>
    api.post<{ id: string; name: string; status: string }>('/simulations/zones', input),
  createCXU: (input: CreateCXUInput) => api.post<CXU>('/simulations/cxus', input),
  createSwarm: (input: CreateSwarmInput) =>
    api.post<Record<string, unknown>>('/simulations/swarms', input),
  runCrossZone: (input: RunCrossZoneInput) =>
    api.post<SimulationRun>('/simulations/cross-zone', input),
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
