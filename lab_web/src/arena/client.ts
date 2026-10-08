// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The page's side of the Arena worker. Created as soon as the Arena view
 * opens (README 5.5: Pyodide loads while attract mode plays), so the cold
 * start overlaps with what the visitor is already watching.
 */

import { PYODIDE_INDEX_URL } from '../../site.config.ts';
import { wallMs, type BootRequest, type FromWorker, type InputRow, type SearchColumns, type Tick, type World } from './protocol';
import { perf } from './perf';

export interface ArenaEvents {
  onWorld?(world: World, occupancy: Uint8Array): void;
  onPlanBatch?(meta: Extract<FromWorker, { type: 'plan_batch' }>['meta'], columns: SearchColumns): void;
  onTick?(tick: Tick, ranges: Float32Array): void;
  onError?(stage: string, message: string): void;
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
        else if (d.type === 'world') {
          this.world = d.world;
          this.tick = 0;
          perf.mark('world_received', wallMs());
          ev.onWorld?.(d.world, d.occupancy);
          resolve(d.world);
        } else if (d.type === 'plan_batch') {
          perf.planBatch(d.columns.seq.length, d.at);
          ev.onPlanBatch?.(d.meta, d.columns);
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

  /** Advance one tick, applying `inputs` at its start (each row gets this tick). */
  step(inputs: Omit<InputRow, 'tick'>[] = []): void {
    this.worker.postMessage({ type: 'step', inputs: inputs.map((i) => ({ ...i, tick: this.tick })) });
  }

  close(): void {
    this.worker.terminate();
  }
}
