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
import { wallMs, type FromWorker, type InputRow, type SearchColumns, type ToWorker } from './protocol';

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
  pyimport(name: string): { init: (...a: unknown[]) => PyProxy; step: (s: string) => PyProxy;
    compare: (...a: unknown[]) => string;
    begin: (s: string) => void; advance: (n: number) => boolean; amend: (s: string) => void; finish: () => PyProxy };
}

/**
 * Events of the tick's search taken per slice (M2.0). Between slices the
 * worker yields to its event loop, so an `amend` posted by the page is seen
 * within about one slice; the plan itself does not depend on the slicing.
 */
const SLICE_EVENTS = 4096;

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
interface PackInfo { file: string; bytes: number; sha256: string; requires: string[]; modules: string[] }
let booted: { py: Pyodide; manifest: { packs?: Record<string, PackInfo> }; assetsBase: string } | null = null;
const packsLoaded = new Map<string, Promise<number>>();

/**
 * A lens's Python pack (M2.2; tools/arena_packs.json), loaded the first
 * time it is asked for: its `requires` first, then fetched, sha256-checked
 * against the manifest, unpacked and every module imported. Resolves with
 * the milliseconds it took (0 if it was already loaded).
 */
function loadPack(name: string): Promise<number> {
  const have = packsLoaded.get(name);
  if (have) return have.then(() => 0);
  const p = (async () => {
    if (!booted) throw new Error('load_pack before boot');
    const t0 = performance.now();
    const info = booted.manifest.packs?.[name];
    if (!info) throw new Error(`no pack ${name} in the manifest`);
    for (const r of info.requires) await loadPack(r);
    const buf = new Uint8Array(await (await fetch(`${booted.assetsBase}arena/${info.file}`, { credentials: 'omit' })).arrayBuffer());
    const digest = await sha256(buf);
    if (digest !== info.sha256) throw new Error(`${info.file} sha256 ${digest} is not the manifest's ${info.sha256}`);
    booted.py.unpackArchive(buf, 'zip', { extractDir: '/home/pyodide' });
    booted.py.runPython(`import importlib\nfor m in ${JSON.stringify(info.modules)}: importlib.import_module('coco_lab.' + m)`);
    return performance.now() - t0;
  })();
  packsLoaded.set(name, p);
  return p;
}
let onBatchFn: ((cols: PyProxy, metaJson: string) => void) | null = null;

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
  booted = { py, manifest, assetsBase: req.assetsBase };
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
  onBatchFn = onBatch;
  // M2.2: whole-loop family batches -- numeric columns transferred, the rest as JSON
  const onFamily = (numeric: PyProxy, json: string) => {
    const d = JSON.parse(json) as { channel: string; tick?: number; numeric?: string[]; plain?: Record<string, unknown[]>;
      scalars?: Record<string, number | string | boolean>; header?: Record<string, unknown> };
    if (d.header) { numeric.destroy(); post({ type: 'family', channel: d.channel, header: d.header }); return; }
    const columns: Record<string, ArrayLike<number> | ArrayLike<bigint> | boolean[] | string[]> = {};
    const buffers: ArrayBuffer[] = [];
    for (const name of d.numeric ?? []) {
      const a = column(numeric, name);
      columns[name] = a as unknown as ArrayLike<number>;
      buffers.push(a.buffer as ArrayBuffer);
    }
    numeric.destroy();
    for (const [name, v] of Object.entries(d.plain ?? {})) columns[name] = v as boolean[] | string[];
    post({ type: 'family', channel: d.channel, tick: d.tick, columns, scalars: d.scalars }, buffers);
  };
  const out = glue.init(spec, req.seed, req.planner, onBatch, req.batchSize, onFamily);
  const world = JSON.parse(out.get(0) as unknown as string);
  const occ = out.get(1);
  const occupancy = (occ.toJs() as Uint8Array).slice();
  occ.destroy();
  out.destroy();
  post({ type: 'world', world, occupancy, at: wallMs() }, [occupancy.buffer]);
  mark('arena_ready');
}

// A yield to the event loop with no timer clamp (setTimeout(0) waits >= 4 ms once nested).
const yieldChannel = new MessageChannel();
const yielded: (() => void)[] = [];
yieldChannel.port1.onmessage = () => yielded.shift()?.();
const yieldNow = () => new Promise<void>((resolve) => { yielded.push(resolve); yieldChannel.port2.postMessage(0); });

/** Inputs that arrived by `amend`: they join the tick in flight, or open the next one. */
const amends: InputRow[] = [];

async function step(req: Extract<ToWorker, { type: 'step' }>) {
  if (!glue) throw new Error('step before boot');
  const t0 = performance.now();
  glue.begin(JSON.stringify([...amends.splice(0), ...req.inputs]));
  for (;;) {
    if (!glue.advance(SLICE_EVENTS)) { await yieldNow(); }
    else {
      // a last look: an input that arrived during the final slice still joins this tick
      await yieldNow();
      if (amends.length === 0) break;
    }
    if (amends.length) {
      try {
        glue.amend(JSON.stringify(amends.splice(0)));
      } catch (e) {
        // refused (the model said why); the tick goes on with what it had
        post({ type: 'error', stage: 'amend', message: e instanceof Error ? e.message : String(e) });
      }
    }
  }
  const out = glue.finish();
  const tick = JSON.parse(out.get(0) as unknown as string);
  const r = out.get(1);
  const b = r.getBuffer('f32');
  const ranges = (b.data as Float32Array).slice();
  b.release();
  r.destroy();
  out.destroy();
  post({ type: 'tick', tick, ranges, stepMs: performance.now() - t0, at: wallMs() }, [ranges.buffer]);
}

function compare(req: Extract<ToWorker, { type: 'compare' }>) {
  if (!glue || !onBatchFn) throw new Error('compare before boot');
  const result = JSON.parse(glue.compare(req.a, req.b, req.x, req.y, onBatchFn, 2048));
  post({ type: 'compare_done', result });
}

let queue: Promise<void> = Promise.resolve();
self.onmessage = (ev: MessageEvent<ToWorker>) => {
  const req = ev.data;
  // not queued behind a step: the step in flight picks these up between slices
  if (req.type === 'amend') { amends.push(...req.inputs); return; }
  // a pack loads beside the steps (its fetch overlaps them); the model never waits for it
  if (req.type === 'load_pack') {
    void queue.then(() => loadPack(req.pack))
      .then((ms) => { post({ type: 'pack_ready', pack: req.pack, ms }); mark(`pack_${req.pack}_ready`); })
      .catch((e) => post({ type: 'error', stage: 'load_pack', message: e instanceof Error ? e.message : String(e) }));
    return;
  }
  queue = queue.then(async () => {
    try {
      if (req.type === 'boot') await boot(req);
      else if (req.type === 'compare') compare(req);
      else await step(req);
    } catch (e) {
      post({ type: 'error', stage: req.type, message: e instanceof Error ? e.message : String(e) });
    }
  });
};
