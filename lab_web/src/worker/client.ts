// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The page's side of the worker. The Worker object is created on the first
 * edit, not before: until then no Pyodide byte is requested (verified by the
 * browser harness's network log, 1D-6).
 */

import { PYODIDE_INDEX_URL } from '../../site.config.ts';
import type { EditRequest, EditResponse } from './protocol';

let worker: Worker | null = null;
let nextId = 1;
const pending = new Map<number, (r: EditResponse) => void>();

function getWorker(): Worker {
  if (!worker) {
    worker = new Worker(new URL('./pyodide.worker.ts', import.meta.url), { type: 'module' });
    worker.onmessage = (ev: MessageEvent<EditResponse>) => {
      const done = pending.get(ev.data.id);
      pending.delete(ev.data.id);
      done?.(ev.data);
    };
  }
  return worker;
}

export function workerStarted(): boolean {
  return worker !== null;
}

export function requestEdit(req: Omit<EditRequest, 'id' | 'type' | 'pyodideIndexUrl'>): Promise<EditResponse> {
  const id = nextId++;
  return new Promise((resolve) => {
    pending.set(id, resolve);
    // copies, so the page keeps its own bytes
    getWorker().postMessage({
      ...req, id, type: 'edit', pyodideIndexUrl: PYODIDE_INDEX_URL,
      manifest: req.manifest.slice(), arraysFile: req.arraysFile.slice(),
    } satisfies EditRequest);
  });
}
