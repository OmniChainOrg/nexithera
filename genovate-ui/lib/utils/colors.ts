import type { CandidateStatus, EntityType } from '@/lib/types/genovate';

/**
 * Map of CandidateStatus -> Tailwind background utility class.
 * These reference the custom Tailwind tokens defined in `tailwind.config.js`.
 */
export const candidateStatusBg: Record<CandidateStatus, string> = {
  idea: 'bg-idea',
  evidence_map: 'bg-evidence-map',
  hypothesis: 'bg-hypothesis',
  candidate: 'bg-candidate',
  simulation: 'bg-simulation',
  guardian_review: 'bg-guardian-review',
  promoted: 'bg-promoted',
  killed: 'bg-killed',
  parked: 'bg-parked',
};

export const candidateStatusText: Record<CandidateStatus, string> = {
  idea: 'text-idea',
  evidence_map: 'text-evidence-map',
  hypothesis: 'text-hypothesis',
  candidate: 'text-candidate',
  simulation: 'text-simulation',
  guardian_review: 'text-guardian-review',
  promoted: 'text-promoted',
  killed: 'text-killed',
  parked: 'text-parked',
};

export const candidateStatusOrder: CandidateStatus[] = [
  'idea',
  'evidence_map',
  'hypothesis',
  'candidate',
  'simulation',
  'guardian_review',
  'promoted',
  'killed',
  'parked',
];

export function entityColor(entityType: EntityType): string {
  switch (entityType) {
    case 'gene':
      return '#3b82f6';
    case 'disease':
      return '#ef4444';
    case 'compound':
      return '#10b981';
    case 'pathway':
      return '#8b5cf6';
    case 'assay':
      return '#f59e0b';
    default:
      return '#64748b';
  }
}

export function confidenceTier(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= 0.75) return 'high';
  if (confidence >= 0.4) return 'medium';
  return 'low';
}

export function confidenceColor(confidence: number): string {
  const tier = confidenceTier(confidence);
  if (tier === 'high') return '#10b981';
  if (tier === 'medium') return '#f59e0b';
  return '#ef4444';
}
