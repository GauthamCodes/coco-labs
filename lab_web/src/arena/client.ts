// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The page's side of the Arena worker. Created as soon as the Arena view
 * opens (README 5.5: Pyodide loads while attract mode plays), so the cold
 * start overlaps with what the visitor is already watching.
 */

import { PYODIDE_INDEX_URL } from '../../site.config.ts';
import { wallMs, type BootRequest, type CompareSide, type FamilyMessage, type FromWorker, type InputRow, type SearchColumns, type Tick, type World } from './protocol';
import { perf } from './perf';

export interface ArenaEvents {
  onWorld?(world: World, occupancy: Uint8Array): void;
  onPlanBatch?(meta: Extract<FromWorker, { type: 'plan_batch' }>['meta'], columns: SearchColumns): void;
  onTick?(tick: Tick, ranges: Float32Array): void;
  onCompareBatch?(meta: Extract<FromWorker, { type: 'plan_batch' }>['meta'], columns: SearchColumns): void;
  onCompareDone?(result: { A: CompareSide; B: CompareSide }): void;
  onError?(stage: string, message: string): void;
  /** M2.2: a whole-loop family batch or a channel's static header. */
  onFamily?(msg: FamilyMessage): void;
  /** M2.2: a lens's Python pack is loaded (ms it took; 0 if it already was). */
  onPackReady?(pack: string, ms: number): void;
}

export type PyodideSource = 'self' | 'cdn';

export class ArenaClient {
  readonly worker: Worker;
  world: World | null = null;
  tick = 0;
  private readonly ready: Promise<World>;

  constructor(ev: ArenaEvents, opts: { seed?: number; planner?: string; pyodide?: PyodideSource } = {}) {
    const base = import.meta.env.BASE_URL;
    perf.mark('worker_create', wallMs());
    this.worker = new Worker(new URL('./arena.worker.ts', import.meta.url), { type: 'module' });
    this.ready = new Promise((resolve, reject) => {
      this.worker.onmessage = (m: MessageEvent<FromWorker>) => {
        const d = m.data;
        if (d.type === 'mark') perf.mark(d.name, d.at);
        else if (d.type === 'family') ev.onFamily?.(d);
        else if (d.type === 'pack_ready') { this.packs.add(d.pack); ev.onPackReady?.(d.pack, d.ms); }
        else if (d.type === 'world') {
          this.world = d.world;
          this.tick = 0;
          perf.mark('world_received', wallMs());
          ev.onWorld?.(d.world, d.occupancy);
          resolve(d.world);
        } else if (d.type === 'plan_batch') {
          perf.planBatch(d.columns.seq.length, d.at);
          if (d.meta.compare) ev.onCompareBatch?.(d.meta, d.columns);
          else ev.onPlanBatch?.(d.meta, d.columns);
        } else if (d.type === 'compare_done') {
          ev.onCompareDone?.(d.result);
        } else if (d.type === 'play_done') {
          const w = this.playWaiting.get(d.id);
          this.playWaiting.delete(d.id);
          if (d.error !== undefined) w?.reject(new Error(d.error));
          else w?.resolve(JSON.parse(d.result ?? 'null'));
        } else if (d.type === 'tick') {
          this.tick = d.tick.tick;
          perf.tick(d.stepMs);
          ev.onTick?.(d.tick, d.ranges);
        } else {
          ev.onError?.(d.stage, d.message);
          if (d.stage === 'boot') reject(new Error(d.message));
        }
      };
    });
    const boot: BootRequest = {
      type: 'boot',
      pyodideBase: opts.pyodide === 'cdn' ? PYODIDE_INDEX_URL : `${base}generated/pyodide/`,
      assetsBase: `${base}generated/`,
      seed: opts.seed ?? 1,
      planner: opts.planner ?? 'astar',
      batchSize: 2048,
    };
    this.worker.postMessage(boot);
  }

  whenReady(): Promise<World> {
    return this.ready;
  }

  /**
   * Advance one tick, applying `inputs` at its start (each row gets this
   * tick). Returns the stamped rows: the run's input log (share links).
   */
  step(inputs: Omit<InputRow, 'tick'>[] = []): InputRow[] {
    const rows = inputs.map((i) => ({ ...i, tick: this.tick }) as InputRow);
    this.worker.postMessage({ type: 'step', inputs: rows });
    return rows;
  }

  /**
   * Inputs made while a step is in flight (M2.0): they join that step's
   * tick if it is still planning (cancelling its search), otherwise the next.
   * The model stamps them; `Tick.inputs` reports where they landed.
   */
  amend(inputs: Omit<InputRow, 'tick'>[]): void {
    const rows = inputs.map((i) => ({ ...i, tick: this.tick }) as InputRow);
    this.worker.postMessage({ type: 'amend', inputs: rows });
  }

  /** Packs the worker has loaded (M2.2). */
  readonly packs = new Set<string>(['core']);

  /** Load a lens's Python pack in the worker (once). */
  loadPack(pack: string): void {
    if (pack === 'core' || this.packs.has(pack)) return;
    this.worker.postMessage({ type: 'load_pack', pack });
  }

  /** Two planners on the same start, goal and seed; the model is unchanged. */
  compare(a: string, b: string, x: number, y: number): void {
    this.worker.postMessage({ type: 'compare', a, b, x, y });
  }

  private playNext = 1;
  private readonly playWaiting = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();

  /**
   * M3.5: ask coco_lab.play (in the worker) to view a level, score a
   * submission or begin a map budget. Queued behind any step in flight.
   */
  play<T>(request: Record<string, unknown>): Promise<T> {
    const id = this.playNext++;
    return new Promise<T>((resolve, reject) => {
      this.playWaiting.set(id, { resolve: resolve as (v: unknown) => void, reject });
      this.worker.postMessage({ type: 'play', id, request: JSON.stringify(request) });
    });
  }

  close(): void {
    this.worker.terminate();
  }
}
