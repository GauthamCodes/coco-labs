// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The attract-mode recording (M1.8), made at build time:
 * public/generated/arena/attract.mcap.
 *
 * The REAL Arena (coco_lab + arena_glue.py in Pyodide-in-Node, the same code
 * the worker runs) plays a scripted demo -- three goals, three planners --
 * and every tick and every plan event is written in the v2 container
 * (MCAP + zstd, coco_schemas' protobuf channels; README 5.2) with the
 * site's own TypeScript encoders, loaded through Vite. The page plays it
 * while Pyodide loads (README 5.5), so a visitor sees motion and computation
 * at once. It is a MODEL recording, labelled so on screen.
 *
 * Deterministic: same spec, seed and script, same file (CI builds twice).
 *
 *   node tools/build_attract.mjs
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { zstdCompressSync } from 'node:zlib';
import { loadPyodide } from 'pyodide';
import { createServer } from 'vite';

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '..');
const repo = join(web, '..');
const GEN = join(web, 'public', 'generated', 'arena');

/** The demo: [planner, goal x, goal y] (map frame), each driven to arrival. */
export const SCRIPT = [['astar', 2.5, 2.0], ['dijkstra', 0.5, -2.5], ['greedy', -1.5, 1.0]];
const SEED = 1;
const MAX_TICKS_PER_GOAL = 400;
/** Ranges are kept every SCAN_EVERY ticks (the fan holds its last scan between). */
const SCAN_EVERY = 2;

