// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 1 bundles -> v2 runs (M1.9), and back, with nothing lost.
 *
 * A v1 bundle (coco_lab.bundle: manifest.json + arrays) becomes a v2 run
 * file (MCAP, coco_schemas channels):
 *
 *   spec            the bundle's manifest.json, byte for byte
 *                   (spec_format "coco_lab.bundle.v1+json"): its run block,
 *                   provenance and the recording's measured results;
 *   world.grid      map.occupancy (+ map.cost as f32, refused unless exact);
 *   plan.search.*   the trace: header, events, summary;
 *   recorded runs (Phase 1C, the full ROS 2 stack in Gazebo):
 *     truth.pose     recording.gt   (/model/coco/odometry, ground truth)
 *     robot.state    recording.amcl (the stack's belief; v, omega NaN: the
 *                    belief carries no command)
 *     plan.path      recording.plan (/lab/plan)
 *     metrics        recording.cmd  (cmd.v, cmd.w; /diff_drive_controller/cmd_vel)
 *     annotation     the arbiter and collision-monitor timelines.
 *
 * Tier and evidence class: a recorded run is TIER_STACK / STACK; a
 * glass-box trace is TIER_TRACE / MODEL (coco_lab computed it).
 *
 * Clocks. A glass-box trace has no world: tick 0, t_world 0. A recording
 * keeps its sim time as t_world, exactly, and tick = 0.1 s bins from the
 * rosbag's start; the search (computed before the drive) is placed at
 * FollowPath acceptance, `result.t_accept_sim`.
 *
 * `toLab1` rebuilds the v1 arrays from the CHANNELS alone and hands them,
 * with the spec bytes, to the site's v1 decoder, which re-checks the
 * bundle's content hash: a lossless conversion is one that decodes.
 */

import { create, fromBinary, toBinary, type DescMessage } from '@bufbuild/protobuf';

import { decode, parseManifest } from '../bundle/decode';
import { JFloat, JInt, JObject, isList, isObj, type JNode } from '../bundle/json';
import type { DecodedBundle } from '../bundle/model';
import { encodeBatch, type Column } from '../schemas/columns';
import { AnnotationBatchSchema, Level } from '../schemas/gen/coco/annotation/v1/annotation_pb';
import { ManifestSchema, Tier, EvidenceClass, type Manifest } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import { ParamsSchema, type Params } from '../schemas/gen/coco/common/v1/common_pb';
import { MetricBatchSchema } from '../schemas/gen/coco/metrics/v1/metrics_pb';
import { PathBatchSchema } from '../schemas/gen/coco/plan/v1/path_pb';
import { SearchEventBatchSchema, SearchHeaderSchema, SearchStatus, SearchSummarySchema } from '../schemas/gen/coco/plan/v1/search_pb';
import { RobotStateBatchSchema } from '../schemas/gen/coco/robot/v1/robot_pb';
import { TruthPoseBatchSchema } from '../schemas/gen/coco/truth/v1/truth_pb';
import { WorldGridSchema } from '../schemas/gen/coco/world/v1/world_pb';
import type { ReadMessage, RunRecord } from '../schemas/mcap';
import { runId, specSha256 } from '../schemas/runid';

export const SPEC_FORMAT = 'coco_lab.bundle.v1+json';
export const CONVERTER = 'lab_web/src/convert/lab1.ts';
const DT = 0.1;
const EVENTS_PER_BATCH = 8192;
const TRACE_COLS = ['row', 'col', 'sub', 'g', 'h', 'f', 'parent_row', 'parent_col', 'parent_sub'] as const;

export interface Converted { manifest: Manifest; records: RunRecord[] }

const rec = (channel: string, schema: DescMessage, data: Uint8Array, tWorld: number, seq = 0): RunRecord =>
  ({ channel, schema, data, tWorld, seq });

