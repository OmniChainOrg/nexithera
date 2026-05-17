export interface CXUIterationMessage {
  iteration: number
  input_state: any
  output_state: any
  metrics: { duration_ms: number; [key: string]: number }
  confidence?: number
  trace_id: string
}

export interface SwarmUpdateMessage {
  consensus_score: number
  diversity_metric: number
  member_results: Array<{ cxu_id: string; contribution: number; latest_output: any }>
  completed_members: number
  total_members: number
}

export interface AgentOutputMessage {
  type: 'chunk' | 'tool_call' | 'confidence' | 'complete'
  content?: string
  tool_name?: string
  confidence?: number
}

export interface ProgramEventMessage {
  event_type: 'candidate_created' | 'candidate_status_changed' | 'review_created' | 'agent_run_completed'
  entity_id: string
  old_status?: string
  new_status?: string
}
