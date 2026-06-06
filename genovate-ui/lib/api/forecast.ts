import { api } from './client';

/**
 * PR #11 — Clinical Forecaster API client.
 *
 * Mirrors the FastAPI endpoints in `Backend/app/api/forecast.py`:
 *
 *   POST   /forecast/clinical
 *   GET    /forecast/clinical/{forecast_id}
 *   POST   /forecast/clinical/{forecast_id}/guardian
 *   POST   /forecast/clinical/precedent
 *
 * Optional (Dashboard PR #5):
 *   GET    /forecast/clinical/{candidate_id}/history
 *
 * The history endpoint is not guaranteed to exist on every deployment; the
 * UI should gracefully degrade when it returns 404.
 */

export interface TrialDesign {
  enrollment?: number | null;
  duration_months?: number | null;
  statistical_power?: number | null;
  alpha?: number | null;
  endpoint?: string | null;
  patient_enrichment?: boolean | null;
  enrichment_criteria?: string | null;
  inclusion_criteria?: string | null;
  exclusion_criteria?: string | null;
  biomarker_stratification?: string | null;
}

export interface ScenarioOverride {
  name: string;
  factors: Record<string, number>;
}

export interface ForecastRequest {
  candidate_id: string;
  phase: string;
  primary_endpoint?: string | null;
  trial_design?: TrialDesign | null;
  known_safety_flags?: string[] | null;
  scenarios?: ScenarioOverride[] | null;
}

export interface ForecastDecomposition {
  biology_contribution?: number;
  safety_contribution?: number;
  design_contribution?: number;
  competition_contribution?: number;
  precedent_contribution?: number;
  [key: string]: number | undefined;
}

export interface TornadoDatum {
  factor: string;
  base: number;
  low: number;
  high: number;
  low_probability?: number;
  high_probability?: number;
  rationale?: string | null;
}

export interface ForecastSensitivity {
  tornado_data?: TornadoDatum[];
  notes?: string | null;
  [key: string]: unknown;
}

export interface ClinicalPrecedent {
  trial_id: string;
  similarity: number;
  outcome: 'success' | 'fail' | string;
  effect_size?: number | null;
  phase?: string | null;
  modality?: string | null;
  target?: string | null;
  disease?: string | null;
  title?: string | null;
  status?: string | null;
  enrollment?: number | null;
  start_date?: string | null;
  completion_date?: string | null;
  primary_endpoint?: string | null;
  secondary_endpoints?: string[] | null;
  inclusion_criteria_summary?: string | null;
  exclusion_criteria_summary?: string | null;
  publication_references?: string[] | null;
  similarity_breakdown?: Record<string, number> | null;
  weight?: number | null;
}

export interface ForecastResponse {
  forecast_id: string;
  candidate_id: string;
  phase: string;
  primary_endpoint?: string | null;
  probability: number;
  confidence_interval: [number | null, number | null];
  decomposition: ForecastDecomposition;
  sensitivity: ForecastSensitivity;
  scenarios?: Record<string, unknown>;
  factors?: Record<string, unknown>;
  weights?: Record<string, number>;
  verdict?: string | null;
  top_precedents: ClinicalPrecedent[];
  trace_id?: string;
  status?: string;
  sub_errors?: Record<string, string>;
  scenario_alternatives?: SavedScenario[];
}

export interface SavedScenario {
  id?: string;
  name: string;
  trial_design: TrialDesign;
  probability?: number | null;
  saved_at?: string | null;
}

export interface GuardianSubmission {
  reviewer_id: string;
  decision: string;
  decision_rationale: string;
}

export interface ForecastHistoryEvent {
  timestamp: string;
  probability: number;
  confidence_interval?: [number | null, number | null] | null;
  trigger?: string | null;
  description?: string | null;
  forecast_id?: string | null;
}

export interface ForecastHistoryResponse {
  candidate_id: string;
  events: ForecastHistoryEvent[];
}

export const forecastApi = {
  /** Always POST — request includes the trial_design payload. */
  clinical: (request: ForecastRequest) =>
    api.post<ForecastResponse>('/forecast/clinical', request),

  submitGuardian: (forecastId: string, body: GuardianSubmission) =>
    api.post<Record<string, unknown>>(
      `/forecast/clinical/${encodeURIComponent(forecastId)}/guardian`,
      body,
    ),

  /**
   * Forecast history (Dashboard PR #5). Backend may not expose this yet;
   * callers should treat a 404 as "no history available" rather than an
   * error.
   */
  history: (candidateId: string) =>
    api.get<ForecastHistoryResponse>(
      `/forecast/clinical/${encodeURIComponent(candidateId)}/history`,
    ),
};
