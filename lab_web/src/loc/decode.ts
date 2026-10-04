// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The localisation bundle 1.0 decoder: a port of `coco_lab/locbundle.py`'s
 * STRUCTURAL checks (`parse_manifest`, `decode`, `LocBundle.validate`,
 * `LocTrace.validate`), reusing bundle v1's JSON, content hash, map and
 * provenance code so the two formats cannot disagree on those.
 *
 * NOT ported: `replay_check`, which re-runs the Sketch world and the
 * filters. That is localisation code, which the browser must not
 * re-implement (CLAUDE.md rule 8); coco_lab runs it at site build time,
 * and a worker result comes straight from coco_lab. Like Lab 1, the page
 * draws a bundle only when its content hash is one coco_lab produced or
 * validated (`requireLocValidated`).
 */

import { DTYPE_SIZE as V1_SIZE, HOST_LITTLE_ENDIAN, readArray } from '../bundle/arrays';
import { buildMap, checkProvenance, contentHash } from '../bundle/decode';
import { fail } from '../bundle/errors';
import { boundedGunzip } from '../bundle/gzip';
import {
  decodeUtf8, isInt, isList, isObj, isStr, JInt, JObject, parseJson, toPlain, type JNode,
} from '../bundle/json';
import type { MapLayer, Provenance } from '../bundle/model';

export const LOC_SCHEMA = 'coco_lab.loc_bundle';
export const LOC_MAJOR = 1;
export const MAX_MANIFEST_BYTES = 1024 * 1024;
export const MAX_ARRAY_BYTES = 256 * 1024 * 1024;
export const MAX_RUNS = 4;
export const MAX_ROWS = 200_000;

type LocDtype = 'u8' | 'i32' | 'f64' | 'f32';
const SIZE: Record<LocDtype, number> = { ...V1_SIZE, f32: 4 };

export const WORLD_COLUMNS = ['t', 'gt_x', 'gt_y', 'gt_yaw', 'odom_x', 'odom_y', 'odom_yaw',
  'cmd_v', 'cmd_w'] as const;
export const COMMON_COLUMNS = ['row', 't', 'est_x', 'est_y', 'est_yaw', 'cov_xx', 'cov_xy',
  'cov_yy', 'cov_yaw', 'err_xy', 'err_yaw'] as const;
export const FILTER_COLUMNS = {
  mcl: ['n_eff', 'resampled', 'injected', 'p_inject', 'w_avg', 'w_slow', 'w_fast', 'cluster_weight'],
  ekf: ['beams_used', 'beams_gated', 'nis'],
} as const;
const INT_COLUMNS = new Set(['row', 'resampled', 'injected', 'beams_used', 'beams_gated']);
export const PARTICLE_COLUMNS = ['x', 'y', 'yaw', 'w'] as const;

export type FilterKind = keyof typeof FILTER_COLUMNS;

export interface LocLidar {
  samples: number; angle_min: number; angle_max: number; range_min: number; range_max: number;
  mount: [number, number, number];
}

export interface LocScenario {
  start: [number, number, number];
  route: Array<[number, number]>;
  seed: number;
  noise: { odom_alphas: [number, number, number, number]; range_sigma: number };
  kidnap: { t: number; to: [number, number, number] } | null;
  dt: number; v_max: number; w_max: number; max_time: number;
  lidar: LocLidar;
}

export interface LocWorld {
  status: string;
  nRows: number;
  kidnapRow: number | null;
  t: Float64Array; gtX: Float64Array; gtY: Float64Array; gtYaw: Float64Array;
  odomX: Float64Array; odomY: Float64Array; odomYaw: Float64Array;
  cmdV: Float64Array; cmdW: Float64Array;
  updates: Int32Array;
  /** n_updates x n_beams, row-major; Infinity = no return */
  ranges: Float64Array;
  nBeams: number;
}

export interface LocSummary {
  n_updates: number;
  mean_err_xy: number | null; max_err_xy: number | null;
  final_err_xy: number | null; final_err_yaw: number | null;
  converged_s: number | null; kidnap_s: number | null;
  recovered: boolean | null; recovery_s: number | null;
  ok_xy: number; ok_yaw: number; ok_hold: number;
}

export interface LocParticles {
  offset: Int32Array; x: Float32Array; y: Float32Array; yaw: Float32Array; w: Float32Array;
}

export interface LocRun {
  id: string;
  kind: FilterKind;
  params: Record<string, unknown>;
  summary: LocSummary;
  cols: Record<string, Float64Array | Int32Array>;
  particles: LocParticles | null;
  n: number;
}

