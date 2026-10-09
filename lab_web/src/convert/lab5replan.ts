// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 5 replanning bundles (D* Lite) -> v2 runs (M2.7), and back.
 *
 * A replan bundle (coco_lab.movebundle, REPLAN_SCHEMA: a Sketch world or a
 * glass-box world built from two recorded Nav2 costmaps; coco_lab computed
 * the trace, so MODEL) becomes one v2 run:
 *
 *   spec               the bundle's manifest.json, byte for byte
 *   world.grid x 3     "known" (what the robot knew at the start, with the
 *                      `cost` layer), "truth" (with `truth_cost`),
 *                      "known_final"; the bundle's 0/1 cells verbatim in
 *                      `occupancy` (and `blocked`); costs are exact in f32
 *                      or the conversion is refused
 *   plan.search        the D* Lite trace: one header, every event with
 *                      its kind (EXPAND, RAISE, UPDATE, CHANGE, PATH, MOVE),
 *                      cell, g, rhs and replanning round
 *
 * The robot's walk and every round's path are NOT stored twice: the walk is
 * the start cell then every MOVE event's cell, the paths every PATH event's
 * cell in order (the converter refuses a bundle where that is not so).
 * `toLab5Replan` rebuilds every array from the channels and the v1 decoder
 * re-checks the content hash.
 */

import { create, fromBinary, toBinary } from '@bufbuild/protobuf';

import { encodeBatch } from '../schemas/columns';
import { ManifestSchema, Tier, EvidenceClass, type Manifest } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import { ParamsSchema } from '../schemas/gen/coco/common/v1/common_pb';
import { SearchEventBatchSchema, SearchEventKind, SearchHeaderSchema, SearchStatus, SearchSummarySchema } from '../schemas/gen/coco/plan/v1/search_pb';
import { WorldGridSchema } from '../schemas/gen/coco/world/v1/world_pb';
import { REPLAN_KINDS, REPLAN_SCHEMA, decodeReplan, parseMoveManifest, type DecodedReplanBundle } from '../move/decode';
import type { ReadMessage, RunRecord } from '../schemas/mcap';
import { runId, specSha256 } from '../schemas/runid';
import { rawFromColumns } from './raw';

export const REPLAN_SPEC_FORMAT = 'coco_lab.replan_bundle.v1+json';
export const CONVERTER = 'lab_web/src/convert/lab5replan.ts';
const PER_BATCH = 8192;
/** REPLAN_KINDS (coco_lab.dstarlite) <-> SearchEventKind, both ways. */
export const KIND: Record<(typeof REPLAN_KINDS)[number], SearchEventKind> = {
  expand: SearchEventKind.EXPAND, raise: SearchEventKind.RAISE, update: SearchEventKind.UPDATE,
  change: SearchEventKind.CHANGE, path: SearchEventKind.PATH, move: SearchEventKind.MOVE,
};
const GRIDS = [['known', 'known', 'cost'], ['truth', 'truth', 'truth_cost'], ['known_final', 'knownFinal', null]] as const;

export interface Converted { manifest: Manifest; records: RunRecord[] }

function f32Exact(a: Float64Array, what: string): number[] {
  const f = Float32Array.from(a);
  for (let i = 0; i < a.length; i += 1) {
    if (f[i] !== a[i] && !(Number.isNaN(f[i]) && Number.isNaN(a[i]))) throw new Error(`${what}[${i}] = ${a[i]} is not exact in f32`);
  }
  return Array.from(f);
}

