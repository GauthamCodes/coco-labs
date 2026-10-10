// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 3 mapping/SLAM bundles -> v2 runs (M2.7), and back, with nothing lost.
 *
 * A slam bundle (coco_lab.slambundle: one drive -- a Sketch, or one
 * recorded on the full stack in Gazebo -- coco_lab's mappers and SLAMs run
 * on it, and, for a recorded drive, slam_toolbox and Cartographer run on the
 * same recording) becomes one v2 run. World row k is tick k at its own t;
 * update u is at tick world.updates[u].
 *
 *   spec                 the bundle's manifest.json, byte for byte
 *   world.grid           the truth map the runs are scored against
 *   truth.pose           ground truth;  estimate.pose "world:odometry": dead
 *                        reckoning ("odometry" is a RUN here: mapping from it)
 *   sensor.scan.lidar    the scan at every update (`ranges_f64`)
 *   sensor.detect        the IDEALISED landmark sensor's observations, one
 *                        row per sighting ("landmark:<id>", range, bearing)
 *   map.grid.header / map.slam.header  per run (and per external run): its
 *                        grid, its algorithm; params.evidence MODEL for
 *                        coco_lab's runs, STACK for the external backends
 *   estimate.pose        each run's estimate ("<run>"; covariance where the
 *                        run has one) and final trajectory ("<run>:final");
 *                        each external run's ("ext:<id>")
 *   map.grid.snapshot    every map snapshot and every score diff map, as
 *                        nav_msgs cells (`cells_u8`): "<run>" at its update,
 *                        "<run>:score.diff", "ext:<id>", "ext:<id>:score.diff"
 *   map.slam.particles   FastSLAM's particles at every update
 *   map.slam.landmarks   EKF-SLAM's landmarks with covariance at every update
 *   map.slam.edges       the pose graph's edges (stage "final"; kind = the
 *                        bundle's code) and its loop events (stage
 *                        "loop_events": from the matched node to the update)
 *   metrics              "<run>.<column>" for every other per-update column
 *                        (loops, icp_ok, optimised, neff, best, ...),
 *                        "<run>.score.err_*", "<run>.opt.*", "ext:<id>.err_online"
 *
 * An array this converter does not know is refused, never dropped.
 * `toLab3` rebuilds every array and the v1 decoder re-checks the content hash.
 */

import { create, fromBinary, toBinary, type DescMessage } from '@bufbuild/protobuf';

import { encodeBatch, type Column } from '../schemas/columns';
import { ManifestSchema, Tier, EvidenceClass, type Manifest } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import { EstimateBatchSchema } from '../schemas/gen/coco/estimate/v1/estimate_pb';
import { ParamsSchema } from '../schemas/gen/coco/common/v1/common_pb';
import { GraphEdgeBatchSchema, LandmarkBatchSchema, MapGridHeaderSchema, MapGridSnapshotBatchSchema, SlamHeaderSchema,
  SlamParticleBatchSchema } from '../schemas/gen/coco/map/v1/map_pb';
import { MetricBatchSchema } from '../schemas/gen/coco/metrics/v1/metrics_pb';
import { DetectionBatchSchema } from '../schemas/gen/coco/sensor/v1/detect_pb';
import { ScanBatchSchema } from '../schemas/gen/coco/sensor/v1/scan_pb';
import { TruthPoseBatchSchema } from '../schemas/gen/coco/truth/v1/truth_pb';
import { WorldGridSchema } from '../schemas/gen/coco/world/v1/world_pb';
import { decodeSlam, parseSlamManifest, type DecodedSlamBundle, type Grid } from '../map/decode';
import type { ReadMessage, RunRecord } from '../schemas/mcap';
import { runId, specSha256 } from '../schemas/runid';
import { rawFromColumns } from './raw';

