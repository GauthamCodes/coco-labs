// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Cross-engine determinism of the Arena model (M1 B.4, "Determinism"):
 * identical per-tick hashes across Chromium, Firefox and WebKit (Playwright)
 * and Pyodide-in-Node, over 100 recorded sessions with random goals and
 * teleop.
 *
 *   node tools/perf/determinism.mjs make   --out DIR [--n 100 --ticks 150]
 *   node tools/perf/determinism.mjs node   --out DIR
 *   node tools/perf/determinism.mjs chromium|firefox|webkit --out DIR --site URL [--webkit-exe PATH]
 *   node tools/perf/determinism.mjs compare --out DIR
 *
 * CI (lab.yml) replays a prefix against the committed recording and Node
 * reference: `--sessions FILE` (default DIR/sessions.json), `--limit N`
 * (the first N sessions), and for `compare`, `--ref DIR` (where
 * hashes_pyodide-node.json.gz is; default DIR).
 *
 * `make` writes DIR/sessions.json: per session a seed and an input log
 * (goals in the map frame, teleop within the spec's limits, stops, planner
 * switches) drawn from a fixed-seed generator, so the sessions are a
 * recording, not a property of this run. Each engine then plays every
 * session from a FRESH model (a new Pyodide in Node; a new production
 * worker -- the built site's own arena.worker -- in a browser), applies
 * each input at its tick exactly as the page does, and writes
 * DIR/hashes_<engine>.json.gz: every tick's state hash, every session's
 * final hash chain. `compare` checks every tick of every session against
 * the Node reference and writes DIR/determinism.json.
 */

import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gunzipSync, gzipSync } from 'node:zlib';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const web = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const GEN = join(web, 'public', 'generated');
const [mode, ...rest] = process.argv.slice(2);
const args = Object.fromEntries(rest.reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const OUT = args.out ?? 'determinism-out';
mkdirSync(OUT, { recursive: true });
const PLANNERS = ['bfs', 'dijkstra', 'astar', 'greedy', 'weighted_astar'];

/** xoshiro-free, tiny and fixed: mulberry32 (the generator, not the model). */
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function make() {
  const spec = JSON.parse(readFileSync(join(GEN, 'arena', 'coco_arena_v1.json'), 'utf-8'));
  const { x_min, x_max, y_min, y_max } = spec.bounds;
  const [dx, dy] = spec.world_to_map;
  const lim = spec.robot.limits;
  const n = Number(args.n ?? 100);
  const ticks = Number(args.ticks ?? 150);
  const r = rng(Number(args['gen-seed'] ?? 20261009));
  // --loop 1 (M2): every session also switches on the whole loop -- range
  // noise, a localisation filter with random knobs -- and may be kidnapped
  const LOOP = args.loop === '1';
  const sessions = [];
  for (let s = 0; s < n; s += 1) {
    const inputs = [];
    let t = 0;
    if (LOOP) {
      const filt = ['mcl', 'ekf', 'both'][Math.floor(r() * 3)];
      inputs.push({ tick: 0, kind: 'config', choice: `arena.range_sigma=${[0.01, 0.02, 0.04][Math.floor(r() * 3)]}` });
      inputs.push({ tick: 0, kind: 'config', choice: `localise.mcl.particles=${50 + 10 * Math.floor(r() * 26)}` });
      inputs.push({ tick: 0, kind: 'config', choice: `localise.mcl.injection=${['none', 'augmented', 'fixed'][Math.floor(r() * 3)]}` });
      if (r() < 0.3) inputs.push({ tick: 0, kind: 'config', choice: 'arena.slip=on' });
      inputs.push({ tick: 0, kind: 'config', choice: `localise.filter=${filt}` });
    }
    while (true) {
      t += 1 + Math.floor(r() * 30);
      if (t >= ticks - 5) break;
      const u = r();
      if (u < 0.45) {
        inputs.push({ tick: t, kind: 'goal', x: x_min + dx + 0.5 + r() * (x_max - x_min - 1), y: y_min + dy + 0.5 + r() * (y_max - y_min - 1) });
      } else if (u < 0.8) {
        inputs.push({ tick: t, kind: 'teleop', linear: (2 * r() - 1) * lim.teleop_linear, angular: (2 * r() - 1) * lim.teleop_angular });
      } else if (LOOP && u < 0.85) {
        // a kidnap to a known-free goal-sized spot (the Arena refuses walls; the generator stays clear)
        const spots = [[6.0, 4.0], [2.5, 2.0], [0.5, -2.5], [12.0, 5.5], [9.0, -4.0], [3.0, -6.5]];
        const [kx, ky] = spots[Math.floor(r() * spots.length)];
        inputs.push({ tick: t, kind: 'kidnap', x: kx, y: ky, theta: (2 * r() - 1) * Math.PI, has_theta: true });
      } else if (u < 0.9) {
        inputs.push({ tick: t, kind: 'planner', choice: PLANNERS[Math.floor(r() * PLANNERS.length)] });
      } else {
        inputs.push({ tick: t, kind: 'stop' });
      }
    }
    sessions.push({ id: s, seed: 1 + Math.floor(r() * 2 ** 31), ticks, planner: PLANNERS[Math.floor(r() * PLANNERS.length)], inputs });
  }
  writeFileSync(join(OUT, 'sessions.json'), JSON.stringify({ schema: 'lab_web.determinism_sessions', version: '1.0',
    generator: 'mulberry32(20261009)', spec_id: spec.id, sessions }, null, 0) + '\n');
  const counts = {};
  for (const s of sessions) for (const i of s.inputs) counts[i.kind] = (counts[i.kind] ?? 0) + 1;
  console.log(`${n} sessions x ${ticks} ticks; inputs ${JSON.stringify(counts)}`);
}

const load = () => JSON.parse(readFileSync(args.sessions ?? join(OUT, 'sessions.json'), 'utf-8')).sessions
  .slice(0, Number(args.limit ?? Infinity));
const save = (engine, info, res) => {
  writeFileSync(join(OUT, `hashes_${engine}.json.gz`), gzipSync(JSON.stringify({ engine, conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...info, sessions: res })));
  console.log(`${engine}: ${res.length} sessions, ${res.reduce((n, x) => n + x.hashes.length, 0)} ticks`);
};

async function node() {
  const { loadPyodide } = await import('pyodide');
  const py = await loadPyodide({ indexURL: join(web, 'node_modules', 'pyodide') + '/', stdLibURL: join(GEN, 'pyodide', 'python_stdlib.zip') });
  const spec = readFileSync(join(GEN, 'arena', 'coco_arena_v1.json'), 'utf-8');
  const res = [];
  const t0 = Date.now();
  for (const s of load()) {
    // a fresh interpreter state per session would cost a reload of Pyodide; a fresh
    // MODULE (importlib.reload) plus a fresh Arena from init() is what is reset
    py.unpackArchive(new Uint8Array(readFileSync(join(GEN, 'arena', 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
    // every lens pack (M2.2), and the subsystems they register (M2.3)
    const mf = JSON.parse(readFileSync(join(GEN, 'arena', 'manifest.json'), 'utf-8'));
    for (const p of Object.values(mf.packs ?? {})) py.unpackArchive(new Uint8Array(readFileSync(join(GEN, 'arena', p.file))), 'zip', { extractDir: '/home/pyodide' });
    py.runPython(`import importlib\nfor m in ${JSON.stringify(Object.values(mf.packs ?? {}).flatMap((p) => p.modules))}: importlib.import_module('coco_lab.' + m)`);
    py.FS.writeFile('/home/pyodide/arena_glue.py', readFileSync(join(web, 'src', 'arena', 'arena_glue.py'), 'utf-8'));
    py.runPython("import sys\nif '/home/pyodide' not in sys.path: sys.path.insert(0, '/home/pyodide')\nimport importlib, arena_glue\nimportlib.reload(arena_glue)");
    const glue = py.pyimport('arena_glue');
    glue.init(spec, s.seed, s.planner, () => {}, 4096).destroy();
    const hashes = [];
    let chain = '';
    for (let k = 0; k < s.ticks; k += 1) {
      const out = glue.step(JSON.stringify(s.inputs.filter((x) => x.tick === k)));
      const t = JSON.parse(out.get(0));
      out.destroy();
      hashes.push(t.hash);
      chain = t.chain;
    }
    glue.destroy();
    res.push({ id: s.id, hashes, chain });
  }
  save('pyodide-node', { version: `Pyodide ${py.version}, Node ${process.version}`, seconds: (Date.now() - t0) / 1000 }, res);
}

async function browser(name) {
  const pw = await import('playwright');
  const SITE = args.site ?? 'http://127.0.0.1:4174/coco-labs/';
  const worker = readdirSync(join(web, 'dist', 'assets')).find((f) => /^arena\.worker-.*\.js$/.test(f));
  if (!worker) throw new Error('no built arena.worker in dist/assets: build the site first');
  const PACK_NAMES = Object.keys(JSON.parse(readFileSync(join(web, 'dist', 'generated', 'arena', 'manifest.json'), 'utf-8')).packs ?? {});
  const opts = name === 'chromium' ? {} : name === 'webkit' && args['webkit-exe'] ? { executablePath: args['webkit-exe'] } : {};
  const b = await pw[name].launch(opts);
  const page = await b.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  // a blank page on the site's origin: the worker is the site's own, nothing else loads
  await page.route(`${SITE}__determinism.html`, (route) => route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>determinism</title>' }));
  await page.goto(`${SITE}__determinism.html`);
  const version = `${name} ${b.version()}`;
  const res = [];
  const t0 = Date.now();
  for (const s of load()) {
    const r = await page.evaluate(async ([url, base, s, PACKS]) => {
      const w = new Worker(url, { type: 'module' });
      let packs = 0;
      const hashes = [];
      let chain = '';
      let k = 0;
      try {
        await new Promise((resolve, reject) => {
          const next = () => w.postMessage({ type: 'step', inputs: s.inputs.filter((x) => x.tick === k) });
          w.onmessage = (m) => {
            const d = m.data;
            if (d.type === 'error') reject(new Error(`${d.stage}: ${d.message}`));
            else if (d.type === 'world') { packs = PACKS.length; if (!packs) next(); else for (const p of PACKS) w.postMessage({ type: 'load_pack', pack: p }); }
            else if (d.type === 'pack_ready') { packs -= 1; if (packs === 0) next(); }
            else if (d.type === 'tick') {
              hashes.push(d.tick.hash);
              chain = d.tick.chain;
              k += 1;
              if (k < s.ticks) next(); else resolve();
            }
          };
          w.onerror = (e) => reject(new Error(e.message));
          w.postMessage({ type: 'boot', pyodideBase: `${base}generated/pyodide/`, assetsBase: `${base}generated/`, seed: s.seed,
            planner: s.planner, batchSize: 4096 });
        });
      } finally {
        w.terminate();
      }
      return { hashes, chain };
    }, [`${SITE}assets/${worker}`, new URL(SITE).pathname, s, PACK_NAMES]);
    res.push({ id: s.id, ...r });
    if (s.id % 10 === 9) console.log(`${name}: ${s.id + 1} sessions, ${Math.round((Date.now() - t0) / 1000)} s`);
  }
  await b.close();
  save(name, { version, seconds: (Date.now() - t0) / 1000, worker, page_errors: errors }, res);
}

function compare() {
  const read = (dir, f) => JSON.parse(gunzipSync(readFileSync(join(dir, f))).toString('utf-8'));
  const runs = Object.fromEntries(readdirSync(OUT).filter((f) => /^hashes_.*\.json\.gz$/.test(f))
    .map((f) => read(OUT, f)).map((d) => [d.engine, d]));
  if (args.ref) runs['pyodide-node'] = read(args.ref, 'hashes_pyodide-node.json.gz');
  const ref = runs['pyodide-node'];
  if (!ref) throw new Error('no Pyodide-in-Node reference');
  const sessions = load();
  const out = { criterion: 'identical per-tick hashes across engines, 100 recorded sessions (README M1 B.4)', engines: {} };
  for (const [engine, d] of Object.entries(runs)) {
    let ticks = 0; let mismatched = 0; const firstDiffs = [];
    for (const s of sessions) {
      const a = ref.sessions.find((x) => x.id === s.id);
      const b = d.sessions.find((x) => x.id === s.id);
      if (!a) throw new Error(`the reference has no session ${s.id}`);
      if (!b || b.hashes.length !== s.ticks) { mismatched += s.ticks; firstDiffs.push({ session: s.id, tick: 'missing' }); continue; }
      for (let k = 0; k < s.ticks; k += 1) {
        ticks += 1;
        if (a.hashes[k] !== b.hashes[k]) { mismatched += 1; if (!firstDiffs.some((f) => f.session === s.id)) firstDiffs.push({ session: s.id, tick: k }); }
      }
      if (a.chain !== b.chain && !firstDiffs.some((f) => f.session === s.id)) firstDiffs.push({ session: s.id, tick: 'chain' });
    }
    const mine = d.sessions.filter((x) => sessions.some((s) => s.id === x.id));
    const digest = createHash('sha256').update(mine.map((x) => x.hashes.join('')).join('|')).digest('hex');
    out.engines[engine] = { version: d.version, seconds: d.seconds, sessions: mine.length, ticks_compared: ticks,
      ticks_mismatched: mismatched, sessions_differing: firstDiffs.length, first_differences: firstDiffs.slice(0, 10),
      all_hashes_sha256: digest, page_errors: d.page_errors ?? [] };
  }
  out.pass = Object.keys(runs).length >= Number(args.engines ?? 4) && Object.values(out.engines).every((e) => e.ticks_mismatched === 0 && e.sessions === sessions.length);
  writeFileSync(join(OUT, 'determinism.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
  console.log(JSON.stringify(Object.fromEntries(Object.entries(out.engines).map(([k, v]) => [k, [v.ticks_compared, v.ticks_mismatched, v.all_hashes_sha256.slice(0, 12)]]))), 'pass', out.pass);
  process.exit(out.pass ? 0 : 1);
}

if (mode === 'make') make();
else if (mode === 'node') await node();
else if (['chromium', 'firefox', 'webkit'].includes(mode)) await browser(mode);
else if (mode === 'compare') compare();
else { console.error('mode: make | node | chromium | firefox | webkit | compare'); process.exit(2); }
