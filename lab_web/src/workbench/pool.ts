// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1: the Workbench's runner -- a pool of Arena workers (Pyodide + coco_lab), each
 * running one experiment run at a time through arena_glue.experiment.
 *
 * Every run is a pure function of the spec and its index (coco_lab.experiments,
 * hash version 3), so which worker runs it, and in what order, never changes its
 * record: results stream in as they finish and are keyed by run index. Pause stops
 * handing out runs (those in flight finish); cancel stops at once, terminating busy
 * workers, and keeps every record already received. Nothing here computes a result.
 */
import { createArenaWorker } from '../arena/worker_pool';
import { pinnedBase } from '../offline/updates';
import type { ExperimentRequest, FromWorker } from '../arena/protocol';

export interface RunRecord {
  index: number; sweep_index: number; sweep: Record<string, number | string>;
  algorithm: string; name: string; scenario: string; scenario_index: number;
  status: string; success: boolean; metrics: Record<string, number | boolean | null>;
  chain: string; fail_tick: number | null; series?: number[][]; error?: string;
  record?: unknown; game_chain?: string;
}

export interface PlanInfo {
  spec: Record<string, unknown>; id: string; world_sha256: string;
  scenarios: Record<string, unknown>[]; scenario_info: Record<string, unknown>;
  sweep_points: Record<string, number | string>[]; n_runs: number;
}

export interface Progress { done: number; total: number; running: number; etaMs: number | null; paused: boolean }

type Op = ExperimentRequest['op'];

/** How many workers this device gets: its cores less one for the page, capped (phones lower). */
export function defaultPoolSize(nav: { hardwareConcurrency?: number; deviceMemory?: number } = globalThis.navigator ?? {},
  phone = false): number {
  const cores = Math.max(1, (nav.hardwareConcurrency ?? 2) - 1);
  const cap = phone || (nav.deviceMemory !== undefined && nav.deviceMemory <= 4) ? 2 : 6;
  return Math.max(1, Math.min(cores, cap));
}

/** The median of the last durations (ms), for the time-left estimate. */
export function etaMs(durations: number[], remaining: number, workers: number): number | null {
  if (!durations.length || remaining <= 0) return remaining <= 0 ? 0 : null;
  const recent = durations.slice(-40).sort((a, b) => a - b);
  const mid = recent.length >> 1;
  const median = recent.length % 2 ? recent[mid] : (recent[mid - 1] + recent[mid]) / 2;
  return (median * remaining) / Math.max(1, workers);
}

interface Slot { worker: Worker; busy: boolean; ready: Promise<void>; waiting: Map<number, (m: Extract<FromWorker, { type: 'experiment_done' }>) => void> }

export class ExperimentPool {
  private slots: Slot[] = [];
  private nextId = 1;
  constructor(readonly size: number = defaultPoolSize(), private readonly makeWorker: () => Worker = createArenaWorker,
    private readonly base: string = pinnedBase()) {}

  private spawn(): Slot {
    const worker = this.makeWorker();
    const waiting = new Map<number, (m: Extract<FromWorker, { type: 'experiment_done' }>) => void>();
    let failed: (e: Error) => void = () => {};
    const ready = new Promise<void>((resolve, reject) => {
      failed = reject;
      worker.addEventListener('message', (ev: MessageEvent<FromWorker>) => {
        const m = ev.data;
        if (m.type === 'mark' && m.name === 'model_warm') resolve();
        else if (m.type === 'mark' && m.name === 'model_warm_failed') reject(new Error('the interpreter could not start'));
        else if (m.type === 'experiment_done') { waiting.get(m.id)?.(m); waiting.delete(m.id); }
      });
    });
    ready.catch(() => {});
    worker.addEventListener('error', (e) => {
      const err = new Error(e.message || 'a worker stopped');
      failed(err);
      for (const [id, done] of waiting) done({ type: 'experiment_done', id, error: err.message });
      waiting.clear();
    });
    worker.postMessage({ type: 'warm', pyodideBase: `${this.base}generated/pyodide/`, assetsBase: `${this.base}generated/`,
      seed: 1, planner: 'astar', batchSize: 2048, hashVersion: 3 });
    return { worker, busy: false, ready, waiting };
  }

  private ensure(n: number): Slot[] {
    while (this.slots.length < n) this.slots.push(this.spawn());
    return this.slots.slice(0, n);
  }

