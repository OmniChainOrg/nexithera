import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  buildDecompositionSegments,
  clampProbability,
  decodeTrialDesign,
  encodeTrialDesign,
  filterPrecedents,
  formatConfidenceInterval,
  formatProbability,
  gaugeColor,
  paginate,
  sortTornadoData,
} from '@/lib/utils/clinical-forecast';
import type {
  ClinicalPrecedent,
  ForecastDecomposition,
  TornadoDatum,
} from '@/lib/api/forecast';

// ---------------------------------------------------------------------------
// Gauge color logic
// ---------------------------------------------------------------------------
describe('gaugeColor', () => {
  it('returns red/orange in the low band (0–0.4)', () => {
    expect(gaugeColor(0).band).toBe('low');
    expect(gaugeColor(0).stroke).toBe('#ef4444');
    expect(gaugeColor(0.3).band).toBe('low');
    expect(gaugeColor(0.3).stroke).toBe('#f97316');
    expect(gaugeColor(0.399).band).toBe('low');
  });

  it('returns amber in the medium band (0.4–0.7)', () => {
    expect(gaugeColor(0.4).band).toBe('medium');
    expect(gaugeColor(0.4).stroke).toBe('#f59e0b');
    expect(gaugeColor(0.6).stroke).toBe('#d97706');
    expect(gaugeColor(0.699).band).toBe('medium');
  });

  it('returns green/emerald in the high band (0.7–1)', () => {
    expect(gaugeColor(0.7).band).toBe('high');
    expect(gaugeColor(0.7).stroke).toBe('#10b981');
    expect(gaugeColor(0.9).stroke).toBe('#059669');
    expect(gaugeColor(1).band).toBe('high');
  });

  it('clamps NaN and out-of-range values into the low band', () => {
    expect(gaugeColor(NaN).band).toBe('low');
    expect(gaugeColor(-0.5).band).toBe('low');
    expect(gaugeColor(2).band).toBe('high');
  });
});

