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
