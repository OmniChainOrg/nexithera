/**
 * Pure utilities for the Clinical Forecast tab (Dashboard PR #5).
 *
 * Kept free of React / DOM imports so they can be unit-tested directly with
 * Vitest and shared between the gauge, decomposition bars, tornado plot and
 * precedent browser.
 */

import type {
  ClinicalPrecedent,
  ForecastDecomposition,
  TornadoDatum,
  TrialDesign,
} from '@/lib/api/forecast';

// ---------------------------------------------------------------------------
// Gauge color logic
// ---------------------------------------------------------------------------

export type ForecastBand = 'low' | 'medium' | 'high';

export interface GaugeColor {
  band: ForecastBand;
  /** Hex string used by SVG strokes / Tailwind arbitrary values. */
  stroke: string;
  /** Tailwind text color class for the % label. */
  textClass: string;
  /** Tailwind ring/border class for tooltips and rings. */
  ringClass: string;
}

/**
 * Map a probability in [0, 1] to the spec color band:
 *   • 0.0–0.4  → red→orange (low)
 *   • 0.4–0.7  → yellow→amber (medium)
 *   • 0.7–1.0  → green→emerald (high)
 *
 * NaN, negative and >1 values clamp to the nearest band so the gauge never
 * renders without a color.
 */
export function gaugeColor(probability: number): GaugeColor {
  const p = clampProbability(probability);
  if (p < 0.4) {
    return {
      band: 'low',
      stroke: p < 0.2 ? '#ef4444' : '#f97316',
      textClass: 'text-red-500 dark:text-red-400',
      ringClass: 'ring-red-500/40',
    };
  }
  if (p < 0.7) {
    return {
      band: 'medium',
      stroke: p < 0.55 ? '#f59e0b' : '#d97706',
      textClass: 'text-amber-500 dark:text-amber-400',
      ringClass: 'ring-amber-500/40',
    };
  }
  return {
    band: 'high',
    stroke: p < 0.85 ? '#10b981' : '#059669',
    textClass: 'text-emerald-500 dark:text-emerald-400',
    ringClass: 'ring-emerald-500/40',
  };
}

export function clampProbability(p: number): number {
  if (Number.isNaN(p) || !Number.isFinite(p)) return 0;
  if (p < 0) return 0;
  if (p > 1) return 1;
  return p;
}

export function formatProbability(p: number, digits = 0): string {
  return `${(clampProbability(p) * 100).toFixed(digits)}%`;
}

export function formatConfidenceInterval(
  ci: readonly [number | null | undefined, number | null | undefined] | null | undefined,
  confidenceLevel = 95,
): string | null {
  if (!ci) return null;
  const [lo, hi] = ci;
  if (lo == null || hi == null) return null;
  return `${confidenceLevel}% CI: ${formatProbability(lo)} – ${formatProbability(hi)}`;
}

// ---------------------------------------------------------------------------
// Decomposition bars
// ---------------------------------------------------------------------------

export interface DecompositionSegment {
  key: string;
  label: string;
  contribution: number;
  color: string;
}

export const DECOMPOSITION_COLORS: Record<string, { label: string; color: string }> = {
  biology_contribution: { label: 'Biology', color: '#3b82f6' },
  safety_contribution: { label: 'Safety', color: '#f97316' },
  design_contribution: { label: 'Design', color: '#8b5cf6' },
  competition_contribution: { label: 'Competition', color: '#ef4444' },
  precedent_contribution: { label: 'Precedent', color: '#10b981' },
};

export const DECOMPOSITION_UNCERTAINTY_COLOR = 'rgba(148, 163, 184, 0.3)';

/**
 * Project a decomposition payload into the stacked-bar series expected by the
 * UI. The total of all returned `contribution` values plus
 * `uncertaintyContribution` always equals 1.0 (modulo floating-point noise),
 * even when individual contributions are missing or sum past the supplied
 * probability — that lets the visualisation always render a full-width bar
 * with the gray "Other / uncertainty" segment filling the remainder.
 */
export function buildDecompositionSegments(
  decomposition: ForecastDecomposition | null | undefined,
  probability: number,
): {
  segments: DecompositionSegment[];
  uncertaintyContribution: number;
  totalContribution: number;
} {
  const segments: DecompositionSegment[] = [];
  let total = 0;
  for (const [key, meta] of Object.entries(DECOMPOSITION_COLORS)) {
    const raw = decomposition?.[key];
    const value = typeof raw === 'number' && Number.isFinite(raw) ? Math.max(0, raw) : 0;
    if (value === 0) continue;
    total += value;
    segments.push({
      key,
      label: meta.label,
      contribution: value,
      color: meta.color,
    });
  }
  // Anchor the bar to the larger of the contribution sum or the headline
  // probability. If the agents over-contribute we trust the explicit sum;
  // otherwise we treat the gap to `probability` as additional explained-but-
  // unattributed signal and the gap to 1.0 as uncertainty.
  const probabilityClamped = clampProbability(probability);
  const anchor = Math.max(total, probabilityClamped);
  const uncertainty = Math.max(0, 1 - anchor);
  return {
    segments,
    uncertaintyContribution: uncertainty,
    totalContribution: total,
  };
}

