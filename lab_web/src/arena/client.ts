// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The page's side of the Arena worker. Created as soon as the Arena view
 * opens (README 5.5: Pyodide loads while attract mode plays), so the cold
 * start overlaps with what the visitor is already watching.
 */

import { PYODIDE_INDEX_URL } from '../../site.config.ts';
import { wallMs, type BootRequest, type CompareResult, type CompareInflation, type FamilyMessage, type FromWorker, type InputRow, type SearchColumns, type SpecFile, type Tick, type World } from './protocol';
import { perf } from './perf';
import { claimWarmWorker } from './worker_pool';
import { pinnedBase } from '../offline/updates';

export interface ArenaEvents {
  onLoopCompareBatch?(frames: import('./protocol').LoopFrame[][], done: boolean): void;
  onWorld?(world: World, occupancy: Uint8Array): void;
  onPlanBatch?(meta: Extract<FromWorker, { type: 'plan_batch' }>['meta'], columns: SearchColumns): void;
  onTick?(tick: Tick, ranges: Float32Array): void;
  onCompareBatch?(meta: Extract<FromWorker, { type: 'plan_batch' }>['meta'], columns: SearchColumns): void;
  onCompareDone?(result: CompareResult): void;
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

  constructor(ev: ArenaEvents, opts: { hashVersion?: 1 | 2 | 3; seed?: number; planner?: string; pyodide?: PyodideSource; spec?: SpecFile; game?: BootRequest['game'] } = {}) {
    // G1.8: the worker loads its runtime and data pinned to this page's build
    const pinned = pinnedBase();
    perf.mark('worker_create', wallMs());
    this.worker = claimWarmWorker(opts.pyodide !== 'cdn');
    this.ready = new Promise((resolve, reject) => {
      this.worker.onerror = (event) => {
        const message = event.message || 'The model worker could not load';
        ev.onError?.('worker', message); reject(new Error(message));
      };
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
        } else if (d.type === 'compare_loop_batch') {
          ev.onLoopCompareBatch?.(d.frames, d.done);
        } else if (d.type === 'compare_done') {
          ev.onCompareDone?.(d.result);
        } else if (d.type === 'play_done') {
          const w = this.playWaiting.get(d.id);
          this.playWaiting.delete(d.id);
          if (d.error !== undefined) w?.reject(new Error(d.error));
          else w?.resolve(JSON.parse(d.result ?? 'null'));
        } else if (d.type === 'game_done') {
          const w = this.gameWaiting.get(d.id);
          this.gameWaiting.delete(d.id);
          w?.(d.error !== undefined ? { error: d.error } : JSON.parse(d.result ?? 'null'));
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
    // Event-only users report errors through onError; promise users still get
    // the original rejection when they call whenReady().
    void this.ready.catch(() => {});
    const boot: BootRequest = {
      type: 'boot',
      pyodideBase: opts.pyodide === 'cdn' ? PYODIDE_INDEX_URL : `${pinned}generated/pyodide/`,
      assetsBase: `${pinned}generated/`,
      seed: opts.seed ?? 1,
      planner: opts.planner ?? 'astar',
      batchSize: 2048,
      hashVersion: opts.hashVersion ?? 1,
      ...(opts.spec ? { spec: opts.spec } : {}),
      ...(opts.game ? { game: opts.game } : {}),
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
  compare(a: string, b: string, x: number, y: number, inflation?: import('./protocol').CompareInflation): void {
    this.worker.postMessage({ type: 'compare', a, b, x, y, ...(inflation ? { inflation } : {}) });
  }

  /** One graph/start/goal for every pane; Python validates the two/four names. */
  compareMany(planners: string[], x: number, y: number, inflation?: CompareInflation): void {
    if (planners.length !== 2 && planners.length !== 4) throw new Error('Compare needs two or four planners');
    this.worker.postMessage({ type: 'compare', a: planners[0], b: planners[1], planners, x, y, ...(inflation ? { inflation } : {}) });
  }

  compareLoop(request: Omit<import('./protocol').LoopCompareRequest, 'type'>): void {
    this.worker.postMessage({ type: 'compare_loop', ...request });
  }

  /** G1.13: delta = only the cells changed since the last view, from a cached static map (Play). */
  requestCostmap(delta = false): void { this.worker.postMessage({ type: 'costmap_view', delta }); }

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

  private gameNext = 1;
  private readonly gameWaiting = new Map<number, (v: unknown) => void>();

  /** G1: a read-only game query (Grasp Assist's preview, AUTO's goal, the record, the stars). */
  game<T>(op: string, arg?: unknown): Promise<T> {
    const id = this.gameNext++;
    return new Promise<T>((resolve) => {
      this.gameWaiting.set(id, resolve as (v: unknown) => void);
      this.worker.postMessage({ type: 'game', id, op, arg: arg === undefined || arg === null ? null : JSON.stringify(arg) });
    });
  }

  close(): void {
    this.worker.terminate();
  }
}
