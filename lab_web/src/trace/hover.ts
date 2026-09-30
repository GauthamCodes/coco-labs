// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * What hovering a cell shows: for each `sub` state at that cell, the LAST
 * event before the cursor -- its kind and its stored g, h and f. Nothing is
 * recomputed. The per-cell event index is built once, lazily (O(n)).
 */

import { EVENT_KINDS, type EventKind, type TraceEvents } from '../bundle/model';

export interface HoverState {
  sub: number;
  index: number;
  kind: EventKind;
  g: number;
  h: number;
  f: number;
  parent: [number, number, number];
}

export class HoverIndex {
  private start: Int32Array | null = null;
  private order: Int32Array | null = null;

  constructor(private readonly events: TraceEvents, private readonly n: number,
    private readonly width: number, private readonly height: number) {}

  private build(): void {
    const cells = this.width * this.height;
    const counts = new Int32Array(cells + 1);
    const { row, col } = this.events;
    for (let i = 0; i < this.n; i++) counts[row[i] * this.width + col[i] + 1]++;
    for (let c = 0; c < cells; c++) counts[c + 1] += counts[c];
    const fill = counts.slice(0, cells);
    const order = new Int32Array(this.n);
    for (let i = 0; i < this.n; i++) order[fill[row[i] * this.width + col[i]]++] = i;
    this.start = counts;
    this.order = order;
  }

  /** Every sub's last event before cursor `k` at (row, col), sorted by sub. */
  at(row: number, col: number, k: number): HoverState[] {
    if (row < 0 || row >= this.height || col < 0 || col >= this.width) return [];
    if (this.start === null) this.build();
    const cell = row * this.width + col;
    const last = new Map<number, number>();
    const e = this.events;
    for (let p = this.start![cell]; p < this.start![cell + 1]; p++) {
      const i = this.order![p];
      if (i >= k) break; // indices are ascending within a cell
      last.set(e.sub[i], i);
    }
    return [...last.entries()].sort(([a], [b]) => a - b).map(([sub, i]) => ({
      sub, index: i, kind: EVENT_KINDS[e.kind[i]], g: e.g[i], h: e.h[i], f: e.f[i],
      parent: [e.parent_row[i], e.parent_col[i], e.parent_sub[i]],
    }));
  }
}

/** What the trace's `f` column means for this algorithm (TRACE_SCHEMA). */
export function fMeaning(algorithm: string, weight: number | null): string {
  switch (algorithm) {
    case 'bfs': return 'f = depth in moves (BFS ignores cost)';
    case 'dijkstra': return 'f = g';
    case 'astar': return 'f = g + h';
    case 'greedy': return 'f = h';
    case 'weighted_astar': return `f = g + w·h (w = ${weight})`;
    default: return 'f = the priority the queue used';
  }
}
