import { create } from 'zustand';
import type {
  AgentName,
  AgentRunStatus,
  CandidateStatus,
  EntityType,
} from '@/lib/types/genovate';

interface FilterStoreState {
  candidateStatuses: CandidateStatus[];
  agentNames: AgentName[];
  agentRunStatuses: AgentRunStatus[];
  evidenceEntityTypes: EntityType[];
  search: string;

  toggleCandidateStatus: (s: CandidateStatus) => void;
  toggleAgentName: (n: AgentName) => void;
  toggleAgentRunStatus: (s: AgentRunStatus) => void;
  toggleEvidenceEntityType: (t: EntityType) => void;
  setSearch: (s: string) => void;
  reset: () => void;
}

const initial = {
  candidateStatuses: [] as CandidateStatus[],
  agentNames: [] as AgentName[],
  agentRunStatuses: [] as AgentRunStatus[],
  evidenceEntityTypes: [] as EntityType[],
  search: '',
};

function toggle<T>(arr: T[], value: T): T[] {
  return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
}

export const useFilterStore = create<FilterStoreState>((set) => ({
  ...initial,
  toggleCandidateStatus: (s) =>
    set((state) => ({ candidateStatuses: toggle(state.candidateStatuses, s) })),
  toggleAgentName: (n) => set((state) => ({ agentNames: toggle(state.agentNames, n) })),
  toggleAgentRunStatus: (s) =>
    set((state) => ({ agentRunStatuses: toggle(state.agentRunStatuses, s) })),
  toggleEvidenceEntityType: (t) =>
    set((state) => ({ evidenceEntityTypes: toggle(state.evidenceEntityTypes, t) })),
  setSearch: (s) => set({ search: s }),
  reset: () => set(initial),
}));