// ---------------------------------------------------------------------------
// Tornado plot
// ---------------------------------------------------------------------------

export interface TornadoRow extends TornadoDatum {
  impact: number;
}

/**
 * Sort tornado data by absolute impact (|high - low|) descending. Stable for
 * ties so factor ordering is deterministic in snapshots / tests.
 */
export function sortTornadoData(rows: readonly TornadoDatum[] | null | undefined): TornadoRow[] {
  if (!rows || rows.length === 0) return [];
  return rows
    .map((row, idx) => ({
      ...row,
      impact: Math.abs((row.high ?? 0) - (row.low ?? 0)),
      _idx: idx,
    }))
    .sort((a, b) => {
      if (b.impact !== a.impact) return b.impact - a.impact;
      return a._idx - b._idx;
    })
    .map(({ _idx, ...rest }) => rest);
}

// ---------------------------------------------------------------------------
// Precedent browser
// ---------------------------------------------------------------------------

export type PrecedentOutcomeFilter = 'all' | 'success' | 'fail';

export type PrecedentSortKey = 'similarity' | 'effect_size';

export interface PrecedentFilterOptions {
  search?: string;
  outcome?: PrecedentOutcomeFilter;
  phase?: string | 'all';
  modality?: string | 'all';
  sortBy?: PrecedentSortKey;
  sortDirection?: 'asc' | 'desc';
}

const TEXT_FIELDS: (keyof ClinicalPrecedent)[] = [
  'trial_id',
  'target',
  'disease',
  'modality',
  'title',
];

export function filterPrecedents(
  precedents: readonly ClinicalPrecedent[] | null | undefined,
  options: PrecedentFilterOptions = {},
): ClinicalPrecedent[] {
  const list = precedents ? [...precedents] : [];
  const {
    search = '',
    outcome = 'all',
    phase = 'all',
    modality = 'all',
    sortBy = 'similarity',
    sortDirection = 'desc',
  } = options;

  const q = search.trim().toLowerCase();

  const filtered = list.filter((row) => {
    if (outcome !== 'all') {
      const o = (row.outcome ?? '').toString().toLowerCase();
      if (outcome === 'success' && o !== 'success') return false;
      if (outcome === 'fail' && !(o === 'fail' || o === 'failure')) return false;
    }
    if (phase !== 'all' && (row.phase ?? '').toString() !== phase) return false;
    if (modality !== 'all' && (row.modality ?? '').toString() !== modality) return false;
    if (q) {
      const hay = TEXT_FIELDS.map((k) => (row[k] ?? '').toString().toLowerCase()).join(' ');
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  filtered.sort((a, b) => {
    const av = (a[sortBy] ?? 0) as number;
    const bv = (b[sortBy] ?? 0) as number;
    return sortDirection === 'asc' ? av - bv : bv - av;
  });

  return filtered;
}

export function paginate<T>(rows: readonly T[], page: number, pageSize: number): T[] {
  const safePageSize = Math.max(1, pageSize);
  const safePage = Math.max(1, page);
  const start = (safePage - 1) * safePageSize;
  return rows.slice(start, start + safePageSize);
}

// ---------------------------------------------------------------------------
// Trial design serialization for shareable URLs
// ---------------------------------------------------------------------------

export function encodeTrialDesign(design: TrialDesign): string {
  // base64url-encode JSON to keep URLs short and forwards-compatible.
  const json = JSON.stringify(design);
  if (typeof btoa === 'function') {
    return btoa(unescape(encodeURIComponent(json)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  }
  // Node.js / SSR fallback.
  return Buffer.from(json, 'utf-8').toString('base64url');
}

export function decodeTrialDesign(token: string): TrialDesign | null {
  try {
    const padded = token.replace(/-/g, '+').replace(/_/g, '/');
    const json =
      typeof atob === 'function'
        ? decodeURIComponent(escape(atob(padded)))
        : Buffer.from(token, 'base64url').toString('utf-8');
    const parsed = JSON.parse(json);
    return parsed && typeof parsed === 'object' ? (parsed as TrialDesign) : null;
  } catch {
    return null;
  }
}
