// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** R1.2: the Workbench's worker pool -- order-independent records, pause, cancel, ETA. */
import { describe, expect, it } from 'vitest';
import { defaultPoolSize, etaMs, ExperimentPool, type RunRecord } from '../src/workbench/pool';

type Listener = (ev: { data: unknown }) => void;
/** A worker that warms at once and answers each run after a delay that depends on the run. */
class FakeWorker {
  static made: FakeWorker[] = [];
  listeners: Listener[] = [];
  terminated = false;
  constructor(private readonly delay: (i: number) => number) { FakeWorker.made.push(this); }
  addEventListener(type: string, fn: Listener) { if (type === 'message') this.listeners.push(fn); }
  emit(data: unknown) { if (!this.terminated) for (const fn of this.listeners) fn({ data }); }
  terminate() { this.terminated = true; }
  postMessage(m: { type: string; id: number; op: string; arg?: string }) {
    if (m.type === 'warm') { setTimeout(() => this.emit({ type: 'mark', name: 'model_warm', at: 0 }), 0); return; }
    if (m.type !== 'experiment') return;
    if (m.op === 'plan') { setTimeout(() => this.emit({ type: 'experiment_done', id: m.id, result: JSON.stringify({ n_runs: 20 }) }), 0); return; }
    const [i] = JSON.parse(m.arg!) as number[];
    const rec: Partial<RunRecord> = { index: i, status: 'found', success: true, chain: `c${i}`, metrics: { expansions: i * 10 } };
    setTimeout(() => this.emit({ type: 'experiment_done', id: m.id, result: JSON.stringify([rec]), ms: 5 }), this.delay(i));
  }
}
const make = (delay: (i: number) => number) => () => new FakeWorker(delay) as unknown as Worker;

describe('the Workbench worker pool', () => {
  it('returns every record, keyed by run index, whatever order the workers finish in', async () => {
    const pool = new ExperimentPool(4, make((i) => (20 - i) % 7), '/');
    const seen: number[] = [];
    const out = await pool.run('{}', 'coco_arena_v1', [...Array(20).keys()], { onRecord: (r) => seen.push(r.index) }).done;
    expect(out.map((r) => r.index)).toEqual([...Array(20).keys()]);
    expect(out.map((r) => r.chain)).toEqual([...Array(20).keys()].map((i) => `c${i}`));
    expect(seen.slice().sort((a, b) => a - b)).toEqual([...Array(20).keys()]);
    expect(seen).not.toEqual([...Array(20).keys()]);
    pool.close();
  });

  it('pauses (in-flight runs finish), resumes, and reports progress', async () => {
    const pool = new ExperimentPool(2, make(() => 3), '/');
    const progress: number[] = [];
    const h = pool.run('{}', 'w', [...Array(10).keys()], { onProgress: (p) => progress.push(p.done) });
    h.pause();
    await new Promise((r) => setTimeout(r, 40));
    const paused = progress[progress.length - 1];
    expect(paused).toBeLessThan(10);
    await new Promise((r) => setTimeout(r, 30));
    expect(progress[progress.length - 1]).toBe(paused);
    h.resume();
    expect((await h.done).length).toBe(10);
    pool.close();
  });

  it('cancel keeps every record received and terminates busy workers', async () => {
    FakeWorker.made = [];
    const pool = new ExperimentPool(3, make((i) => (i < 4 ? 1 : 200)), '/');
    const h = pool.run('{}', 'w', [...Array(12).keys()]);
    await new Promise((r) => setTimeout(r, 40));
    h.cancel();
    const partial = await h.done;
    expect(partial.length).toBeGreaterThan(0);
    expect(partial.length).toBeLessThan(12);
    expect(partial.map((r) => r.index)).toEqual([...partial.map((r) => r.index)].sort((a, b) => a - b));
    expect(FakeWorker.made.some((w) => w.terminated)).toBe(true);
    pool.close();
  });

  it('sizes itself from the device and estimates time left from recent runs', () => {
    expect(defaultPoolSize({ hardwareConcurrency: 12 })).toBe(6);
    expect(defaultPoolSize({ hardwareConcurrency: 8 }, true)).toBe(2);
    expect(defaultPoolSize({ hardwareConcurrency: 1 })).toBe(1);
    expect(defaultPoolSize({ hardwareConcurrency: 8, deviceMemory: 4 })).toBe(2);
    expect(etaMs([], 5, 2)).toBeNull();
    expect(etaMs([10, 30, 20], 6, 2)).toBe(60);
    expect(etaMs([10], 0, 2)).toBe(0);
  });
});
