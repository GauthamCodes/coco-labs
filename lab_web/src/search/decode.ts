// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The search bundle 1.0 decoder: a port of `coco_lab/searchbundle.py`'s
 * STRUCTURAL checks (`parse_manifest`, `decode`, `SearchBundle.validate`,
 * `SearchTrace.validate`), reusing bundle v1's JSON, content hash and
 * provenance code so the formats cannot disagree on those.
 *
 * NOT ported: `replay_check`, Bayes' rule, the expected-cost search and
 * every policy. They are search code, which the browser must not
 * re-implement (CLAUDE.md rule 8); coco_lab runs them at site build time
 * or in the worker, and the page draws a bundle only when its content
 * hash is one coco_lab produced or validated.
 */

import { readArray } from '../bundle/arrays';
import { checkProvenance, contentHash } from '../bundle/decode';
import { fail } from '../bundle/errors';
import { boundedGunzip } from '../bundle/gzip';
import {
  decodeUtf8, isInt, isList, isObj, isStr, JInt, JObject, parseJson, toPlain, type JNode,
} from '../bundle/json';
import type { Provenance } from '../bundle/model';

export const SEARCH_SCHEMA = 'coco_lab.search_bundle';
export const SEARCH_MAJOR = 1;
export const MAX_MANIFEST_BYTES = 1024 * 1024;
export const MAX_ARRAY_BYTES = 256 * 1024 * 1024;
export const MAX_RUNS = 32;
export const MAX_REGIONS = 8;
export const MAX_TIMELINE = 4096;
/** coco_lab.regionsearch.KINDS, in order: the codes in a run's `kind` column. */
export const EVENT_KINDS = ['select', 'survey', 'mark', 'discover', 'exhausted', 'stopped'] as const;
export type EventKind = (typeof EVENT_KINDS)[number];
export const POLICIES = ['expected_cost', 'nearest', 'most_likely', 'given'] as const;
export type Policy = (typeof POLICIES)[number];

type Dtype = 'u8' | 'i32' | 'f64';
const SIZE: Record<Dtype, number> = { u8: 1, i32: 4, f64: 8 };

export interface Region {
  id: string; label: string;
  approach: [number, number];
  platform: [number, number, number, number];
  survey_pose: [number, number, number];
  exit: [number, number];
  survey_cost: number;
}

export interface Problem {
  regions: Region[];
  start: string;
  start_xy: [number, number];
  travel: Record<string, Record<string, number>>;
  detection: number[];
  prior: number[];
  meta: Record<string, unknown>;
}

export interface SearchSummary {
  status: 'discovered' | 'exhausted' | 'stopped';
  order: string[];
  surveys: number;
  discovered: string | null;
  discovered_at: number | null;
  cost: number;
  truth: string | null;
  model_contradicted: boolean;
}

export interface SearchRun {
  id: string;
  kind: 'sketch' | 'recorded';
  header: Record<string, unknown>;
  summary: SearchSummary;
  n: number;
  /** per event: index into EVENT_KINDS */
  kinds: Int32Array;
  region: Int32Array;
  outcome: Int32Array;
  cost: Float64Array;
  /** n x n_regions, the belief AFTER each event */
  belief: Float64Array;
  /** n x n_regions, candidate expected costs at a select (NaN elsewhere) */
  candidates: Float64Array;
  /** recorded only: simulator seconds per event (NaN if unknown) */
  t: Float64Array | null;
  timeline: Array<[number, string, string | null]>;
  record: Record<string, unknown> | null;
  evaluator: Record<string, unknown> | null;
}

export interface DecodedSearchBundle {
  version: string;
  contentHash: string;
  provenance: Provenance;
  problem: Problem;
  runs: SearchRun[];
}

export interface ParsedSearchManifest { tree: JObject; compression: 'none' | 'gzip'; total: number }

