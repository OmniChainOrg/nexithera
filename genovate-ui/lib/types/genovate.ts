/**
 * Genovate API — TypeScript domain types.
 *
 * Manually maintained to mirror the FastAPI schemas in `Backend/app/schemas/*`.
 * For an OpenAPI-generated client, swap this file out for the output of
 * `openapi-typescript` against `${NEXT_PUBLIC_API_URL}/openapi.json`.
 */

export type ISODateString = string;

export type ProgramStatus = 'active' | 'archived';

export interface Program {
  id: string;
  name: string;
  therapeutic_area: string;
  description: string | null;
  status: ProgramStatus;
  created_at: ISODateString;
}

export type CandidateStatus =
  | 'idea'
  | 'evidence_map'
  | 'hypothesis'
  | 'candidate'
  | 'simulation'
  | 'guardian_review'
  | 'promoted'
  | 'killed'
  | 'parked';

export type CandidateType =
  | 'small_molecule'
  | 'biologic'
  | 'immunotherapy'
  | 'formulation'
  | 'gene_target'
  | 'protein_target';

export interface Candidate {
  id: string;
  name: string;
  candidate_type: CandidateType;
  target_id: string | null;
  target_name?: string;
  mechanism_of_action: string | null;
  therapeutic_area: string;
  status: CandidateStatus;
  kill_rationale: string | null;
  program_id: string;
  created_at: ISODateString;
  updated_at: ISODateString;
  current_score?: number;
}

export interface Scorecard {
  id: string;
  candidate_id: string;
  evidence_score: number;
  simulation_score: number;
  safety_score: number;
  formulation_score: number;
  translational_score: number;
  program_fit_score: number;
  overall_score: number;
  scoring_rationale: string | null;
  version: number;
  scored_at: ISODateString;
}

export type EntityType = 'gene' | 'disease' | 'compound' | 'pathway' | 'assay' | string;

export interface EvidenceEntity {
  id: string;
  entity_type: EntityType;
  name: string;
  description?: string | null;
  metadata?: Record<string, unknown>;
}

export interface EvidenceEdge {
  id: string;
  source_id: string;
  target_id: string;
  relation: string;
  confidence: number;
  references?: string[];
}

export interface EvidenceGraph {
  entities: EvidenceEntity[];
  edges: EvidenceEdge[];
}

export type HypothesisStatus =
  | 'draft'
  | 'under_review'
  | 'supported'
  | 'refuted'
  | 'deprecated';

export interface Hypothesis {
  id: string;
  program_id: string;
  text: string;
  claim_type: string;
  confidence: number;
  status: HypothesisStatus;
  version: number;
  supporting_evidence_count: number;
  contradicting_evidence_count: number;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface HypothesisVersion {
  version: number;
  text: string;
  confidence: number;
  created_at: ISODateString;
  author?: string;
}

export type AgentName =
  | 'TargetBiology'
  | 'Oncology'
  | 'EvidenceSynthesizer'
  | 'SimulationCritic'
  | string;

export type AgentRunStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface AgentRun {
  id: string;
  agent_name: AgentName;
  agent_role: string;
  run_type: string;
  output_summary: string;
  confidence: number;
  uncertainty_reason: string | null;
  recommended_next_step: string | null;
  status: AgentRunStatus;
  started_at: ISODateString;
  completed_at: ISODateString | null;
  program_id?: string;
  structured_output?: Record<string, unknown>;
  trace?: AgentTraceStep[];
}

export interface AgentTraceStep {
  step: number;
  kind: 'reasoning' | 'tool_call' | 'critique' | string;
  content: string;
  metadata?: Record<string, unknown>;
}

export type RiskSeverity = 'low' | 'medium' | 'high';

export interface RiskFlag {
  flag: string;
  severity: RiskSeverity;
  mitigation: string | null;
}

export type GuardianDecision =
  | 'approve'
  | 'request_revision'
  | 'escalate'
  | 'park'
  | 'kill'
  | 'promote_epistemicos';

export type GuardianReviewStatus = 'pending' | 'in_review' | 'decided';

export interface GuardianReview {
  id: string;
  review_type: string;
  entity_id: string;
  entity_type: string;
  decision: GuardianDecision | string;
  decision_rationale: string;
  risk_flags: RiskFlag[];
  reviewer_email: string;
  reviewed_at: ISODateString;
  is_final: boolean;
  status?: GuardianReviewStatus;
  program_id?: string;
}

export type CXUStatus = 'idle' | 'running' | 'paused' | 'terminated' | 'failed';

export interface CXU {
  id: string;
  name: string;
  zone_id: string;
  status: CXUStatus;
  iteration: number;
  latest_output: string | null;
  metrics?: Record<string, number>;
}

export type SimulationRunStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface SimulationRun {
  id: string;
  program_id: string;
  pipeline: string;
  status: SimulationRunStatus;
  started_at: ISODateString;
  completed_at: ISODateString | null;
  progress?: number;
  trace_url?: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}
