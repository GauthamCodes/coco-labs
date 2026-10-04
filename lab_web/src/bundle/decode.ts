// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The bundle 1.0 / 1.1 decoder: a port of `coco_lab/bundle.py`'s STRUCTURAL
 * checks, in Python's order, so a refused bundle gets the same class of
 * error on both sides (`test/invalid/index.json`).
 *
 * Ported (tier i): `parse_manifest`; `decode` up to building the bundle;
 * `_check_provenance`; `Trace.validate`; `_check_run` (including the
 * run-versus-header equality); the map's construction checks and its content
 * hash; `_check_recording`. Also, because a renderer indexes cells with
 * them: every event and the run's start and goal lie inside the map.
 *
 * NOT ported (tier ii, `_check_trace_on_graph`): start/goal free, the first
 * push is the start, relax/expand/parent order, the path moving only between
 * neighbours, the path cost recomputed. Those need the graph's neighbour and
 * cost functions -- algorithm code, which the browser must not re-implement
 * (CLAUDE.md rule 8). `coco_lab` itself checks them: at site build time
 * (`tools/build_catalog.py`) or in the Pyodide worker. The browser draws a
 * bundle only when its content hash is one `coco_lab` validated
 * (`requireValidated` in `load.ts`).
 */

import { columnBytes, DTYPE_SIZE, readArray, type Dtype } from './arrays';
import { canonicalJson } from './canonical';
import { fail } from './errors';
import {
  isInt, isList, isNum, isObj, isStr, JFloat, JInt, JObject, numeric, parseJson, decodeUtf8,
  pyEquals, toPlain, truthy, type JNode,
} from './json';
import {
  EVENT_KINDS, RECORDING_GROUPS, TRACE_COLUMNS, type ArrayEntry, type DecodedBundle, type Geo,
  type MapLayer, type Provenance, type Recording, type RecordingGroup, type RunBlock, type Trace,
  type TraceEvents, type TraceHeader, type TraceSummary,
} from './model';
import { pyFloatRepr } from './pyrepr';
import { concatBytes, sha256Hex } from './sha256';

export const SCHEMA = 'coco_lab.bundle';
export const MAJOR = 1n;
export const MAX_MANIFEST_BYTES = 1024 * 1024;
export const MAX_ARRAY_BYTES = 256 * 1024 * 1024;
export const MAX_EVENTS = 50_000_000;
export const MAX_SIDE = 16384;
export const MAX_CELLS = 16_000_000;
const SOURCE_KINDS = ['glass-box', 'recorded-run', 'sketch'];
const ALGORITHMS = ['bfs', 'dijkstra', 'astar', 'greedy', 'weighted_astar'];
const TIE_BREAKS = ['low_h', 'fifo'];
const GRAPH_KINDS = ['grid', 'heading_grid'];
const MODEL_KEYS: Record<string, string[]> = {
  grid: ['connectivity', 'diagonal_cost', 'corner_cutting', 'cost_weight', 'cost_scale', 'unknown'],
  heading_grid: ['turn_penalty', 'corner_cutting', 'unknown'],
};
const TRACE_DTYPES: Record<string, Dtype> = {
  kind: 'u8', row: 'i32', col: 'i32', sub: 'i32', g: 'f64', h: 'f64', f: 'f64',
  parent_row: 'i32', parent_col: 'i32', parent_sub: 'i32',
};
const MAP_ARRAYS: Record<string, Dtype> = { 'map.occupancy': 'u8', 'map.cost': 'f64' };

// -- Python's str() and int() on the version field --------------------------------

function pyStr(v: JNode | undefined): string {
  if (v === undefined) return '';
  if (typeof v === 'string') return v;
  if (v instanceof JInt) return v.lex;
  if (v instanceof JFloat) return pyFloatRepr(v.value);
  if (v === null) return 'None';
  if (v === true) return 'True';
  if (v === false) return 'False';
  return Array.isArray(v) ? '[...]' : '{...}';
}

