import { describe, expect, it } from 'vitest';
import { qualityToColor } from '@/lib/utils/heatmap';

describe('qualityToColor', () => {
  it('maps endpoints and midpoint to the expected palette', () => {
    expect(qualityToColor(0)).toBe('#ef4444');
    expect(qualityToColor(0.5)).toBe('#f59e0b');
    expect(qualityToColor(1)).toBe('#10b981');
  });

  it('clamps values outside 0..1', () => {
    expect(qualityToColor(-1)).toBe('#ef4444');
    expect(qualityToColor(2)).toBe('#10b981');
  });
});
