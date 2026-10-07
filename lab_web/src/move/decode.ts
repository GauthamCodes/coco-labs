// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 5's two bundle decoders, 1.0: a port of `coco_lab/movebundle.py`'s
 * STRUCTURAL checks (`parse_manifest`, `load_replan_bundle`,
 * `load_drive_bundle`, `validate_drive`), reusing bundle v1's JSON parser,
 * content hash and provenance check so the formats cannot disagree on
 * those.
 *
 * NOT ported: `run_replan` (D* Lite and the episode), `replay_replan`,
 * `replay_drive` and every metric. They are algorithm code, which the
 * browser must not re-implement (CLAUDE.md rule 8): coco_lab runs them at
 * site build time or in the worker, and the page draws a bundle only when
 * its content hash is one coco_lab produced or validated.
 */

import { readArray, type Dtype } from '../bundle/arrays';
import { checkProvenance, contentHash } from '../bundle/decode';
import { fail } from '../bundle/errors';
import { boundedGunzip } from '../bundle/gzip';
import {
  decodeUtf8, isInt, isList, isObj, isStr, JInt, JObject, parseJson, toPlain, type JNode,
} from '../bundle/json';
import type { Provenance } from '../bundle/model';

export const REPLAN_SCHEMA = 'coco_lab.replan_bundle';
export const DRIVE_SCHEMA = 'coco_lab.drive_bundle';
export const MOVE_MAJOR = 1;
export const MAX_MANIFEST_BYTES = 1024 * 1024;
export const MAX_ARRAY_BYTES = 256 * 1024 * 1024;
export const MAX_RUNS = 64;
/** coco_lab.dstarlite.EVENT_KINDS, in order: the codes in the trace's `kind` column. */
export const REPLAN_KINDS = ['expand', 'raise', 'update', 'change', 'path', 'move'] as const;
export const CONTROLLERS = ['DWB', 'MPPI', 'RPP'] as const;
export const OUTCOMES = ['succeeded', 'follow_failed', 'failed', 'error'] as const;
/** -1 in a g / rhs column means infinity (costs are never negative). */
export const INF_SENTINEL = -1;

const SIZE: Record<Dtype, number> = { u8: 1, i32: 4, f64: 8 };

export interface ParsedMoveManifest { tree: JObject; compression: 'none' | 'gzip'; total: number }

