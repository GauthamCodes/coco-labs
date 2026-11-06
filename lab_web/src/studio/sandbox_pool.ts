// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.4: an experiment that includes an algorithm file runs in user-code sandboxes only (ADR
 * 0012): every run of it -- the built-ins' too, so one runtime measures them all -- goes to a
 * pool of Sandbox workers. Each run is a pure function of the spec and its index, so which
 * sandbox runs it never changes its record (the same records as `coco experiment run`).
 */
import { Sandbox, type Ended, type Family } from './sandbox';
import type { RunRecord } from '../workbench/pool';

export interface PoolProgress { done: number; total: number; failed: number }

export class SandboxPool {
  private boxes: Sandbox[];
  private cancelled = false;
  constructor(readonly size: number) { this.boxes = Array.from({ length: Math.max(1, size) }, () => new Sandbox()); }

  async call(op: string, payload: Record<string, unknown>, family: Family): Promise<string> {
    const e = await this.boxes[0].run({ op, ...payload }, family);
    if (!e.ok) throw new Error(e.message);
    return e.result;
  }

  /** Run `indices` across the pool; a run a sandbox could not finish is recorded as an error. */
  async run(spec: unknown, code: string[], family: Family, indices: number[], onRecord: (r: RunRecord) => void,
    onProgress: (p: PoolProgress) => void, describe: (i: number) => Partial<RunRecord> = () => ({})): Promise<RunRecord[]> {
    this.cancelled = false;
    const queue = [...indices];
    const out: RunRecord[] = [];
    let failed = 0;
    const worker = async (box: Sandbox) => {
      for (;;) {
        const i = queue.shift();
        if (i === undefined || this.cancelled) return;
        const e: Ended = await box.run({ op: 'runs', spec, code, indices: [i] }, family);
        let rec: RunRecord;
        if (e.ok) rec = (JSON.parse(e.result) as RunRecord[])[0];
        else {
          failed += 1;
          rec = { index: i, sweep_index: 0, sweep: {}, algorithm: '?', name: '?', scenario: '?', scenario_index: -1, ...describe(i),
            status: 'error', success: false, metrics: {}, chain: `sandbox:${e.reason}`, fail_tick: null, error: `${e.reason}: ${e.message}` };
        }
        out.push(rec);
        onRecord(rec);
        onProgress({ done: out.length, total: indices.length, failed });
      }
    };
    await Promise.all(this.boxes.map(worker));
    return out.sort((a, b) => a.index - b.index);
  }

  cancel(): void { this.cancelled = true; }
  close(): void { for (const b of this.boxes) b.terminate(); }
}
