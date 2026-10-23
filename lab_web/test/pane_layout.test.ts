// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { paneLayout } from '../src/ui/reference/paneLayout';

describe('one-context scissor layout', () => {
  it.each([1, 2, 4] as const)('tiles the complete viewport with %i panes', (count) => {
    for (const [width, height] of [[1440, 900], [915, 412], [412, 915]]) {
      const panes = paneLayout(count, width, height);
      expect(panes).toHaveLength(count);
      expect(panes.reduce((area, p) => area + p.width * p.height, 0)).toBeCloseTo(width * height);
      for (const p of panes) {
        expect(p.left).toBeGreaterThanOrEqual(0);
        expect(p.bottom).toBeGreaterThanOrEqual(0);
        expect(p.left + p.width).toBeLessThanOrEqual(width);
        expect(p.bottom + p.height).toBeLessThanOrEqual(height);
        for (const other of panes.filter((item) => item !== p)) {
          const overlapWidth = Math.min(p.left + p.width, other.left + other.width) - Math.max(p.left, other.left);
          const overlapHeight = Math.min(p.bottom + p.height, other.bottom + other.height) - Math.max(p.bottom, other.bottom);
          expect(overlapWidth <= 0 || overlapHeight <= 0).toBe(true);
        }
      }
      if (width < height) {
        expect(panes.every((p) => p.width === width && p.left === 0)).toBe(true);
        expect(panes[0].bottom).toBeGreaterThanOrEqual(panes.at(-1)!.bottom);
      }
    }
  });
});
