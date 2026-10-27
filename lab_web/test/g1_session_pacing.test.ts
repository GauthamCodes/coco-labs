// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.13: the session's tick pacing (src/game/session.ts). The worker is replaced by a fake
 * client whose step takes a scripted time; the clock is vitest's.
 *
 * - ordinary ticks reach the game exactly every 100 ms when steps vary but fit the lead
 *   (before G1.13 a 60 ms step after a 20 ms one made a 140 ms gap);
 * - a tick an input starts is sent at once and shown on arrival (no added wait);
 * - a held tick is shown before the tick an input starts, in tick order;
 * - a step longer than the lead is shown late, never early, and the schedule restarts.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const sent: { at: number; inputs: unknown[] }[] = [];
let deliver: ((t: unknown, r: Float32Array) => void) | null = null;
let stepMs: (k: number) => number = () => 20;

vi.mock('../src/arena/client', () => ({
  ArenaClient: class {
    worker = { addEventListener() {} };
    constructor(ev: { onTick: (t: unknown, r: Float32Array) => void }) { deliver = ev.onTick; }
    step(inputs: unknown[] = []) {
      const k = sent.length;
      sent.push({ at: performance.now(), inputs });
      setTimeout(() => deliver?.({ tick: k, mode: 'idle' }, new Float32Array(0)), stepMs(k));
      return [];
    }
    amend() {}
    close() {}
    whenReady() { return Promise.resolve(); }
    game() { return Promise.resolve(null); }
  },
}));

const { GameSession } = await import('../src/game/session');

function session() {
  const shown: { tick: number; at: number }[] = [];
  const s = new GameSession('depot', 'free', 1, {
    onWorld() {}, onTick() {}, onError() {},
  });
  (s as unknown as { world: unknown }).world = { game: { setup: [] }, limits: { teleop_linear: 0.3, teleop_angular: 1 } };
  s.presentHook = (t, at) => shown.push({ tick: (t as unknown as { tick: number }).tick, at });
  return { s, shown };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'performance'] });
  (globalThis as unknown as { window: unknown }).window = globalThis;
  sent.length = 0;
});
afterEach(() => { vi.useRealTimers(); });

describe('G1.13 tick pacing', () => {
  it('shows ordinary ticks every 100 ms although the steps vary', () => {
    // steps of 20 and 60 ms alternate (G1.13's laptop: a 25-62 ms longer step made a 130-168 ms gap)
    stepMs = (k) => (k % 2 ? 60 : 20);
    const { s, shown } = session();
    s.start();
    vi.advanceTimersByTime(5000);
    const gaps = shown.slice(10).map((x, i) => x.at - shown[9 + i].at);
    expect(gaps.length).toBeGreaterThan(30);
    expect(Math.max(...gaps)).toBeLessThanOrEqual(100 + 10); // the 10 ms pump
    expect(Math.min(...gaps)).toBeGreaterThanOrEqual(100 - 10);
    expect(shown.map((x) => x.tick)).toEqual(shown.map((_, i) => i)); // in order
    s.close();
  });

  it('sends and shows an input tick at once', () => {
    stepMs = () => 20;
    const { s, shown } = session();
    s.start();
    vi.advanceTimersByTime(1000);
    const before = sent.length;
    const t0 = performance.now();
    s.goal(1, 2);
    vi.advanceTimersByTime(15); // the next pump (10 ms) sends it
    expect(sent.length).toBe(before + 1);
    expect(sent[sent.length - 1].inputs).toEqual([{ kind: 'goal', x: 1, y: 2 }]);
    expect(sent[sent.length - 1].at - t0).toBeLessThanOrEqual(10);
    vi.advanceTimersByTime(25);
    const last = shown[shown.length - 1];
    expect(last.tick).toBe(before);
    expect(last.at - sent[before].at).toBe(20); // shown on arrival
    s.close();
  });

  it('shows a held tick before the tick an input starts', () => {
    // 5 ms steps: the lead is 10 ms, the 10 ms pump sends 10 ms early, so each tick waits 5 ms
    stepMs = () => 5;
    const { s, shown } = session();
    s.start();
    vi.advanceTimersByTime(1000);
    // find a moment when a tick is held (arrived, not yet due)
    for (let i = 0; i < 100 && !(s as unknown as { held: unknown }).held; i++) vi.advanceTimersByTime(1);
    expect((s as unknown as { held: unknown }).held).not.toBeNull();
    s.goal(3, 4);
    vi.advanceTimersByTime(40);
    const ticks = shown.map((x) => x.tick);
    expect(ticks).toEqual(ticks.map((_, i) => i));
    s.close();
  });

  it('G2.9: an input with nothing in flight is sent at once, not at the next 10 ms pump', () => {
    stepMs = () => 20;
    const { s } = session();
    s.start();
    vi.advanceTimersByTime(1000);
    // wait for a moment with nothing in flight
    for (let i = 0; i < 200 && (s as unknown as { inFlight: boolean }).inFlight; i++) vi.advanceTimersByTime(1);
    const before = sent.length, t0 = performance.now();
    s.drive(1, 0);
    expect(sent.length).toBe(before + 1);
    expect(sent[before].at).toBe(t0);
    s.close();
  });

  it('G2.9: after an input amended into the tick in flight, the next tick is sent when that one arrives', () => {
    // 60 ms steps: an input during one may miss it in the worker (its last look), so the next must not wait for the schedule
    stepMs = () => 60;
    const { s, shown } = session();
    s.start();
    vi.advanceTimersByTime(1000);
    for (let i = 0; i < 200 && !(s as unknown as { inFlight: boolean }).inFlight; i++) vi.advanceTimersByTime(1);
    const k = sent.length - 1;            // the step in flight
    s.drive(1, 0);                        // amended into it
    vi.advanceTimersByTime(80);
    const arrivedAt = sent[k].at + 60;
    expect(shown.find((x) => x.tick === k)?.at).toBe(arrivedAt);    // shown on arrival, not held to its due time
    expect(sent[k + 1].at - arrivedAt).toBeLessThanOrEqual(0);      // the next step at once
    s.close();
  });

  it('shows a step longer than the lead late, then keeps the schedule from it', () => {
    stepMs = (k) => (k === 30 ? 250 : 20);
    const { s, shown } = session();
    s.start();
    vi.advanceTimersByTime(6000);
    const i = shown.findIndex((x) => x.tick === 30);
    expect(shown[i].at - shown[i - 1].at).toBeGreaterThan(200); // late, as measured
    const after = shown.slice(i + 2, i + 20).map((x, j) => x.at - shown[i + 1 + j].at);
    expect(Math.max(...after)).toBeLessThanOrEqual(110);
    s.close();
  });
});
