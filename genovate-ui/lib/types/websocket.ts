/**
 * WebSocket message contracts mirroring the Genovate backend endpoints
 * (Genovate PR #7). Channels:
 *  - /ws/cxu/{cxu_id}            → CXUIterationMessage
 *  - /ws/swarm/{swarm_id}        → SwarmUpdateMessage
 *  - /ws/agent/{run_id}          → AgentOutputMessage
 *  - /ws/simulation/{run_id}     → CXUIterationMessage | SwarmUpdateMessage
 *  - /ws/program/{program_id}    → ProgramEventMessage
 */

export interface CXUIterationMessage {
  iteration: number;
  input_state: unknown;
  output_state: unknown;
  metrics: { duration_ms: number; [key: string]: number };
  confidence?: number;
  trace_id: string;
}

export interface SwarmMemberResult {
  cxu_id: string;
  contribution: number;
  latest_output: unknown;
}

export interface SwarmUpdateMessage {
  consensus_score: number;
  diversity_metric: number;
  member_results: SwarmMemberResult[];
  completed_members: number;
  total_members: number;
}

export type AgentOutputMessageType = 'chunk' | 'tool_call' | 'confidence' | 'complete';

export interface AgentOutputMessage {
  type: AgentOutputMessageType;
  content?: string;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  confidence?: number;
}

export type ProgramEventType =
  | 'candidate_created'
  | 'candidate_status_changed'
  | 'review_created'
  | 'agent_run_completed'
  | 'evidence_edge_added'
  | 'target_discovery.new'
  | 'gap_analysis.completed'
  | 'experiment.status_changed'
  | 'experiment.completed'
  | 'guardian.bulk_complete';

export interface ProgramEventMessage {
  event_type: ProgramEventType;
  entity_id: string;
  entity_type?: string;
  old_status?: string;
  new_status?: string;
  payload?: Record<string, unknown>;
}

/** High-level lifecycle status surfaced to the UI. */
export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed' | 'error';

/** Stream channel — used by the singleton client to namespace pools and topics. */
export type StreamChannel = 'cxu' | 'swarm' | 'agent' | 'simulation' | 'program';

/** Discriminated message used by `useAgentRunStream` for incremental UI updates. */
export type AnyWSMessage =
  | CXUIterationMessage
  | SwarmUpdateMessage
  | AgentOutputMessage
  | ProgramEventMessage;

export interface WebSocketHookState<TMessage> {
  status: ConnectionStatus;
  lastMessage: TMessage | null;
  error: string | null;
  /** True once the underlying socket has been open at least once. */
  hasEverConnected: boolean;
}

/** Toast/notification entry stored in the global WebSocket store. */
export interface NotificationEntry {
  id: string;
  title: string;
  body?: string;
  level: 'info' | 'success' | 'warning' | 'error';
  createdAt: number;
  /** Optional originating program id, useful for navigation. */
  programId?: string;
}

