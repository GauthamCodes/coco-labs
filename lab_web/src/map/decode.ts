// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The map bundle 1.0 decoder: a port of `coco_lab/slambundle.py`'s
 * STRUCTURAL checks (`parse_manifest`, `decode`, `SlamBundle.validate`,
 * `SlamTrace.validate`), reusing bundle v1's JSON, content hash, map and
 * provenance code so the formats cannot disagree on those.
 *
 * NOT ported: `replay_check` and every score. They are mapping code, which
 * the browser must not re-implement (CLAUDE.md rule 8); coco_lab runs them
 * at site build time or in the worker, and the page draws a bundle only
 * when its content hash is one coco_lab produced or validated.
 */

import { HOST_LITTLE_ENDIAN, readArray } from '../bundle/arrays';
import { buildMap, checkProvenance, contentHash } from '../bundle/decode';
import { fail } from '../bundle/errors';
import { boundedGunzip } from '../bundle/gzip';
import {
  decodeUtf8, isInt, isList, isObj, isStr, JInt, JObject, parseJson, toPlain, type JNode,
} from '../bundle/json';
import type { MapLayer, Provenance } from '../bundle/model';

export const SLAM_SCHEMA = 'coco_lab.slam_bundle';
export const SLAM_MAJOR = 1;
export const MAX_MANIFEST_BYTES = 1024 * 1024;
export const MAX_ARRAY_BYTES = 256 * 1024 * 1024;
export const MAX_RUNS = 6;
export const MAX_EXTERNAL = 4;
export const MAX_ROWS = 200_000;
export const ALGORITHMS = ['known', 'odometry', 'ekf_slam', 'fastslam', 'pose_graph'] as const;
export type Algorithm = (typeof ALGORITHMS)[number];

type Dtype = 'u8' | 'i32' | 'f64' | 'f32';
const SIZE: Record<Dtype, number> = { u8: 1, i32: 4, f64: 8, f32: 4 };
export const WORLD_COLUMNS = ['t', 'gt_x', 'gt_y', 'gt_yaw', 'odom_x', 'odom_y', 'odom_yaw'] as const;
const COMMON = ['row', 't', 'est_x', 'est_y', 'est_yaw'];

export type Column = Float64Array | Int32Array | Float32Array | Uint8Array;

export interface Lidar {
  samples: number; angle_min: number; angle_max: number; range_min: number; range_max: number;
  mount: [number, number, number];
}

export interface AteSummary {
  n: number; aligned: boolean; alignment: [number, number, number];
  rmse: number; mean: number; max: number; final: number;
}

export interface MapScore {
  tol_m: number; precision: number | null; recall: number | null; f1: number;
  coverage: number | null; occupied_cells: number; visible_wall_cells: number;
  reachable_free_cells: number;
  exact: { precision: number | null; recall: number | null };
}

export interface Grid { width: number; height: number; resolution: number; origin: [number, number] }

export interface SlamRun {
  id: string;
  algorithm: Algorithm;
  params: Record<string, unknown>;
  header: Record<string, unknown>;
  grid: Grid;
  summary: { ate_online: AteSummary; ate_final: AteSummary; map: MapScore };
  cols: Record<string, Float64Array | Int32Array>;
  arrays: Record<string, Column>;
  snapshots: Int32Array;
  /** one Uint8Array per snapshot, nav_msgs/OccupancyGrid bytes, NORTH row first */
  maps: Uint8Array[];
  n: number;
}

export interface ExternalRun {
  id: string; backend: string; arm: string; grid: Grid; source: Record<string, unknown>;
  summary: { ate_online: AteSummary; map: MapScore };
  estX: Float64Array; estY: Float64Array; estYaw: Float64Array;
  cells: Uint8Array; errOnline: Float64Array; diff: Uint8Array;
}

export interface SlamWorld {
  source: 'sketch' | 'recorded';
  status: string;
  nRows: number;
  t: Float64Array; gtX: Float64Array; gtY: Float64Array; gtYaw: Float64Array;
  odomX: Float64Array; odomY: Float64Array; odomYaw: Float64Array;
  updates: Int32Array;
  ranges: Float64Array;
  nBeams: number;
  lidar: Lidar;
  start: [number, number, number];
  landmarks: Array<[number, number, number]>;
  landmarkSpec: Record<string, unknown>;
  obsOffset: Int32Array; obsId: Int32Array; obsR: Float64Array; obsB: Float64Array;
  scenario: Record<string, unknown> | null;
  recorded: Record<string, unknown> | null;
}