export function parseSearchManifest(bytes: Uint8Array): ParsedSearchManifest {
  if (bytes.length > MAX_MANIFEST_BYTES) fail('bounds', `manifest exceeds ${MAX_MANIFEST_BYTES} bytes`);
  const tree = parseJson(decodeUtf8(bytes));
  if (!isObj(tree)) fail('structure', 'manifest must be an object');
  if (tree.get('schema') !== SEARCH_SCHEMA) fail('schema', `schema is not ${SEARCH_SCHEMA}`);
  const version = tree.get('version');
  const major = isStr(version) && /^\d+(\.\d+)?$/.test(version) ? Number(version.split('.')[0]) : NaN;
  if (!Number.isInteger(major)) fail('version', `bad version ${JSON.stringify(toPlain(version ?? null))}`);
  if (major !== SEARCH_MAJOR) {
    fail('version', `search bundle major version ${major} is not supported (this reader speaks 1.x)`);
  }
  const kinds: Array<[string, (v: JNode | undefined) => boolean]> = [
    ['provenance', isObj], ['problem', isObj], ['runs', isList], ['arrays', isList],
    ['encoding', isObj], ['content_hash', isStr],
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

const okWord = (id: unknown): id is string => typeof id === 'string' && /^[A-Za-z0-9_-]{1,32}$/.test(id);
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const pair = (v: unknown) => Array.isArray(v) && v.length === 2 && v.every(num);

function checkProblem(p: Problem): void {
  const n = p.regions?.length ?? 0;
  if (!(n >= 1 && n <= MAX_REGIONS)) fail('structure', `1..${MAX_REGIONS} regions`);
  const ids = p.regions.map((r) => r.id);
  if (new Set(ids).size !== n || !ids.every(okWord)) fail('structure', 'region ids must be unique short words');
  if (!okWord(p.start) || ids.includes(p.start)) fail('structure', 'start must be a word that is not a region');
  if (!pair(p.start_xy)) fail('structure', 'start_xy');
  for (const r of p.regions) {
    if (!(pair(r.approach) && pair(r.exit) && Array.isArray(r.platform) && r.platform.length === 4
      && r.platform.every(num) && r.platform[0] <= r.platform[1] && r.platform[2] <= r.platform[3]
      && Array.isArray(r.survey_pose) && r.survey_pose.length === 3 && r.survey_pose.every(num)
      && num(r.survey_cost) && r.survey_cost >= 0 && typeof r.label === 'string')) {
      fail('structure', `region ${r.id}`);
    }
  }
  const locations = [p.start, ...ids];
  if (Object.keys(p.travel ?? {}).sort().join() !== [...locations].sort().join()) {
    fail('structure', 'travel must have a row per location');
  }
  for (const a of locations) {
    const row = p.travel[a];
    if (Object.keys(row).sort().join() !== [...ids].sort().join()) fail('structure', `travel[${a}]`);
    if (!Object.values(row).every((c) => num(c) && c >= 0)) fail('structure', `travel[${a}] costs`);
  }
  if (!(p.detection?.length === n && p.detection.every((d) => num(d) && d > 0 && d <= 1))) {
    fail('structure', 'detection');
  }
  checkBelief(p.prior, n, 'prior');
}

function checkBelief(b: ArrayLike<number>, n: number, what: string): void {
  if (b.length !== n) fail('structure', `${what} has ${b.length} entries, not ${n}`);
  let s = 0;
  for (let i = 0; i < n; i++) {
    if (!(Number.isFinite(b[i]) && b[i] >= 0 && b[i] <= 1)) fail('structure', `${what} entries must be in [0, 1]`);
    s += b[i];
  }
  if (Math.abs(s - 1) > 1e-9) fail('structure', `${what} must sum to 1`);
}

export async function decodeSearch(parsed: ParsedSearchManifest, raw: Uint8Array): Promise<DecodedSearchBundle> {
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
  const take = (name: string, dtype: Dtype) => {
    const a = table.get(name);
    if (!a) fail('table', `missing array ${name}`);
    if (a.get('dtype') !== dtype) fail('dtype', `array ${name} must be ${dtype}`);
    used.add(name);
    return readArray(raw, (a.get('offset') as JInt).value, (a.get('count') as JInt).value, dtype as 'i32' | 'f64');
  };
  const problem = toPlain(tree.get('problem')!) as unknown as Problem;
  checkProblem(problem);
  const nReg = problem.regions.length;

  const runsNode = tree.get('runs') as JNode[];
  if (runsNode.length < 1 || runsNode.length > MAX_RUNS) fail('structure', `1..${MAX_RUNS} runs`);
  const ids = new Set<string>();
  const runs: SearchRun[] = [];
  for (const r of runsNode) {
    if (!(isObj(r) && isObj(r.get('header')))) fail('structure', 'bad run entry');
    const id = toPlain(r.get('id') ?? null);
    const kind = toPlain(r.get('kind') ?? null);
    if (!okWord(id) || ids.has(id)) fail('structure', 'run ids must be unique short words');
    if (kind !== 'sketch' && kind !== 'recorded') fail('structure', `run ${id}: kind`);
    ids.add(id);
    const kinds = take(`run.${id}.kind`, 'i32') as Int32Array;
    const region = take(`run.${id}.region`, 'i32') as Int32Array;
    const outcome = take(`run.${id}.outcome`, 'i32') as Int32Array;
    const cost = take(`run.${id}.cost`, 'f64') as Float64Array;
    const belief = take(`run.${id}.belief`, 'f64') as Float64Array;
    const candidates = take(`run.${id}.candidates`, 'f64') as Float64Array;
    const n = kinds.length;
    const nEvents = r.get('n_events');
    if (!(isInt(nEvents) && nEvents.value === n)) fail('structure', `run ${id}: n_events disagrees`);
    if (region.length !== n || outcome.length !== n || cost.length !== n) fail('structure', `run ${id}: column lengths`);
    if (belief.length !== n * nReg || candidates.length !== n * nReg) {
      fail('structure', `run ${id}: belief/candidates must be n_events x n_regions`);
    }
    for (let e = 0; e < n; e++) {
      if (!(kinds[e] >= 0 && kinds[e] < EVENT_KINDS.length)) fail('structure', `run ${id}: kind out of range`);
      if (!(region[e] >= -1 && region[e] < nReg)) fail('structure', `run ${id}: region out of range`);
      if (!(outcome[e] >= -1 && outcome[e] <= 1)) fail('structure', `run ${id}: outcome must be -1, 0 or 1`);
      if (!Number.isFinite(cost[e]) || (e > 0 && cost[e] < cost[e - 1] - 1e-12)) {
        fail('structure', `run ${id}: cost must be finite and not decrease`);
      }
      checkBelief(belief.subarray(e * nReg, (e + 1) * nReg), nReg, `run ${id} belief`);
    }
    const header = toPlain(r.get('header')!) as Record<string, unknown>;
    if (header.schema !== 'coco_lab.search_trace' || !/^1\./.test(String(header.version))) {
      fail('version', `run ${id}: not a search_trace 1.x`);
    }
    if (!POLICIES.includes(header.policy as Policy)) fail('structure', `run ${id}: unknown policy`);
    const summary = toPlain(r.get('summary') ?? null) as unknown as SearchSummary;
    if (!(summary && ['discovered', 'exhausted', 'stopped'].includes(summary.status) && Array.isArray(summary.order))) {
      fail('structure', `run ${id}: bad summary`);
    }
    let t: Float64Array | null = null;
    let timeline: SearchRun['timeline'] = [];
    let record: Record<string, unknown> | null = null;
    let evaluator: Record<string, unknown> | null = null;
    if (kind === 'recorded') {
      t = take(`run.${id}.t`, 'f64') as Float64Array;
      if (t.length !== n) fail('structure', `run ${id}: t must have one value per event`);
      timeline = toPlain(r.get('timeline') ?? null) as SearchRun['timeline'];
      if (!Array.isArray(timeline) || timeline.length > MAX_TIMELINE || !timeline.every((row) =>
        Array.isArray(row) && row.length === 3 && typeof row[0] === 'number' && typeof row[1] === 'string'
        && (row[2] === null || typeof row[2] === 'string'))) {
        fail('structure', `run ${id}: bad timeline`);
      }
      record = toPlain(r.get('record') ?? null) as Record<string, unknown>;
      evaluator = toPlain(r.get('evaluator') ?? null) as Record<string, unknown>;
    } else if (r.get('timeline') !== undefined) {
      fail('structure', `run ${id}: a sketch has no recording`);
    }
    runs.push({
      id, kind, header, summary, n, kinds, region, outcome, cost, belief, candidates,
      t, timeline, record, evaluator,
    });
  }
  const extra = [...table.keys()].filter((k) => !used.has(k));
  if (extra.length) fail('table', `unexpected arrays ${extra.sort().slice(0, 5).join(', ')}`);
  const prov = tree.get('provenance') as JObject;
  checkProvenance(prov);
  return {
    version: tree.get('version') as string, contentHash: tree.get('content_hash') as string,
    provenance: toPlain(prov) as Provenance, problem, runs,
  };
}

export async function loadSearchBytes(manifest: Uint8Array, arraysFile: Uint8Array): Promise<DecodedSearchBundle> {
  const parsed = parseSearchManifest(manifest);
  const raw = parsed.compression === 'gzip'
    ? await boundedGunzip(arraysFile, parsed.total)
    : arraysFile.subarray(0, parsed.total + 1);
  return decodeSearch(parsed, raw);
}
