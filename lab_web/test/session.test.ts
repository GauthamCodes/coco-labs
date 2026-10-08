// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The timeline (M1.7): world and computation tracks, play / pause / step /
 * speed / scrub, and seeking a LARGE search in under 100 ms through its
 * keyframes (M1 responsiveness criterion; laptop, Node).
 */

import { describe, expect, it } from 'vitest';

import type { SearchColumns, Tick } from '../src/arena/protocol';
import { KEY_EVERY, PlanStore } from '../src/arena/render/planStore';
import { ArenaSession } from '../src/arena/session';

const W = 500;
const H = 380;

/** A BFS-shaped search over the whole 500 x 380 grid: ~380k events, like Lab 1's arena Dijkstra. */
function bigSearch(): SearchColumns[] {
  const rows: number[][] = [];
  const seen = new Uint8Array(W * H);
  const q: number[] = [0];
  seen[0] = 1;
  rows.push([1, 0, 0, -1, -1]);
  while (q.length) {
    const c = q.shift()!;
    const r = Math.floor(c / W);
    const k = c % W;
    rows.push([2, r, k, -1, -1]);
    for (const [dr, dk] of [[1, 0], [0, 1], [-1, 0], [0, -1]]) {
      const rr = r + dr;
      const kk = k + dk;
      if (rr < 0 || kk < 0 || rr >= H || kk >= W || seen[rr * W + kk]) continue;
      seen[rr * W + kk] = 1;
      q.push(rr * W + kk);
      rows.push([1, rr, kk, r, k]);
    }
  }
  const batches: SearchColumns[] = [];
  for (let a = 0; a < rows.length; a += 2048) {
    const part = rows.slice(a, a + 2048);
    const n = part.length;
    batches.push({
      seq: BigUint64Array.from(part.map((_, i) => BigInt(a + i))), tick: new BigUint64Array(n), t_world: new Float64Array(n),
      kind: Int32Array.from(part.map((p) => p[0])), row: Int32Array.from(part.map((p) => p[1])), col: Int32Array.from(part.map((p) => p[2])),
      sub: new Int32Array(n), g: Float64Array.from(part.map((_, i) => a + i)), h: new Float64Array(n), f: Float64Array.from(part.map((_, i) => a + i)),
      parent_row: Int32Array.from(part.map((p) => p[3])), parent_col: Int32Array.from(part.map((p) => p[4])), parent_sub: new Int32Array(n),
    });
  }
  return batches;
}

function tick(k: number): Tick {
  return { tick: k, t_world: k * 0.1, pose: [k * 0.01, 0, 0], v: 0.1, w: 0, mode: 'goal', blocked: false, arrived: false,
    hash: `h${k}`, chain: '', plans: [] };
}

describe('keyframed seeking on a large search', () => {
  const batches = bigSearch();
  const store = new PlanStore(W, H);
  store.begin(0, 'bfs');
  batches.forEach((b, i) => store.append(b, i === batches.length - 1));
  const N = store.received;

  it('the search is Lab-1-arena sized and keyframes are taken', () => {
    expect(N).toBeGreaterThan(370_000);
    store.advance(N);
    expect(store.keyframes).toBe(Math.floor(N / KEY_EVERY));
  });

  it('seeking anywhere, backwards or forwards, takes < 100 ms and equals a fresh replay', () => {
    const targets = [N - 1, 5, Math.floor(N / 2), 123_456, N - 50_000, 1, N];
    const times: number[] = [];
    for (const t of targets) {
      const t0 = performance.now();
      store.seek(t);
      times.push(performance.now() - t0);
      const fresh = new PlanStore(W, H);
      fresh.begin(0, 'bfs');
      batches.forEach((b, i) => fresh.append(b, i === batches.length - 1));
      fresh.advance(t);
      expect(store.cursor).toBe(t);
      expect(store.expansions).toBe(fresh.expansions);
      expect(store.frontier).toBe(fresh.frontier);
      expect(Buffer.from(store.state).equals(Buffer.from(fresh.state))).toBe(true);
      expect(Buffer.from(store.order.buffer).equals(Buffer.from(fresh.order.buffer))).toBe(true);
    }
    // the budget: every seek well under 100 ms (laptop, Node)
    expect(Math.max(...times)).toBeLessThan(100);
  });
});

describe('the two tracks', () => {
  function session() {
    const s = new ArenaSession(W, H, 0.1);
    for (let k = 1; k <= 50; k += 1) s.onTick(tick(k), new Float32Array(480));
    const b = bigSearch().slice(0, 3);
    b.forEach((c, i) => s.onPlanBatch({ search_id: 0, planner: 'bfs', tick: 10, final: i === 2 }, c));
    return s;
  }

  it('follows live; seeking the world track shows a recorded tick', () => {
    const s = session();
    expect(s.live).toBe(true);
    expect(s.shownTick?.tick).toBe(50);
    s.seekTick(20);
    expect(s.live).toBe(false);
    expect(s.shownTick?.pose[0]).toBeCloseTo(0.2);
    s.seekTick(9);
    expect(s.shownSearch).toBeNull(); // before the plan existed
    s.seekTick(11);
    expect(s.shownSearch?.searchId).toBe(0);
    s.seekTick(99);
    expect(s.live).toBe(true);
  });

  it('the computation track scrubs the shown search, and steps one event at a time', () => {
    const s = session();
    s.seekTick(30);
    s.seekSeq(100);
    expect(s.shownSearch?.cursor).toBe(100);
    s.stepSeq(+1);
    expect(s.shownSearch?.cursor).toBe(101);
    expect(s.playing).toBe(false);
    s.stepSeq(-2);
    expect(s.shownSearch?.cursor).toBe(99);
  });

  it('pause stops the world clock; speed scales it; history replays then rejoins live', () => {
    const s = session();
    expect(s.frame(100)).toBe(1);        // dt = 100 ms at speed 1
    s.setSpeed(2);
    expect(s.frame(100)).toBe(2);
    s.playing = false;
    expect(s.frame(1000)).toBe(0);
    s.playing = true;
    s.setSpeed(1);
    s.seekTick(45);
    expect(s.frame(300)).toBe(0);        // replaying: no model steps
    expect(s.shownTick?.tick).toBe(48);
    s.frame(500);
    expect(s.live).toBe(true);           // reached the head
    s.setSpeed(3);
    expect(s.speed).toBe(1);             // not an offered speed
  });

  it('old ranges are dropped, poses kept', () => {
    const s = new ArenaSession(W, H, 0.1);
    for (let k = 1; k <= 12_005; k += 1) s.onTick(tick(k), new Float32Array(4));
    expect(s.recordAt(1)?.ranges).toBeNull();
    expect(s.recordAt(1)?.pose[0]).toBeCloseTo(0.01);
    expect(s.recordAt(12_005)?.ranges).not.toBeNull();
  });
});
