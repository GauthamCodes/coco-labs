// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
// The tactical map's view limits (Gautham, 2026-10-25: zooming out and dragging lost the level
// off-screen and the whole screen looked black): zoom out stops where the whole level fits, the
// centre stays on the level, and a tap off the level sends no goal.
import { describe, expect, it } from 'vitest';
import { clampView, fitMpp, levelBounds, MIN_MPP, onLevel } from '../src/game/hud/Maps';
import type { World } from '../src/arena/protocol';

const depot = { width: 480, height: 320, resolution: 0.1, origin: [0, 0] } as unknown as World;

describe('tactical map view', () => {
  it('fits the whole 48 x 32 m level at the widest zoom', () => {
    expect(levelBounds(depot)).toEqual({ x0: 0, y0: 0, x1: 48, y1: 32 });
    const m = fitMpp(depot, 1440, 900);
    expect(48 / m).toBeLessThanOrEqual(1440);
    expect(32 / m).toBeLessThanOrEqual(900);
    expect(clampView({ cx: 10, cy: 10, mpp: 99 }, depot, 1440, 900).mpp).toBeCloseTo(m, 12);
    expect(clampView({ cx: 10, cy: 10, mpp: 0 }, depot, 1440, 900).mpp).toBe(MIN_MPP);
  });
  it('never lets the level leave the screen when dragged', () => {
    expect(clampView({ cx: -500, cy: 900, mpp: 0.06 }, depot, 1440, 900)).toMatchObject({ cx: 0, cy: 32 });
    expect(clampView({ cx: 23, cy: 6, mpp: 0.03 }, depot, 1440, 900)).toEqual({ cx: 23, cy: 6, mpp: 0.03 });
  });
  it('sends a goal only for a tap on the level', () => {
    expect(onLevel(depot, 23, 6)).toBe(true);
    expect(onLevel(depot, -1, 6)).toBe(false);
    expect(onLevel(depot, 23, 40)).toBe(false);
  });
});
