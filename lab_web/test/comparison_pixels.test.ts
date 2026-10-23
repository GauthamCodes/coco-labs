// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { expect, it } from 'vitest';
import { comparisonPixels } from '../src/ui/reference/comparisonPixels';
import { PlanStore, CLOSED, PATH } from '../src/arena/render/planStore';
it('keeps north-first costs aligned with the floor texture and draws band contours', () => {
  const store = new PlanStore(2, 2), occupancy = new Uint8Array(4);
  const grid = new Uint8Array([254, 253, 0, 100]);
  const costs = { static: grid, inflation: grid, obstacle: grid, combined: grid };
  const pixels = comparisonPixels(2, 2, occupancy, store, 'dark', costs);
  expect(pixels[3]).toBe(0); // bottom-left free cell from row 1
  expect(pixels[11]).toBe(255); // top-left lethal contour
  expect(pixels[15]).toBe(120); // top-right alternating inscribed contour
  expect(pixels[7]).toBe(210); // continuous inflation
});
it('difference uses actual expanded history even when a cell becomes a path', () => {
  const a = new PlanStore(3, 1), b = new PlanStore(3, 1);
  a.order[0] = 0; a.state[0] = CLOSED; a.order[2] = 1; a.state[2] = PATH; b.order[1] = 0; b.state[1] = CLOSED;
  const pixels = comparisonPixels(3, 1, new Uint8Array(3), a, 'dark', undefined, 'combined', [a, b]);
  expect(pixels[3]).toBe(230); expect(pixels[7]).toBe(65); expect(pixels[11]).toBe(255);
  expect([...pixels.slice(0, 3)]).toEqual([...pixels.slice(4, 7)]);
  expect([...pixels.slice(0, 3)]).not.toEqual([...pixels.slice(8, 11)]);
});

// Retained M5.7 presentation is the byte oracle, including transparent RGB.
import { comparisonPixels as original } from './reference/comparison_pixels_m57';
import { comparisonBasePixels } from '../src/ui/reference/comparisonPixels';
it('matches the previous pixels across all costs, themes, trace states and difference patterns', () => {
  let seed = 23; const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) >>> 8);
  for (const [width, height] of [[1, 1], [1, 256], [256, 1], [19, 29]]) {
    const n = width * height, occupancy = Uint8Array.from({ length: n }, () => random() % 2);
    const grid = Uint8Array.from({ length: n }, (_, i) => i % 256);
    const costs = { static: grid, inflation: grid, obstacle: grid, combined: grid };
    const a = new PlanStore(width, height), b = new PlanStore(width, height);
    for (let i = 0; i < n; i++) { a.state[i] = random() % 4; b.state[i] = random() % 4; a.order[i] = random() % 3 - 1; b.order[i] = random() % 3 - 1; }
    for (const theme of ['dark', 'light'] as const) for (const data of [costs, undefined]) for (const difference of [undefined, [a, b] as [PlanStore, PlanStore]]) {
      const base = comparisonBasePixels(width, height, occupancy, theme, data);
      expect(comparisonPixels(width, height, occupancy, a, theme, data, 'combined', difference, new Uint8Array(n * 4).fill(42), base)).toEqual(original(width, height, occupancy, a, theme, data, 'combined', difference));
    }
  }
});