/** Python `int(s)` for ASCII input (TS refuses non-ASCII digits: stricter). */
function pyInt(s: string | undefined): bigint | null {
  if (s === undefined) return null;
  const m = /^[ \t\n\r\f\v]*([+-]?[0-9](?:_?[0-9])*)[ \t\n\r\f\v]*$/.exec(s);
  return m ? BigInt(m[1].replaceAll('_', '')) : null;
}

// -- parse_manifest -------------------------------------------------------------

export interface ParsedManifest {
  tree: JObject;
  compression: 'none' | 'gzip';
  /** Sum of the table's byte lengths (what the arrays must total). */
  total: number;
}

export function parseManifest(bytes: Uint8Array): ParsedManifest {
  if (bytes.length > MAX_MANIFEST_BYTES) {
    fail('bounds', `manifest exceeds ${MAX_MANIFEST_BYTES} bytes`);
  }
  const tree = parseJson(decodeUtf8(bytes));
  if (!isObj(tree)) fail('structure', 'manifest must be an object');
  if (tree.get('schema') !== SCHEMA) fail('schema', `schema is not ${SCHEMA}`);
  const version = pyStr(tree.get('version'));
  const major = pyInt(version.split('.')[0]);
  if (major === null) fail('version', `bad bundle version ${JSON.stringify(version)}`);
  if (major !== MAJOR) {
    fail('version', `bundle major version ${major} is not supported (this reader speaks 1.x)`);
  }
  const kinds: Array<[string, (v: JNode | undefined) => boolean, string]> = [
    ['provenance', isObj, 'dict'], ['run', isObj, 'dict'], ['map', isObj, 'dict'],
    ['trace', isObj, 'dict'], ['arrays', isList, 'list'], ['encoding', isObj, 'dict'],
    ['content_hash', isStr, 'str'],
  ];
  for (const [key, ok, kind] of kinds) {
    if (!ok(tree.get(key))) fail('structure', `manifest.${key} must be a ${kind}`);
  }
  const enc = tree.get('encoding') as JObject;
  if (enc.get('byte_order') !== 'little') fail('structure', 'encoding.byte_order must be little');
  const compression = enc.get('compression');
  if (compression !== 'none' && compression !== 'gzip') {
    fail('structure', 'encoding.compression must be none or gzip');
  }
  let offset = 0n;
  for (const a of tree.get('arrays') as JNode[]) {
    if (!(isObj(a) && isStr(a.get('name')) && (a.get('dtype') as string) in DTYPE_SIZE &&
        isStr(a.get('dtype')))) {
      fail('table', 'bad array entry');
    }
    const name = a.get('name') as string;
    for (const key of ['count', 'offset', 'byte_length']) {
      const v = a.get(key);
      if (!(isInt(v) && v.big >= 0n)) fail('table', `array ${name}: ${key} must be an int >= 0`);
    }
    const off = (a.get('offset') as JInt).big;
    if (off !== offset) {
      fail('table', `array ${name}: offset ${off}, expected ${offset} (arrays are contiguous)`);
    }
    const size = BigInt(DTYPE_SIZE[a.get('dtype') as Dtype]);
    const bl = (a.get('byte_length') as JInt).big;
    if (bl !== (a.get('count') as JInt).big * size) {
      fail('table', `array ${name}: byte_length disagrees with count x dtype`);
    }
    offset += bl;
  }
  if (offset > BigInt(MAX_ARRAY_BYTES)) {
    fail('bounds', `arrays total ${offset} bytes, over ${MAX_ARRAY_BYTES}`);
  }
  return { tree, compression, total: Number(offset) };
}

// -- the content hash -------------------------------------------------------------

export async function contentHash(tree: JObject, raw: Uint8Array): Promise<string> {
  const prov = tree.get('provenance') as JObject;
  const m = tree.without('content_hash', 'encoding').with('provenance', prov.without('created_utc'));
  const text = new TextEncoder().encode(canonicalJson(m) + '\n');
  return 'sha256:' + await sha256Hex(concatBytes([text, raw]));
}