export function parseMoveManifest(bytes: Uint8Array, schema: string): ParsedMoveManifest {
  if (bytes.length > MAX_MANIFEST_BYTES) fail('bounds', `manifest exceeds ${MAX_MANIFEST_BYTES} bytes`);
  const tree = parseJson(decodeUtf8(bytes));
  if (!isObj(tree)) fail('structure', 'manifest must be an object');
  if (tree.get('schema') !== schema) fail('schema', `schema is not ${schema}`);
  const version = tree.get('version');
  const major = isStr(version) && /^\d+(\.\d+)?$/.test(version) ? Number(version.split('.')[0]) : NaN;
  if (!Number.isInteger(major)) fail('version', `bad version ${JSON.stringify(toPlain(version ?? null))}`);
  if (major !== MOVE_MAJOR) fail('version', `major version ${major} is not supported (this reader speaks 1.x)`);
  const kinds: Array<[string, (v: JNode | undefined) => boolean]> = [
    ['provenance', isObj], ['arrays', isList], ['encoding', isObj], ['content_hash', isStr],
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

type Taker = {
  <D extends Dtype>(name: string, dtype: D): D extends 'u8' ? Uint8Array : D extends 'i32' ? Int32Array : Float64Array;
  has(name: string): boolean;
  done(): void;
};

async function open(parsed: ParsedMoveManifest, raw: Uint8Array): Promise<Taker> {
  const { tree } = parsed;
  if (raw.length !== parsed.total) fail('length', 'array bytes do not match the table');
  if (tree.get('content_hash') !== await contentHash(tree, raw)) fail('hash', 'content_hash does not match the content');
  const table = new Map<string, JObject>();
  for (const a of tree.get('arrays') as JObject[]) {
    const name = a.get('name') as string;
    if (table.has(name)) fail('table', `duplicate array ${name}`);
    table.set(name, a);
  }
  const used = new Set<string>();
  const take = ((name: string, dtype: Dtype) => {
    const a = table.get(name);
    if (!a) fail('table', `missing array ${name}`);
    if (a.get('dtype') !== dtype) fail('dtype', `array ${name} must be ${dtype}`);
    used.add(name);
    return readArray(raw, (a.get('offset') as JInt).value, (a.get('count') as JInt).value, dtype);
  }) as Taker;
  take.has = (name) => table.has(name);
  take.done = () => {
    const extra = [...table.keys()].filter((k) => !used.has(k));
    if (extra.length) fail('table', `unexpected arrays ${extra.sort().slice(0, 5).join(', ')}`);
  };
  return take;
}

const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const allFinite = (a: Float64Array) => a.every((v) => Number.isFinite(v));

async function bytesOf(parsed: ParsedMoveManifest, arraysFile: Uint8Array): Promise<Uint8Array> {
  return parsed.compression === 'gzip' ? boundedGunzip(arraysFile, parsed.total)
    : arraysFile.subarray(0, parsed.total + 1);
}

// -- replan bundle ---------------------------------------------------------------

export interface ReplanWorldInfo {
  width: number; height: number; start: [number, number]; goal: [number, number];
  sense_radius: number | null; connectivity: number; heuristic: string; has_cost: boolean;
  has_truth_cost?: boolean; first_sense_step?: number;
  schedule: Array<[number, Array<[number, number, boolean]>]>; max_steps: number;
}

export interface ReplanRound {
  step: number; robot: [number, number]; changed: Array<[number, number]>; found: boolean;
  cost: number | null; path_offset: number; path_len: number;
  dstar_expansions: number; dstar_reexpansions: number; astar_expansions: number; astar_cost: number | null;
}

export interface ReplanSummary {
  status: 'reached' | 'no_path' | 'step_limit'; steps: number; replans: number;
  dstar_expansions: number; astar_expansions: number; reexpansions: number;
  first_cost: number | null; walked_length: number; costs_agree: boolean;
}

export interface DecodedReplanBundle {
  version: string;
  contentHash: string;
  provenance: Provenance;
  world: ReplanWorldInfo;
  status: ReplanSummary['status'];
  summary: ReplanSummary;
  rounds: ReplanRound[];
  known: Uint8Array;
  truth: Uint8Array;
  knownFinal: Uint8Array;
  cost: Float64Array | null;
  /** the world's cost layer where it differs from the map's (Experiment C) */
  truthCost: Float64Array | null;
  /** the robot's cells, row, col interleaved */
  walk: Int32Array;
  /** every round's path, row, col interleaved, at its round's path_offset */
  paths: Int32Array;
  trace: { kind: Int32Array; row: Int32Array; col: Int32Array; sub: Int32Array; g: Float64Array;
    rhs: Float64Array; round: Int32Array; n: number };
}

export async function decodeReplan(parsed: ParsedMoveManifest, raw: Uint8Array): Promise<DecodedReplanBundle> {
  const { tree } = parsed;
  const take = await open(parsed, raw);
  const world = toPlain(tree.get('world') ?? null) as unknown as ReplanWorldInfo;
  if (!(world && Number.isInteger(world.width) && Number.isInteger(world.height)
    && world.width >= 1 && world.height >= 1 && world.width <= 512 && world.height <= 512)) {
    fail('structure', 'world: width and height');
  }
  const n = world.width * world.height;
  const inside = (c: unknown) => Array.isArray(c) && c.length === 2 && Number.isInteger(c[0]) && Number.isInteger(c[1])
    && c[0] >= 0 && c[0] < world.height && c[1] >= 0 && c[1] < world.width;
  if (!inside(world.start) || !inside(world.goal)) fail('structure', 'world: start and goal');
  const known = take('known', 'u8');
  const truth = take('truth', 'u8');
  const knownFinal = take('known_final', 'u8');
  if (known.length !== n || truth.length !== n || knownFinal.length !== n) fail('structure', 'maps must cover the grid');
  if (![known, truth, knownFinal].every((m) => m.every((v) => v === 0 || v === 1))) fail('structure', 'maps are 0 or 1');
  const cost = world.has_cost ? take('cost', 'f64') : null;
  if (cost && (cost.length !== n || !cost.every((c) => Number.isFinite(c) && c >= 0))) fail('structure', 'cost layer');
  const truthCost = world.has_truth_cost ? take('truth_cost', 'f64') : null;
  if (truthCost && (!cost || truthCost.length !== n || !truthCost.every((c) => Number.isFinite(c) && c >= 0))) {
    fail('structure', 'truth cost layer');
  }
  const walk = take('walk', 'i32');
  const paths = take('paths', 'i32');
  if (walk.length < 2 || walk.length % 2 || paths.length % 2) fail('structure', 'walk and paths are cell pairs');
  for (let i = 0; i < walk.length; i += 2) if (!inside([walk[i], walk[i + 1]])) fail('structure', 'walk leaves the grid');
  const trace = {
    kind: take('trace.kind', 'i32'), row: take('trace.row', 'i32'), col: take('trace.col', 'i32'),
    sub: take('trace.sub', 'i32'), g: take('trace.g', 'f64'), rhs: take('trace.rhs', 'f64'),
    round: take('trace.round', 'i32'), n: 0,
  };
  take.done();
  const nEvents = tree.get('n_events');
  if (!isInt(nEvents)) fail('structure', 'n_events');
  trace.n = nEvents.value;
  for (const col of [trace.kind, trace.row, trace.col, trace.sub, trace.g, trace.rhs, trace.round]) {
    if (col.length !== trace.n) fail('structure', 'trace columns must have n_events rows');
  }
  for (let e = 0; e < trace.n; e++) {
    if (!(trace.kind[e] >= 0 && trace.kind[e] < REPLAN_KINDS.length)) fail('structure', 'trace kind out of range');
    for (const v of [trace.g[e], trace.rhs[e]]) {
      if (!(Number.isFinite(v) && (v >= 0 || v === INF_SENTINEL))) fail('structure', 'g and rhs are >= 0 or -1');
    }
    if (e > 0 && trace.round[e] < trace.round[e - 1]) fail('structure', 'trace rounds go backwards');
  }
  const rounds = toPlain(tree.get('rounds') ?? null) as unknown as ReplanRound[];
  if (!Array.isArray(rounds) || rounds.length < 1) fail('structure', 'rounds');
  let off = 0;
  for (const r of rounds) {
    if (r.path_offset !== off || !Number.isInteger(r.path_len) || r.path_len < 0) fail('structure', 'round path offsets');
    if (!(r.found ? num(r.cost) : r.cost === null)) fail('structure', 'a round has a cost iff it found a path');
    off += r.path_len;
  }
  if (off * 2 !== paths.length) fail('structure', 'paths length disagrees with the rounds');
  const summary = toPlain(tree.get('summary') ?? null) as unknown as ReplanSummary;
  const status = toPlain(tree.get('status') ?? null);
  if (!(summary && ['reached', 'no_path', 'step_limit'].includes(String(status)) && summary.status === status)) {
    fail('structure', 'status');
  }
  const prov = tree.get('provenance') as JObject;
  checkProvenance(prov);
  const kind = prov.get('source_kind');
  if (kind !== 'sketch' && kind !== 'glass-box') fail('provenance', 'a replan bundle is a sketch or glass-box');
  return {
    version: tree.get('version') as string, contentHash: tree.get('content_hash') as string,
    provenance: toPlain(prov) as Provenance, world, status: status as ReplanSummary['status'], summary, rounds,
    known, truth, knownFinal, cost, truthCost, walk, paths, trace,
  };
}

export async function loadReplanBytes(manifest: Uint8Array, arraysFile: Uint8Array): Promise<DecodedReplanBundle> {
  const parsed = parseMoveManifest(manifest, REPLAN_SCHEMA);
  return decodeReplan(parsed, await bytesOf(parsed, arraysFile));
}

// -- drive bundle ------------------------------------------------------------------

export interface DriveMetrics {
  tracking_m: { n: number; mean: number | null; p95: number | null; max: number | null };
  time_s: number;
  smoothness: { n: number; rms_linear_accel: number | null; rms_angular_accel: number | null; skipped_pairs: number };
  clearance: {
    min_m: number | null; contact: boolean;
    static: { min_m: number | null; t: number | null; index: number | null };
    actor: { min_m: number | null; t: number | null; index: number | null };
  };
  samples: { gt: number; cmd: number };
}

export interface Rollouts {
  t: Float64Array; n: Int32Array; coff: Int32Array; poff: Int32Array; pts: Float64Array;
  flags: Uint8Array; total: Float64Array;
}

export interface DriveRun {
  id: string;
  controller: (typeof CONTROLLERS)[number];
  outcome: (typeof OUTCOMES)[number];
  window: [number, number];
  record: Record<string, unknown>;
  metrics: DriveMetrics;
  monitor: Array<[number, number, string]>;
  actorTrigger: Record<string, number>;
  /** t, x, y, yaw rows (map frame, sim time) */
  gt: Float64Array; amcl: Float64Array;
  /** t, v, w rows: the controller's output, and what reached the wheels */
  cmd: Float64Array; wheel: Float64Array;
  actors: Record<string, Float64Array>;
  chosenT: Float64Array; chosenOff: Int32Array; chosenPts: Float64Array;
  /** t, n, n_valid rows (DWB only) */
  eval: Float64Array;
  rollouts: Rollouts | null;
}

export interface DriveScenario {
  id: string; title: string; path: Float64Array; path_sha256: string;
  start: number[]; goal: number[]; boxes: number[][]; actor_radius: number;
  actors_spec: unknown[]; inject: Record<string, number> | null;
  [extra: string]: unknown;
}

export interface DecodedDriveBundle {
  version: string;
  contentHash: string;
  provenance: Provenance;
  scenario: DriveScenario;
  runs: DriveRun[];
}

const okWord = (id: unknown): id is string => typeof id === 'string' && /^[A-Za-z0-9_-]{1,48}$/.test(id);
const WIDTH: Record<string, number> = { gt: 4, amcl: 4, cmd: 3, wheel: 3 };

export async function decodeDrive(parsed: ParsedMoveManifest, raw: Uint8Array): Promise<DecodedDriveBundle> {
  const { tree } = parsed;
  const take = await open(parsed, raw);
  const sc = toPlain(tree.get('scenario') ?? null) as Record<string, unknown> | null;
  const runsNode = tree.get('runs');
  if (!sc || typeof sc !== 'object' || !isList(runsNode)) fail('structure', 'manifest.scenario / runs missing');
  const path = take('path', 'f64');
  if (path.length % 3 || path.length / 3 !== sc.path_len || path.length < 6 || !allFinite(path)) {
    fail('structure', 'path');
  }
  const { path_len: _pl, ...rest } = sc;
  void _pl;
  const scenario = { ...rest, path } as unknown as DriveScenario;
  if (runsNode.length < 1 || runsNode.length > MAX_RUNS) fail('structure', `1..${MAX_RUNS} runs`);
  const ids = new Set<string>();
  const runs: DriveRun[] = [];
  for (const node of runsNode) {
    if (!isObj(node)) fail('structure', 'bad run entry');
    const b = toPlain(node) as Record<string, any>;
    const id = b.id;
    if (!okWord(id) || ids.has(id)) fail('structure', 'run ids must be unique short words');
    ids.add(id);
    if (!CONTROLLERS.includes(b.controller)) fail('structure', `run ${id}: controller`);
    if (!OUTCOMES.includes(b.outcome)) fail('structure', `run ${id}: outcome`);
    const w = b.window;
    if (!(Array.isArray(w) && w.length === 2 && num(w[0]) && num(w[1]) && w[0] <= w[1])) fail('structure', `run ${id}: window`);
    const series: Record<string, Float64Array> = {};
    for (const [name, width] of Object.entries(WIDTH)) {
      const a = take(`run.${id}.${name}`, 'f64');
      if (a.length % width || a.length / width !== b.n?.[name] || !allFinite(a)) fail('structure', `run ${id}: ${name}`);
      for (let i = width; i < a.length; i += width) {
        if (a[i] < a[i - width]) fail('structure', `run ${id}: ${name} goes back in time`);
      }
      series[name] = a;
    }
    const actors: Record<string, Float64Array> = {};
    for (const aid of (b.actors ?? []) as string[]) {
      const a = take(`run.${id}.actor.${aid}`, 'f64');
      if (a.length % 4 || !allFinite(a)) fail('structure', `run ${id}: actor ${aid}`);
      actors[aid] = a;
    }
    const chosenT = take(`run.${id}.chosen.t`, 'f64');
    const chosenOff = take(`run.${id}.chosen.off`, 'i32');
    const chosenPts = take(`run.${id}.chosen.pts`, 'f64');
    if (chosenOff.length !== chosenT.length + 1 || chosenOff[0] !== 0 || chosenOff[chosenOff.length - 1] * 2 !== chosenPts.length) {
      fail('structure', `run ${id}: chosen offsets`);
    }
    for (let i = 1; i < chosenOff.length; i++) if (chosenOff[i] < chosenOff[i - 1]) fail('structure', `run ${id}: chosen offsets`);
    const ev = take(`run.${id}.eval`, 'f64');
    if (ev.length % 3) fail('structure', `run ${id}: eval`);
    let rollouts: Rollouts | null = null;
    if (b.has_rollouts) {
      rollouts = {
        t: take(`run.${id}.roll.t`, 'f64'), n: take(`run.${id}.roll.n`, 'i32'),
        coff: take(`run.${id}.roll.coff`, 'i32'), poff: take(`run.${id}.roll.poff`, 'i32'),
        pts: take(`run.${id}.roll.pts`, 'f64'), flags: take(`run.${id}.roll.flags`, 'u8'),
        total: take(`run.${id}.roll.total`, 'f64'),
      };
      const nf = rollouts.t.length;
      const nc = rollouts.flags.length;
      if (rollouts.n.length !== 2 * nf || rollouts.coff.length !== nf + 1 || rollouts.coff[nf] !== nc
        || rollouts.poff.length !== nc + 1 || rollouts.poff[nc] * 2 !== rollouts.pts.length || rollouts.total.length !== nc) {
        fail('structure', `run ${id}: rollout tables`);
      }
    }
    runs.push({
      id, controller: b.controller, outcome: b.outcome, window: [w[0], w[1]], record: b.record ?? {},
      metrics: b.metrics, monitor: b.monitor ?? [], actorTrigger: b.actor_trigger ?? {},
      gt: series.gt, amcl: series.amcl, cmd: series.cmd, wheel: series.wheel, actors,
      chosenT, chosenOff, chosenPts, eval: ev, rollouts,
    });
  }
  take.done();
  const prov = tree.get('provenance') as JObject;
  checkProvenance(prov);
  if (prov.get('source_kind') !== 'recorded-run') fail('provenance', 'a drive bundle is a recorded-run bundle');
  return {
    version: tree.get('version') as string, contentHash: tree.get('content_hash') as string,
    provenance: toPlain(prov) as Provenance, scenario, runs,
  };
}

export async function loadDriveBytes(manifest: Uint8Array, arraysFile: Uint8Array): Promise<DecodedDriveBundle> {
  const parsed = parseMoveManifest(manifest, DRIVE_SCHEMA);
  return decodeDrive(parsed, await bytesOf(parsed, arraysFile));
}