export interface DecodedLocBundle {
  version: string;
  contentHash: string;
  provenance: Provenance;
  map: MapLayer;
  scenario: LocScenario;
  world: LocWorld;
  runs: LocRun[];
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

export interface ParsedLocManifest { tree: JObject; compression: 'none' | 'gzip'; total: number }

export function parseLocManifest(bytes: Uint8Array): ParsedLocManifest {
  if (bytes.length > MAX_MANIFEST_BYTES) fail('bounds', `manifest exceeds ${MAX_MANIFEST_BYTES} bytes`);
  const tree = parseJson(decodeUtf8(bytes));
  if (!isObj(tree)) fail('structure', 'manifest must be an object');
  if (tree.get('schema') !== LOC_SCHEMA) fail('schema', `schema is not ${LOC_SCHEMA}`);
  const version = tree.get('version');
  const major = isStr(version) && /^\d+(\.\d+)?$/.test(version) ? Number(version.split('.')[0]) : NaN;
  if (!Number.isInteger(major)) fail('version', `bad version ${JSON.stringify(toPlain(version ?? null))}`);
  if (major !== LOC_MAJOR) {
    fail('version', `loc bundle major version ${major} is not supported (this reader speaks 1.x)`);
  }
  const kinds: Array<[string, (v: JNode | undefined) => boolean]> = [
    ['provenance', isObj], ['map', isObj], ['scenario', isObj], ['world', isObj], ['runs', isList],
    ['arrays', isList], ['encoding', isObj], ['content_hash', isStr],
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
    if (bl !== (a.get('count') as JInt).value * SIZE[a.get('dtype') as LocDtype]) {
      fail('table', `array ${a.get('name')}: byte_length disagrees with count x dtype`);
    }
    offset += bl;
  }
  if (offset > MAX_ARRAY_BYTES) fail('bounds', `arrays total ${offset} bytes`);
  return { tree, compression: compression as 'none' | 'gzip', total: offset };
}

export async function decodeLoc(parsed: ParsedLocManifest, raw: Uint8Array): Promise<DecodedLocBundle> {
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
  const take = (name: string, dtype: LocDtype) => {
    const a = table.get(name);
    if (!a) fail('table', `missing array ${name}`);
    if (a.get('dtype') !== dtype) fail('dtype', `array ${name} must be ${dtype}`);
    used.add(name);
    const off = (a.get('offset') as JInt).value;
    const count = (a.get('count') as JInt).value;
    return dtype === 'f32' ? readF32(raw, off, count) : readArray(raw, off, count, dtype);
  };
  used.add('map.occupancy');
  const map = await buildMap(tree.get('map') as JObject, table, raw,
    (name) => take(name, 'f64') as Float64Array);
  if (!map.geo) fail('map', 'a localisation map is placed (resolution and origin)');

  const scenario = toPlain(tree.get('scenario')!) as LocScenario;
  const lidar = scenario.lidar;
  if (!(lidar && Number.isInteger(lidar.samples) && lidar.samples >= 1 && lidar.samples <= 480)) {
    fail('structure', 'scenario.lidar.samples must be 1..480');
  }
  const wm = tree.get('world') as JObject;
  const nRows = wm.get('n_rows');
  if (!(isInt(nRows) && nRows.value > 0 && nRows.value <= MAX_ROWS)) fail('bounds', 'world.n_rows out of range');
  const n = (nRows as JInt).value;
  const col = (c: string) => {
    const v = take(`world.${c}`, 'f64') as Float64Array;
    if (v.length !== n) fail('structure', `world.${c} has ${v.length} rows, expected ${n}`);
    if (!v.every(Number.isFinite)) fail('structure', `world.${c} must be finite`);
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
  const ranges = take('world.ranges', 'f64') as Float64Array;
  if (ranges.length !== updates.length * lidar.samples) fail('structure', 'world.ranges is not n_updates x n_beams');
  if (ranges.some((v) => Number.isNaN(v) || v < 0)) fail('structure', 'ranges must be >= 0 or inf');
  const kr = wm.get('kidnap_row');
  const kidnapRow = kr === null || kr === undefined ? null : (isInt(kr) ? kr.value : NaN);
  if (kidnapRow !== null && !(kidnapRow > 0 && kidnapRow < n)) fail('structure', 'world.kidnap_row out of range');
  const status = wm.get('status');
  if (!(isStr(status) && ['route_done', 'timeout', 'stuck'].includes(status))) fail('structure', 'world.status');
  const world: LocWorld = {
    status: status as string, nRows: n, kidnapRow, t,
    gtX: col('gt_x'), gtY: col('gt_y'), gtYaw: col('gt_yaw'),
    odomX: col('odom_x'), odomY: col('odom_y'), odomYaw: col('odom_yaw'),
    cmdV: col('cmd_v'), cmdW: col('cmd_w'), updates, ranges, nBeams: lidar.samples,
  };

  const runsNode = tree.get('runs') as JNode[];
  if (runsNode.length < 1 || runsNode.length > MAX_RUNS) fail('structure', `1..${MAX_RUNS} runs`);
  const runs: LocRun[] = [];
  const ids = new Set<string>();
  for (const r of runsNode) {
    if (!isObj(r) || !isObj(r.get('header'))) fail('structure', 'bad run entry');
    const id = r.get('id');
    if (!(isStr(id) && /^[A-Za-z0-9_-]{1,32}$/.test(id)) || ids.has(id)) {
      fail('structure', 'run ids must be unique short words');
    }
    ids.add(id as string);
    const header = r.get('header') as JObject;
    if (header.get('schema') !== 'coco_lab.loc_trace' || !/^1\./.test(String(header.get('version')))) {
      fail('version', `run ${id}: not a loc_trace 1.x`);
    }
    const kind = header.get('filter');
    if (kind !== 'mcl' && kind !== 'ekf') fail('structure', `run ${id}: unknown filter`);
    const cols: Record<string, Float64Array | Int32Array> = {};
    for (const c of [...COMMON_COLUMNS, ...FILTER_COLUMNS[kind]]) {
      const v = take(`run.${id}.${c}`, INT_COLUMNS.has(c) ? 'i32' : 'f64') as Float64Array | Int32Array;
      if (v.length !== updates.length) fail('structure', `run ${id}: column ${c} length`);
      if (!INT_COLUMNS.has(c) && !(v as Float64Array).every(Number.isFinite)) {
        fail('structure', `run ${id}: column ${c} must be finite`);
      }
      cols[c] = v;
    }
    const rows = cols.row as Int32Array;
    if (rows.some((v, i) => v !== updates[i])) fail('structure', `run ${id}: rows are not the world's updates`);
    let particles: LocParticles | null = null;
    if (kind === 'mcl') {
      const offset = take(`run.${id}.particles.offset`, 'i32') as Int32Array;
      if (offset.length !== updates.length + 1 || offset[0] !== 0) fail('structure', `run ${id}: particle offsets`);
      for (let i = 1; i < offset.length; i++) if (offset[i] < offset[i - 1]) fail('structure', 'offsets decrease');
      const p = {
        offset, x: take(`run.${id}.particles.x`, 'f32') as Float32Array,
        y: take(`run.${id}.particles.y`, 'f32') as Float32Array,
        yaw: take(`run.${id}.particles.yaw`, 'f32') as Float32Array,
        w: take(`run.${id}.particles.w`, 'f32') as Float32Array,
      };
      const total = offset[offset.length - 1];
      for (const c of PARTICLE_COLUMNS) if (p[c].length !== total) fail('structure', `particles.${c} length`);
      particles = p;
    }
    runs.push({
      id: id as string, kind, params: toPlain(header.get('params') ?? null) as Record<string, unknown>,
      summary: toPlain(r.get('summary') ?? null) as LocSummary, cols, particles, n: updates.length,
    });
  }
  const extra = [...table.keys()].filter((k) => !used.has(k));
  if (extra.length) fail('table', `unexpected arrays ${extra.sort().join(', ')}`);
  const prov = tree.get('provenance') as JObject;
  checkProvenance(prov);
  if (prov.get('source_kind') !== 'sketch') fail('provenance', 'a localisation bundle is a sketch');
  return {
    version: tree.get('version') as string, contentHash: tree.get('content_hash') as string,
    provenance: toPlain(prov) as Provenance, map, scenario, world, runs,
  };
}

export async function loadLocBytes(manifest: Uint8Array, arraysFile: Uint8Array): Promise<DecodedLocBundle> {
  const parsed = parseLocManifest(manifest);
  const raw = parsed.compression === 'gzip'
    ? await boundedGunzip(arraysFile, parsed.total)
    : arraysFile.subarray(0, parsed.total + 1);
  return decodeLoc(parsed, raw);
}

/** Beam angles in the sensor frame: the LiDAR spec's even spacing. */
export function beamAngles(l: LocLidar): number[] {
  if (l.samples === 1) return [l.angle_min];
  const step = (l.angle_max - l.angle_min) / (l.samples - 1);
  return Array.from({ length: l.samples }, (_, i) => l.angle_min + i * step);
}

/** The index of the last update at or before world row `row`. */
export function updateAt(world: LocWorld, row: number): number {
  const u = world.updates;
  let lo = 0;
  let hi = u.length - 1;
  if (row < u[0]) return 0;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (u[mid] <= row) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}