/** `LabMap.content_hash`, byte for byte (Python `repr` for the geo floats). */
export async function mapContentHash(m: {
  width: number; height: number; occupancy: Uint8Array; cost: Float64Array | null; geo: Geo | null;
}): Promise<string> {
  const enc = new TextEncoder();
  const parts: Uint8Array[] = [enc.encode(`coco_lab.map/1 ${m.width} ${m.height}\n`), m.occupancy];
  if (m.cost === null) parts.push(enc.encode('nocost\n'));
  else parts.push(enc.encode('cost\n'), columnBytes(m.cost));
  if (m.geo) {
    const g = m.geo;
    parts.push(enc.encode(`geo ${pyFloatRepr(g.resolution)} ${pyFloatRepr(g.origin[0])} ` +
      `${pyFloatRepr(g.origin[1])} ${g.frame || ''}\n`));
  } else {
    parts.push(enc.encode('nogeo\n'));
  }
  return 'sha256:' + await sha256Hex(concatBytes(parts));
}

// -- decode -------------------------------------------------------------------------

function recordingArrays(recording: JObject | null): Array<[RecordingGroup, string]> {
  if (recording === null) return [];
  const present = recording.get('groups');
  const out: Array<[RecordingGroup, string]> = [];
  for (const [g, cols] of Object.entries(RECORDING_GROUPS) as Array<[RecordingGroup, readonly string[]]>) {
    if (isObj(present) && present.has(g)) for (const c of cols) out.push([g, c]);
  }
  return out;
}

export interface DecodeOptions {
  /** Test hook: read every array through DataView (the big-endian path). */
  forceDataView?: boolean;
}

export async function decode(parsed: ParsedManifest, raw: Uint8Array,
  opts: DecodeOptions = {}): Promise<DecodedBundle> {
  const tree = parsed.tree;
  const entries = tree.get('arrays') as JObject[];
  const table = new Map<string, JObject>();
  for (const a of entries) table.set(a.get('name') as string, a); // Python dict: last wins
  const md = tree.get('map') as JObject;
  const expected = [...TRACE_COLUMNS.map((c) => `trace.${c}`), 'map.occupancy'];
  if (truthy(md.get('cost_layer'))) expected.push('map.cost');
  const recNode = tree.get('recording');
  const recording = recNode === undefined || recNode === null ? null : recNode;
  const version = pyStr(tree.get('version'));
  const minor = pyInt(version.split('.')[1]);
  if (minor === null) fail('version', `bad bundle version ${JSON.stringify(version)}`);
  if (recording !== null) {
    if (minor < 1n) fail('recording', 'a recording needs bundle version 1.1 or later');
    if (!(isObj(recording) && isObj(recording.get('groups')))) {
      fail('recording', 'recording.groups must be an object');
    }
    for (const [g, c] of recordingArrays(recording)) expected.push(`recording.${g}.${c}`);
  }
  const names = [...table.keys()];
  if (names.length !== expected.length || names.some((n, k) => n !== expected[k])) {
    fail('table', `arrays must be exactly ${JSON.stringify(expected)}, in order; got ${JSON.stringify(names)}`);
  }
  const total = entries.reduce((s, a) => s + (a.get('byte_length') as JInt).value, 0);
  if (raw.length !== total) {
    fail('length', `array data is ${raw.length} bytes, the manifest lists ${total} (truncated or padded)`);
  }
  const declared = tree.get('content_hash') as string;
  const actual = await contentHash(tree, raw);
  if (declared !== actual) fail('hash', `content_hash ${declared} does not match the content (${actual})`);

  const column = (name: string) => {
    const a = table.get(name)!;
    const want = name.startsWith('trace.') ? TRACE_DTYPES[name.slice(6)]
      : name.startsWith('recording.') ? 'f64' : MAP_ARRAYS[name];
    if (a.get('dtype') !== want) fail('dtype', `array ${name}: dtype ${a.get('dtype')}, expected ${want}`);
    return readArray(raw, (a.get('offset') as JInt).value, (a.get('count') as JInt).value, want,
      opts.forceDataView);
  };

  const counts = new Set(TRACE_COLUMNS.map((c) => (table.get(`trace.${c}`)!.get('count') as JInt).value));
  if (counts.size !== 1) fail('table', 'trace columns differ in length');
  const n = [...counts][0];
  if (n > MAX_EVENTS) fail('bounds', `more than ${MAX_EVENTS} events`);
  const ev = {} as Record<string, ReturnType<typeof readArray>>;
  for (const c of TRACE_COLUMNS) ev[c] = column(`trace.${c}`);
  const events = ev as unknown as TraceEvents;
  for (const c of ['g', 'h', 'f'] as const) {
    if (!events[c].every(Number.isFinite)) fail('nonfinite', `trace column ${c} holds a non-finite value`);
  }

  const map = await buildMap(md, table, raw, column);
  const tr = tree.get('trace') as JObject;
  const headerNode = tr.get('header');
  const summaryNode = tr.get('summary');
  if (!isObj(headerNode) || !isObj(summaryNode)) fail('trace_invariant', 'trace: missing header or summary');

  let streams: Recording['streams'] | null = null;
  if (recording !== null) {
    streams = {};
    for (const [g, c] of recordingArrays(recording as JObject)) {
      (streams[g] ??= {})[c] = column(`recording.${g}.${c}`) as Float64Array;
    }
  }

  // -- Bundle.validate(), in Python's order ------------------------------------------
  const provNode = tree.get('provenance') as JObject;
  checkProvenance(provNode);
  checkTrace(headerNode, summaryNode, events, n);
  const runNode = tree.get('run') as JObject;
  checkRun(runNode, headerNode);
  if (runNode.get('map_hash') !== map.contentHash) {
    fail('run_header', `run.map_hash is not the embedded map (${map.contentHash})`);
  }
  checkInBounds(runNode, events, n, map);
  const rec = recording === null ? null : checkRecording(recording as JObject, streams!, provNode);

  const arrays: ArrayEntry[] = entries.map((a) => ({
    name: a.get('name') as string, dtype: a.get('dtype') as Dtype,
    count: (a.get('count') as JInt).value, offset: (a.get('offset') as JInt).value,
    byteLength: (a.get('byte_length') as JInt).value,
  }));
  return {
    version, minor: Number(minor), contentHash: declared, compression: parsed.compression,
    provenance: toPlain(provNode) as Provenance,
    run: toPlain(runNode) as RunBlock,
    map,
    trace: {
      header: toPlain(headerNode) as TraceHeader, summary: toPlain(summaryNode) as TraceSummary,
      n, events,
    } satisfies Trace,
    recording: rec,
    arrays, manifest: tree, rawBytes: raw.length,
  };
}

