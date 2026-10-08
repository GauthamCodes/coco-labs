// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena worker (M1.5): Pyodide + coco_lab + arena_glue.py, one Arena.
 *
 * Boot: Pyodide from `pyodideBase` -- the SELF-HOSTED copy this site ships
 * (generated/pyodide/, same origin, trimmed stdlib), or the pinned CDN for
 * comparison -- and coco_lab from arena/coco_lab.zip, sha256-checked
 * against arena/manifest.json and unpacked into the file system: no wheel,
 * no micropip, no package from Pyodide's index. Then the glue builds the
 * Arena from the World Spec's canonical JSON.
 *
 * Step: one tick per request. Plan events stream to the page WHILE the
 * search runs, in columnar batches (ADR 0001), posted with their buffers
 * transferred; the tick follows with its ranges. Nothing here computes:
 * coco_lab does (README section 3).
 */

import glueSource from './arena_glue.py?raw';
import { wallMs, type FromWorker, type SearchColumns, type ToWorker } from './protocol';

interface PyBuf { data: ArrayBufferView & ArrayLike<number | bigint>; release(): void }
interface PyProxy {
  get(k: string | number): PyProxy & string & Uint8Array;
  getBuffer(type?: string): PyBuf;
  toJs(): unknown;
  destroy(): void;
}
interface Pyodide {
  FS: { writeFile(path: string, data: Uint8Array | string): void };
  unpackArchive(buf: Uint8Array, format: string, opts: { extractDir: string }): void;
  runPython(code: string): unknown;
  pyimport(name: string): { init: (...a: unknown[]) => PyProxy; step: (s: string) => PyProxy };
}

const post = (msg: FromWorker, transfer: Transferable[] = []) =>
  (self as unknown as { postMessage(m: unknown, t: Transferable[]): void }).postMessage(msg, transfer);
const mark = (name: string) => post({ type: 'mark', name, at: wallMs() });

const COLUMN_TYPES: Record<keyof SearchColumns, 'u64' | 'f64' | 'i32'> = {
  seq: 'u64', tick: 'u64', t_world: 'f64', kind: 'i32', row: 'i32', col: 'i32', sub: 'i32',
  g: 'f64', h: 'f64', f: 'f64', parent_row: 'i32', parent_col: 'i32', parent_sub: 'i32',
};

async function sha256(bytes: Uint8Array): Promise<string> {
  const d = await crypto.subtle.digest('SHA-256', bytes as Uint8Array<ArrayBuffer>);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

let glue: ReturnType<Pyodide['pyimport']> | null = null;

/** Copy one Python array column out into its own transferable typed array. */
function column(cols: PyProxy, name: string): ArrayBufferView {
  const p = cols.get(name);
  const b = p.getBuffer();
  const copy = (b.data as unknown as { slice(): ArrayBufferView }).slice();
  b.release();
  p.destroy();
  return copy;
}

async function boot(req: Extract<ToWorker, { type: 'boot' }>) {
  mark('worker_boot');
  const files = Promise.all([
    fetch(`${req.assetsBase}arena/manifest.json`, { credentials: 'omit' }).then((r) => r.json()),
    fetch(`${req.assetsBase}arena/coco_lab.zip`, { credentials: 'omit' }).then((r) => r.arrayBuffer()),
    fetch(`${req.assetsBase}arena/coco_arena_v1.json`, { credentials: 'omit' }).then((r) => r.text()),
  ]);
  const mod = await import(/* @vite-ignore */ `${req.pyodideBase}pyodide.mjs`);
  mark('pyodide_module');
  const py: Pyodide = await mod.loadPyodide({ indexURL: req.pyodideBase });
  mark('pyodide_ready');
  const [manifest, zipBuf, spec] = await files;
  const zip = new Uint8Array(zipBuf);
  const digest = await sha256(zip);
  if (digest !== manifest.coco_lab_zip.sha256) {
    throw new Error(`coco_lab.zip sha256 ${digest} is not the manifest's ${manifest.coco_lab_zip.sha256}`);
  }
  py.unpackArchive(zip, 'zip', { extractDir: '/home/pyodide' });
  py.FS.writeFile('/home/pyodide/arena_glue.py', glueSource);
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  glue = py.pyimport('arena_glue');
  mark('coco_lab_ready');
  const onBatch = (cols: PyProxy, metaJson: string) => {
    const columns = {} as Record<string, ArrayBufferView>;
    for (const name of Object.keys(COLUMN_TYPES)) columns[name] = column(cols, name);
    cols.destroy();
    post({ type: 'plan_batch', meta: JSON.parse(metaJson), columns: columns as unknown as SearchColumns, at: wallMs() },
      Object.values(columns).map((a) => a.buffer as ArrayBuffer));
  };
  const out = glue.init(spec, req.seed, req.planner, onBatch, req.batchSize);
  const world = JSON.parse(out.get(0) as unknown as string);
  const occ = out.get(1);
  const occupancy = (occ.toJs() as Uint8Array).slice();
  occ.destroy();
  out.destroy();
  post({ type: 'world', world, occupancy, at: wallMs() }, [occupancy.buffer]);
  mark('arena_ready');
}

function step(req: Extract<ToWorker, { type: 'step' }>) {
  if (!glue) throw new Error('step before boot');
  const t0 = performance.now();
  const out = glue.step(JSON.stringify(req.inputs));
  const tick = JSON.parse(out.get(0) as unknown as string);
  const r = out.get(1);
  const b = r.getBuffer('f32');
  const ranges = (b.data as Float32Array).slice();
  b.release();
  r.destroy();
  out.destroy();
  post({ type: 'tick', tick, ranges, stepMs: performance.now() - t0, at: wallMs() }, [ranges.buffer]);
}

let queue: Promise<void> = Promise.resolve();
self.onmessage = (ev: MessageEvent<ToWorker>) => {
  const req = ev.data;
  queue = queue.then(async () => {
    try {
      if (req.type === 'boot') await boot(req);
      else step(req);
    } catch (e) {
      post({ type: 'error', stage: req.type, message: e instanceof Error ? e.message : String(e) });
    }
  });
};