export const SPEC_FORMAT = 'coco_lab.slam_bundle.v1+json';
export const CONVERTER = 'lab_web/src/convert/lab3.ts';
const PER_BATCH = 2048;
export const CH = {
  grid: 'coco.world.grid.v1', truth: 'coco.truth.pose.v1', estimate: 'coco.estimate.pose.v1', scan: 'coco.sensor.scan.lidar.v1',
  detect: 'coco.sensor.detect.colour.v1', gridHeader: 'coco.map.grid.header.v1', slamHeader: 'coco.map.slam.header.v1',
  snapshot: 'coco.map.grid.snapshot.v1', particles: 'coco.map.slam.particles.v1', landmarks: 'coco.map.slam.landmarks.v1',
  edges: 'coco.map.slam.edges.v1', metrics: 'coco.metrics.values.v1',
} as const;
/** The arrays (arr.*) this converter knows; anything else is refused. */
const KNOWN_ARRAYS = new Set(['final.x', 'final.y', 'final.yaw', 'score.diff', 'score.err_final', 'score.err_online',
  'particles.offset', 'particles.x', 'particles.y', 'particles.yaw', 'particles.w',
  'lm.offset', 'lm.id', 'lm.x', 'lm.y', 'lm.cxx', 'lm.cxy', 'lm.cyy',
  'edges.i', 'edges.j', 'edges.kind', 'loops.j', 'loops.k', 'opt.k', 'opt.chi2_before', 'opt.chi2_after', 'opt.iterations']);
const EST_COLS = new Set(['row', 't', 'est_x', 'est_y', 'est_yaw', 'cov_xx', 'cov_xy', 'cov_yy', 'cov_tt']);
const OPT = ['k', 'chi2_before', 'chi2_after', 'iterations'];

export interface Converted { manifest: Manifest; records: RunRecord[] }

const big = (n: number) => BigInt(n);
const nan = (n: number) => new Array(n).fill(NaN);
const str = (key: string, value: string) => ({ key, value: { value: { case: 'stringValue' as const, value } } });

