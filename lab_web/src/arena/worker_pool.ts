// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** One warm interpreter, no running model or personal data. Claimed once. */
import { perf } from './perf';
import { pinnedBase } from '../offline/updates';
let warm: Worker | null = null;
export function createArenaWorker(): Worker {
  return new Worker(new URL('./arena.worker.ts', import.meta.url), { type: 'module' });
}
export function warmModel(): void {
  if (warm) return;
  warm = createArenaWorker();
  warm.addEventListener('message', event => { if (event.data.type === 'mark') perf.mark(event.data.name, event.data.at); });
  const base = pinnedBase();  // G1.8: pinned to this page's build
  warm.postMessage({ type: 'warm', pyodideBase: `${base}generated/pyodide/`, assetsBase: `${base}generated/`, seed: 1, planner: 'astar', batchSize: 2048, hashVersion: 3 });
  warm.onerror = () => { warm?.terminate(); warm = null; };
}
export function claimWarmWorker(eligible: boolean): Worker {
  if (!eligible || !warm) return createArenaWorker();
  const worker = warm; warm = null; worker.onerror = null;
  return worker;
}
