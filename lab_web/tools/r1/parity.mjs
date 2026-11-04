// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.2: native-vs-browser parity of experiments. tools/r1/parity_cases.py runs the
 * golden experiments (coco_lab/test/fixtures/r1/golden_experiment.json: one per family)
 * in CPython (a subprocess, the installed coco_lab) and in Pyodide (the built site's
 * coco_lab packs, public/generated/arena/: run `npm run arena-assets` first). Every
 * count, status, per-run hash chain, digest, results.csv row and summary.json number
 * must be IDENTICAL -- the wall-clock compute_ms excluded -- and both digests must be
 * the committed golden ones.
 *
 *   node tools/r1/parity.mjs [--python PY] [--out OUT.json]
 *
 * Exit 0 only if everything matches.
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

const worlds = {};
for (const id of ['coco_arena_v1', 'coco_arena_v2', 'coco_depot_v1', 'coco_depot_colours_v1']) {
  worlds[id] = readFileSync(join(repo, 'worlds', `${id}.json`), 'utf-8');
}
const inputs = {
  golden_json: readFileSync(join(repo, 'coco_lab', 'test', 'fixtures', 'r1', 'golden_experiment.json'), 'utf-8'),
  worlds_json: JSON.stringify(worlds),
};
const code = readFileSync(join(here, 'parity_cases.py'), 'utf-8');

const python = args.python ?? process.env.PYTHON ?? 'python3';
let t0 = Date.now();
const native = spawnSync(python, ['-P', '-c', 'import json, sys\ng = json.load(sys.stdin)\nexec(sys.argv[1], g)\nsys.stdout.write(g["result"])', code],
  { input: JSON.stringify(inputs), maxBuffer: 1e9, cwd: os.tmpdir() });
if (native.status !== 0) throw new Error(`CPython failed: ${native.stderr}`);
const nativeMs = Date.now() - t0;
const nativeVersion = spawnSync(python, ['-c', 'import sys, platform; print(sys.version.split()[0], platform.machine())']).stdout.toString().trim();

t0 = Date.now();
const py = await loadPyodide({ indexURL: join(web, 'node_modules', 'pyodide') + '/', stdLibURL: join(gen, 'pyodide', 'python_stdlib.zip') });
py.unpackArchive(new Uint8Array(readFileSync(join(gen, 'arena', 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
const manifest = JSON.parse(readFileSync(join(gen, 'arena', 'manifest.json'), 'utf-8'));
if (!manifest.packs.experiments) throw new Error('the built site has no experiments pack: run npm run arena-assets');
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
  const n = nat[name], w = wasm[name];
  if (n.digest !== n.golden_digest) failures.push({ path: `${name}.digest`, native: n.digest, golden: n.golden_digest });
  if (w.digest !== w.golden_digest) failures.push({ path: `${name}.digest`, pyodide: w.digest, golden: w.golden_digest });
  cases[name] = { runs: n.records.length, digest: n.digest, golden: n.golden_digest, failures: failures.length - before };
}
const report = {
  about: 'R1.2 native-vs-Pyodide experiment parity (lab_web/tools/r1/parity.mjs); compute_ms excluded',
  pass: failures.length === 0, compared, cases, failures: failures.slice(0, 50),
  native: { python: nativeVersion, ms: nativeMs }, pyodide: { version: pyodideVersion, ms: wasmMs },
};
if (args.out) writeFileSync(args.out, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ pass: report.pass, compared, cases, failures: failures.slice(0, 5) }, null, 1));
process.exit(report.pass ? 0 : 1);