export async function fromLab3(b: DecodedSlamBundle, manifestBytes: Uint8Array): Promise<Converted> {
  const stack = b.world.source === 'recorded';
  const spec = await specSha256(manifestBytes);
  const engines: [string, string][] = [['coco_lab', b.provenance.coco_lab_version], ['converter', `${CONVERTER} 1`]];
  const records: RunRecord[] = [];
  const rec = (channel: string, schema: DescMessage, data: Uint8Array, tWorld: number, seq = 0) =>
    records.push({ channel, schema, data, tWorld: Number.isFinite(tWorld) ? tWorld : 0, seq });
  const w = b.world;
  const ups = Array.from(w.updates);
  const tOf = (k: number) => w.t[k];
  const seqs = new Map<string, number>();
  const take = (ch: string, n: number) => { const s = seqs.get(ch) ?? 0; seqs.set(ch, s + n); return Array.from({ length: n }, (_, i) => big(s + i)); };
  const metric = (ticks: number[], names: string[], values: ArrayLike<number>, unit = '') => {
    for (let s = 0; s < names.length; s += PER_BATCH) {
      const e = Math.min(names.length, s + PER_BATCH);
      const n = e - s;
      rec(CH.metrics, MetricBatchSchema, encodeBatch(MetricBatchSchema, { seq: take(CH.metrics, n),
        tick: ticks.slice(s, e).map(big), t_world: ticks.slice(s, e).map(tOf), name: names.slice(s, e),
        value: Array.from({ length: n }, (_, i) => values[s + i]), unit: new Array(n).fill(unit) }), tOf(ticks[s]));
    }
  };
  const estimate = (est: string, ticks: number[], x: ArrayLike<number>, y: ArrayLike<number>, th: ArrayLike<number>,
    cov?: Record<string, ArrayLike<number>>) => {
    for (let s = 0; s < ticks.length; s += PER_BATCH) {
      const e = Math.min(ticks.length, s + PER_BATCH);
      const n = e - s;
      const sl = (a: ArrayLike<number> | undefined) => (a ? Array.from({ length: n }, (_, i) => a[s + i]) : nan(n));
      rec(CH.estimate, EstimateBatchSchema, encodeBatch(EstimateBatchSchema, { seq: take(`${CH.estimate}|${est}`, n),
        tick: ticks.slice(s, e).map(big), t_world: ticks.slice(s, e).map(tOf), x: sl(x), y: sl(y), theta: sl(th),
        cov_xx: sl(cov?.cov_xx), cov_xy: sl(cov?.cov_xy), cov_xt: nan(n), cov_yy: sl(cov?.cov_yy), cov_yt: nan(n), cov_tt: sl(cov?.cov_tt) },
      { estimator: est }), tOf(ticks[s]));
    }
  };
  const header = (id: string, g: Grid, algorithm: string, evidence: string, sensor: string) => {
    rec(CH.gridHeader, MapGridHeaderSchema, toBinary(MapGridHeaderSchema, create(MapGridHeaderSchema, {
      mapId: id, width: g.width, height: g.height, resolution: g.resolution, originX: g.origin[0], originY: g.origin[1],
      row0IsBottom: false, estimator: id })), 0);
    rec(CH.slamHeader, SlamHeaderSchema, toBinary(SlamHeaderSchema, create(SlamHeaderSchema, {
      slamId: id, algorithm, sensor, params: create(ParamsSchema, { items: [str('evidence', evidence)] }) })), 0);
  };
  const snapshot = (mapId: string, update: number, tick: number, cells: Uint8Array) =>
    rec(CH.snapshot, MapGridSnapshotBatchSchema, toBinary(MapGridSnapshotBatchSchema, create(MapGridSnapshotBatchSchema, {
      seq: take(CH.snapshot, 1), tick: [big(tick)], tWorld: [tOf(tick)], mapId, update: big(update), cellsU8: cells })), tOf(tick));

  // the world
  const m = b.map;
  rec(CH.grid, WorldGridSchema, toBinary(WorldGridSchema, create(WorldGridSchema, {
    mapId: m.id, width: m.width, height: m.height, resolution: m.geo?.resolution ?? 0, originX: m.geo?.origin[0] ?? 0,
    originY: m.geo?.origin[1] ?? 0, blocked: m.occupancy.map((v) => (v === 0 ? 0 : 1)), occupancy: m.occupancy, cost: [],
    specSha256: spec, row0IsBottom: false })), 0);
  const rows = Array.from({ length: w.nRows }, (_, i) => i);
  for (let s = 0; s < w.nRows; s += PER_BATCH) {
    const e = Math.min(w.nRows, s + PER_BATCH);
    rec(CH.truth, TruthPoseBatchSchema, encodeBatch(TruthPoseBatchSchema, { seq: take(CH.truth, e - s), tick: rows.slice(s, e).map(big),
      t_world: Array.from(w.t.subarray(s, e)), x: w.gtX.subarray(s, e), y: w.gtY.subarray(s, e), theta: w.gtYaw.subarray(s, e) }), w.t[s]);
  }
  estimate('world:odometry', rows, w.odomX, w.odomY, w.odomYaw);
  const li = w.lidar;
  const nb = w.nBeams;
  const inc = nb > 1 ? (li.angle_max - li.angle_min) / (nb - 1) : 0;
  ups.forEach((k, u) => {
    const r = w.ranges.subarray(u * nb, (u + 1) * nb);
    rec(CH.scan, ScanBatchSchema, encodeBatch(ScanBatchSchema, { seq: take(CH.scan, 1), tick: [big(k)], t_world: [tOf(k)],
      angle_min: [li.angle_min], angle_increment: [inc], range_min: [li.range_min], range_max: [li.range_max], count: [nb],
      ranges: Array.from(Float32Array.from(r)), ranges_f64: r }), tOf(k));
    const a = w.obsOffset[u]; const z = w.obsOffset[u + 1];
    if (z > a) {
      rec(CH.detect, DetectionBatchSchema, encodeBatch(DetectionBatchSchema, { seq: take(CH.detect, z - a),
        tick: new Array(z - a).fill(big(k)), t_world: new Array(z - a).fill(tOf(k)),
        region_id: Array.from(w.obsId.subarray(a, z), (id) => `landmark:${id}`), colour: new Array(z - a).fill(''),
        detected: new Array(z - a).fill(true), range: w.obsR.subarray(a, z), bearing: w.obsB.subarray(a, z) } as Record<string, Column>,
      { detection_probability: 1, detection_label: 'IDEALISED landmark sensor: obstacle corners with known identities, no misses' }), tOf(k));
    }
  });

  // coco_lab's runs
  for (const r of b.runs) {
    for (const name of Object.keys(r.arrays)) if (!KNOWN_ARRAYS.has(name)) throw new Error(`run ${r.id}: array ${name} has no v2 home`);
    header(r.id, r.grid, r.algorithm, 'MODEL', r.algorithm === 'ekf_slam' ? 'landmarks (IDEALISED)' : 'lidar');
    const c = r.cols as Record<string, ArrayLike<number>>;
    const ticks = Array.from(c.row);
    estimate(r.id, ticks, c.est_x, c.est_y, c.est_yaw, 'cov_xx' in c ? c : undefined);
    const a = r.arrays as Record<string, ArrayLike<number>>;
    if (a['final.x']) estimate(`${r.id}:final`, ticks, a['final.x'], a['final.y'], a['final.yaw']);
    for (const name of Object.keys(c).filter((x) => !EST_COLS.has(x)).sort()) metric(ticks, ticks.map(() => `${r.id}.${name}`), c[name]);
    for (const name of ['score.err_final', 'score.err_online']) {
      if (a[name]) metric(ticks, ticks.map(() => `${r.id}.${name}`), a[name], 'm');
    }
    r.maps.forEach((cells, i) => snapshot(r.id, r.snapshots[i], ticks[r.snapshots[i]], cells));
    if (a['score.diff']) snapshot(`${r.id}:score.diff`, r.n - 1, ticks[r.n - 1], a['score.diff'] as Uint8Array);
    if (a['particles.offset']) {
      const off = a['particles.offset'];
      for (let u = 0; u < r.n; u += 1) {
        const p0 = off[u]; const p1 = off[u + 1];
        const sl = (k: string) => Array.from({ length: p1 - p0 }, (_, i) => a[k][p0 + i]);
        rec(CH.particles, SlamParticleBatchSchema, encodeBatch(SlamParticleBatchSchema, { seq: take(CH.particles, p1 - p0),
          tick: new Array(p1 - p0).fill(big(ticks[u])), t_world: new Array(p1 - p0).fill(tOf(ticks[u])),
          x: sl('particles.x'), y: sl('particles.y'), theta: sl('particles.yaw'), weight: sl('particles.w') },
        { best: c.best ? c.best[u] : 0, update: big(u), slam_id: r.id }), tOf(ticks[u]));
      }
    }
    if (a['lm.offset']) {
      const off = a['lm.offset'];
      for (let u = 0; u < r.n; u += 1) {
        const p0 = off[u]; const p1 = off[u + 1];
        const sl = (k: string) => Array.from({ length: p1 - p0 }, (_, i) => a[k][p0 + i]);
        rec(CH.landmarks, LandmarkBatchSchema, encodeBatch(LandmarkBatchSchema, { seq: take(CH.landmarks, p1 - p0),
          tick: new Array(p1 - p0).fill(big(ticks[u])), t_world: new Array(p1 - p0).fill(tOf(ticks[u])),
          landmark_id: sl('lm.id'), x: sl('lm.x'), y: sl('lm.y'), cov_xx: sl('lm.cxx'), cov_xy: sl('lm.cxy'), cov_yy: sl('lm.cyy') },
        { update: big(u), slam_id: r.id }), tOf(ticks[u]));
      }
    }
    const last = ticks[r.n - 1];
    for (const [stage, from, to, kind] of [['final', 'edges.i', 'edges.j', 'edges.kind'], ['loop_events', 'loops.j', 'loops.k', null]] as const) {
      const f = a[from];
      if (!f) continue;
      const n = f.length;
      rec(CH.edges, GraphEdgeBatchSchema, encodeBatch(GraphEdgeBatchSchema, { seq: take(CH.edges, n), tick: new Array(n).fill(big(last)),
        t_world: new Array(n).fill(tOf(last)), from_node: Array.from(f), to_node: Array.from(a[to]),
        kind: kind ? Array.from(a[kind], String) : new Array(n).fill('loop'), dx: nan(n), dy: nan(n), dtheta: nan(n), error: nan(n) },
      { stage, slam_id: r.id }), tOf(last));
    }
    if (a['opt.k']) {
      const n = a['opt.k'].length;
      const names: string[] = []; const vals: number[] = []; const tk: number[] = [];
      for (let i = 0; i < n; i += 1) for (const o of OPT) { names.push(`${r.id}.opt.${o}`); vals.push(a[`opt.${o}`][i]); tk.push(last); }
      if (n) metric(tk, names, vals);
    }
  }
  // the external backends (STACK)
  for (const e of b.external) {
    const id = `ext:${e.id}`;
    header(id, e.grid, e.backend, 'STACK', `lidar (${e.arm})`);
    estimate(id, ups, e.estX, e.estY, e.estYaw);
    metric(ups, ups.map(() => `${id}.err_online`), e.errOnline, 'm');
    const last = ups[ups.length - 1];
    snapshot(id, ups.length - 1, last, e.cells);
    snapshot(`${id}:score.diff`, ups.length - 1, last, e.diff);
  }
  records.sort((x, y) => x.tWorld - y.tWorld);
  const channels = [...new Map(records.map((x) => [x.channel, x.schema.typeName])).entries()].map(([name, message]) => ({ name, message }));
  const manifest = create(ManifestSchema, {
    runId: await runId(manifestBytes, b.provenance.seed ?? 0, engines), specFormat: SPEC_FORMAT, spec: manifestBytes, specSha256: spec,
    seed: big(b.provenance.seed ?? 0), tier: stack ? Tier.STACK : Tier.TRACE, evidenceClass: stack ? EvidenceClass.STACK : EvidenceClass.MODEL,
    engines: engines.map(([name, version]) => ({ name, version })), channels,
    provenance: { createdUtc: b.provenance.created_utc, tool: CONVERTER, gitSha: b.provenance.git_commit ?? '',
      gitDirty: b.provenance.git_dirty ?? false, source: `coco_lab.slam_bundle ${b.contentHash}`,
      note: stack ? 'Lab 3: a drive recorded on the full ROS 2 stack in Gazebo; coco_lab\'s SLAMs (MODEL) and slam_toolbox / Cartographer (STACK) on it'
        : 'Lab 3: a Sketch drive and the mappers coco_lab ran on it' },
    schemaPackageVersion: '1.0.0',
  });
  return { manifest, records };
}