export async function buildMap(md: JObject, table: Map<string, JObject>, raw: Uint8Array,
  column: (name: string) => ReturnType<typeof readArray>): Promise<MapLayer> {
  // Python evaluates LabMap's arguments first: the cost column (dtype), then geo
  const cost = table.has('map.cost') ? column('map.cost') as Float64Array : null;
  const geoNode = md.get('geo');
  let resolution: JNode | undefined;
  let origin: JNode[] | null = null;
  let frame: JNode | undefined;
  if (geoNode !== undefined && geoNode !== null) {
    if (!isObj(geoNode)) fail('map', 'map: geo must be an object');
    resolution = geoNode.get('resolution');
    const o = geoNode.get('origin');
    if (!truthy(o)) origin = [];
    else if (isList(o)) origin = o;
    else fail('map', 'map: geo.origin must be (x, y)');
    frame = geoNode.get('frame');
  }
  const w = md.get('width');
  const h = md.get('height');
  for (const [name, v] of [['width', w], ['height', h]] as const) {
    if (!(isInt(v) && v.big > 0n && v.big <= BigInt(MAX_SIDE))) {
      fail('map', `map: ${name} must be an int in 1..${MAX_SIDE}`);
    }
  }
  const width = (w as JInt).value;
  const height = (h as JInt).value;
  if (width * height > MAX_CELLS) fail('map', `map: ${width} x ${height} exceeds ${MAX_CELLS} cells`);
  const occEntry = table.get('map.occupancy')!;
  const occOff = (occEntry.get('offset') as JInt).value;
  const occ = raw.slice(occOff, occOff + (occEntry.get('byte_length') as JInt).value);
  if (occ.length !== width * height) {
    fail('map', `map: occupancy has ${occ.length} cells, expected ${width * height}`);
  }
  if (occ.some((v) => v > 2)) fail('map', 'map: occupancy values must be 0, 1 or 2');
  if (cost !== null) {
    if (cost.length !== width * height) fail('map', `map: cost has ${cost.length} cells`);
    if (!cost.every((c) => Number.isFinite(c) && c >= 0)) fail('map', 'map: cost must be finite and >= 0');
  }
  const resNone = resolution === undefined || resolution === null;
  if (resNone !== (origin === null)) fail('map', 'map: resolution and origin come together or not at all');
  let geo: Geo | null = null;
  if (!resNone) {
    if (!(isNum(resolution) && resolution.value > 0)) fail('map', 'map: resolution must be finite and > 0');
    if (origin!.length !== 2) fail('map', 'map: origin must be (x, y)');
    const [ox, oy] = origin!;
    if (!(isNum(ox) && isNum(oy))) fail('map', 'map: origin must be finite');
    geo = { resolution: (resolution as JInt | JFloat).value, origin: [ox.value, oy.value], frame: null };
  }
  if (frame !== undefined && frame !== null && !isStr(frame)) fail('map', 'map: frame must be a string');
  if (geo) geo.frame = (frame as string | null | undefined) ?? null;
  const id = md.has('id') ? md.get('id') : '';
  if (!isStr(id)) fail('map', 'map: id must be a string');
  const meta = md.get('meta');
  if (truthy(meta) && !isObj(meta)) fail('map', 'map: meta must be an object');
  if (occEntry.get('dtype') !== 'u8') fail('dtype', 'map.occupancy must be u8');
  const contentHash = await mapContentHash({ width, height, occupancy: occ, cost, geo });
  if (md.get('content_hash') !== contentHash) {
    fail('map_hash', 'map.content_hash does not match the embedded map');
  }
  return {
    id, width, height, occupancy: occ, cost, geo,
    meta: (isObj(meta) ? toPlain(meta) : {}) as Record<string, unknown>, contentHash,
  };
}

