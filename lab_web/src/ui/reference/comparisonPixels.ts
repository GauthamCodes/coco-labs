// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { TOKENS } from '../tokens';
import { CLOSED, FRONTIER, PATH, type PlanStore } from '../../arena/render/planStore';
import type { Theme } from '../tokens';
export type CostLayer = 'static' | 'inflation' | 'obstacle' | 'combined';
export interface CostmapData { static: Uint8Array; inflation: Uint8Array; obstacle: Uint8Array; combined: Uint8Array }
const rgb = (hex: string) => [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16));
/** Static emitted costs, shared by panes; no model computation. */
export function comparisonBasePixels(width: number, height: number, occupancy: Uint8Array,
  theme: Theme, costs?: CostmapData, layer: CostLayer = 'combined') {
  const out = new Uint8Array(width * height * 4), occupied = rgb(TOKENS.computation[theme].occupied);
  const gradient = TOKENS.viridis.map(rgb), outline = rgb(TOKENS.colours[theme].fg), grid = costs?.[layer];
  const palette = Array.from({ length: 256 }, (_, value) => {
    const t = Math.min(1, value / 254) * (gradient.length - 1), lower = Math.floor(t), f = t - lower;
    return gradient[lower].map((v, c) => Math.round(v + ((gradient[lower + 1] ?? gradient[lower])[c] - v) * f));
  });
  for (let row = 0; row < height; row++) for (let col = 0; col < width; col++) {
    const i = row * width + col, pixel = ((height - 1 - row) * width + col) * 4;
    let colour = occupied, alpha = occupancy[i] ? 75 : 0;
    if (grid) {
      const value = grid[i]; colour = palette[value]; alpha = value ? 210 : 0;
      if (value >= 253 && (row === 0 || row + 1 === height || col === 0 || col + 1 === width || grid[i - width] !== value || grid[i + width] !== value || grid[i - 1] !== value || grid[i + 1] !== value)) {
        colour = outline; alpha = value === 254 || (row + col) % 2 === 0 ? 255 : 120;
      }
    }
    out[pixel] = colour[0]; out[pixel + 1] = colour[1]; out[pixel + 2] = colour[2]; out[pixel + 3] = alpha;
  }
  return out;
}
/** Presentation of emitted costs/trace events, never an algorithm or map inference. */
export function comparisonPixels(width: number, height: number, occupancy: Uint8Array, store: PlanStore,
  theme: Theme, costs?: CostmapData, layer: CostLayer = 'combined', difference?: [PlanStore, PlanStore], out: Uint8Array = new Uint8Array(width * height * 4), base?: Uint8Array) {
  out.set(base ?? comparisonBasePixels(width, height, occupancy, theme, costs, layer));
  const p = TOKENS.computation[theme], colours = [rgb(p.occupied), rgb(p.frontier), rgb(p.closed), rgb(p.path)];
  for (let i = 0; i < width * height; i++) {
    const row = Math.floor(i / width), col = i % width;
    const pixel = ((height - 1 - row) * width + col) * 4;
    let colour: number[] | undefined, alpha = out[pixel + 3];
    if (difference) {
      const [a, b] = difference, onlyA = a.order[i] >= 0, onlyB = b.order[i] >= 0;
      if (onlyA || onlyB) { colour = colours[2]; alpha = onlyA && onlyB ? 180 : (onlyA ? (row + col) % 6 : (row - col + width) % 6) < 2 ? 230 : 65; }
      if (a.state[i] === PATH || b.state[i] === PATH) { colour = colours[3]; alpha = a.state[i] === PATH ? 255 : (row + col) % 6 < 3 ? 255 : 70; }
    } else {
      const state = store.state[i];
      if (state) { colour = colours[state]; alpha = state === CLOSED ? Math.round(p.closedAlpha * 255) : state === FRONTIER || state === PATH ? 255 : alpha; }
    }
    if (colour) { out[pixel] = colour[0]; out[pixel + 1] = colour[1]; out[pixel + 2] = colour[2]; out[pixel + 3] = alpha; }
  }
  return out;
}
