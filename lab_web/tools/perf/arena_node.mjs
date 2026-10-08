// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena model inside Pyodide-in-Node (M1.5): where its time goes, and
 * its per-tick state hashes (README M1 determinism criterion: Pyodide in
 * Node is one of the runtimes whose hashes must agree).
 *
 *   node tools/perf/arena_node.mjs [--spec ../worlds/coco_arena_v1.json]
 *        [--session FILE.json] [--out FILE.json]
 *
 * Pyodide comes from the pinned npm package (node_modules/pyodide), coco_lab
 * from this checkout; nothing is fetched (coco_lab needs no packages). With
 * --session (a JSON {seed, ticks, inputs:[...]}) it replays that session and
 * prints every tick's hash; otherwise it times the stages of a default run.
 */

import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import { loadPyodide, version as pyodideVersion } from 'pyodide';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..', '..', '..');

export async function bootArena() {
  const t0 = performance.now();
  const py = await loadPyodide({ indexURL: join(repo, 'lab_web', 'node_modules', 'pyodide') + '/' });
  const loadMs = performance.now() - t0;
  const src = join(repo, 'coco_lab', 'coco_lab');
  const walk = (d) => readdirSync(d).flatMap((n) => { const p = join(d, n); return statSync(p).isDirectory() ? walk(p) : [p]; });
  const t1 = performance.now();
  for (const f of walk(src).filter((p) => /\.(py|json)$/.test(p))) {
    const dst = `/home/pyodide/coco_lab/${relative(src, f)}`;
    py.FS.mkdirTree(dirname(dst));
    py.FS.writeFile(dst, readFileSync(f));
  }
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  return { py, loadMs, writeMs: performance.now() - t1 };
}

async function main() {
  const specPath = args.spec ?? join(repo, 'worlds', 'coco_arena_v1.json');
  const { py, loadMs, writeMs } = await bootArena();
  py.globals.set('SPEC_JSON', readFileSync(specPath, 'utf-8'));
  if (args.session) {
    py.globals.set('SESSION_JSON', readFileSync(args.session, 'utf-8'));
    const hashes = py.runPython(`
import json
from coco_lab.arena import InputEvent, replay
spec = json.loads(SPEC_JSON)
s = json.loads(SESSION_JSON)
ev = [InputEvent(**e) for e in s['inputs']]
json.dumps(replay(spec, s['seed'], ev, s['ticks'], **s.get('options', {})))
`);
    process.stdout.write(hashes + '\n');
    return;
  }
  const out = JSON.parse(py.runPython(`
import json, time
T = {}
t = time.perf_counter(); from coco_lab import arena, worldspec, sketch; T['import_ms'] = (time.perf_counter() - t) * 1000
spec = json.loads(SPEC_JSON)
t = time.perf_counter(); n = worldspec.normalize(spec); T['normalize_ms'] = (time.perf_counter() - t) * 1000
t = time.perf_counter(); m = worldspec.arena_map(n); T['arena_map_ms'] = (time.perf_counter() - t) * 1000
t = time.perf_counter(); sm = sketch.SketchMap(m); T['sketchmap_edt_ms'] = (time.perf_counter() - t) * 1000
t = time.perf_counter(); inf = sketch._inflated_grid_map(sm, n['robot']['radius']); T['inflate_ms'] = (time.perf_counter() - t) * 1000
t = time.perf_counter(); g = inf.to_grid(connectivity=8); T['to_grid_ms'] = (time.perf_counter() - t) * 1000
t = time.perf_counter(); a = arena.Arena(spec, seed=1); T['arena_init_total_ms'] = (time.perf_counter() - t) * 1000
t = time.perf_counter(); tk = a.step([arena.InputEvent(0, 'goal', x=6.0, y=4.0)]); T['first_step_with_astar_plan_ms'] = (time.perf_counter() - t) * 1000
T['plan_events'] = len(tk.plans[0].result.trace)
T['plan_expansions'] = tk.plans[0].result.trace.summary['expansions']
t = time.perf_counter()
for _ in range(100): a.step()
T['steps_100_ms'] = (time.perf_counter() - t) * 1000
t = time.perf_counter()
for _ in range(10): sm.scan(a.pose, a.lidar, a.angles)
T['scan_480_beams_ms'] = (time.perf_counter() - t) * 100
T['hash_after_101'] = a.state_hash()
json.dumps(T)
`));
  const result = {
    meta: { at_utc: new Date().toISOString(), node: process.version, pyodide: pyodideVersion, cpu: os.cpus()[0].model, load1: Math.round(os.loadavg()[0] * 10) / 10 },
    load_pyodide_ms: Math.round(loadMs), write_coco_lab_ms: Math.round(writeMs),
    python: Object.fromEntries(Object.entries(out).map(([k, v]) => [k, typeof v === 'number' ? Math.round(v * 10) / 10 : v])),
  };
  console.log(JSON.stringify(result, null, 1));
  if (args.out) writeFileSync(args.out, JSON.stringify(result, null, 1) + '\n');
}

if (import.meta.url === `file://${process.argv[1]}`) await main();