/** A JSON value as a protobuf Scalar, int / float / string / bool kept apart. */
function params(o: JObject): Params {
  return create(ParamsSchema, { items: o.entries.map(([key, v]) => {
    let value;
    if (v instanceof JInt) value = { case: 'intValue' as const, value: v.big };
    else if (v instanceof JFloat) value = { case: 'doubleValue' as const, value: v.value };
    else if (typeof v === 'string') value = { case: 'stringValue' as const, value: v };
    else if (typeof v === 'boolean') value = { case: 'boolValue' as const, value: v };
    else throw new Error(`graph.${key}: v2 Params carry scalars only`);
    return { key, value: { value } };
  }) });
}

const loc = (v: JNode | undefined) => {
  if (!isList(v) || v.length !== 3) throw new Error('a trace start/goal is [row, col, sub]');
  const [row, col, sub] = v.map((x) => (x as JInt).value);
  return { row, col, sub };
};

/** Seconds of sim time -> tick (0.1 s bins from t0). */
const tickOf = (t: number, t0: number) => Math.max(0, Math.floor((t - t0) / DT + 1e-9));

export async function fromLab1(b: DecodedBundle, manifestBytes: Uint8Array): Promise<Converted> {
  const stack = b.provenance.source_kind === 'recorded-run';
  if (stack && !b.recording) throw new Error('a recorded run without a recording');
  const spec = await specSha256(manifestBytes);
  const engines: [string, string][] = [['coco_lab', b.provenance.coco_lab_version], ['converter', `${CONVERTER} 1`]];
  const meta = (b.recording?.meta ?? {}) as Record<string, unknown>;
  const t0 = stack ? b.provenance.rosbag?.sim_time_start ?? 0 : 0;
  const tPlan = stack ? Number((meta.result as { t_accept_sim?: number } | undefined)?.t_accept_sim ?? t0) : 0;
  const kPlan = tickOf(tPlan, t0);
  const records: RunRecord[] = [];

  // the world
  const m = b.map;
  let cost: Float32Array | undefined;
  if (m.cost) {
    cost = Float32Array.from(m.cost);
    for (let i = 0; i < cost.length; i += 1) {
      if (cost[i] !== m.cost[i] && !(Number.isNaN(cost[i]) && Number.isNaN(m.cost[i]))) {
        throw new Error(`map.cost[${i}] = ${m.cost[i]} is not exact in f32; WorldGrid.cost would lose it`);
      }
    }
  }
  records.push(rec('coco.world.grid.v1', WorldGridSchema, toBinary(WorldGridSchema, create(WorldGridSchema, {
    mapId: m.id, width: m.width, height: m.height, resolution: m.geo?.resolution ?? 0,
    originX: m.geo?.origin[0] ?? 0, originY: m.geo?.origin[1] ?? 0, blocked: m.occupancy.map((v) => (v === 0 ? 0 : 1)),
    occupancy: m.occupancy, cost: cost ? Array.from(cost) : [], specSha256: spec, row0IsBottom: false,
  })), 0));

  // the search
  const tr = b.manifest.get('trace') as JObject;
  const th = tr.get('header') as JObject;
  // as trace_v1.py: a field the schema does not carry is refused, never dropped
  const refuse = (o: JObject, known: string[], what: string) => {
    const extra = o.keys().filter((k) => !known.includes(k));
    if (extra.length) throw new Error(`${what} fields v2 does not carry: ${extra.join(', ')}`);
  };
  refuse(th, ['schema', 'version', 'algorithm', 'heuristic', 'weight', 'tie_break', 'start', 'goal', 'graph'], 'trace header');
  refuse(tr.get('summary') as JObject, ['status', 'expansions', 'pushes', 'relaxes', 'path_cost', 'path_length', 'path_steps'],
    'trace summary');
  const hdr = b.trace.header;
  records.push(rec('coco.plan.search.header.v1', SearchHeaderSchema, toBinary(SearchHeaderSchema, create(SearchHeaderSchema, {
    searchId: 0n, sourceSchema: hdr.schema, sourceVersion: hdr.version, algorithm: hdr.algorithm, heuristic: hdr.heuristic,
    ...(hdr.weight != null ? { weight: hdr.weight } : {}), tieBreak: hdr.tie_break,
    start: loc(th.get('start')), goal: loc(th.get('goal')), graph: params(th.get('graph') as JObject),
    tick: BigInt(kPlan), tWorld: tPlan,
  })), tPlan));
  const ev = b.trace.events;
  for (let s = 0; s < b.trace.n; s += EVENTS_PER_BATCH) {
    const e = Math.min(b.trace.n, s + EVENTS_PER_BATCH);
    const n = e - s;
    const cols: Record<string, Column> = {
      seq: Array.from({ length: n }, (_, i) => BigInt(s + i)), tick: new Array(n).fill(BigInt(kPlan)),
      t_world: new Array(n).fill(tPlan), kind: Array.from(ev.kind.subarray(s, e), (k) => k + 1),
    };
    for (const c of TRACE_COLS) cols[c] = ev[c].subarray(s, e);
    records.push(rec('coco.plan.search.events.v1', SearchEventBatchSchema,
      encodeBatch(SearchEventBatchSchema, cols, { search_id: 0n }), tPlan, s));
  }
  const sm = b.trace.summary;
  records.push(rec('coco.plan.search.summary.v1', SearchSummarySchema, toBinary(SearchSummarySchema, create(SearchSummarySchema, {
    searchId: 0n, status: sm.status === 'found' ? SearchStatus.FOUND : SearchStatus.NO_PATH,
    expansions: BigInt(sm.expansions), pushes: BigInt(sm.pushes), relaxes: BigInt(sm.relaxes),
    ...(sm.path_cost != null ? { pathCost: sm.path_cost } : {}), ...(sm.path_length != null ? { pathLength: sm.path_length } : {}),
    ...(sm.path_steps != null ? { pathSteps: BigInt(sm.path_steps) } : {}),
  })), tPlan));

  // the recording, binned by tick
  const st = b.recording?.streams ?? {};
  const binned = (t: Float64Array, emit: (s: number, e: number, k: number) => void) => {
    let s = 0;
    while (s < t.length) {
      const k = tickOf(t[s], t0);
      let e = s + 1;
      while (e < t.length && tickOf(t[e], t0) === k) e += 1;
      emit(s, e, k);
      s = e;
    }
  };
  const clocks = (t: Float64Array, s: number, e: number, k: number) => ({
    seq: Array.from({ length: e - s }, (_, i) => BigInt(s + i)), tick: new Array(e - s).fill(BigInt(k)), t_world: t.subarray(s, e),
  });
  if (st.gt) {
    const g = st.gt;
    binned(g.t, (s, e, k) => records.push(rec('coco.truth.pose.v1', TruthPoseBatchSchema, encodeBatch(TruthPoseBatchSchema,
      { ...clocks(g.t, s, e, k), x: g.x.subarray(s, e), y: g.y.subarray(s, e), theta: g.yaw.subarray(s, e) }), g.t[s], s)));
  }
  if (st.amcl) {
    const a = st.amcl;
    binned(a.t, (s, e, k) => records.push(rec('coco.robot.state.v1', RobotStateBatchSchema, encodeBatch(RobotStateBatchSchema,
      { ...clocks(a.t, s, e, k), x: a.x.subarray(s, e), y: a.y.subarray(s, e), theta: a.yaw.subarray(s, e),
        v: new Array(e - s).fill(NaN), omega: new Array(e - s).fill(NaN) }), a.t[s], s)));
  }
  if (st.plan) {
    const p = st.plan;
    const n = p.x.length;
    records.push(rec('coco.plan.path.poses.v1', PathBatchSchema, encodeBatch(PathBatchSchema, {
      seq: Array.from({ length: n }, (_, i) => BigInt(i)), tick: new Array(n).fill(BigInt(kPlan)), t_world: new Array(n).fill(tPlan),
      x: p.x, y: p.y, theta: p.yaw }, { search_id: 0n }), tPlan));
  }
  if (st.cmd) {
    const c = st.cmd;
    binned(c.t, (s, e, k) => {
      const n = e - s;
      const t = c.t.subarray(s, e);
      const rows = Array.from({ length: 2 * n }, (_, i) => i);
      records.push(rec('coco.metrics.values.v1', MetricBatchSchema, encodeBatch(MetricBatchSchema, {
        seq: rows.map((i) => BigInt(2 * s + i)), tick: rows.map(() => BigInt(k)), t_world: rows.map((i) => t[i >> 1]),
        name: rows.map((i) => (i & 1 ? 'cmd.w' : 'cmd.v')), value: rows.map((i) => (i & 1 ? c.w[s + (i >> 1)] : c.v[s + (i >> 1)])),
        unit: rows.map((i) => (i & 1 ? 'rad/s' : 'm/s')) }), c.t[s], 2 * s));
    });
  }
  const notes: [number, string][] = [];
  for (const [t, mode, active] of (meta.arbiter_timeline ?? []) as [number, string, string][]) {
    notes.push([t, `arbiter: mode ${mode}, active ${active}`]);
  }
  for (const [t, code, name] of (meta.collision_monitor_timeline ?? []) as [number, number, string][]) {
    notes.push([t, code === 0 ? 'collision monitor: clear' : `collision monitor: ${name} (action ${code})`]);
  }
  notes.sort((x, y) => x[0] - y[0]);
  notes.forEach(([t, text], i) => records.push(rec('coco.annotation.text.v1', AnnotationBatchSchema, encodeBatch(AnnotationBatchSchema, {
    seq: [BigInt(i)], tick: [BigInt(tickOf(t, t0))], t_world: [t], text: [text], level: [Level.INFO], has_position: [false],
    x: [0], y: [0], source: ['coco_lab_ros.lab_export'] }), t, i)));

  records.sort((x, y) => x.tWorld - y.tWorld);
  const channels = [...new Map(records.map((r) => [r.channel, r.schema.typeName])).entries()]
    .map(([name, message]) => ({ name, message }));
  const manifest = create(ManifestSchema, {
    runId: await runId(manifestBytes, b.provenance.seed ?? 0, engines), specFormat: SPEC_FORMAT, spec: manifestBytes,
    specSha256: spec, seed: BigInt(b.provenance.seed ?? 0),
    tier: stack ? Tier.STACK : Tier.TRACE, evidenceClass: stack ? EvidenceClass.STACK : EvidenceClass.MODEL,
    engines: engines.map(([name, version]) => ({ name, version })), channels,
    provenance: { createdUtc: b.provenance.created_utc, tool: CONVERTER, gitSha: b.provenance.git_commit ?? '',
      gitDirty: b.provenance.git_dirty ?? false, source: `coco_lab.bundle ${b.contentHash}`,
      note: stack ? 'converted from a recorded full-stack run (ROS 2 + Gazebo)' : 'converted from a glass-box trace' },
    schemaPackageVersion: '1.0.0',
  });
  return { manifest, records };
}

