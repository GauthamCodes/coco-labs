// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.6: a game session in Pyodide-in-Node, through the SAME glue the browser
 * worker runs (src/arena/arena_glue.py: game_init, begin/advance/finish,
 * game_op), and its per-tick cost.
 *
 *   node tools/g1/game_node.mjs --record RECORD.json [--out OUT.json]
 *   node tools/g1/game_node.mjs --script fetch1 [--out OUT.json]
 *
 * --record replays a record {game, arg, seed, ticks, inputs, hash_version}
 * (what the page's "record" query returns, or a games_reference.json run) by
 * feeding each tick its logged inputs; --script plays a built-in scripted
 * session (AUTO to the first pick, GRAB, AUTO to the drop, DROP). Either way
 * the output is the record the glue kept, its hash chain, the scorecard and
 * the per-tick wall times (Pyodide in Node on this machine: not a phone).
 * tools/g1/game_parity.py replays the same record in CPython
 * (coco_lab.games.play) and compares the chains.
 */
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import { loadPyodide, version as pyodideVersion } from 'pyodide';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => { if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]); return acc; }, []));
const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '..', '..');
const repo = join(web, '..');

export async function bootGlue() {
  const py = await loadPyodide({ indexURL: join(web, 'node_modules', 'pyodide') + '/' });
  const src = join(repo, 'coco_lab', 'coco_lab');
  const walk = (d) => readdirSync(d).flatMap((n) => { const p = join(d, n); return statSync(p).isDirectory() ? walk(p) : [p]; });
  for (const f of walk(src).filter((p) => /\.(py|json)$/.test(p))) {
    const dest = '/home/pyodide/coco_lab/' + relative(src, f);
    py.FS.mkdirTree(dirname(dest));
    py.FS.writeFile(dest, readFileSync(f));
  }
  py.FS.writeFile('/home/pyodide/arena_glue.py', readFileSync(join(web, 'src', 'arena', 'arena_glue.py')));
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  return { py, glue: py.pyimport('arena_glue') };
}

const slow = [];
function step(glue, rows) {
  const t0 = performance.now();
  glue.begin(JSON.stringify(rows));
  while (!glue.advance(4096));
  const out = glue.finish();
  const tick = JSON.parse(out.get(0));
  out.destroy();
  const ms = performance.now() - t0;
  if (ms > 500) slow.push({ tick: tick.tick, ms: Math.round(ms), inputs: rows.map((r) => r.kind + (r.choice ? ':' + r.choice : '')), plans: tick.plans.map((p) => ({ planner: p.planner, status: p.status, expanded: p.summary?.expanded ?? p.summary?.nodes_expanded })) });
  return { tick, ms };
}

export async function play({ record, script }) {
  const { py, glue } = await bootGlue();
  const spec = readFileSync(join(repo, 'worlds', 'coco_depot_v1.json'), 'utf-8');
  const game = record ? record.game : 'fetch_rush';
  const arg = record ? record.arg : 1;
  const hv = record?.hash_version ?? Number(args.hv ?? 2);
  const init = glue.game_init(spec, game, arg, record?.seed ?? 1, () => {}, 2048, () => {}, hv);
  const world = JSON.parse(init.get(0));
  init.destroy();
  const ms = [];
  const ticks = [];
  if (record) {
    const by = new Map();
    for (const e of record.inputs) { if (!by.has(e.tick)) by.set(e.tick, []); const { tick: _t, ...row } = e; by.get(e.tick).push(row); }
    for (let k = 0; k < record.ticks; k++) { const r = step(glue, by.get(k) ?? []); ms.push(r.ms); ticks.push(r.tick.hash); }
  } else {
    // a scripted player: AUTO to the first pick, GRAB, AUTO to the drop, DROP (the same queries the page sends)
    let t = step(glue, world.game.setup); ms.push(t.ms); ticks.push(t.tick.hash);
    const q = (op, a = null) => JSON.parse(glue.game_op(op, a));
    let phase = 'to_pick';
    for (let k = 1; k < (Number(args.ticks) || 1800); k++) {
      let rows = [];
      const a = t.tick.game.assist, f = t.tick.game.fetch;
      if (f?.over) break;
      if (phase === 'to_pick' && (k === 1 || (t.tick.arrived && a.phase === 'idle'))) {
        if (k > 1) { rows = [{ kind: 'config', choice: `assist.target=${f.order[0]}` }, { kind: 'config', choice: 'assist.grasp=go' }]; phase = 'grabbing'; }
        else { const g = q('auto_goal'); rows = [{ kind: 'goal', x: g.x, y: g.y }]; }
      } else if (phase === 'grabbing' && a.carried) { const g = q('auto_goal'); rows = [{ kind: 'goal', x: g.x, y: g.y }]; phase = 'to_drop'; }
      else if (phase === 'grabbing' && a.phase === 'idle' && !a.carried) { phase = 'failed'; }
      else if (phase === 'to_drop' && t.tick.arrived) { rows = [{ kind: 'config', choice: 'assist.grasp=go' }]; phase = 'dropping'; }
      else if (phase === 'dropping' && a.phase === 'idle') { const g = q('auto_goal'); if (g) rows = [{ kind: 'goal', x: g.x, y: g.y }]; phase = 'to_pick'; }
      t = step(glue, rows); ms.push(t.ms); ticks.push(t.tick.hash);
    }
  }
  const rec = JSON.parse(glue.game_op('record', null));
  const stars = JSON.parse(glue.game_op('stars', null));
  py.runPython('import gc; gc.collect()');
  const sorted = [...ms].sort((a, b) => a - b);
  return { record: rec.record, hash_chain: rec.hash_chain, last_hash: rec.last_hash, scorecard: stars.card, hashes: ticks,
    timing: { runtime: `Pyodide ${pyodideVersion} in Node ${process.version}`, cpu: os.cpus()[0]?.model, ticks: ms.length,
      median_ms: sorted[Math.floor(sorted.length / 2)], p95_ms: sorted[Math.floor(sorted.length * 0.95)], max_ms: sorted[sorted.length - 1],
      note: 'wall time per tick in Pyodide-in-Node on this machine; not a phone, not a browser', slow_ticks: slow } };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const record = args.record ? JSON.parse(readFileSync(args.record, 'utf-8')) : null;
  const res = await play({ record: record?.record ?? record, script: args.script });
  const text = JSON.stringify(res, null, 1) + '\n';
  if (args.out) writeFileSync(args.out, text);
  console.log(JSON.stringify({ chain: res.hash_chain, ticks: res.record.ticks, scorecard: { deliveries: res.scorecard?.deliveries, contacts: res.scorecard?.contacts, time_used: res.scorecard?.time_used }, timing: res.timing }));
}