// -- _check_provenance ------------------------------------------------------------------

const STRPTIME = /^(\d{4})-(1[0-2]|0[1-9]|[1-9])-(3[01]|[12]\d|0[1-9]|[1-9]| [1-9])T(2[0-3]|[0-1]\d|\d):([0-5]\d|\d):([0-5]\d|\d)Z$/;

function validUtc(s: string): boolean {
  const m = STRPTIME.exec(s);
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3].trim())];
  const days = new Date(Date.UTC(y, mo, 0)).getUTCDate();
  return y >= 1 && d <= days;
}

export function checkProvenance(p: JObject): void {
  const kind = p.get('source_kind');
  if (!(isStr(kind) && SOURCE_KINDS.includes(kind))) {
    fail('provenance', `provenance.source_kind ${JSON.stringify(toPlain(kind ?? null))} not in ${SOURCE_KINDS}`);
  }
  for (const key of ['coco_lab_version', 'created_utc']) {
    const v = p.get(key);
    if (!(isStr(v) && v.length > 0)) fail('provenance', `provenance.${key} must be a non-empty string`);
  }
  if (!validUtc(p.get('created_utc') as string)) {
    fail('provenance', 'provenance.created_utc is not YYYY-MM-DDTHH:MM:SSZ');
  }
  const commit = p.get('git_commit') ?? null;
  if (commit !== null && !(isStr(commit) && /^[0-9a-f]{40}$/.test(commit))) {
    fail('provenance', 'provenance.git_commit is not a 40-hex SHA or null');
  }
  const dirty = p.get('git_dirty') ?? null;
  const dn = numeric(dirty);
  if (!(dirty === null || (dn !== undefined && (dn === 0 || dn === 1)))) {
    fail('provenance', 'provenance.git_dirty must be a bool or null');
  }
  if ((commit === null) !== (dirty === null)) {
    fail('provenance', 'git_commit and git_dirty are both known or both null');
  }
  const seed = p.get('seed') ?? null;
  if (seed !== null && !isInt(seed)) fail('provenance', 'provenance.seed must be an int or null');
  for (const key of ['episode_spec_hash', 'tool']) {
    const v = p.get(key) ?? null;
    if (v !== null && !isStr(v)) fail('provenance', `provenance.${key} must be a string or null`);
  }
  const bag = p.get('rosbag') ?? null;
  if (kind === 'recorded-run') {
    if (!isObj(bag)) fail('provenance', 'a recorded-run needs provenance.rosbag');
    const sha = bag.get('sha256');
    if (!(isStr(sha) && sha.length === 64)) fail('provenance', 'provenance.rosbag.sha256 must be 64 hex');
    const t0 = bag.get('sim_time_start');
    const t1 = bag.get('sim_time_end');
    if (!(isNum(t0) && isNum(t1) && t0.value <= t1.value)) {
      fail('provenance', 'provenance.rosbag sim_time_start <= sim_time_end, both finite');
    }
  } else if (bag !== null) {
    fail('provenance', `provenance.rosbag is only for a recorded-run, not ${kind}`);
  }
}

