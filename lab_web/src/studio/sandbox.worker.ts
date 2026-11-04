// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.2: the user-code worker (ADR 0012). The ONLY place a stranger's algorithm runs in the
 * browser. It is started from a `blob:` URL (sandbox.ts), so it inherits the page's CSP: no
 * `eval`, no `Function`, no dynamic import of new code.
 *
 * Boot: Pyodide (self-hosted, pinned to this build) + coco_lab and the packs the experiments
 * need, every shipped World Spec fetched -- then, before any user code, lockdown(): the network,
 * storage, other contexts and devices are deleted and pinned; the WebAssembly memory gets a
 * ceiling; Python loses its `js` bridge. Only then does the page hear `ready`.
 *
 * Runs: one request at a time. The Python glue posts `beat` after the user's function returns
 * (the page's watchdog terminates this worker when a call is silent past its time limit) and
 * `chunk`s of thinking and frames while the run goes. Nothing here computes a result.
 */
import glueSource from './sandbox_glue.py?raw';
import { capMemory, lockdown, probe } from './lockdown';

interface Py {
  FS: { writeFile(path: string, data: Uint8Array | string): void };
  unpackArchive(buf: Uint8Array, format: string, opts: { extractDir: string }): void;
  runPython(code: string): unknown;
  pyimport(name: string): { set_post(fn: (s: string) => void): void; register_worlds(s: string): void;
    lockdown(): void; probe(): string; run(s: string): string };
  _module?: { HEAPU8?: Uint8Array };
}
interface PackInfo { file: string; sha256: string; requires: string[]; modules: string[] }
interface Manifest { coco_lab_zip: { sha256: string }; packs?: Record<string, PackInfo> }

/** The worlds an experiment can name (coco_lab.experiments.WORLDS), as shipped. */
const WORLDS = ['coco_arena_v1', 'coco_arena_v2', 'coco_depot_v1', 'coco_depot_colours_v1'];
/** The memory the algorithm may grow to on top of what the boot used. */
const HEADROOM = 1024 * 2 ** 20;

const send = (self as unknown as { postMessage(m: unknown): void }).postMessage.bind(self);
let glue: ReturnType<Py['pyimport']> | null = null;
let py: Py | null = null;

const memory = () => py?._module?.HEAPU8?.length ?? 0;

async function sha256(bytes: Uint8Array): Promise<string> {
  const d = await crypto.subtle.digest('SHA-256', bytes as Uint8Array<ArrayBuffer>);
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function boot(pyodideBase: string, assetsBase: string): Promise<void> {
  const get = (path: string) => fetch(`${assetsBase}${path}`, { credentials: 'omit' });
  const manifest = await (await get('arena/manifest.json')).json() as Manifest;
  const mod = await import(/* @vite-ignore */ `${pyodideBase}pyodide.mjs`);
  // PYTHONHASHSEED=0: a set of strings iterates in the same order here, natively and in CI
  py = await mod.loadPyodide({ indexURL: pyodideBase, env: { PYTHONHASHSEED: '0', HOME: '/home/pyodide' } }) as Py;
  const zip = new Uint8Array(await (await get('arena/coco_lab.zip')).arrayBuffer());
  if (await sha256(zip) !== manifest.coco_lab_zip.sha256) throw new Error('coco_lab.zip does not match the manifest');
  py.unpackArchive(zip, 'zip', { extractDir: '/home/pyodide' });
  const order: string[] = [];
  const visit = (name: string) => {
    if (order.includes(name)) return;
    for (const r of manifest.packs?.[name]?.requires ?? []) visit(r);
    order.push(name);
  };
  visit('experiments');
  for (const name of order) {
    const info = manifest.packs?.[name];
    if (!info) throw new Error(`no pack ${name}`);
    const buf = new Uint8Array(await (await get(`arena/${info.file}`)).arrayBuffer());
    if (await sha256(buf) !== info.sha256) throw new Error(`${info.file} does not match the manifest`);
    py.unpackArchive(buf, 'zip', { extractDir: '/home/pyodide' });
  }
  const worlds: Record<string, string> = {};
  for (const w of WORLDS) worlds[w] = await (await get(`arena/${w}.json`)).text();
  py.FS.writeFile('/home/pyodide/sandbox_glue.py', glueSource);
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  for (const name of order) py.runPython(`import importlib\nfor m in ${JSON.stringify(manifest.packs![name].modules)}: importlib.import_module('coco_lab.' + m)`);
  glue = py.pyimport('sandbox_glue');
  glue.register_worlds(JSON.stringify(worlds));
  glue.set_post((s: string) => {
    const m = JSON.parse(s) as Record<string, unknown>;
    send({ type: m.k, ...m, memory: memory() });
  });
  // -- from here on no user code has run, and none can reach out -------------------------------
  glue.lockdown();
  const removed = lockdown(self as unknown as Record<string, unknown>);
  capMemory(memory() + HEADROOM);
  send({ type: 'ready', memory: memory(), removed });
}

let booting: Promise<void> | null = null;

self.onmessage = async (ev: MessageEvent) => {
  const req = ev.data as { type: string; id?: number; pyodideBase?: string; assetsBase?: string; request?: string };
  try {
    if (req.type === 'boot') {
      booting ??= boot(req.pyodideBase!, req.assetsBase!);
      await booting;
    } else if (req.type === 'probe') {
      await booting;
      send({ type: 'probe', id: req.id, js: await probe(self as unknown as Record<string, unknown>), python: JSON.parse(glue!.probe()) });
    } else if (req.type === 'run') {
      await booting;
      const t0 = performance.now();
      const result = glue!.run(req.request!);
      send({ type: 'done', id: req.id, result, ms: performance.now() - t0, memory: memory() });
    }
  } catch (e) {
    send({ type: 'failed', id: req.id, error: e instanceof Error ? e.message : String(e), memory: memory() });
  }
};
