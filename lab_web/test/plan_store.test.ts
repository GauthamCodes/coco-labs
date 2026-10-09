// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The renderer's search state (M1.6), on a real coco_lab search: the
 * SearchEventBatch that coco_schemas' vectors froze (Python wrote it).
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fromBinary } from '@bufbuild/protobuf';
import { describe, expect, it } from 'vitest';

import type { SearchColumns } from '../src/arena/protocol';
import { CLOSED, FRONTIER, NONE, PATH, PlanStore } from '../src/arena/render/planStore';
import { SearchEventBatchSchema } from '../src/schemas/gen/coco/plan/v1/search_pb';
import { REPO } from './helpers';

const bytes = new Uint8Array(readFileSync(join(REPO, 'coco_schemas', 'test', 'vectors', 'search_batch.binpb')));
const b = fromBinary(SearchEventBatchSchema, bytes);
const cols: SearchColumns = {
  seq: BigUint64Array.from(b.seq), tick: BigUint64Array.from(b.tick), t_world: Float64Array.from(b.tWorld),
  kind: Int32Array.from(b.kind), row: Int32Array.from(b.row), col: Int32Array.from(b.col), sub: Int32Array.from(b.sub),
  g: Float64Array.from(b.g), h: Float64Array.from(b.h), f: Float64Array.from(b.f),
  parent_row: Int32Array.from(b.parentRow), parent_col: Int32Array.from(b.parentCol), parent_sub: Int32Array.from(b.parentSub),
};
const W = 7;
const H = 5;
const N = cols.kind.length;

function full(): PlanStore {
  const s = new PlanStore(W, H);
  s.begin(3, 'astar');
  s.append(cols, true);
  s.advance(N);
  return s;
}

describe('PlanStore on a real search', () => {
  it('expands in event order, ends with the path, and counts the frontier', () => {
    const s = full();
    const expands = [...cols.kind].map((k, i) => [k, i]).filter(([k]) => k === 2).map(([, i]) => i);
    expect(s.expansions).toBe(expands.length);
    // expansion order is the order of expand events
    expands.forEach((i, ord) => expect(s.order[cols.row[i] * W + cols.col[i]]).toBe(ord));
    const pathCells = [...cols.kind].map((k, i) => [k, i]).filter(([k]) => k === 4).map(([, i]) => cols.row[i] * W + cols.col[i]);
    expect(s.pathCells).toEqual(pathCells);
    for (const c of pathCells) expect(s.state[c]).toBe(PATH);
    let frontier = 0;
    for (let c = 0; c < W * H; c += 1) if (s.state[c] === FRONTIER) frontier += 1;
    expect(s.frontier).toBe(frontier);
  });

  it('the inspector reports the cell\'s own latest event', () => {
    const s = full();
    const i = N - 1; // the last event: the goal, on the path
    const info = s.info(cols.row[i], cols.col[i])!;
    expect(info.state).toBe('path');
    expect(info.event).toBe(i);
    expect(info.kind).toBe('path');
    expect([info.g, info.h, info.f]).toEqual([cols.g[i], cols.h[i], cols.f[i]]);
    expect(info.parent).toEqual([cols.parent_row[i], cols.parent_col[i]]);
    expect(s.info(-1, 0)).toBeNull();
    expect(s.info(0, W)).toBeNull();
  });

  it('seeking back to k gives the state a fresh replay of k events gives', () => {
    for (const k of [0, 1, 5, Math.floor(N / 2), N - 3]) {
      const s = full();
      s.seek(k);
      const t = new PlanStore(W, H);
      t.begin(3, 'astar');
      t.append(cols, true);
      t.advance(k);
      expect([...s.state]).toEqual([...t.state]);
      expect([...s.order]).toEqual([...t.order]);
      expect(s.cursor).toBe(k);
    }
  });

  it('arriving in batches is the same as arriving at once', () => {
    const s = new PlanStore(W, H);
    s.begin(0, 'astar');
    const slice = (a: number, z: number) => Object.fromEntries(Object.entries(cols).map(([k, v]) => [k, v.slice(a, z)])) as unknown as SearchColumns;
    for (let a = 0; a < N; a += 7) { s.append(slice(a, Math.min(N, a + 7)), a + 7 >= N); s.advance(s.received); }
    expect([...s.state]).toEqual([...full().state]);
    expect(s.final).toBe(true);
  });

  it('a new search clears the old one', () => {
    const s = full();
    s.begin(4, 'bfs');
    expect(s.received).toBe(0);
    expect([...s.state].every((v) => v === NONE)).toBe(true);
    expect(s.expansions).toBe(0);
    void CLOSED;
  });
});
