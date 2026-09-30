// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Where the player is in a trace, as DISPLAY state per cell.
 *
 * This reads the event log; it never searches. The display rule (pinned
 * against the Python oracle `lab_web/tools/common.py`) is:
 *
 *     state(cell, k) = max over events i < k at that cell of
 *                      push 1 (open), expand 2 (closed), relax 1 (open),
 *                      path 3 (path)
 *
 * A search state only moves open -> closed -> path, so on a plain grid this
 * is exactly the state after k events; on a (cell, heading) graph a cell
 * shows the highest-precedence state of any of its subs (path > closed >
 * open) and the hover readout lists every sub.
 *
 * Moving forward applies events incrementally; moving backward recomputes
 * from 0 (O(k): a few ms at 283k events -- measured in 1D-6).
 */

import type { TraceEvents } from '../bundle/model';

export const NONE = 0;
export const OPEN = 1;
export const CLOSED = 2;
export const PATH = 3;
/** Display value of each event kind code: push, expand, relax, path. */
export const KIND_STATE = Uint8Array.of(OPEN, CLOSED, OPEN, PATH);

export class TraceCursor {
  readonly n: number;
  /** Display state of every cell, row-major: NONE/OPEN/CLOSED/PATH. */
  readonly state: Uint8Array;
  private k = 0;
  private readonly dirty: number[] = [];
  private full = true;

  constructor(private readonly events: TraceEvents, n: number, private readonly width: number, height: number) {
    this.n = n;
    this.state = new Uint8Array(width * height);
  }

  get position(): number {
    return this.k;
  }

  /** Move to `k` events applied (0..n). */
  seek(k: number): void {
    const target = Math.max(0, Math.min(this.n, Math.floor(k)));
    if (target < this.k) {
      this.state.fill(NONE);
      this.k = 0;
      this.full = true;
      this.dirty.length = 0;
    }
    const { kind, row, col } = this.events;
    const w = this.width;
    for (let i = this.k; i < target; i++) {
      const idx = row[i] * w + col[i];
      const v = KIND_STATE[kind[i]];
      if (v > this.state[idx]) {
        this.state[idx] = v;
        if (!this.full) this.dirty.push(idx);
      }
    }
    this.k = target;
  }

  /**
   * Cells whose state changed since the last call, or `null` when every
   * cell must be redrawn (after a backward seek or at the start).
   */
  takeChanges(): number[] | null {
    if (this.full) {
      this.full = false;
      this.dirty.length = 0;
      return null;
    }
    return this.dirty.splice(0, this.dirty.length);
  }

  counts(): { open: number; closed: number; path: number } {
    const c = [0, 0, 0, 0];
    for (const v of this.state) c[v]++;
    return { open: c[OPEN], closed: c[CLOSED], path: c[PATH] };
  }
}

/** The display state after `k` events, computed from scratch (reference). */
export function cellStates(events: TraceEvents, width: number, height: number, k: number): Uint8Array {
  const c = new TraceCursor(events, events.kind.length, width, height);
  c.seek(k);
  return c.state;
}

/** The path events among the first `k`, in order: [row, col] cells. */
export function pathCells(events: TraceEvents, k: number): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (let i = 0; i < k; i++) if (events.kind[i] === 3) out.push([events.row[i], events.col[i]]);
  return out;
}
