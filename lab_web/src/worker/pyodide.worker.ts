// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Pyodide worker. Started only when a user paints a map, changes a
 * search setting or starts a race (the page never creates it otherwise), it
 * loads the PINNED Pyodide from its CDN, installs coco_lab from the wheel
 * this site serves (sha256-checked against the catalog before
 * installation), and runs `recompute.py` -- glue that calls coco_lab's own
 * load_bundle, search and bundle serialisation. No package other than
 * micropip (from Pyodide's own lock file) and coco_lab is installed.
 */

import recomputeSource from './recompute.py?raw';
import type { RecomputeRequest, RecomputeResponse, WorkerBundle, WorkerTimings } from './protocol';

interface PyProxy {
  toJs(opts?: { dict_converter?: typeof Object.fromEntries; create_pyproxies?: boolean }): unknown;
  destroy(): void;
}
interface Pyodide {
  version: string;
  FS: { writeFile(path: string, data: Uint8Array | string): void; mkdirTree(path: string): void };
  loadPackage(names: string[]): Promise<void>;
  pyimport(name: string): { install(url: string): Promise<void> } & Record<string, unknown>;
  runPython(code: string): unknown;
  runPythonAsync(code: string): Promise<unknown>;
  globals: { get(name: string): (...args: unknown[]) => PyProxy };
}

let ready: Promise<{ py: Pyodide; cold: Partial<WorkerTimings> }> | null = null;

async function sha256(bytes: Uint8Array): Promise<string> {
  const d = await crypto.subtle.digest('SHA-256', bytes as Uint8Array<ArrayBuffer>);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function start(req: RecomputeRequest) {
  const cold: Partial<WorkerTimings> = {};
  let t = performance.now();
  const mod = await import(/* @vite-ignore */ `${req.pyodideIndexUrl}pyodide.mjs`);
  const py: Pyodide = await mod.loadPyodide({ indexURL: req.pyodideIndexUrl });
  cold.pyodide_load_ms = performance.now() - t;

  t = performance.now();
  await py.loadPackage(['micropip']);
  cold.micropip_ms = performance.now() - t;

  t = performance.now();
  const res = await fetch(req.wheelUrl, { credentials: 'omit' });
  if (!res.ok) throw new Error(`cannot fetch the coco_lab wheel: HTTP ${res.status}`);
  const wheel = new Uint8Array(await res.arrayBuffer());
  const digest = await sha256(wheel);
  if (digest !== req.wheelSha256) {
    throw new Error(`coco_lab wheel sha256 ${digest} is not the catalog's ${req.wheelSha256}`);
  }
  const name = req.wheelUrl.split('/').pop()!;
  py.FS.mkdirTree('/tmp/wheels');
  py.FS.writeFile(`/tmp/wheels/${name}`, wheel);
  await py.pyimport('micropip').install(`emfs:/tmp/wheels/${name}`);
  cold.wheel_install_ms = performance.now() - t;

  t = performance.now();
  py.FS.mkdirTree('/home/pyodide/lab');
  py.FS.writeFile('/home/pyodide/lab/lab_recompute.py', recomputeSource);
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide/lab')\nimport lab_recompute");
  cold.import_ms = performance.now() - t;
  return { py, cold };
}

self.onmessage = async (ev: MessageEvent<RecomputeRequest>) => {
  const req = ev.data;
  let stage: 'load' | 'edit' = 'load';
  const post = (msg: RecomputeResponse, transfer: Transferable[] = []) =>
    (self as unknown as { postMessage(m: unknown, t: Transferable[]): void }).postMessage(msg, transfer);
  try {
    const first = ready === null;
    ready ??= start(req);
    const { py, cold } = await ready;
    stage = 'edit';
    const fn = req.type === 'localise' ? 'lab_recompute.localise'
      : req.type === 'mapping' ? 'lab_recompute.mapping'
        : req.type === 'search' ? 'lab_recompute.search_lab'
          : req.type === 'replan' ? 'lab_recompute.replan_lab' : 'lab_recompute.recompute';
    const recompute = py.runPython(fn) as (...a: unknown[]) => PyProxy;
    const out = recompute(JSON.stringify(req.spec), req.manifest, req.arraysName, req.arraysFile);
    const r = out.toJs({ dict_converter: Object.fromEntries }) as Record<string, any>;
    out.destroy();
    const bundles: WorkerBundle[] = (r.bundles as Array<Record<string, any>>).map((b) => ({
      manifest: new Uint8Array(b.manifest), arraysFile: new Uint8Array(b.arrays_file),
      arraysName: b.arrays_name, contentHash: b.content_hash,
    }));
    post({
      id: req.id, ok: true, bundles, optimalCost: r.optimal_cost ?? null,
      cocoLabVersion: r.coco_lab_version, pythonVersion: r.python_version, pyodideVersion: py.version,
      timings: { ...(first ? cold : {}), ...(r.timings as WorkerTimings) },
    }, bundles.flatMap((b) => [b.manifest.buffer, b.arraysFile.buffer]));
  } catch (exc) {
    const msg = (exc as Error).message ?? String(exc);
    if (stage === 'load') ready = null; // let a later request retry the load
    // a Python exception's message ends with its own "Type: message" line
    const last = msg.trim().split('\n').filter(Boolean).pop() ?? msg;
    const refused = /^(lab_recompute\.)?Refused: /.test(last);
    post({
      id: req.id, ok: false, stage, refused,
      error: stage === 'edit' ? last.replace(/^(lab_recompute\.)?\w+: /, '') : msg,
    });
  }
};