async function record() {
  const py = await loadPyodide({ indexURL: join(web, 'node_modules', 'pyodide') + '/' });
  py.unpackArchive(new Uint8Array(readFileSync(join(GEN, 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
  py.FS.writeFile('/home/pyodide/arena_glue.py', readFileSync(join(web, 'src', 'arena', 'arena_glue.py')));
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  const glue = py.pyimport('arena_glue');
  const batches = [];
  const post = (cols, meta) => {
    const m = JSON.parse(meta);
    const c = {};
    for (const k of ['seq', 'tick', 't_world', 'kind', 'row', 'col', 'sub', 'g', 'h', 'f', 'parent_row', 'parent_col', 'parent_sub']) {
      const p = cols.get(k); const b = p.getBuffer(); c[k] = b.data.slice(); b.release(); p.destroy();
    }
    cols.destroy();
    batches.push({ meta: m, cols: c });
  };
  const spec = readFileSync(join(GEN, 'coco_arena_v1.json'), 'utf-8');
  const init = glue.init(spec, SEED, 'astar', post, 4096);
  const world = JSON.parse(init.get(0));
  const occProxy = init.get(1);
  const occupancy = occProxy.toJs().slice();
  occProxy.destroy();
  init.destroy();
  const ticks = [];
  const inputs = [];
  const step = (rows) => {
    const out = glue.step(JSON.stringify(rows));
    const t = JSON.parse(out.get(0));
    const r = out.get(1); const b = r.getBuffer('f32'); const ranges = b.data.slice(); b.release(); r.destroy(); out.destroy();
    ticks.push({ t, ranges });
    return t;
  };
  let tick = 0;
  for (const [planner, x, y] of SCRIPT) {
    const rows = [{ tick, kind: 'planner', choice: planner }, { tick, kind: 'goal', x, y }];
    inputs.push(...rows);
    let t = step(rows);
    tick = t.tick;
    for (let k = 0; k < MAX_TICKS_PER_GOAL && t.mode === 'goal'; k += 1) { t = step([]); tick = t.tick; }
  }
  glue.destroy();
  return { spec, world, occupancy, ticks, batches, inputs, chain: ticks.at(-1).t.chain, pyodide: py.version };
}

async function write(rec) {
  const server = await createServer({ root: web, logLevel: 'error', server: { middlewareMode: true }, appType: 'custom' });
  try {
    const { encodeBatch } = await server.ssrLoadModule('/src/schemas/columns.ts');
    const { writeRun } = await server.ssrLoadModule('/src/schemas/mcap.ts');
    const { runId, specSha256 } = await server.ssrLoadModule('/src/schemas/runid.ts');
    const { create } = await server.ssrLoadModule('/node_modules/@bufbuild/protobuf/dist/esm/index.js');
    const env = await server.ssrLoadModule('/src/schemas/gen/coco/envelope/v1/manifest_pb.ts');
    const plan = await server.ssrLoadModule('/src/schemas/gen/coco/plan/v1/search_pb.ts');
    const robot = await server.ssrLoadModule('/src/schemas/gen/coco/robot/v1/robot_pb.ts');
    const truth = await server.ssrLoadModule('/src/schemas/gen/coco/truth/v1/truth_pb.ts');
    const scan = await server.ssrLoadModule('/src/schemas/gen/coco/sensor/v1/scan_pb.ts');
    const input = await server.ssrLoadModule('/src/schemas/gen/coco/input/v1/input_pb.ts');
    const worldPb = await server.ssrLoadModule('/src/schemas/gen/coco/world/v1/world_pb.ts');
    const { toBinary } = await server.ssrLoadModule('/node_modules/@bufbuild/protobuf/dist/esm/index.js');

    const specBytes = new TextEncoder().encode(rec.spec);
    const engines = [['coco_lab', `zip:${JSON.parse(readFileSync(join(GEN, 'manifest.json'), 'utf-8')).coco_lab_zip.sha256.slice(0, 16)}`],
      ['pyodide', rec.pyodide], ['arena_glue', 'lab_web/src/arena/arena_glue.py']];
    const manifest = create(env.ManifestSchema, {
      runId: await runId(specBytes, SEED, engines), specFormat: 'coco.world_spec.v1+json', spec: specBytes,
      specSha256: await specSha256(specBytes), seed: BigInt(SEED), tier: env.Tier.ARENA, evidenceClass: env.EvidenceClass.MODEL,
      engines: engines.map(([name, version]) => ({ name, version })),
      channels: [
        ['coco.world.grid.v1', 'coco.world.v1.WorldGrid'],
        ['coco.robot.state.v1', 'coco.robot.v1.RobotStateBatch'], ['coco.truth.pose.v1', 'coco.truth.v1.TruthPoseBatch'],
        ['coco.sensor.scan.lidar.v1', 'coco.sensor.v1.ScanBatch'], ['coco.input.events.v1', 'coco.input.v1.InputEventBatch'],
        ['coco.plan.search.header.v1', 'coco.plan.v1.SearchHeader'], ['coco.plan.search.events.v1', 'coco.plan.v1.SearchEventBatch'],
        ['coco.plan.search.summary.v1', 'coco.plan.v1.SearchSummary'],
      ].map(([name, message]) => ({ name, message })),
      provenance: { tool: 'lab_web/tools/build_attract.mjs', source: `script ${JSON.stringify(SCRIPT)}; final chain ${rec.chain}`,
        note: 'attract mode: a MODEL recording made at build time' },
      schemaPackageVersion: '1.0.0',
    });
    const records = [];
    // the world, once: the grid the model drives in (occupancy = LabMap codes)
    const w = rec.world;
    records.push({ channel: 'coco.world.grid.v1', schema: worldPb.WorldGridSchema, tWorld: 0,
      data: toBinary(worldPb.WorldGridSchema, create(worldPb.WorldGridSchema, {
        mapId: w.id, width: w.width, height: w.height, resolution: w.resolution, originX: w.origin[0], originY: w.origin[1],
        blocked: rec.occupancy.map((v) => (v === 0 ? 0 : 1)), occupancy: rec.occupancy,
        specSha256: await specSha256(specBytes), row0IsBottom: false })) });
    const kinds = { goal: input.InputKind.GOAL, planner: input.InputKind.PLANNER };
    // inputs (one batch per tick that had any)
    const byTick = new Map();
    for (const r of rec.inputs) { if (!byTick.has(r.tick)) byTick.set(r.tick, []); byTick.get(r.tick).push(r); }
    for (const [t, rows] of byTick) {
      records.push({ channel: 'coco.input.events.v1', schema: input.InputEventBatchSchema, tWorld: t * rec.world.dt, seq: 0,
        data: encodeBatch(input.InputEventBatchSchema, {
          seq: rows.map((_, i) => i), tick: rows.map(() => t), t_world: rows.map(() => t * rec.world.dt),
          kind: rows.map((r) => kinds[r.kind]), x: rows.map((r) => r.x ?? 0), y: rows.map((r) => r.y ?? 0),
          theta: rows.map(() => 0), has_theta: rows.map(() => false), linear: rows.map(() => 0), angular: rows.map(() => 0),
          choice: rows.map((r) => r.choice ?? '') }) });
    }
    // plans: header + events + summary, at the tick they were made
    for (const { meta, cols } of rec.batches) {
      records.push({ channel: 'coco.plan.search.events.v1', schema: plan.SearchEventBatchSchema, tWorld: meta.tick * rec.world.dt,
        seq: Number(cols.seq[0] ?? 0n), data: encodeBatch(plan.SearchEventBatchSchema, cols, { search_id: meta.search_id }) });
    }
    for (const { t } of rec.ticks) {
      for (const p of t.plans) {
        records.push({ channel: 'coco.plan.search.header.v1', schema: plan.SearchHeaderSchema, tWorld: p.tick * rec.world.dt,
          data: toBinary(plan.SearchHeaderSchema, create(plan.SearchHeaderSchema, { searchId: BigInt(p.search_id), algorithm: p.planner,
            tick: BigInt(p.tick), tWorld: p.tick * rec.world.dt })) });
        const sm = p.summary;
        records.push({ channel: 'coco.plan.search.summary.v1', schema: plan.SearchSummarySchema, tWorld: t.t_world,
          data: toBinary(plan.SearchSummarySchema, create(plan.SearchSummarySchema, { searchId: BigInt(p.search_id),
            status: sm.status === 'found' ? plan.SearchStatus.FOUND : plan.SearchStatus.NO_PATH,
            expansions: BigInt(sm.expansions), pushes: BigInt(sm.pushes), relaxes: BigInt(sm.relaxes),
            ...(sm.path_cost != null ? { pathCost: sm.path_cost, pathLength: sm.path_length, pathSteps: BigInt(sm.path_steps) } : {}) })) });
      }
    }
    // the world, tick by tick: state, truth (the same numbers: no localisation in M1), scans
    for (const { t, ranges } of rec.ticks) {
      const one = { seq: [t.tick], tick: [t.tick], t_world: [t.t_world] };
      records.push({ channel: 'coco.robot.state.v1', schema: robot.RobotStateBatchSchema, tWorld: t.t_world, seq: t.tick,
        data: encodeBatch(robot.RobotStateBatchSchema, { ...one, x: [t.pose[0]], y: [t.pose[1]], theta: [t.pose[2]], v: [t.v], omega: [t.w] }) });
      records.push({ channel: 'coco.truth.pose.v1', schema: truth.TruthPoseBatchSchema, tWorld: t.t_world, seq: t.tick,
        data: encodeBatch(truth.TruthPoseBatchSchema, { ...one, x: [t.pose[0]], y: [t.pose[1]], theta: [t.pose[2]] }) });
      if (t.tick % SCAN_EVERY === 0) {
        const li = rec.world.lidar;
        records.push({ channel: 'coco.sensor.scan.lidar.v1', schema: scan.ScanBatchSchema, tWorld: t.t_world, seq: t.tick,
          data: encodeBatch(scan.ScanBatchSchema, { ...one, angle_min: [li.angle_min],
            angle_increment: [(li.angle_max - li.angle_min) / (li.samples - 1)], range_min: [0.15], range_max: [li.range_max],
            count: [ranges.length], ranges }) });
      }
    }
    records.sort((a, b) => a.tWorld - b.tWorld);
    const bytes = await writeRun(manifest, records, (d) => new Uint8Array(zstdCompressSync(d)));
    writeFileSync(join(GEN, 'attract.mcap'), bytes);
    return { bytes: bytes.length, ticks: rec.ticks.length, events: rec.batches.reduce((n, b) => n + b.cols.kind.length, 0), chain: rec.chain };
  } finally {
    await server.close();
  }
}

const rec = await record();
const info = await write(rec);
console.log(`attract.mcap: ${info.bytes} B, ${info.ticks} ticks, ${info.events} plan events, chain ${info.chain.slice(0, 12)}`);
