// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * One search's events, as they arrive, and the grid state they imply at a
 * cursor (M1.6; the timeline seeks it in M1.7). It lays out and counts; it
 * never searches (README section 3): every value shown comes from an event
 * coco_lab emitted.
 *
 * Event kinds are SearchEventBatch's (coco.plan.search.events.v1): 1 push,
 * 2 expand, 3 relax, 4 path. Cells are ``row * width + col`` with row 0 at
 * the top, as in coco_lab's LabMap and grid.
 */

import type { SearchColumns } from '../protocol';

export const NONE = 0;
export const FRONTIER = 1;
export const CLOSED = 2;
export const PATH = 3;

const PUSH = 1;
const EXPAND = 2;
const RELAX = 3;
const PATH_EVENT = 4;
/** A keyframe every this many events (M1.7). */
export const KEY_EVERY = 16384;

export interface CellInfo {
  row: number; col: number; state: 'none' | 'frontier' | 'closed' | 'path';
  expansion: number | null;      // 0-based expansion order, if expanded
  event: number | null;          // the latest event at this cell (seq)
  kind: string | null; g: number | null; h: number | null; f: number | null;
  parent: [number, number] | null;
}

function grow<T extends Int32Array | Float64Array>(a: T, need: number, make: (n: number) => T): T {
  if (need <= a.length) return a;
  const b = make(Math.max(need, a.length * 2, 1024));
  b.set(a);
  return b;
}

export class PlanStore {
  searchId = -1;
  planner = '';
  /** Events received so far, and how many of them are applied (the cursor). */
  received = 0;
  cursor = 0;
  final = false;
  kind = new Int32Array(0);
  row = new Int32Array(0);
  col = new Int32Array(0);
  g = new Float64Array(0);
  h = new Float64Array(0);
  f = new Float64Array(0);
  prow = new Int32Array(0);
  pcol = new Int32Array(0);
  /** Grid state at the cursor. */
  readonly state: Uint8Array;
  readonly order: Int32Array;
  readonly last: Int32Array;
  expansions = 0;
  frontier = 0;
  pathCells: number[] = [];
  /** Set when the state changed; the renderer clears it after uploading. */
  dirty = true;

  constructor(readonly width: number, readonly height: number) {
    const n = width * height;
    this.state = new Uint8Array(n);
    this.order = new Int32Array(n).fill(-1);
    this.last = new Int32Array(n).fill(-1);
  }

  /** Start a new search: everything shown so far is cleared. */
  begin(searchId: number, planner: string) {
    this.searchId = searchId;
    this.planner = planner;
    this.received = 0;
    this.final = false;
    this.keys = [];
    this.reset();
  }

  private reset() {
    this.cursor = 0;
    this.state.fill(NONE);
    this.order.fill(-1);
    this.last.fill(-1);
    this.expansions = 0;
    this.frontier = 0;
    this.pathCells = [];
    this.dirty = true;
  }

  /** Append a batch (not yet applied: see advance). */
  append(c: SearchColumns, final: boolean) {
    const n = this.received + c.kind.length;
    this.kind = grow(this.kind, n, (k) => new Int32Array(k));
    this.row = grow(this.row, n, (k) => new Int32Array(k));
    this.col = grow(this.col, n, (k) => new Int32Array(k));
    this.g = grow(this.g, n, (k) => new Float64Array(k));
    this.h = grow(this.h, n, (k) => new Float64Array(k));
    this.f = grow(this.f, n, (k) => new Float64Array(k));
    this.prow = grow(this.prow, n, (k) => new Int32Array(k));
    this.pcol = grow(this.pcol, n, (k) => new Int32Array(k));
    const at = this.received;
    this.kind.set(c.kind, at); this.row.set(c.row, at); this.col.set(c.col, at);
    this.g.set(c.g, at); this.h.set(c.h, at); this.f.set(c.f, at);
    this.prow.set(c.parent_row, at); this.pcol.set(c.parent_col, at);
    this.received = n;
    if (final) this.final = true;
  }

  /** Apply events up to (not including) ``to``, forward only (keyframing as it goes). */
  advance(to: number) {
    const end = Math.min(to, this.received);
    const start = this.cursor;
    while (this.cursor < end) {
      const nextKey = (Math.floor(this.cursor / KEY_EVERY) + 1) * KEY_EVERY;
      const seg = Math.min(end, nextKey);
      this.apply(this.cursor, seg);
      this.cursor = seg;
      if (seg === nextKey && !this.keys.some((k) => k.at === seg)) this.snapshot();
    }
    if (end !== start) this.dirty = true;
  }

  /** Keyframes: the state after every KEY_EVERY events (M1.7: seek < 100 ms). */
  private keys: { at: number; state: Uint8Array; order: Int32Array; last: Int32Array;
    expansions: number; frontier: number; pathLen: number }[] = [];

  get keyframes(): number { return this.keys.length; }

  private snapshot() {
    this.keys.push({ at: this.cursor, state: this.state.slice(), order: this.order.slice(), last: this.last.slice(),
      expansions: this.expansions, frontier: this.frontier, pathLen: this.pathCells.length });
  }

  private apply(from: number, end: number) {
    const W = this.width;
    for (let i = from; i < end; i += 1) {
      const cell = this.row[i] * W + this.col[i];
      const k = this.kind[i];
      const s = this.state[cell];
      if (k === PUSH || k === RELAX) {
        if (s === NONE) { this.state[cell] = FRONTIER; this.frontier += 1; }
      } else if (k === EXPAND) {
        if (s === FRONTIER) this.frontier -= 1;
        this.state[cell] = CLOSED;
        this.order[cell] = this.expansions;
        this.expansions += 1;
      } else if (k === PATH_EVENT) {
        if (s === FRONTIER) this.frontier -= 1;
        this.state[cell] = PATH;
        this.pathCells.push(cell);
      }
      this.last[cell] = i;
    }
  }

  /**
   * Show the state after exactly ``to`` events. Backwards: restore the last
   * keyframe at or before ``to`` (or start over), then replay forward.
   */
  seek(to: number) {
    const t = Math.max(0, Math.min(to, this.received));
    if (t < this.cursor) {
      let key = null;
      for (const k of this.keys) if (k.at <= t && (!key || k.at > key.at)) key = k;
      if (key) {
        this.state.set(key.state); this.order.set(key.order); this.last.set(key.last);
        this.expansions = key.expansions; this.frontier = key.frontier;
        this.pathCells.length = key.pathLen;
        this.cursor = key.at;
        this.dirty = true;
      } else {
        this.reset();
      }
    }
    this.advance(t);
  }

  info(row: number, col: number): CellInfo | null {
    if (row < 0 || col < 0 || row >= this.height || col >= this.width) return null;
    const cell = row * this.width + col;
    const i = this.last[cell];
    const s = this.state[cell];
    const ord = this.order[cell];
    const kinds = ['', 'push', 'expand', 'relax', 'path'];
    return {
      row, col,
      state: s === FRONTIER ? 'frontier' : s === CLOSED ? 'closed' : s === PATH ? 'path' : 'none',
      expansion: ord >= 0 ? ord : null,
      event: i >= 0 ? i : null,
      kind: i >= 0 ? kinds[this.kind[i]] : null,
      g: i >= 0 ? this.g[i] : null, h: i >= 0 ? this.h[i] : null, f: i >= 0 ? this.f[i] : null,
      parent: i >= 0 && this.prow[i] >= 0 ? [this.prow[i], this.pcol[i]] : null,
    };
  }
}
