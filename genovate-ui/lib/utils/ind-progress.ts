import type {
  INDChecklistItem,
  INDReadinessResponse,
} from '@/lib/api/partnerability';

export interface INDProgressSummary {
  total: number;
  complete: number;
  /** Percentage 0–100, rounded to 1 decimal. */
  percentage: number;
  /** 'green' ≥80%, 'yellow' 50–79%, 'red' <50%. */
  level: 'green' | 'yellow' | 'red';
  /** Required items not yet complete. */
  criticalGaps: INDChecklistItem[];
  estimatedTimelineMonths?: number;
}

/**
 * Items in these statuses count as "complete" for progress purposes.
 * `waived` items are excluded from the *required* checklist but still
 * count as resolved for the overall completion percentage.
 */
const COMPLETED_STATUSES = new Set(['complete', 'waived']);

export function calculateINDProgress(
  response: INDReadinessResponse | null | undefined,
): INDProgressSummary {
  const items = response?.items ?? [];

  // Prefer agent-reported totals when items are not echoed back.
  const total =
    items.length > 0
      ? items.length
      : response?.items_total ?? 0;
  const complete =
    items.length > 0
      ? items.filter((i) => COMPLETED_STATUSES.has(i.status)).length
      : response?.items_complete ?? 0;

  const percentage = total > 0 ? Math.round((complete / total) * 1000) / 10 : 0;
  const level: INDProgressSummary['level'] =
    percentage >= 80 ? 'green' : percentage >= 50 ? 'yellow' : 'red';

  const criticalGaps = items.filter(
    (i) => i.is_required && !COMPLETED_STATUSES.has(i.status),
  );

  return {
    total,
    complete,
    percentage,
    level,
    criticalGaps,
    estimatedTimelineMonths: response?.estimated_timeline_months,
  };
}

/**
 * Group items by category for the optional category tabs / scrollable grid.
 */
export function groupItemsByCategory(
  items: INDChecklistItem[],
): Record<string, INDChecklistItem[]> {
  const out: Record<string, INDChecklistItem[]> = {};
  for (const item of items) {
    const k = item.category ?? 'other';
    (out[k] ??= []).push(item);
  }
  return out;
}
