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

export interface DiscoveredTarget {
  id?: string;
  rank: number;
  target_id?: string;
  target_name: string;
  opportunity_score: number;
  confidence: number;
  proposed_hypothesis: string;
  rationale?: string;
  run_id?: string;
  program_id?: string;
  created_at?: ISODateString;
}

export interface DiscoverTargetsRequest {
  program_id: string;
  max_results?: number;
  therapeutic_area?: string;
}

export interface DiscoverTargetsResponse {
  run_id: string;
  program_id: string;
  targets: DiscoveredTarget[];
  generated_at: ISODateString;
}

export interface EvidenceGap {
  id?: string;
  target_id: string;
  target_name: string;
  disease_id: string;
  disease_name: string;
  evidence_quality: number;
  severity: number;
  gap_type: 'missing_edge' | 'low_confidence' | 'contradiction' | string;
  proposed_experiment_id?: string | null;
  details?: string;
}

export interface GapAnalysisRequest {
  program_id: string;
  min_severity?: number;
}

export interface GapAnalysisResponse {
  program_id: string;
  gaps: EvidenceGap[];
  targets: { id: string; name: string }[];
  diseases: { id: string; name: string }[];
  generated_at: ISODateString;
}

export type ProposedExperimentStatus = 'proposed' | 'in_progress' | 'completed' | 'cancelled' | 'dismissed';

export interface ProposedExperiment {
  id: string;
  description: string;
  information_gain: number;
  cost: number;
  duration_days: number;
  priority: number;
  status: ProposedExperimentStatus;
  if_positive?: string;
  if_negative?: string;
  target_id?: string;
  hypothesis_id?: string;
  program_id?: string;
  created_at: ISODateString;
  updated_at?: ISODateString;
}

export interface NextExperimentsRequest {
  program_id: string;
  limit?: number;
  target_id?: string;
}

export interface ExperimentOutcome {
  experiment_id: string;
  result: 'positive' | 'negative' | 'inconclusive';
  observed_confidence_delta?: number;
  notes?: string;
}

export interface BeliefTimelinePoint {
  timestamp: ISODateString;
  confidence: number;
  uncertainty_low?: number;
  uncertainty_high?: number;
  experiment_id?: string;
  experiment_name?: string;
  outcome?: 'positive' | 'negative' | 'inconclusive';
  confidence_delta?: number;
  agent_run_id?: string;
}

export interface BeliefTimeline {
  entity_id: string;
  entity_type: 'candidate' | 'hypothesis';
  points: BeliefTimelinePoint[];
}

export type GuardianBulkAction = 'approve' | 'kill' | 'park';

export interface GuardianBulkRequest {
  action: GuardianBulkAction;
  review_ids: string[];
  note?: string;
}

export interface GuardianBulkResponse {
  approved_count: number;
  killed_count: number;
  parked_count: number;
  failed_ids: string[];
}
