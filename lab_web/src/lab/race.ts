// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Race mode: two to four traces on identical inputs, advanced together.
 *
 * The shared step counter counts EXPANSIONS, the unit every algorithm
 * shares ("goal test on expansion", coco_lab/search.py): at step s each
 * pane shows its trace just after its own s-th expansion, or finished once
 * it has none left. The table's numbers are the traces' own summaries,
 * written by coco_lab; only units and the ratio to the optimum are
 * computed here.
 */

import type { DecodedBundle, TraceEvents } from '../bundle/model';

const EXPAND = 1;

/** ends[j] = the cursor just after the (j+1)-th expansion event. */
export function expansionEnds(events: TraceEvents, n: number): Int32Array {
  let count = 0;
  for (let i = 0; i < n; i++) if (events.kind[i] === EXPAND) count++;
  const ends = new Int32Array(count);
  let j = 0;
  for (let i = 0; i < n; i++) if (events.kind[i] === EXPAND) ends[j++] = i + 1;
  return ends;
}

/** The cursor for shared step `step` (0 = nothing expanded yet). */
export function cursorAtStep(ends: Int32Array, n: number, step: number): number {
  if (step <= 0) return 0;
  return step >= ends.length ? n : ends[step - 1];
}

export interface RaceRow {
  algorithm: string;
  status: 'found' | 'no_path';
  expansions: number;
  cost: number | null;
  length: number | null;
  lengthUnit: 'm' | 'cells';
  /** cost / optimum - 1, or null when either is missing */
  gap: number | null;
}

export function raceRow(b: DecodedBundle, optimal: number | null): RaceRow {
  const s = b.trace.summary;
  const res = b.map.geo?.resolution ?? null;
  const length = s.path_length === null ? null : res === null ? s.path_length : s.path_length * res;
  let gap: number | null = null;
  if (s.path_cost !== null && optimal !== null) gap = optimal === 0 ? 0 : s.path_cost / optimal - 1;
  return {
    algorithm: b.trace.header.algorithm,
    status: s.status,
    expansions: s.expansions,
    cost: s.path_cost,
    length,
    lengthUnit: res === null ? 'cells' : 'm',
    gap,
  };
}