/** The v1 bundle back, from the channels alone: decoded (so hash-checked) by the v1 decoder. */
export async function toLab1(manifest: Manifest, messages: ReadMessage[]): Promise<DecodedBundle> {
  if (manifest.specFormat !== SPEC_FORMAT) throw new Error(`not a converted Lab 1 bundle: ${manifest.specFormat}`);
  const parsed = parseManifest(manifest.spec);
  const on = (ch: string) => messages.filter((m) => m.channel === ch);
  const col: Record<string, ArrayLike<number>> = {};
  const cat = <T extends { seq: bigint[] }>(ch: string, schema: DescMessage, get: (b: T) => Record<string, ArrayLike<number>>) => {
    const out: Record<string, number[]> = {};
    const rows: [bigint, Record<string, number>][] = [];
    for (const m of on(ch)) {
      const b = fromBinary(schema, m.data) as unknown as T;
      const cols = get(b);
      b.seq.forEach((s, i) => rows.push([s, Object.fromEntries(Object.entries(cols).map(([k, v]) => [k, v[i]]))]));
    }
    rows.sort((x, y) => (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0));
    for (const [, r] of rows) for (const [k, v] of Object.entries(r)) (out[k] ??= []).push(v);
    return out;
  };
  const grid = on('coco.world.grid.v1').map((m) => fromBinary(WorldGridSchema, m.data))[0];
  if (grid) { col['map.occupancy'] = grid.occupancy; if (grid.cost.length) col['map.cost'] = grid.cost; }
  type Ev = ReturnType<typeof fromBinary<typeof SearchEventBatchSchema>>;
  const ev = cat<Ev>('coco.plan.search.events.v1', SearchEventBatchSchema, (b) => ({
    kind: b.kind.map((k) => k - 1), row: b.row, col: b.col, sub: b.sub, g: b.g, h: b.h, f: b.f,
    parent_row: b.parentRow, parent_col: b.parentCol, parent_sub: b.parentSub }));
  for (const [k, v] of Object.entries(ev)) col[`trace.${k}`] = v;
  type Tp = ReturnType<typeof fromBinary<typeof TruthPoseBatchSchema>>;
  for (const [k, v] of Object.entries(cat<Tp>('coco.truth.pose.v1', TruthPoseBatchSchema,
    (b) => ({ t: b.tWorld, x: b.x, y: b.y, yaw: b.theta })))) col[`recording.gt.${k}`] = v;
  type Rs = ReturnType<typeof fromBinary<typeof RobotStateBatchSchema>>;
  for (const [k, v] of Object.entries(cat<Rs>('coco.robot.state.v1', RobotStateBatchSchema,
    (b) => ({ t: b.tWorld, x: b.x, y: b.y, yaw: b.theta })))) col[`recording.amcl.${k}`] = v;
  type Pb = ReturnType<typeof fromBinary<typeof PathBatchSchema>>;
  for (const [k, v] of Object.entries(cat<Pb>('coco.plan.path.poses.v1', PathBatchSchema,
    (b) => ({ x: b.x, y: b.y, yaw: b.theta })))) col[`recording.plan.${k}`] = v;
  type Mb = ReturnType<typeof fromBinary<typeof MetricBatchSchema>>;
  const mrows: [bigint, string, number, number][] = [];
  for (const m of on('coco.metrics.values.v1')) {
    const b = fromBinary(MetricBatchSchema, m.data) as Mb;
    b.seq.forEach((s, i) => mrows.push([s, b.name[i], b.tWorld[i], b.value[i]]));
  }
  mrows.sort((x, y) => (x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : 0));
  if (mrows.length) {
    col['recording.cmd.t'] = mrows.filter((r) => r[1] === 'cmd.v').map((r) => r[2]);
    col['recording.cmd.v'] = mrows.filter((r) => r[1] === 'cmd.v').map((r) => r[3]);
    col['recording.cmd.w'] = mrows.filter((r) => r[1] === 'cmd.w').map((r) => r[3]);
  }

  const table = (parsed.tree.get('arrays') as JNode[]).filter(isObj);
  const raw = new Uint8Array(parsed.total);
  const dv = new DataView(raw.buffer);
  for (const a of table) {
    const name = a.get('name') as string;
    const dtype = a.get('dtype') as string;
    const count = (a.get('count') as JInt).value;
    let off = (a.get('offset') as JInt).value;
    const v = col[name];
    if (!v) throw new Error(`no v2 channel carries ${name}`);
    if (v.length !== count) throw new Error(`${name}: ${v.length} values from the channels, the bundle has ${count}`);
    for (let i = 0; i < count; i += 1) {
      if (dtype === 'u8') { dv.setUint8(off, v[i]); off += 1; } else if (dtype === 'i32') { dv.setInt32(off, v[i], true); off += 4; } else {
        dv.setFloat64(off, v[i], true); off += 8;
      }
    }
  }
  return decode(parsed, raw);
}