/** The slam bundle back, from the channels alone: decoded (hash-checked) by the v1 decoder. */
export async function toLab3(manifest: Manifest, messages: ReadMessage[]): Promise<DecodedSlamBundle> {
  if (manifest.specFormat !== SPEC_FORMAT) throw new Error(`not a converted Lab 3 bundle: ${manifest.specFormat}`);
  const parsed = parseSlamManifest(manifest.spec);
  const on = (ch: string) => messages.filter((x) => x.channel === ch);
  const col: Record<string, number[]> = {};
  const push = (name: string, vals: ArrayLike<number>) => { const a = (col[name] ??= []); for (let i = 0; i < vals.length; i += 1) a.push(vals[i]); };
  const first = (b: { seq: bigint[] }) => (b.seq.length ? b.seq[0] : -1n);
  const sorted = <T extends { seq: bigint[] }>(ch: string, schema: DescMessage) =>
    on(ch).map((x) => fromBinary(schema, x.data) as unknown as T).sort((a, c) => Number(first(a) - first(c)));
  col['map.occupancy'] = Array.from(fromBinary(WorldGridSchema, on(CH.grid)[0].data).occupancy);
  type Tp = { seq: bigint[]; tWorld: number[]; x: number[]; y: number[]; theta: number[] };
  for (const t of sorted<Tp>(CH.truth, TruthPoseBatchSchema)) { push('world.t', t.tWorld); push('world.gt_x', t.x); push('world.gt_y', t.y); push('world.gt_yaw', t.theta); }
  type Es = Tp & { estimator: string; covXx: number[]; covXy: number[]; covYy: number[]; covTt: number[] };
  const ests = on(CH.estimate).map((x) => fromBinary(EstimateBatchSchema, x.data) as unknown as Es);
  const byEst = new Map<string, Es[]>();
  for (const e of ests) (byEst.get(e.estimator) ?? byEst.set(e.estimator, []).get(e.estimator)!).push(e);
  for (const list of byEst.values()) list.sort((a, c) => Number(a.seq[0] - c.seq[0]));
  for (const e of byEst.get('world:odometry') ?? []) { push('world.odom_x', e.x); push('world.odom_y', e.y); push('world.odom_yaw', e.theta); }
  type Sc = { seq: bigint[]; tick: bigint[]; rangesF64: number[] };
  for (const s of sorted<Sc>(CH.scan, ScanBatchSchema)) { push('world.updates', s.tick.map(Number)); push('world.ranges', s.rangesF64); }
  // observations: offsets by update
  type Dt = { seq: bigint[]; tick: bigint[]; regionId: string[]; range: number[]; bearing: number[] };
  const ups = col['world.updates'];
  const obsAt = new Map<number, Dt[]>();
  for (const d of sorted<Dt>(CH.detect, DetectionBatchSchema)) (obsAt.get(Number(d.tick[0])) ?? obsAt.set(Number(d.tick[0]), []).get(Number(d.tick[0]))!).push(d);
  push('world.obs.offset', [0]);
  let off = 0;
  for (const k of ups) {
    for (const d of obsAt.get(k) ?? []) {
      push('world.obs.id', d.regionId.map((r) => Number(r.slice('landmark:'.length)))); push('world.obs.r', d.range); push('world.obs.b', d.bearing);
      off += d.regionId.length;
    }
    push('world.obs.offset', [off]);
  }
  col['world.obs.id'] ??= []; col['world.obs.r'] ??= []; col['world.obs.b'] ??= [];
  // estimates of runs and externals
  for (const [est, list] of byEst) {
    if (est === 'world:odometry') continue;
    if (est.startsWith('ext:')) {
      const E = est.slice(4);
      for (const e of list) { push(`ext.${E}.est_x`, e.x); push(`ext.${E}.est_y`, e.y); push(`ext.${E}.est_yaw`, e.theta); }
    } else if (est.endsWith(':final')) {
      const R = est.slice(0, -':final'.length);
      for (const e of list) { push(`run.${R}.arr.final.x`, e.x); push(`run.${R}.arr.final.y`, e.y); push(`run.${R}.arr.final.yaw`, e.theta); }
    } else {
      for (const e of list) {
        push(`run.${est}.col.row`, (e as unknown as { tick: bigint[] }).tick.map(Number)); push(`run.${est}.col.t`, e.tWorld);
        push(`run.${est}.col.est_x`, e.x); push(`run.${est}.col.est_y`, e.y); push(`run.${est}.col.est_yaw`, e.theta);
        push(`run.${est}.col.cov_xx`, e.covXx); push(`run.${est}.col.cov_xy`, e.covXy); push(`run.${est}.col.cov_yy`, e.covYy);
        push(`run.${est}.col.cov_tt`, e.covTt);
      }
    }
  }
  // metrics: per-update columns, scores, optimisations, external errors
  type Mb = { seq: bigint[]; name: string[]; value: number[] };
  for (const mb of sorted<Mb>(CH.metrics, MetricBatchSchema)) {
    mb.name.forEach((nm, i) => {
      const v = [mb.value[i]];
      if (nm.startsWith('ext:')) { const [E, what] = [nm.slice(4, nm.lastIndexOf('.')), nm.slice(nm.lastIndexOf('.') + 1)]; push(`ext.${E}.${what}`, v); return; }
      const R = nm.slice(0, nm.indexOf('.'));
      const rest = nm.slice(nm.indexOf('.') + 1);
      if (rest.startsWith('score.') || rest.startsWith('opt.')) push(`run.${R}.arr.${rest}`, v);
      else push(`run.${R}.col.${rest}`, v);
    });
  }
  // snapshots and diffs
  type Sn = { seq: bigint[]; mapId: string; update: bigint; cellsU8: Uint8Array };
  for (const s of sorted<Sn>(CH.snapshot, MapGridSnapshotBatchSchema)) {
    if (s.mapId.startsWith('ext:')) {
      const E = s.mapId.slice(4);
      if (E.endsWith(':score.diff')) push(`ext.${E.slice(0, -':score.diff'.length)}.diff`, s.cellsU8); else push(`ext.${E}.cells`, s.cellsU8);
    } else if (s.mapId.endsWith(':score.diff')) push(`run.${s.mapId.slice(0, -':score.diff'.length)}.arr.score.diff`, s.cellsU8);
    else { push(`run.${s.mapId}.snap.k`, [Number(s.update)]); push(`run.${s.mapId}.snap.cells`, s.cellsU8); }
  }
  // particles and landmarks, with their offsets
  type Sp = { seq: bigint[]; slamId: string; update: bigint; x: number[]; y: number[]; theta: number[]; weight: number[] };
  // by update: an update with no particles is a batch with no rows
  const parts = sorted<Sp>(CH.particles, SlamParticleBatchSchema).sort((a, c) => Number(a.update - c.update));
  for (const R of [...new Set(parts.map((p) => p.slamId))]) {
    let o = 0; push(`run.${R}.arr.particles.offset`, [0]);
    for (const p of parts.filter((q) => q.slamId === R)) {
      push(`run.${R}.arr.particles.x`, p.x); push(`run.${R}.arr.particles.y`, p.y); push(`run.${R}.arr.particles.yaw`, p.theta);
      push(`run.${R}.arr.particles.w`, p.weight); o += p.x.length; push(`run.${R}.arr.particles.offset`, [o]);
    }
  }
  type Lm = { seq: bigint[]; slamId: string; update: bigint; landmarkId: number[]; x: number[]; y: number[]; covXx: number[]; covXy: number[]; covYy: number[] };
  const lms = sorted<Lm>(CH.landmarks, LandmarkBatchSchema).sort((a, c) => Number(a.update - c.update));
  for (const R of [...new Set(lms.map((p) => p.slamId))]) {
    let o = 0; push(`run.${R}.arr.lm.offset`, [0]);
    for (const p of lms.filter((q) => q.slamId === R)) {
      push(`run.${R}.arr.lm.id`, p.landmarkId); push(`run.${R}.arr.lm.x`, p.x); push(`run.${R}.arr.lm.y`, p.y);
      push(`run.${R}.arr.lm.cxx`, p.covXx); push(`run.${R}.arr.lm.cxy`, p.covXy); push(`run.${R}.arr.lm.cyy`, p.covYy);
      o += p.x.length; push(`run.${R}.arr.lm.offset`, [o]);
    }
  }
  type Ed = { seq: bigint[]; slamId: string; stage: string; fromNode: number[]; toNode: number[]; kind: string[] };
  for (const e of sorted<Ed>(CH.edges, GraphEdgeBatchSchema)) {
    if (e.stage === 'final') { push(`run.${e.slamId}.arr.edges.i`, e.fromNode); push(`run.${e.slamId}.arr.edges.j`, e.toNode); push(`run.${e.slamId}.arr.edges.kind`, e.kind.map(Number)); }
    else { push(`run.${e.slamId}.arr.loops.j`, e.fromNode); push(`run.${e.slamId}.arr.loops.k`, e.toNode); }
  }
  // the optimisation metrics came interleaved (k, chi2_before, chi2_after, iterations per row): already pushed in order by name
  return decodeSlam(parsed, rawFromColumns(parsed.tree, parsed.total, col));
}
