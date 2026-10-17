// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { TOKENS } from '../tokens';
import { CLOSED, FRONTIER, PATH, type PlanStore } from '../../arena/render/planStore';
import type { Theme } from '../tokens';
export type CostLayer = 'static' | 'inflation' | 'obstacle' | 'combined';
export interface CostmapData { static: Uint8Array; inflation: Uint8Array; obstacle: Uint8Array; combined: Uint8Array }
const rgb = (hex: string) => [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16));
/** Presentation of emitted costs/trace events, never an algorithm or map inference. */
export function comparisonPixels(width: number, height: number, occupancy: Uint8Array, store: PlanStore,
  theme: Theme, costs?: CostmapData, layer: CostLayer = 'combined', difference?: [PlanStore, PlanStore], out: Uint8Array = new Uint8Array(width * height * 4)) {
  const p = TOKENS.computation[theme];
  const colours = [rgb(p.occupied), rgb(p.frontier), rgb(p.closed), rgb(p.path)];
  const gradient = TOKENS.viridis.map(rgb), outline = rgb(TOKENS.colours[theme].fg);
  const grid = costs?.[layer];
  for (let row = 0; row < height; row++) for (let col = 0; col < width; col++) {
    const i = row * width + col, pixel = ((height - 1 - row) * width + col) * 4;
    let colour = colours[0], alpha = occupancy[i] ? 75 : 0;
    if (grid) {
      const value = grid[i], t = Math.min(1, value / 254) * (gradient.length - 1), lower = Math.floor(t), f = t - lower;
      colour = gradient[lower].map((v, c) => Math.round(v + ((gradient[lower + 1] ?? gradient[lower])[c] - v) * f));
      alpha = value ? 210 : 0;
      // One-cell contours around distinct lethal/inscribed bands.
      if (value >= 253 && [i - width, i + width, col ? i - 1 : -1, col + 1 < width ? i + 1 : -1].some(j => j < 0 || j >= grid.length || grid[j] !== value)) { colour = outline; alpha = value === 254 || (row + col) % 2 === 0 ? 255 : 120; }
    }
    if (difference) {
      const [a, b] = difference, onlyA = a.order[i] >= 0, onlyB = b.order[i] >= 0;
      if (onlyA || onlyB) { colour = colours[2]; alpha = onlyA && onlyB ? 180 : (onlyA ? (row + col) % 6 : (row - col + width) % 6) < 2 ? 230 : 65; }
      if (a.state[i] === PATH || b.state[i] === PATH) { colour = colours[3]; alpha = a.state[i] === PATH ? 255 : (row + col) % 6 < 3 ? 255 : 70; }
    } else {
      const state = store.state[i];
      if (state) { colour = colours[state]; alpha = state === CLOSED ? Math.round(p.closedAlpha * 255) : state === FRONTIER || state === PATH ? 255 : alpha; }
    }
    out[pixel] = colour[0]; out[pixel + 1] = colour[1]; out[pixel + 2] = colour[2]; out[pixel + 3] = alpha;
  }
  return out;
}
