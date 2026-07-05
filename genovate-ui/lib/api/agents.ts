import { api } from './client';
import type { AgentName, AgentRun, AgentRunStatus } from '@/lib/types/genovate';

export interface RunAgentInput {
  agent_name: AgentName;
  run_type: string;
  program_id: string;
  inputs: Record<string, unknown>;
}

export interface ListAgentRunsParams {
  program_id?: string;
  agent_name?: AgentName;
  status?: AgentRunStatus;
  limit?: number;
  offset?: number;
}

export const agentsApi = {
  listRuns: (params: ListAgentRunsParams = {}, signal?: AbortSignal) =>
    api.get<AgentRun[]>('/agents/runs', { query: params as Record<string, unknown>, signal }),
  getRun: (id: string, signal?: AbortSignal) =>
    api.get<AgentRun>(`/agents/runs/${encodeURIComponent(id)}`, { signal }),
  run: (input: RunAgentInput) => api.post<AgentRun>('/agents/run', input),
  rerun: (id: string) => api.post<AgentRun>(`/agents/runs/${encodeURIComponent(id)}/rerun`),
};