export interface DecodedSlamBundle {
  version: string;
  contentHash: string;
  provenance: Provenance;
  map: MapLayer;
  world: SlamWorld;
  scoring: { align: boolean; tol_m: number; definitions: string };
  runs: SlamRun[];
  external: ExternalRun[];
}

function readF32(raw: Uint8Array, offset: number, count: number): Float32Array {
  if (offset < 0 || offset + 4 * count > raw.length) {
    throw new RangeError(`array [${offset}, +${4 * count}) outside ${raw.length} bytes`);
  }
  const start = raw.byteOffset + offset;
  if (HOST_LITTLE_ENDIAN) return new Float32Array(raw.buffer.slice(start, start + 4 * count) as ArrayBuffer);
  const dv = new DataView(raw.buffer, start, 4 * count);
  const out = new Float32Array(count);
  for (let k = 0; k < count; k++) out[k] = dv.getFloat32(4 * k, true);
  return out;
}

export interface ParsedSlamManifest { tree: JObject; compression: 'none' | 'gzip'; total: number }

export function parseSlamManifest(bytes: Uint8Array): ParsedSlamManifest {
  if (bytes.length > MAX_MANIFEST_BYTES) fail('bounds', `manifest exceeds ${MAX_MANIFEST_BYTES} bytes`);
  const tree = parseJson(decodeUtf8(bytes));
  if (!isObj(tree)) fail('structure', 'manifest must be an object');
  if (tree.get('schema') !== SLAM_SCHEMA) fail('schema', `schema is not ${SLAM_SCHEMA}`);
  const version = tree.get('version');
  const major = isStr(version) && /^\d+(\.\d+)?$/.test(version) ? Number(version.split('.')[0]) : NaN;
  if (!Number.isInteger(major)) fail('version', `bad version ${JSON.stringify(toPlain(version ?? null))}`);
  if (major !== SLAM_MAJOR) {
    fail('version', `map bundle major version ${major} is not supported (this reader speaks 1.x)`);
  }
  const kinds: Array<[string, (v: JNode | undefined) => boolean]> = [
    ['provenance', isObj], ['map', isObj], ['world', isObj], ['scoring', isObj], ['runs', isList],
    ['external', isList], ['arrays', isList], ['encoding', isObj], ['content_hash', isStr],
  ];
  for (const [k, ok] of kinds) if (!ok(tree.get(k))) fail('structure', `manifest.${k} has the wrong type`);
  const enc = tree.get('encoding') as JObject;
  const compression = enc.get('compression');
  if (enc.get('byte_order') !== 'little' || (compression !== 'none' && compression !== 'gzip')) {
    fail('structure', 'encoding must be little-endian, none or gzip');
  }
  let offset = 0;
  for (const a of tree.get('arrays') as JNode[]) {
    if (!(isObj(a) && isStr(a.get('name')) && isStr(a.get('dtype')) && (a.get('dtype') as string) in SIZE)) {
      fail('table', 'bad array entry');
    }
    for (const k of ['count', 'offset', 'byte_length']) {
      const v = a.get(k);
      if (!(isInt(v) && v.big >= 0n)) fail('table', `array ${a.get('name')}: ${k} must be an int >= 0`);
    }
    if ((a.get('offset') as JInt).value !== offset) fail('table', `array ${a.get('name')}: not contiguous`);
    const bl = (a.get('byte_length') as JInt).value;
    if (bl !== (a.get('count') as JInt).value * SIZE[a.get('dtype') as Dtype]) {
      fail('table', `array ${a.get('name')}: byte_length disagrees with count x dtype`);
    }
    offset += bl;
  }
  if (offset > MAX_ARRAY_BYTES) fail('bounds', `arrays total ${offset} bytes`);
  return { tree, compression: compression as 'none' | 'gzip', total: offset };
}

const finite = (v: Float64Array | Float32Array) => v.every(Number.isFinite);

function gridOf(g: unknown, what: string): Grid {
  const o = g as Grid;
  if (!(o && Number.isInteger(o.width) && Number.isInteger(o.height) && o.width > 0 && o.height > 0
    && o.width * o.height <= 16_000_000 && Number.isFinite(o.resolution) && o.resolution > 0
    && Array.isArray(o.origin) && o.origin.length === 2 && o.origin.every(Number.isFinite))) {
    fail('structure', `${what}: bad grid`);
  }
  return { width: o.width, height: o.height, resolution: o.resolution, origin: [o.origin[0], o.origin[1]] };
}

