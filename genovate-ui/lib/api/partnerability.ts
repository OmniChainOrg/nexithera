import { api } from './client';

/**
 * PR #10 — Partnerability + IND Readiness API client.
 *
 * Mirrors the FastAPI endpoints in `Backend/app/api/analysis.py`:
 *
 *   POST   /analysis/competitive-landscape
 *   POST   /analysis/ip-position
 *   POST   /analysis/ind-readiness
 *   POST   /analysis/partnerability
 *   POST   /analysis/ind-checklist/{candidate_id}/{item_id}
 */

export type CompetitorThreatLevel = 'low' | 'medium' | 'high';

export interface CompetitorEntry {
  id?: string;
  asset_name: string;
  developer?: string | null;
  phase?: string | null;
  modality?: string | null;
  mechanism?: string | null;
  estimated_launch_year?: number | null;
  differentiation?: string | null;
  threat_level?: CompetitorThreatLevel;
  source?: string | null;
  source_ref?: string | null;
  confidence?: number | null;
}

export interface CompetitiveLandscapeResponse {
  run_id: string;
  candidate_id: string;
  competitors: CompetitorEntry[];
  competitive_moat_score?: number;
  summary?: string;
  recommended_next_step?: string;
}

export interface IPPositionEntry {
  id?: string;
  patent_number?: string | null;
  patent_family?: string | null;
  assignee?: string | null;
  expiry_year?: number | null;
  jurisdiction?: string | null;
  claims?: string | null;
  is_blocking: boolean;
  freedom_to_operate_estimate?: number | null;
}

export interface IPPositionResponse {
  run_id: string;
  candidate_id: string;
  positions: IPPositionEntry[];
  ip_strength_score?: number;
  freedom_to_operate_estimate?: number;
  blocking_count?: number;
  white_space_count?: number;
  summary?: string;
  recommended_next_step?: string;
}

export type INDStatus =
  | 'not_started'
  | 'in_progress'
  | 'complete'
  | 'waived'
  | 'failed';

export type INDCategory =
  | 'CMC'
  | 'nonclinical_tox'
  | 'clinical_protocol'
  | 'regulatory'
  | 'gmp';

export interface INDChecklistItem {
  item_id: string;
  category: INDCategory;
  item: string;
  description?: string | null;
  is_required: boolean;
  status: INDStatus;
  evidence_uri?: string | null;
  notes?: string | null;
  updated_at?: string | null;
}

export interface INDReadinessResponse {
  run_id: string;
  candidate_id: string;
  overall_readiness?: number;
  ind_readiness_score?: number;
  items_complete?: number;
  items_total?: number;
  critical_gaps: string[];
  estimated_timeline_months?: number;
  by_category?: Record<string, { total: number; complete: number; required: number }>;
  items?: INDChecklistItem[];
  summary?: string;
  recommended_next_step?: string;
}

export interface PotentialPartner {
  name: string;
  fit_score: number;
  focus_overlap?: boolean;
  rationale: string;
}

export interface PartnerabilityResponse {
  id: string;
  run_id: string;
  candidate_id: string;
  overall_score: number;
  competitive_moat: number;
  ip_strength: number;
  unmet_need: number;
  ind_readiness: number;
  bd_interest_estimate?: number;
  potential_partners: PotentialPartner[];
  verdict: string;
  summary?: string;
  recommended_next_step?: string;
  sub_errors?: Record<string, string>;
  competitive_landscape?: CompetitiveLandscapeResponse;
  ip_position?: IPPositionResponse;
  ind_readiness_assessment?: INDReadinessResponse;
}

export interface UpdateINDChecklistInput {
  status: INDStatus;
  evidence_uri?: string | null;
  notes?: string | null;
  updated_by?: string | null;
}

export const partnerabilityApi = {
  competitiveLandscape: (candidate_id: string) =>
    api.post<CompetitiveLandscapeResponse>(
      '/analysis/competitive-landscape',
      { candidate_id },
    ),
  ipPosition: (candidate_id: string) =>
    api.post<IPPositionResponse>('/analysis/ip-position', { candidate_id }),
  indReadiness: (candidate_id: string) =>
    api.post<INDReadinessResponse>('/analysis/ind-readiness', { candidate_id }),
  partnerability: (candidate_id: string, assessed_by?: string) =>
    api.post<PartnerabilityResponse>('/analysis/partnerability', {
      candidate_id,
      ...(assessed_by ? { assessed_by } : {}),
    }),
  updateChecklistItem: (
    candidate_id: string,
    item_id: string,
    input: UpdateINDChecklistInput,
  ) =>
    api.post<{
      id: string;
      candidate_id: string;
      checklist_item_id: string;
      status: INDStatus;
      evidence_uri?: string | null;
      notes?: string | null;
      updated_at?: string | null;
    }>(
      `/analysis/ind-checklist/${encodeURIComponent(candidate_id)}/${encodeURIComponent(item_id)}`,
      input,
    ),
};