// -- Trace.validate ------------------------------------------------------------------------

function checkTrace(h: JObject, s: JObject, ev: TraceEvents, n: number): void {
  const bad = (msg: string): never => fail('trace_invariant', `trace: ${msg}`);
  if (h.get('schema') !== 'coco_lab.trace') bad('schema is not coco_lab.trace');
  const major = pyInt(pyStr(h.get('version') ?? '').split('.')[0]);
  if (major === null) bad('bad version');
  if (major !== 1n) bad(`trace major version ${major} is not supported`);
  const counts = [0, 0, 0, 0];
  for (let i = 0; i < n; i++) {
    const k = ev.kind[i];
    if (k >= EVENT_KINDS.length) bad('kind column has an unknown event code');
    counts[k]++;
  }
  const status = s.get('status');
  if (status !== 'found' && status !== 'no_path') bad(`status not in found/no_path`);
  for (const [k, field] of [[1, 'expansions'], [0, 'pushes'], [2, 'relaxes']] as const) {
    if (numeric(s.get(field)) !== counts[k]) bad(`summary ${field} but the events hold ${counts[k]}`);
  }
  if (status === 'found') {
    const steps = s.has('path_steps') ? numeric(s.get('path_steps')) : -1;
    if (steps === undefined) bad('path_steps must be a number when found');
    if (counts[3] !== steps! + 1) bad('path events != path_steps + 1');
    for (const field of ['path_cost', 'path_length']) {
      const v = numeric(s.get(field));
      if (v === undefined || !Number.isFinite(v)) bad(`${field} must be finite when found`);
    }
  } else {
    if (counts[3]) bad('a no_path trace has path events');
    for (const field of ['path_cost', 'path_length', 'path_steps']) {
      if ((s.get(field) ?? null) !== null) bad(`${field} must be null when no_path`);
    }
  }
}

// -- _check_run ------------------------------------------------------------------------------

function checkRun(run: JObject, header: JObject): void {
  for (const key of ['algorithm', 'heuristic', 'weight', 'tie_break', 'start', 'goal', 'graph', 'model', 'map_hash']) {
    if (!run.has(key)) fail('run', `run has no ${key}`);
  }
  const alg = run.get('algorithm');
  if (!(isStr(alg) && ALGORITHMS.includes(alg))) fail('run', 'run.algorithm unknown');
  const tb = run.get('tie_break');
  if (!(isStr(tb) && TIE_BREAKS.includes(tb))) fail('run', 'run.tie_break unknown');
  const w = run.get('weight');
  if (alg === 'weighted_astar') {
    if (!(isNum(w) && w.value >= 0)) fail('run', 'weighted_astar needs a finite weight >= 0');
  } else if (w !== null) {
    fail('run', 'weight is only for weighted_astar');
  }
  for (const key of ['start', 'goal']) {
    const cell = run.get(key);
    if (!(isList(cell) && cell.length === 2 && cell.every(isInt))) fail('run', `run.${key} must be [row, col]`);
  }
  const graph = run.get('graph');
  const model = run.get('model');
  const gk = isObj(graph) ? graph.get('kind') : undefined;
  if (!(isStr(gk) && GRAPH_KINDS.includes(gk))) fail('run', `run.graph.kind must be one of ${GRAPH_KINDS}`);
  if (!isObj(model)) fail('run', 'run.model must be an object');
  const extra = model.keys().filter((k) => !MODEL_KEYS[gk].includes(k));
  if (extra.length) fail('run', `run.model has unknown keys ${JSON.stringify(extra.sort())}`);
  for (const key of ['algorithm', 'heuristic', 'weight', 'tie_break', 'graph']) {
    if (!pyEquals(header.get(key) ?? null, run.get(key))) {
      fail('run_header', `run.${key} disagrees with the trace header`);
    }
  }
}