export async function decodeSlam(parsed: ParsedSlamManifest, raw: Uint8Array): Promise<DecodedSlamBundle> {
  const { tree } = parsed;
  if (raw.length !== parsed.total) fail('length', 'array bytes do not match the table');
  if (tree.get('content_hash') !== await contentHash(tree, raw)) {
    fail('hash', 'content_hash does not match the content');
  }
  const table = new Map<string, JObject>();
  for (const a of tree.get('arrays') as JObject[]) {
    const name = a.get('name') as string;
    if (table.has(name)) fail('table', `duplicate array ${name}`);
    table.set(name, a);
  }
  const used = new Set<string>();
  const take = (name: string, dtype: Dtype): Column => {
    const a = table.get(name);
    if (!a) fail('table', `missing array ${name}`);
    if (a.get('dtype') !== dtype) fail('dtype', `array ${name} must be ${dtype}`);
    used.add(name);
    const off = (a.get('offset') as JInt).value;
    const count = (a.get('count') as JInt).value;
    if (dtype === 'f32') return readF32(raw, off, count);
    if (dtype === 'u8') return raw.slice(off, off + count);
    return readArray(raw, off, count, dtype);
  };
  used.add('map.occupancy');
  const map = await buildMap(tree.get('map') as JObject, table, raw,
    (name) => take(name, 'f64') as Float64Array);
  if (!map.geo) fail('map', 'a map bundle\'s truth map is placed (resolution and origin)');

  const wm = tree.get('world') as JObject;
  const source = wm.get('source');
  if (source !== 'sketch' && source !== 'recorded') fail('structure', 'world.source');
  const nRows = wm.get('n_rows');
  if (!(isInt(nRows) && nRows.value > 0 && nRows.value <= MAX_ROWS)) fail('bounds', 'world.n_rows out of range');
  const n = (nRows as JInt).value;
  const lidar = toPlain(wm.get('lidar') ?? null) as Lidar;
  if (!(lidar && Number.isInteger(lidar.samples) && lidar.samples >= 1 && lidar.samples <= 480)) {
    fail('structure', 'world.lidar.samples must be 1..480');
  }
  const col = (c: string) => {
    const v = take(`world.${c}`, 'f64') as Float64Array;
    if (v.length !== n) fail('structure', `world.${c} has ${v.length} rows, expected ${n}`);
    if (!finite(v)) fail('structure', `world.${c} must be finite`);
    return v;
  };
  const t = col('t');
  for (let i = 1; i < n; i++) if (!(t[i] > t[i - 1])) fail('structure', 'world.t must strictly increase');
  const updates = take('world.updates', 'i32') as Int32Array;
  if (updates.length === 0 || updates[0] !== 0) fail('structure', 'world.updates must start at 0');
  for (let i = 1; i < updates.length; i++) {
    if (!(updates[i] > updates[i - 1])) fail('structure', 'world.updates must strictly increase');
  }
  if (updates[updates.length - 1] >= n) fail('structure', 'world.updates must index a row');
  const nu = updates.length;
  const ranges = take('world.ranges', 'f64') as Float64Array;
  if (ranges.length !== nu * lidar.samples) fail('structure', 'world.ranges is not n_updates x n_beams');
  if (ranges.some((v) => Number.isNaN(v) || v < 0)) fail('structure', 'ranges must be >= 0 or inf');
  const obsOffset = take('world.obs.offset', 'i32') as Int32Array;
  const obsId = take('world.obs.id', 'i32') as Int32Array;
  const obsR = take('world.obs.r', 'f64') as Float64Array;
  const obsB = take('world.obs.b', 'f64') as Float64Array;
  if (obsOffset.length !== nu + 1 || obsOffset[0] !== 0 || obsOffset[nu] !== obsId.length
    || obsR.length !== obsId.length || obsB.length !== obsId.length) {
    fail('structure', 'bad landmark observation arrays');
  }
  for (let i = 1; i <= nu; i++) if (obsOffset[i] < obsOffset[i - 1]) fail('structure', 'observation offsets decrease');
  if (!finite(obsR) || !finite(obsB)) fail('structure', 'observations must be finite');
  const landmarks = toPlain(wm.get('landmarks') ?? null) as Array<[number, number, number]>;
  if (!Array.isArray(landmarks)) fail('structure', 'world.landmarks');
  const lmIds = new Set(landmarks.map((l) => l[0]));
  if (Array.from(obsId).some((id) => !lmIds.has(id))) fail('structure', 'an observation names an unknown landmark');
  const status = wm.get('status');
  if (!(isStr(status) && ['route_done', 'timeout', 'stuck'].includes(status))) fail('structure', 'world.status');
  const start = toPlain(wm.get('start') ?? null) as [number, number, number];
  const world: SlamWorld = {
    source: source as 'sketch' | 'recorded', status: status as string, nRows: n, t,
    gtX: col('gt_x'), gtY: col('gt_y'), gtYaw: col('gt_yaw'),
    odomX: col('odom_x'), odomY: col('odom_y'), odomYaw: col('odom_yaw'),
    updates, ranges, nBeams: lidar.samples, lidar, start, landmarks,
    landmarkSpec: toPlain(wm.get('landmark_spec') ?? null) as Record<string, unknown>,
    obsOffset, obsId, obsR, obsB,
    scenario: toPlain(wm.get('scenario') ?? null) as Record<string, unknown> | null,
    recorded: toPlain(wm.get('recorded') ?? null) as Record<string, unknown> | null,
  };

  const ids = new Set<string>();
  const okId = (id: unknown) => isStr(id as JNode) && /^[A-Za-z0-9_-]{1,32}$/.test(id as string) && !ids.has(id as string);
  const runsNode = tree.get('runs') as JNode[];
  if (runsNode.length < 1 || runsNode.length > MAX_RUNS) fail('structure', `1..${MAX_RUNS} runs`);
  const runs: SlamRun[] = [];
  for (const r of runsNode) {
    if (!(isObj(r) && isObj(r.get('header')) && isObj(r.get('arrays')) && isList(r.get('int_columns')))) {
      fail('structure', 'bad run entry');
    }
    const id = r.get('id');
    if (!okId(id)) fail('structure', 'run ids must be unique short words');
    ids.add(id as string);
    const header = toPlain(r.get('header')!) as Record<string, unknown>;
    if (header.schema !== 'coco_lab.slam_trace' || !/^1\./.test(String(header.version))) {
      fail('version', `run ${id}: not a slam_trace 1.x`);
    }
    const algorithm = header.algorithm as Algorithm;
    if (!ALGORITHMS.includes(algorithm)) fail('structure', `run ${id}: unknown algorithm`);
    const grid = gridOf(header.grid, `run ${id}`);
    const ints = new Set(toPlain(r.get('int_columns')!) as string[]);
    const prefix = `run.${id}.col.`;
    const names = [...table.keys()].filter((k) => k.startsWith(prefix)).map((k) => k.slice(prefix.length)).sort();
    for (const c of COMMON) if (!names.includes(c)) fail('structure', `run ${id}: missing column ${c}`);
    const cols: Record<string, Float64Array | Int32Array> = {};
    for (const c of names) {
      const v = take(prefix + c, ints.has(c) ? 'i32' : 'f64') as Float64Array | Int32Array;
      if (v.length !== nu) fail('structure', `run ${id}: column ${c} length`);
      if (!ints.has(c) && !finite(v as Float64Array)) fail('structure', `run ${id}: column ${c} must be finite`);
      cols[c] = v;
    }
    if ((cols.row as Int32Array).some((v, i) => v !== updates[i])) {
      fail('structure', `run ${id}: rows are not the world's updates`);
    }
    const arrays: Record<string, Column> = {};
    for (const [name, dt] of Object.entries(toPlain(r.get('arrays')!) as Record<string, string>)) {
      if (!(dt in SIZE)) fail('dtype', `run ${id}: dtype ${dt}`);
      arrays[name] = take(`run.${id}.arr.${name}`, dt as Dtype);
    }
    if ('final.x' in arrays && arrays['final.x'].length !== nu) fail('structure', `run ${id}: final trajectory length`);
    const snapshots = take(`run.${id}.snap.k`, 'i32') as Int32Array;
    const cells = take(`run.${id}.snap.cells`, 'u8') as Uint8Array;
    const size = grid.width * grid.height;
    if (cells.length !== size * snapshots.length) fail('structure', `run ${id}: snapshot sizes`);
    for (let i = 0; i < snapshots.length; i++) {
      if (!(snapshots[i] >= 0 && snapshots[i] < nu) || (i > 0 && snapshots[i] <= snapshots[i - 1])) {
        fail('structure', `run ${id}: snapshots must be increasing update indices`);
      }
    }
    if (snapshots.length === 0) fail('structure', `run ${id}: no map`);
    const maps = Array.from(snapshots, (_, i) => cells.subarray(i * size, (i + 1) * size));
    const summary = toPlain(r.get('summary') ?? null) as SlamRun['summary'];
    if (!(summary && summary.map && summary.ate_online && summary.ate_final)) fail('structure', `run ${id} is not scored`);
    runs.push({
      id: id as string, algorithm, params: (header.params ?? {}) as Record<string, unknown>, header, grid,
      summary, cols, arrays, snapshots, maps, n: nu,
    });
  }
  const extNode = tree.get('external') as JNode[];
  if (extNode.length > MAX_EXTERNAL) fail('structure', `at most ${MAX_EXTERNAL} external runs`);
  if (extNode.length && source !== 'recorded') fail('structure', 'external runs belong to recorded drives');
  const external: ExternalRun[] = [];
  const truthCells = map.width * map.height;
  for (const e of extNode) {
    if (!isObj(e)) fail('structure', 'bad external entry');
    const id = e.get('id');
    if (!okId(id)) fail('structure', 'run ids must be unique short words');
    ids.add(id as string);
    const grid = gridOf(toPlain(e.get('grid') ?? null), `external ${id}`);
    const f = (c: string) => {
      const v = take(`ext.${id}.${c}`, 'f64') as Float64Array;
      if (v.length !== nu) fail('structure', `external ${id}: ${c} length`);
      return v;
    };
    const cells = take(`ext.${id}.cells`, 'u8') as Uint8Array;
    const diff = take(`ext.${id}.diff`, 'u8') as Uint8Array;
    if (cells.length !== grid.width * grid.height || diff.length !== truthCells) fail('structure', `external ${id}: map sizes`);
    external.push({
      id: id as string, backend: String(toPlain(e.get('backend') ?? null)), arm: String(toPlain(e.get('arm') ?? null)),
      grid, source: toPlain(e.get('source') ?? null) as Record<string, unknown>,
      summary: toPlain(e.get('summary') ?? null) as ExternalRun['summary'],
      estX: f('est_x'), estY: f('est_y'), estYaw: f('est_yaw'), cells, errOnline: f('err_online'), diff,
    });
  }
  const extra = [...table.keys()].filter((k) => !used.has(k));
  if (extra.length) fail('table', `unexpected arrays ${extra.sort().slice(0, 5).join(', ')}`);
  const prov = tree.get('provenance') as JObject;
  checkProvenance(prov);
  const want = source === 'sketch' ? 'sketch' : 'recorded-run';
  if (prov.get('source_kind') !== want) fail('provenance', 'provenance.source_kind does not match the world');
  const sc = toPlain(tree.get('scoring')!) as DecodedSlamBundle['scoring'];
  return {
    version: tree.get('version') as string, contentHash: tree.get('content_hash') as string,
    provenance: toPlain(prov) as Provenance, map, world, scoring: sc, runs, external,
  };
}

export async function loadSlamBytes(manifest: Uint8Array, arraysFile: Uint8Array): Promise<DecodedSlamBundle> {
  const parsed = parseSlamManifest(manifest);
  const raw = parsed.compression === 'gzip'
    ? await boundedGunzip(arraysFile, parsed.total)
    : arraysFile.subarray(0, parsed.total + 1);
  return decodeSlam(parsed, raw);
}

/** Beam angles in the sensor frame: the LiDAR spec's even spacing. */
export function beamAngles(l: Lidar): number[] {
  if (l.samples === 1) return [l.angle_min];
  const step = (l.angle_max - l.angle_min) / (l.samples - 1);
  return Array.from({ length: l.samples }, (_, i) => l.angle_min + i * step);
}

/** The index of the latest snapshot at or before update `k` (or 0). */
export function snapshotAt(run: SlamRun, k: number): number {
  let s = 0;
  for (let i = 0; i < run.snapshots.length; i++) if (run.snapshots[i] <= k) s = i;
  return s;
}
