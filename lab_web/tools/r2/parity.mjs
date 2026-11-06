// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.4: native-vs-browser parity of algorithm files. tools/r2/parity_cases.py runs every
 * starter template (coco_lab/coco_lab/templates/) on the first scenarios of a COCO-Bench v0
 * suite, beside a built-in, in CPython (a subprocess, PYTHONHASHSEED=0 as everywhere user code
 * runs) and in Pyodide (the built site's coco_lab packs: run `npm run arena-assets` first).
 * Every status, hash chain, count, determinism flag, validation report (wall times excluded) and
 * digest must be IDENTICAL: 0 differences, as R1's experiment parity.
 *
 *   node tools/r2/parity.mjs [--python PY] [--out OUT.json] [--only planner_astar.py,...]
 *
 * Exit 0 only if everything matches.
 */
import { spawnSync } from 'node:child_process';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import { loadPyodide, version as pyodideVersion } from 'pyodide';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => { if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]); return acc; }, []));
const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '..', '..');
const repo = join(web, '..');
const gen = join(web, 'public', 'generated');
const tdir = join(repo, 'coco_lab', 'coco_lab', 'templates');
const only = args.only ? new Set(args.only.split(',')) : null;

const worlds = {};
for (const id of ['coco_arena_v1', 'coco_arena_v2', 'coco_depot_v1', 'coco_depot_colours_v1']) {
  worlds[id] = readFileSync(join(repo, 'worlds', `${id}.json`), 'utf-8');
}
const templates = {};
for (const f of readdirSync(tdir).filter((n) => n.endsWith('.py')).sort()) if (!only || only.has(f)) templates[f] = readFileSync(join(tdir, f), 'utf-8');
const inputs = { templates_json: JSON.stringify(templates), worlds_json: JSON.stringify(worlds) };
const code = readFileSync(join(here, 'parity_cases.py'), 'utf-8');

const python = args.python ?? process.env.PYTHON ?? 'python3';
let t0 = Date.now();
const native = spawnSync(python, ['-P', '-c', 'import json, sys\ng = json.load(sys.stdin)\nexec(sys.argv[1], g)\nsys.stdout.write(g["result"])', code],
  { input: JSON.stringify(inputs), maxBuffer: 1e9, cwd: os.tmpdir(), env: { ...process.env, PYTHONHASHSEED: '0' } });
if (native.status !== 0) throw new Error(`CPython failed: ${native.stderr}`);
const nativeMs = Date.now() - t0;
const nativeVersion = spawnSync(python, ['-c', 'import sys, platform; print(sys.version.split()[0], platform.machine())']).stdout.toString().trim();

t0 = Date.now();
const py = await loadPyodide({ indexURL: join(web, 'node_modules', 'pyodide') + '/', stdLibURL: join(gen, 'pyodide', 'python_stdlib.zip'),
  env: { PYTHONHASHSEED: '0', HOME: '/home/pyodide' } });
py.unpackArchive(new Uint8Array(readFileSync(join(gen, 'arena', 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
const manifest = JSON.parse(readFileSync(join(gen, 'arena', 'manifest.json'), 'utf-8'));
if (!manifest.packs.user) throw new Error('the built site has no user pack: run npm run arena-assets');
for (const pack of Object.values(manifest.packs)) py.unpackArchive(new Uint8Array(readFileSync(join(gen, 'arena', pack.file))), 'zip', { extractDir: '/home/pyodide' });
for (const [k, v] of Object.entries(inputs)) py.globals.set(k, v);
py.runPython(code);
const wasm = JSON.parse(py.globals.get('result'));
const wasmMs = Date.now() - t0;
const nat = JSON.parse(native.stdout.toString());

const failures = [];
let compared = 0;
function same(a, b, path) {
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) { failures.push({ path, native: `length ${a.length}`, pyodide: `length ${b.length}` }); return; }
    a.forEach((x, i) => same(x, b[i], `${path}[${i}]`));
    return;
  }
  if (a && b && typeof a === 'object' && typeof b === 'object') {
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) same(a[k], b[k], `${path}.${k}`);
    return;
  }
  compared++;
  if (!Object.is(a, b) && !(a === 0 && b === 0)) failures.push({ path, native: a, pyodide: b });
}
const cases = {};
for (const name of Object.keys(nat)) {
  const before = failures.length;
  same(nat[name], wasm[name], name);
  const n = nat[name];
  const nondet = n.runs.filter((r) => r.deterministic === false).length;
  cases[name] = { runs: n.runs.length, digest: n.digest, statuses: n.runs.map((r) => `${r.algorithm}:${r.status}`), nondeterministic: nondet,
    differences: failures.length - before };
}
const report = {
  about: 'R2.4 native-vs-Pyodide parity of the starter templates (lab_web/tools/r2/parity.mjs); wall times excluded',
  pass: failures.length === 0, compared, cases, failures: failures.slice(0, 50),
  native: { python: nativeVersion, ms: nativeMs }, pyodide: { version: pyodideVersion, ms: wasmMs },
};
if (args.out) writeFileSync(args.out, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ pass: report.pass, compared, cases, failures: failures.slice(0, 5) }, null, 1));
process.exit(report.pass ? 0 : 1);
