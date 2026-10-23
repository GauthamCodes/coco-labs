// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.8: the native-vs-Pyodide gate. tools/g1/native_gate_cases.py runs in CPython
 * (a subprocess, the installed coco_lab) and in Pyodide (the built site's own
 * coco_lab packs, public/generated/arena/: run `npm run arena-assets` first), and
 * the two results must agree:
 *
 *   - global families EXACT: every global planner's event columns, path and
 *     summary, the Compare costmap, and every tick's state hash of a Fetch Rush
 *     session on the Depot (and its scorecard);
 *   - continuous families within 1e-9 (absolute): the Compare loops' poses,
 *     particles, chosen trajectories, distances, clearances and errors; their
 *     discrete fields (status, success, tick) and state hashes exact; the
 *     wall-clock compute_ms excluded.
 *
 *   node tools/g1/native_gate.mjs [--python PY] [--hv 3] [--out OUT.json]
 *
 * Exit 0 only if every case passes. --hv 2 runs the same cases under hash
 * version 2 (the M5 numerics), which is expected to FAIL: that is the
 * divergence G1.8 fixed, kept measurable.
 */
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import { loadPyodide, version as pyodideVersion } from 'pyodide';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => { if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]); return acc; }, []));
const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '..', '..');
const repo = join(web, '..');
const gen = join(web, 'public', 'generated');
const hv = Number(args.hv ?? 3);
const TOL = 1e-9;

const inputs = {
  arena_json: readFileSync(join(repo, 'worlds', 'coco_arena_v1.json'), 'utf-8'),
  depot_json: readFileSync(join(repo, 'worlds', 'coco_depot_v1.json'), 'utf-8'),
  record_json: JSON.stringify(JSON.parse(readFileSync(join(repo, 'docs', 'v2', 'g1', 'data', 'g16', 'browser', 'browser_record.json'), 'utf-8')).record),
  hash_version: hv,
};
const code = readFileSync(join(here, 'native_gate_cases.py'), 'utf-8');

// CPython: the installed coco_lab (CI installs the checkout's copy), -P so the cwd shadows nothing
const python = args.python ?? process.env.PYTHON ?? 'python3';
let t0 = Date.now();
const native = spawnSync(python, ['-P', '-c', 'import json, sys\ng = json.load(sys.stdin)\nexec(sys.argv[1], g)\nsys.stdout.write(g["result"])', code],
  { input: JSON.stringify(inputs), maxBuffer: 1e9, cwd: os.tmpdir() });
if (native.status !== 0) throw new Error(`CPython failed: ${native.stderr}`);
const nativeMs = Date.now() - t0;
const nativeVersion = spawnSync(python, ['-c', 'import sys, platform; print(sys.version.split()[0], platform.machine())']).stdout.toString().trim();

// Pyodide: the shipped packs, every one loaded
t0 = Date.now();
const py = await loadPyodide({ indexURL: join(web, 'node_modules', 'pyodide') + '/', stdLibURL: join(gen, 'pyodide', 'python_stdlib.zip') });
py.unpackArchive(new Uint8Array(readFileSync(join(gen, 'arena', 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
const manifest = JSON.parse(readFileSync(join(gen, 'arena', 'manifest.json'), 'utf-8'));
for (const pack of Object.values(manifest.packs)) py.unpackArchive(new Uint8Array(readFileSync(join(gen, 'arena', pack.file))), 'zip', { extractDir: '/home/pyodide' });
for (const [k, v] of Object.entries(inputs)) py.globals.set(k, v);
py.runPython(code);
const wasm = JSON.parse(py.globals.get('result'));
const wasmMs = Date.now() - t0;
const nat = JSON.parse(native.stdout.toString());

/** Walk two values; floats within `tol` (0 = exact), everything else exact; `skip` names excluded keys. */
function compare(a, b, tol, skip, path, acc) {
  if (typeof a === 'number' && typeof b === 'number') {
    acc.compared++;
    if (Object.is(a, b) || a === b) { acc.exact++; return; }
    const d = Math.abs(a - b);
    acc.max_abs_diff = Math.max(acc.max_abs_diff, Number.isFinite(d) ? d : Infinity);
    const continuous = !(Number.isInteger(a) && Number.isInteger(b));
    if (!(continuous && d <= tol)) acc.failures.push({ path, native: a, pyodide: b });
    return;
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) { acc.failures.push({ path, native: `length ${a.length}`, pyodide: `length ${b.length}` }); return; }
    a.forEach((x, i) => compare(x, b[i], tol, skip, `${path}[${i}]`, acc));
    return;
  }
  if (a && b && typeof a === 'object' && typeof b === 'object') {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const k of keys) if (!skip.has(k)) compare(a[k], b[k], tol, skip, `${path}.${k}`, acc);
    return;
  }
  acc.compared++;
  if (a === b) acc.exact++; else acc.failures.push({ path, native: a, pyodide: b });
}

const CASES = {
  planners: { tol: 0, skip: [], family: 'global (exact)' },
  fetch_rush: { tol: 0, skip: [], family: 'global (exact): every tick\'s state hash, the scorecard' },
  control: { tol: TOL, skip: ['compute_ms'], family: 'continuous (1e-9); discrete fields and hashes exact; compute_ms excluded' },
  localise: { tol: TOL, skip: ['compute_ms'], family: 'continuous (1e-9); discrete fields and hashes exact; compute_ms excluded' },
};
const report = { hash_version: hv, tolerance: TOL, native: `CPython ${nativeVersion}`, pyodide: `Pyodide ${pyodideVersion} in Node ${process.version}`,
  cpu: os.cpus()[0]?.model, seconds: { native: nativeMs / 1000, pyodide: wasmMs / 1000 }, cases: {} };
for (const [name, c] of Object.entries(CASES)) {
  const acc = { compared: 0, exact: 0, max_abs_diff: 0, failures: [] };
  compare(nat[name], wasm[name], c.tol, new Set(c.skip), name, acc);
  let first_differing_tick = null;
  if (name === 'fetch_rush') first_differing_tick = nat.fetch_rush.tick_hashes.findIndex((h, i) => h !== wasm.fetch_rush.tick_hashes[i]);
  report.cases[name] = { family: c.family, compared: acc.compared, exact: acc.exact, max_abs_diff: acc.max_abs_diff,
    failures: acc.failures.length, first_failures: acc.failures.slice(0, 5),
    ...(name === 'fetch_rush' ? { ticks: nat.fetch_rush.tick_hashes.length, first_differing_tick: first_differing_tick < 0 ? null : first_differing_tick } : {}),
    passed: acc.failures.length === 0 };
}
report.passed = Object.values(report.cases).every((c) => c.passed);
if (args.out) writeFileSync(args.out, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ hash_version: hv, passed: report.passed, cases: Object.fromEntries(Object.entries(report.cases).map(([k, v]) => [k, { compared: v.compared, exact: v.exact, failures: v.failures, max_abs_diff: v.max_abs_diff }])), seconds: report.seconds }));
process.exitCode = report.passed ? 0 : 1;
