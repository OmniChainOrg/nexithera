import { describe, expect, it } from 'vitest';
import { formatPercent, formatScore, titleCase } from '@/lib/utils/formatters';

describe('formatPercent', () => {
  it('formats 0..1 as percent', () => {
    expect(formatPercent(0.5)).toBe('50%');
    expect(formatPercent(0.123, 1)).toBe('12.3%');
  });
});

describe('formatScore', () => {
  it('returns em dash for missing values', () => {
    expect(formatScore(undefined)).toBe('—');
    expect(formatScore(null)).toBe('—');
  });
  it('formats to 2 decimals', () => {
    expect(formatScore(0.4567)).toBe('0.46');
  });
});

describe('titleCase', () => {
  it('replaces underscores and capitalises', () => {
    expect(titleCase('evidence_map')).toBe('Evidence Map');
    expect(titleCase('guardian_review')).toBe('Guardian Review');
  });
});
