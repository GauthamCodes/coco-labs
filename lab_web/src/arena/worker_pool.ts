// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** One warm interpreter, no running model or personal data. Claimed once. */
import { perf } from './perf';
let warm: Worker | null = null;
export function createArenaWorker(): Worker {
  return new Worker(new URL('./arena.worker.ts', import.meta.url), { type: 'module' });
}
export function warmModel(): void {
  if (warm) return;
  // Fetch in parallel with worker/module startup, only after title readiness.
  // Pyodide's pinned Emscripten loader uses instantiateStreaming by default.
  for (const file of typeof document === 'undefined' ? [] : ['pyodide.asm.wasm', 'python_stdlib.zip']) {
    const href = `${import.meta.env.BASE_URL}generated/pyodide/${file}`;
    if (document.querySelector(`link[rel="preload"][href="${href}"]`)) continue;
    const link = document.createElement('link');
    link.rel = 'preload'; link.as = 'fetch'; link.crossOrigin = 'anonymous'; link.href = href;
    document.head.append(link);
  }
  warm = createArenaWorker();
  warm.addEventListener('message', event => { if (event.data.type === 'mark') perf.mark(event.data.name, event.data.at); });
  const base = import.meta.env.BASE_URL;
  warm.postMessage({ type: 'warm', pyodideBase: `${base}generated/pyodide/`, assetsBase: `${base}generated/`, seed: 1, planner: 'astar', batchSize: 2048, hashVersion: 2 });
  warm.onerror = () => { warm?.terminate(); warm = null; };
}
export function claimWarmWorker(eligible: boolean): Worker {
  if (!eligible || !warm) return createArenaWorker();
  const worker = warm; warm = null; worker.onerror = null;
  return worker;
}
