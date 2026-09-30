// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Pure layer builders: RGBA pixels at one pixel per cell, row 0 at the top.
 * No canvas here, so the output is deterministic and its hash is pinned by
 * a test; `draw.ts` blits it scaled with smoothing off.
 */

import type { MapLayer } from '../bundle/model';
import { CLOSED, OPEN, PATH } from '../trace/cursor';
import { PALETTE, rgb } from './palette';

const FREE = rgb(PALETTE.free);
const OCC = rgb(PALETTE.occupied);
const UNK = rgb(PALETTE.unknown);
const COST = rgb(PALETTE.costMax);
const STATE_RGB: Record<number, [number, number, number]> = {
  [OPEN]: rgb(PALETTE.open), [CLOSED]: rgb(PALETTE.closed), [PATH]: rgb(PALETTE.path),
};

/** The map: occupancy, with the cost layer (if any) shading the free cells. */
export function buildMapRGBA(m: MapLayer): Uint8ClampedArray {
  const out = new Uint8ClampedArray(m.width * m.height * 4);
  let maxCost = 0;
  if (m.cost) for (let i = 0; i < m.cost.length; i++) if (m.occupancy[i] === 0 && m.cost[i] > maxCost) maxCost = m.cost[i];
  for (let i = 0; i < m.occupancy.length; i++) {
    const o = m.occupancy[i];
    let c = o === 1 ? OCC : o === 2 ? UNK : FREE;
    if (o === 0 && m.cost && maxCost > 0) {
      const t = m.cost[i] / maxCost;
      c = [0, 1, 2].map((j) => Math.round(FREE[j] + (COST[j] - FREE[j]) * t)) as [number, number, number];
    }
    out[4 * i] = c[0];
    out[4 * i + 1] = c[1];
    out[4 * i + 2] = c[2];
    out[4 * i + 3] = 255;
  }
  return out;
}

/** The trace state: transparent where nothing happened yet. */
export function buildTraceRGBA(state: Uint8Array): Uint8ClampedArray {
  const out = new Uint8ClampedArray(state.length * 4);
  updateTraceRGBA(out, state, null);
  return out;
}

/** Update `rgba` for `cells` (or every cell when `cells` is null). */
export function updateTraceRGBA(rgba: Uint8ClampedArray, state: Uint8Array, cells: number[] | null): void {
  const paint = (i: number) => {
    const c = STATE_RGB[state[i]];
    if (c) {
      rgba[4 * i] = c[0];
      rgba[4 * i + 1] = c[1];
      rgba[4 * i + 2] = c[2];
      rgba[4 * i + 3] = 255;
    } else {
      rgba[4 * i + 3] = 0;
    }
  };
  if (cells === null) for (let i = 0; i < state.length; i++) paint(i);
  else for (const i of cells) paint(i);
}