/** Not in tier (i), but a renderer needs it: every index it touches is in the map. */
function checkInBounds(run: JObject, ev: TraceEvents, n: number, m: MapLayer): void {
  for (const key of ['start', 'goal']) {
    const [r, c] = (run.get(key) as JInt[]).map((x) => x.value);
    if (!(r >= 0 && r < m.height && c >= 0 && c < m.width)) fail('run', `run.${key} is outside the map`);
  }
  for (let i = 0; i < n; i++) {
    const r = ev.row[i];
    const c = ev.col[i];
    if (!(r >= 0 && r < m.height && c >= 0 && c < m.width)) {
      fail('trace_invariant', `event ${i}: [${r}, ${c}] is outside the map`);
    }
  }
}

// -- _check_recording ----------------------------------------------------------------------------

function checkRecording(rec: JObject, streams: NonNullable<Recording['streams']>,
  prov: JObject): Recording {
  const bad = (msg: string): never => fail('recording', msg);
  if (prov.get('source_kind') !== 'recorded-run') bad('only a recorded-run bundle carries a recording');
  const keys = rec.keys();
  const want = ['groups', 'missing', 'run_id', 'meta'];
  if (keys.length !== want.length || !want.every((k) => rec.has(k))) {
    bad(`recording must have exactly the keys ${want}`);
  }
  const groups = rec.get('groups');
  const missing = rec.get('missing');
  if (!isObj(groups) || !isList(missing)) bad('recording.groups is an object, .missing a list');
  const g = groups as JObject;
  const miss = missing as JNode[];
  const known = Object.keys(RECORDING_GROUPS);
  if (!miss.every(isStr)) bad('recording.missing must list group names');
  const missNames = miss as string[];
  if ([...g.keys(), ...missNames].some((k) => !known.includes(k))) bad(`unknown recording groups; known: ${known}`);
  const union = new Set([...g.keys(), ...missNames]);
  if (g.keys().some((k) => missNames.includes(k)) || union.size !== known.length ||
      new Set(missNames).size !== missNames.length) {
    bad('every recording group is present or listed in recording.missing, exactly once');
  }
  const runId = rec.get('run_id');
  const meta = rec.get('meta');
  if (!(isStr(runId) && isObj(meta))) bad('recording.run_id is a string, .meta an object');
  const out: Recording['groups'] = {};
  for (const [name, info] of g.entries) {
    const count = isObj(info) ? info.get('count') : undefined;
    if (!(isObj(info) && isStr(info.get('frame')) && isStr(info.get('source')) && isInt(count))) {
      bad(`recording.groups.${name} needs frame, source (strings) and count (int)`);
    }
    const cols = streams[name as RecordingGroup]!;
    const c = (count as JInt).value;
    if (!Object.values(cols).every((v) => v.length === c)) bad(`stream ${name}: columns disagree with count ${c}`);
    for (const [col, v] of Object.entries(cols)) {
      if (!v.every(Number.isFinite)) bad(`stream ${name}.${col} holds a non-finite value`);
    }
    const t = cols.t;
    if (t) for (let k = 1; k < t.length; k++) if (t[k] < t[k - 1]) bad(`stream ${name}.t decreases`);
    const i = info as JObject;
    out[name as RecordingGroup] = { frame: i.get('frame') as string, source: i.get('source') as string, count: c };
  }
  return {
    groups: out, missing: missNames as RecordingGroup[], runId: runId as string,
    meta: toPlain(meta as JObject) as Record<string, unknown>, streams,
  };
}