  /** One request on one slot; resolves with the glue's JSON answer or rejects with its error. */
  private async ask(slot: Slot, op: Op, spec: string, world: string, arg?: string): Promise<{ result: string; ms: number }> {
    await slot.ready;
    const id = this.nextId++;
    const reply = new Promise<Extract<FromWorker, { type: 'experiment_done' }>>((resolve) => slot.waiting.set(id, resolve));
    slot.worker.postMessage({ type: 'experiment', id, op, spec, world, arg } satisfies ExperimentRequest);
    const m = await reply;
    if (m.error !== undefined || m.result === undefined) throw new Error(m.error ?? 'no answer');
    return { result: m.result, ms: m.ms ?? 0 };
  }

  /** The filled spec, its id, scenarios and run count (one worker). */
  async plan(spec: string, world: string): Promise<PlanInfo> {
    return JSON.parse((await this.ask(this.ensure(1)[0], 'plan', spec, world)).result) as PlanInfo;
  }

  async summary(spec: string, world: string, records: RunRecord[]): Promise<Record<string, unknown>> {
    return JSON.parse((await this.ask(this.ensure(1)[0], 'summary', spec, world, JSON.stringify(records))).result);
  }

  async exportFiles(spec: string, world: string, records: RunRecord[], host: Record<string, unknown>): Promise<Record<string, string>> {
    return JSON.parse((await this.ask(this.ensure(1)[0], 'export', spec, world, JSON.stringify({ records, host }))).result);
  }

  /** R1.6: re-run the given runs capturing every tick (and a full task's game record), each checked against its chain. */
  async traces(spec: string, world: string, indices: number[]): Promise<{ index: number; chain: string; status: string; ticks: (number | boolean | string)[][]; record: unknown }[]> {
    return JSON.parse((await this.ask(this.ensure(1)[0], 'trace', spec, world, JSON.stringify(indices))).result);
  }

  async digest(spec: string, world: string, records: RunRecord[]): Promise<string> {
    return JSON.parse((await this.ask(this.ensure(1)[0], 'digest', spec, world, JSON.stringify(records))).result);
  }

  /**
   * Run the given run indices on every worker; `onRecord` sees each record as it
   * arrives (any order), `onProgress` after each. Resolves with every record
   * received, sorted by index -- all of them, or the partial set after cancel().
   */
  run(spec: string, world: string, indices: number[], hooks: { onRecord?: (r: RunRecord) => void; onProgress?: (p: Progress) => void } = {}) {
    const queue = [...indices];
    const records: RunRecord[] = [];
    const durations: number[] = [];
    let paused = false;
    let cancelled = false;
    let running = 0;
    let sleepers: (() => void)[] = [];
    const wakeAll = () => { const s = sleepers; sleepers = []; s.forEach((f) => f()); };
    const slots = this.ensure(Math.min(this.size, Math.max(1, indices.length)));
    const progress = () => hooks.onProgress?.({ done: records.length, total: indices.length, running, paused,
      etaMs: etaMs(durations, indices.length - records.length, slots.length) });
    const lane = async (slot: Slot) => {
      for (;;) {
        while (paused && !cancelled) await new Promise<void>((r) => sleepers.push(r));
        if (cancelled) return;
        const i = queue.shift();
        if (i === undefined) return;
        running++; slot.busy = true; progress();
        let answer: { result: string; ms: number };
        try {
          answer = await this.ask(slot, 'run', spec, world, JSON.stringify([i]));
        } catch (e) {
          if (cancelled) return;
          throw e;
        } finally { running--; slot.busy = false; }
        if (cancelled) return;
        for (const r of JSON.parse(answer.result) as RunRecord[]) { records.push(r); hooks.onRecord?.(r); }
        durations.push(answer.ms);
        progress();
      }
    };
    const done = Promise.all(slots.map(lane)).then(() => records.sort((a, b) => a.index - b.index));
    return {
      done,
      pause: () => { paused = true; progress(); },
      resume: () => { paused = false; wakeAll(); progress(); },
      cancel: () => {
        cancelled = true; paused = false; wakeAll();
        // busy workers stop now; their runs are dropped, every received record kept
        this.slots = this.slots.filter((s) => { if (s.busy) { s.worker.terminate(); for (const [id, d] of s.waiting) d({ type: 'experiment_done', id, error: 'cancelled' }); } return !s.busy; });
      },
    };
  }

  close(): void { for (const s of this.slots) s.worker.terminate(); this.slots = []; }
}