export async function fromLab5Replan(b: DecodedReplanBundle, manifestBytes: Uint8Array): Promise<Converted> {
  const w = b.world;
  const tr = b.trace;
  const kinds = Array.from(tr.kind, (k) => REPLAN_KINDS[k]);
  // the walk and the paths are the MOVE and PATH events: refuse otherwise
  const moves = kinds.flatMap((k, i) => (k === 'move' ? [tr.row[i], tr.col[i]] : []));
  const walk = [w.start[0], w.start[1], ...moves];
  if (walk.length !== b.walk.length || walk.some((v, i) => v !== b.walk[i])) throw new Error('the walk is not the start then the MOVE events');
  const paths = kinds.flatMap((k, i) => (k === 'path' ? [tr.row[i], tr.col[i]] : []));
  if (paths.length !== b.paths.length || paths.some((v, i) => v !== b.paths[i])) throw new Error('the paths are not the PATH events');
  const spec = await specSha256(manifestBytes);
  const engines: [string, string][] = [['coco_lab', b.provenance.coco_lab_version], ['converter', `${CONVERTER} 1`]];
  const records: RunRecord[] = [];
  for (const [id, field, costName] of GRIDS) {
    const cells = b[field];
    const cost = costName === 'cost' ? b.cost : costName === 'truth_cost' ? b.truthCost : null;
    records.push({ channel: 'coco.world.grid.v1', schema: WorldGridSchema, tWorld: 0, seq: records.length, data: toBinary(WorldGridSchema,
      create(WorldGridSchema, { mapId: id, width: w.width, height: w.height, resolution: 0, originX: 0, originY: 0,
        blocked: cells.map((v) => (v === 1 ? 1 : 0)), occupancy: cells, cost: cost ? f32Exact(cost, costName!) : [],
        specSha256: spec, row0IsBottom: false })) });
  }
  const loc = (rc: [number, number]) => ({ row: rc[0], col: rc[1], sub: 0 });
  records.push({ channel: 'coco.plan.search.header.v1', schema: SearchHeaderSchema, tWorld: 0, seq: 0, data: toBinary(SearchHeaderSchema,
    create(SearchHeaderSchema, { searchId: 0n, sourceSchema: REPLAN_SCHEMA, sourceVersion: b.version, algorithm: 'dstar_lite',
      heuristic: w.heuristic, tieBreak: '', start: loc(w.start), goal: loc(w.goal), tick: 0n, tWorld: 0,
      graph: create(ParamsSchema, { items: [
        { key: 'connectivity', value: { value: { case: 'intValue' as const, value: BigInt(w.connectivity) } } },
        { key: 'width', value: { value: { case: 'intValue' as const, value: BigInt(w.width) } } },
        { key: 'height', value: { value: { case: 'intValue' as const, value: BigInt(w.height) } } },
      ] }) })) });
  for (let s = 0; s < tr.n; s += PER_BATCH) {
    const e = Math.min(tr.n, s + PER_BATCH);
    const n = e - s;
    records.push({ channel: 'coco.plan.search.events.v1', schema: SearchEventBatchSchema, tWorld: 0, seq: s,
      data: encodeBatch(SearchEventBatchSchema, {
        seq: Array.from({ length: n }, (_, i) => BigInt(s + i)), tick: Array.from(tr.round.subarray(s, e), (r) => BigInt(r)),
        t_world: new Array(n).fill(0), kind: kinds.slice(s, e).map((k) => KIND[k]), row: tr.row.subarray(s, e), col: tr.col.subarray(s, e),
        sub: tr.sub.subarray(s, e), g: tr.g.subarray(s, e), rhs: tr.rhs.subarray(s, e), round: tr.round.subarray(s, e),
      }, { search_id: 0n }) });
  }
  const sm = b.summary;
  records.push({ channel: 'coco.plan.search.summary.v1', schema: SearchSummarySchema, tWorld: 0, seq: 0, data: toBinary(SearchSummarySchema,
    create(SearchSummarySchema, { searchId: 0n, status: sm.status === 'reached' ? SearchStatus.FOUND : SearchStatus.NO_PATH,
      expansions: BigInt(sm.dstar_expansions), pushes: 0n, relaxes: 0n,
      ...(sm.first_cost != null ? { pathCost: sm.first_cost } : {}), pathLength: sm.walked_length })) });
  const channels = [...new Map(records.map((x) => [x.channel, x.schema.typeName])).entries()].map(([name, message]) => ({ name, message }));
  const manifest = create(ManifestSchema, {
    runId: await runId(manifestBytes, b.provenance.seed ?? 0, engines), specFormat: REPLAN_SPEC_FORMAT, spec: manifestBytes,
    specSha256: spec, seed: BigInt(b.provenance.seed ?? 0), tier: Tier.TRACE, evidenceClass: EvidenceClass.MODEL,
    engines: engines.map(([name, version]) => ({ name, version })), channels,
    provenance: { createdUtc: b.provenance.created_utc, tool: CONVERTER, gitSha: b.provenance.git_commit ?? '',
      gitDirty: b.provenance.git_dirty ?? false, source: `coco_lab.replan_bundle ${b.contentHash}`,
      note: `Lab 5 replanning (D* Lite), computed by coco_lab on a ${b.provenance.source_kind} world` },
    schemaPackageVersion: '1.0.0',
  });
  return { manifest, records };
}

export async function toLab5Replan(manifest: Manifest, messages: ReadMessage[]): Promise<DecodedReplanBundle> {
  if (manifest.specFormat !== REPLAN_SPEC_FORMAT) throw new Error(`not a converted Lab 5 replan: ${manifest.specFormat}`);
  const parsed = parseMoveManifest(manifest.spec, REPLAN_SCHEMA);
  const col: Record<string, number[]> = {};
  for (const m of messages.filter((x) => x.channel === 'coco.world.grid.v1')) {
    const g = fromBinary(WorldGridSchema, m.data);
    const [, , costName] = GRIDS.find(([id]) => id === g.mapId)!;
    col[g.mapId] = Array.from(g.occupancy);
    if (costName && g.cost.length) col[costName] = g.cost;
  }
  const back = Object.fromEntries(Object.entries(KIND).map(([k, v]) => [v, REPLAN_KINDS.indexOf(k as (typeof REPLAN_KINDS)[number])]));
  const ev: Record<string, number[]> = { kind: [], row: [], col: [], sub: [], g: [], rhs: [], round: [] };
  const batches = messages.filter((x) => x.channel === 'coco.plan.search.events.v1').map((m) => fromBinary(SearchEventBatchSchema, m.data))
    .sort((a, b) => Number(a.seq[0] - b.seq[0]));
  for (const b of batches) {
    ev.kind.push(...b.kind.map((k) => back[k])); ev.row.push(...b.row); ev.col.push(...b.col); ev.sub.push(...b.sub);
    ev.g.push(...b.g); ev.rhs.push(...b.rhs); ev.round.push(...b.round);
  }
  for (const [k, v] of Object.entries(ev)) col[`trace.${k}`] = v;
  const start = (parsed.tree.get('world') as { get(k: string): unknown }).get('start') as Array<{ value: number }>;
  const walk = [start[0].value, start[1].value];
  const paths: number[] = [];
  ev.kind.forEach((k, i) => {
    if (REPLAN_KINDS[k] === 'move') walk.push(ev.row[i], ev.col[i]);
    if (REPLAN_KINDS[k] === 'path') paths.push(ev.row[i], ev.col[i]);
  });
  col.walk = walk;
  col.paths = paths;
  return decodeReplan(parsed, rawFromColumns(parsed.tree, parsed.total, col));
}
