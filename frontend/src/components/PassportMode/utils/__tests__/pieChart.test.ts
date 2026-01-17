import { describe, it, expect } from 'vitest';
import { buildPieSlices } from '../pieChart';

describe('pieChart', () => {
  it('builds slices that sum to ~100%', () => {
    const slices = buildPieSlices([
      { label: 'A', value: 1, color: '#000' },
      { label: 'B', value: 1, color: '#fff' },
    ]);

    const total = slices.reduce((sum, slice) => sum + slice.percentage, 0);
    expect(total).toBeCloseTo(100, 5);
    expect(slices.length).toBe(2);
    expect(slices[0].path.length).toBeGreaterThan(0);
  });
});
