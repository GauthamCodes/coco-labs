// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// G2.9 (Gautham's review of the real-phone results): the inset's legend lists only lines that are drawn.

import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MIN_DRIVE_M, PlannerInset, pathLength, type InsetData } from '../src/game/hud/PlannerInset';

const map = { width: 4, height: 4, resolution: 1, origin: [0, 0] as [number, number] };
const base: InsetData = { map, occupancy: new Uint8Array(16), planned: [[[0, 0], [3, 0], [3, 3]]], driven: [] };

describe('results inset legend', () => {
  it('measures a drive along its polyline', () => {
    expect(pathLength([[0, 0], [3, 0], [3, 4]])).toBe(7);
    expect(pathLength([])).toBe(0);
  });

  it('a drive shorter than MIN_DRIVE_M is no legend line; its length is said instead', () => {
    const html = renderToStaticMarkup(<PlannerInset d={{ ...base, driven: [[1, 1], [1.1, 1]] }} still />);
    expect(html).not.toContain('your drive');
    expect(html).toContain('COCO drove 0.1 m');
    expect(html).toContain('A* route for each order');
  });

  it('a real drive is listed', () => {
    const html = renderToStaticMarkup(<PlannerInset d={{ ...base, driven: [[0, 0], [MIN_DRIVE_M + 1, 0]] }} still />);
    expect(html).toContain('your drive');
  });

  it('no planned route: no planner legend line', () => {
    const html = renderToStaticMarkup(<PlannerInset d={{ ...base, planned: [], driven: [[0, 0], [2, 0]] }} still />);
    expect(html).not.toContain('A* route');
  });
});
