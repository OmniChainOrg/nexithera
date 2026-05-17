import { describe, expect, it } from 'vitest';
import { confidenceTier, confidenceColor, entityColor } from '@/lib/utils/colors';

describe('confidenceTier', () => {
  it('classifies high confidence', () => {
    expect(confidenceTier(0.9)).toBe('high');
  });
  it('classifies medium confidence', () => {
    expect(confidenceTier(0.5)).toBe('medium');
  });
  it('classifies low confidence', () => {
    expect(confidenceTier(0.1)).toBe('low');
  });
});

describe('confidenceColor', () => {
  it('returns green for high, yellow for medium, red for low', () => {
    expect(confidenceColor(0.95)).toBe('#10b981');
    expect(confidenceColor(0.5)).toBe('#f59e0b');
    expect(confidenceColor(0.1)).toBe('#ef4444');
  });
});

describe('entityColor', () => {
  it('returns expected hex for known types', () => {
    expect(entityColor('gene')).toBe('#3b82f6');
    expect(entityColor('disease')).toBe('#ef4444');
    expect(entityColor('compound')).toBe('#10b981');
    expect(entityColor('pathway')).toBe('#8b5cf6');
    expect(entityColor('assay')).toBe('#f59e0b');
  });
  it('falls back to slate for unknown types', () => {
    expect(entityColor('unknown' as never)).toBe('#64748b');
  });
});