describe('clampProbability / formatters', () => {
  it('clamps probabilities into [0, 1]', () => {
    expect(clampProbability(-1)).toBe(0);
    expect(clampProbability(0)).toBe(0);
    expect(clampProbability(0.42)).toBeCloseTo(0.42);
    expect(clampProbability(1.7)).toBe(1);
    expect(clampProbability(NaN)).toBe(0);
  });

  it('formats probability as a percentage', () => {
    expect(formatProbability(0.62)).toBe('62%');
    expect(formatProbability(0.62, 1)).toBe('62.0%');
    expect(formatProbability(1.2)).toBe('100%');
  });

  it('formats a confidence interval into the spec string', () => {
    expect(formatConfidenceInterval([0.48, 0.74])).toBe('95% CI: 48% – 74%');
    expect(formatConfidenceInterval(null)).toBeNull();
    expect(formatConfidenceInterval([null, 0.5])).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Decomposition bars
// ---------------------------------------------------------------------------
describe('buildDecompositionSegments', () => {
  const decomposition: ForecastDecomposition = {
    biology_contribution: 0.25,
    safety_contribution: 0.1,
    design_contribution: 0.12,
    competition_contribution: 0.05,
    precedent_contribution: 0.1,
  };

  it('returns a segment per non-zero contributor with the spec colour', () => {
    const { segments, totalContribution } = buildDecompositionSegments(decomposition, 0.62);
    expect(segments.map((s) => s.key)).toEqual([
      'biology_contribution',
      'safety_contribution',
      'design_contribution',
      'competition_contribution',
      'precedent_contribution',
    ]);
    expect(segments[0].color).toBe('#3b82f6');
    expect(totalContribution).toBeCloseTo(0.62);
  });

  it('fills the remainder up to 1.0 with the uncertainty segment', () => {
    const { uncertaintyContribution } = buildDecompositionSegments(decomposition, 0.62);
    expect(uncertaintyContribution).toBeCloseTo(1 - 0.62, 3);
  });

  it('uses the contribution sum when it exceeds the headline probability', () => {
    const { uncertaintyContribution } = buildDecompositionSegments(
      { biology_contribution: 0.6, safety_contribution: 0.3 },
      0.5,
    );
    expect(uncertaintyContribution).toBeCloseTo(0.1, 3);
  });

  it('drops zero / non-finite contributions and tolerates missing data', () => {
    const { segments, uncertaintyContribution } = buildDecompositionSegments(
      { biology_contribution: 0, safety_contribution: Number.NaN },
      0,
    );
    expect(segments).toEqual([]);
    expect(uncertaintyContribution).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// Tornado plot
// ---------------------------------------------------------------------------
describe('sortTornadoData', () => {
  const rows: TornadoDatum[] = [
    { factor: 'a', base: 0.5, low: 0.45, high: 0.55 }, // impact 0.10
    { factor: 'b', base: 0.5, low: 0.2, high: 0.8 }, // impact 0.60
    { factor: 'c', base: 0.5, low: 0.4, high: 0.7 }, // impact 0.30
  ];

  it('sorts descending by |high − low|', () => {
    const sorted = sortTornadoData(rows);
    expect(sorted.map((r) => r.factor)).toEqual(['b', 'c', 'a']);
    expect(sorted[0].impact).toBeCloseTo(0.6);
  });

  it('is stable for equal impact', () => {
    const sorted = sortTornadoData([
      { factor: 'x', base: 0, low: 0.1, high: 0.3 },
      { factor: 'y', base: 0, low: 0.4, high: 0.6 },
    ]);
    expect(sorted.map((r) => r.factor)).toEqual(['x', 'y']);
  });

  it('returns [] for missing input', () => {
    expect(sortTornadoData(null)).toEqual([]);
    expect(sortTornadoData([])).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Precedent filtering / paging
// ---------------------------------------------------------------------------
function precedent(p: Partial<ClinicalPrecedent>): ClinicalPrecedent {
  return {
    trial_id: 'NCT0000000',
    similarity: 0.5,
    outcome: 'success',
    effect_size: 0.2,
    phase: 'II',
    modality: 'small_molecule',
    target: 'KRAS G12C',
    disease: 'NSCLC',
    ...p,
  };
}

describe('filterPrecedents', () => {
  const data: ClinicalPrecedent[] = [
    precedent({ trial_id: 'NCT001', similarity: 0.9, outcome: 'success' }),
    precedent({ trial_id: 'NCT002', similarity: 0.7, outcome: 'fail' }),
    precedent({ trial_id: 'NCT003', similarity: 0.8, outcome: 'success', phase: 'III' }),
    precedent({ trial_id: 'NCT004', similarity: 0.6, outcome: 'failure' }),
  ];

  it('filters by outcome=success', () => {
    const r = filterPrecedents(data, { outcome: 'success' });
    expect(r.map((x) => x.trial_id)).toEqual(['NCT001', 'NCT003']);
  });

  it('treats `fail` and `failure` outcomes as failures', () => {
    const r = filterPrecedents(data, { outcome: 'fail' });
    expect(r.map((x) => x.trial_id).sort()).toEqual(['NCT002', 'NCT004']);
  });

  it('filters by phase', () => {
    const r = filterPrecedents(data, { phase: 'III' });
    expect(r).toHaveLength(1);
    expect(r[0].trial_id).toBe('NCT003');
  });

  it('searches across trial id, target, disease, and modality fields', () => {
    const r = filterPrecedents(data, { search: 'nct002' });
    expect(r).toHaveLength(1);
    expect(r[0].trial_id).toBe('NCT002');
  });

  it('sorts by similarity descending by default', () => {
    const r = filterPrecedents(data);
    expect(r.map((x) => x.trial_id)).toEqual(['NCT001', 'NCT003', 'NCT002', 'NCT004']);
  });

  it('sorts by effect_size ascending when requested', () => {
    const r = filterPrecedents(
      [
        precedent({ trial_id: 'A', effect_size: 0.5 }),
        precedent({ trial_id: 'B', effect_size: 0.1 }),
        precedent({ trial_id: 'C', effect_size: 0.9 }),
      ],
      { sortBy: 'effect_size', sortDirection: 'asc' },
    );
    expect(r.map((x) => x.trial_id)).toEqual(['B', 'A', 'C']);
  });
});

describe('paginate', () => {
  it('returns the requested slice', () => {
    const rows = Array.from({ length: 23 }, (_, i) => i);
    expect(paginate(rows, 1, 10)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    expect(paginate(rows, 3, 10)).toEqual([20, 21, 22]);
  });

  it('clamps invalid page sizes', () => {
    const rows = [1, 2, 3];
    expect(paginate(rows, 0, 0)).toEqual([1]);
  });
});

// ---------------------------------------------------------------------------
// Trial design encode/decode (shareable URLs)
// ---------------------------------------------------------------------------
describe('encodeTrialDesign / decodeTrialDesign', () => {
  it('roundtrips a trial design', () => {
    const design = { enrollment: 200, statistical_power: 0.85, alpha: 0.05 };
    const token = encodeTrialDesign(design);
    expect(typeof token).toBe('string');
    expect(decodeTrialDesign(token)).toEqual(design);
  });

  it('returns null for malformed tokens', () => {
    expect(decodeTrialDesign('@@not-base64@@')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Debounced scenario explorer → API call
// ---------------------------------------------------------------------------
import { renderHook, act } from '@testing-library/react';
import { useDebouncedValue } from '@/lib/hooks/use-debounced-value';

describe('useDebouncedValue', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('emits the latest value only after the debounce window', () => {
    const { result, rerender } = renderHook(({ v }) => useDebouncedValue(v, 500), {
      initialProps: { v: 'a' },
    });
    expect(result.current).toBe('a');

    rerender({ v: 'b' });
    rerender({ v: 'c' });
    expect(result.current).toBe('a');

    act(() => {
      vi.advanceTimersByTime(499);
    });
    expect(result.current).toBe('a');

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe('c');
  });
});
