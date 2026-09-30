// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Brush strokes: which cells a drag covered. Pure geometry on the grid;
 * the map is changed, and the search rerun, only by coco_lab in the worker.
 */

import type { Stroke } from '../worker/protocol';

export type Cell = [number, number]; // [row, col]
export type Tool = 'look' | 'paint' | 'erase';
export const BRUSH_SIZES = [1, 3, 5] as const;

/** The `size` x `size` square of cells centred on `c`, clipped to the map. */
export function brushCells(c: Cell, size: number, width: number, height: number): Cell[] {
  const r0 = c[0] - Math.floor(size / 2);
  const c0 = c[1] - Math.floor(size / 2);
  const out: Cell[] = [];
  for (let r = r0; r < r0 + size; r++) {
    for (let col = c0; col < c0 + size; col++) {
      if (r >= 0 && r < height && col >= 0 && col < width) out.push([r, col]);
    }
  }
  return out;
}

/** One drag: every cell the brush touched, once, in first-touched order. */
export class StrokeBuilder {
  private readonly seen = new Set<number>();
  readonly cells: Cell[] = [];

  constructor(readonly value: Stroke['value'], readonly size: number,
    readonly width: number, readonly height: number) {}

  /** Add the brush at `c`, and along the straight line from `from`. */
  add(c: Cell, from: Cell | null = null): void {
    const steps = from ? Math.max(Math.abs(c[0] - from[0]), Math.abs(c[1] - from[1])) : 0;
    for (let i = 0; i <= steps; i++) {
      const t = steps === 0 ? 1 : i / steps;
      const at: Cell = from
        ? [Math.round(from[0] + (c[0] - from[0]) * t), Math.round(from[1] + (c[1] - from[1]) * t)]
        : c;
      for (const b of brushCells(at, this.size, this.width, this.height)) {
        const k = b[0] * this.width + b[1];
        if (!this.seen.has(k)) {
          this.seen.add(k);
          this.cells.push(b);
        }
      }
    }
  }

  stroke(): Stroke {
    return { value: this.value, cells: this.cells.slice() };
  }
}

/**
 * Whether a painted stroke would cover the start or the goal. The worker
 * refuses the same stroke (src/worker/recompute.py); checking here lets
 * the page say so at once, without starting Python.
 */
export function coversEndpoint(s: Stroke, start: Cell, goal: Cell): { what: 'start' | 'goal'; cell: Cell } | null {
  if (s.value !== 'occupied') return null;
  for (const c of s.cells) {
    if (c[0] === start[0] && c[1] === start[1]) return { what: 'start', cell: c };
    if (c[0] === goal[0] && c[1] === goal[1]) return { what: 'goal', cell: c };
  }
  return null;
}

export function endpointRefusal(what: 'start' | 'goal', c: Cell): string {
  return `the brush covered the ${what} cell (${c[0]}, ${c[1]}). A search needs a free ${what}, ` +
    'so this stroke was not applied: paint around it.';
}
