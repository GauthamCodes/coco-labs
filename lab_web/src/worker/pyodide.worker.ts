// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Pyodide worker. Started only when a user edits a map (the page never
 * creates it otherwise), it loads the PINNED Pyodide from its CDN, installs
 * coco_lab from the wheel this site serves (sha256-checked against the
 * catalog before installation), and runs `recompute.py` -- glue that calls
 * coco_lab's own load_bundle, search and write_bundle. No package other
 * than micropip (from Pyodide's own lock file) and coco_lab is installed.
 */

import recomputeSource from './recompute.py?raw';
import type { EditRequest, EditResponse, WorkerTimings } from './protocol';

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

async function start(req: EditRequest) {
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

self.onmessage = async (ev: MessageEvent<EditRequest>) => {
  const req = ev.data;
  let stage: 'load' | 'edit' = 'load';
  const post = (msg: EditResponse, transfer: Transferable[] = []) =>
    (self as unknown as { postMessage(m: unknown, t: Transferable[]): void }).postMessage(msg, transfer);
  try {
    const first = ready === null;
    ready ??= start(req);
    const { py, cold } = await ready;
    stage = 'edit';
    const edit = py.runPython('lab_recompute.edit') as (...a: unknown[]) => PyProxy;
    const out = edit(req.manifest, req.arraysName, req.arraysFile, req.cell[0], req.cell[1]);
    const r = out.toJs({ dict_converter: Object.fromEntries }) as Record<string, any>;
    out.destroy();
    const manifest = new Uint8Array(r.manifest);
    const arraysFile = new Uint8Array(r.arrays_file);
    post({
      id: req.id, ok: true, manifest, arraysFile, arraysName: r.arrays_name,
      contentHash: r.content_hash, cocoLabVersion: r.coco_lab_version,
      pythonVersion: r.python_version, pyodideVersion: py.version,
      timings: { ...(first ? cold : {}), ...(r.timings as WorkerTimings) },
    }, [manifest.buffer, arraysFile.buffer]);
  } catch (exc) {
    const msg = (exc as Error).message ?? String(exc);
    if (stage === 'load') ready = null; // let a later edit retry the load
    // a Python exception's message ends with its own "Type: message" line
    const last = msg.trim().split('\n').filter(Boolean).pop() ?? msg;
    post({ id: req.id, ok: false, stage, error: stage === 'edit' ? last : msg });
  }
};
