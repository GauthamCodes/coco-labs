// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 4 search bundles -> v2 runs (M2.7), and back, with nothing lost.
 *
 * A search bundle (coco_lab.searchbundle: manifest.json + arrays) becomes
 * one v2 run file holding every search in it; each search's rows carry
 * its run id (`problem_id`, `mission_id`). Event k of a search is tick k:
 *
 *   spec                     the bundle's manifest.json, byte for byte
 *   decide.search.header     the problem as the robot knew it (one per
 *                            search): bays, d and how it is known
 *                            ("ASSUMPTION" when the problem says assumed)
 *   decide.search.belief     the belief AFTER every event (update = k)
 *   decide.search.action     at a `select`: every bay's expected cost of
 *                            looking there next ("candidate"), the bay
 *                            chosen ("chosen"); NaN for a searched bay
 *   decide.search.observation  at a `survey`: the bay and whether it was found
 *   mission.fsm.transition   every event, in order: its kind, its bay (the
 *                            reason; "" for none), its outcome (the result:
 *                            "found", "miss", "" for not a survey)
 *   metrics                  "<run id>.cost": metres driven by then
 *
 * t_world is the recording's simulator seconds for a recorded search and
 * 0 for a Sketch (as M1's glass-box traces). A recorded search is STACK,
 * a Sketch MODEL; one file is never both.
 *
 * `toLab4` rebuilds the v1 arrays from the CHANNELS alone and hands them,
 * with the spec bytes, to the site's v1 decoder, which re-checks the
 * bundle's content hash. coco_schemas/test/test_search_replay_v2.py then
 * rebuilds every recorded search from the converted observations alone
 * (regionsearch.replay_search) and requires these channels' bytes.
 */

import { create, fromBinary, toBinary, type DescMessage } from '@bufbuild/protobuf';

import { EVENT_KINDS, decodeSearch, parseSearchManifest, type DecodedSearchBundle } from '../search/decode';
import { encodeBatch, type Column } from '../schemas/columns';
import { ActionBatchSchema, BeliefBatchSchema, ObservationBatchSchema, SearchProblemHeaderSchema } from '../schemas/gen/coco/decide/v1/decide_pb';
import { ManifestSchema, Tier, EvidenceClass, type Manifest } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import { ParamsSchema } from '../schemas/gen/coco/common/v1/common_pb';
import { MetricBatchSchema } from '../schemas/gen/coco/metrics/v1/metrics_pb';
import { TransitionBatchSchema } from '../schemas/gen/coco/mission/v1/mission_pb';
import type { ReadMessage, RunRecord } from '../schemas/mcap';
import { runId, specSha256 } from '../schemas/runid';
import { Seq, rawFromColumns } from './raw';

export const SPEC_FORMAT = 'coco_lab.search_bundle.v1+json';
export const CONVERTER = 'lab_web/src/convert/lab4.ts';
export const CH = {
  header: 'coco.decide.search.header.v1', belief: 'coco.decide.search.belief.v1', action: 'coco.decide.search.action.v1',
  observation: 'coco.decide.search.observation.v1', transition: 'coco.mission.fsm.transition.v1', metrics: 'coco.metrics.values.v1',
} as const;

export interface Converted { manifest: Manifest; records: RunRecord[] }

const OUTCOME: Record<number, string> = { 1: 'found', 0: 'miss', [-1]: '' };

export async function fromLab4(b: DecodedSearchBundle, manifestBytes: Uint8Array): Promise<Converted> {
  const kinds = new Set(b.runs.map((r) => r.kind));
  if (kinds.size !== 1) throw new Error('a search bundle mixing recorded and Sketch runs is not one evidence class');
  const stack = kinds.has('recorded');
  const p = b.problem;
  if (new Set(p.detection).size !== 1) throw new Error('SearchProblemHeader carries one detection probability; the bays differ');
  const ids = p.regions.map((r) => r.id);
  const n = ids.length;
  const spec = await specSha256(manifestBytes);
  const engines: [string, string][] = [['coco_lab', b.provenance.coco_lab_version], ['converter', `${CONVERTER} 1`]];
  const seq = new Seq();
  const records: RunRecord[] = [];
  const rec = (channel: string, schema: DescMessage, data: Uint8Array, tWorld: number, s = 0) =>
    records.push({ channel, schema, data, tWorld: Number.isFinite(tWorld) ? tWorld : 0, seq: s });
  for (const r of b.runs) {
    const h = r.header as Record<string, unknown>;
    const given = (h.given_order as string[] | undefined) ?? [];
    records.push({ channel: CH.header, schema: SearchProblemHeaderSchema, tWorld: 0, seq: 0, data: toBinary(SearchProblemHeaderSchema,
      create(SearchProblemHeaderSchema, {
        problemId: r.id, regionIds: ids, detection: p.detection[0],
        detectionLabel: p.meta.detection_is === 'assumed' ? 'ASSUMPTION' : 'MEASURED',
        params: create(ParamsSchema, { items: [
          ['policy', String(h.policy)], ['given_order', given.join(',')], ['source', String(h.source ?? '')], ['kind', r.kind],
        ].map(([key, value]) => ({ key, value: { value: { case: 'stringValue' as const, value } } })) }),
      })) });
    let prev = '';
    for (let k = 0; k < r.n; k += 1) {
      const t = r.t ? r.t[k] : 0;
      const kind = EVENT_KINDS[r.kinds[k]];
      const region = r.region[k];
      const tick = BigInt(k);
      const one = (ch: string, rows = 1) => ({ seq: seq.take(ch, r.id, rows), tick: new Array(rows).fill(tick), t_world: new Array(rows).fill(t) });
      rec(CH.transition, TransitionBatchSchema, encodeBatch(TransitionBatchSchema, {
        ...one(CH.transition), from_state: [prev], to_state: [kind], event: [kind],
        reason: [region >= 0 ? ids[region] : ''], result: [OUTCOME[r.outcome[k]]] }, { mission_id: r.id }), t, k);
      prev = kind;
      rec(CH.belief, BeliefBatchSchema, encodeBatch(BeliefBatchSchema, {
        ...one(CH.belief, n), region: ids.map((_, i) => i), probability: r.belief.subarray(k * n, (k + 1) * n) },
      { update: tick, problem_id: r.id }), t, k);
      if (kind === 'select') {
        rec(CH.action, ActionBatchSchema, encodeBatch(ActionBatchSchema, {
          ...one(CH.action, n), region: ids.map((_, i) => i), expected_cost: r.candidates.subarray(k * n, (k + 1) * n),
          reason: ids.map((_, i) => (i === region ? 'chosen' : 'candidate')) }, { update: tick, problem_id: r.id }), t, k);
      }
      if (kind === 'survey') {
        rec(CH.observation, ObservationBatchSchema, encodeBatch(ObservationBatchSchema, {
          ...one(CH.observation), region: [region], found: [r.outcome[k] === 1] } as Record<string, Column>, { problem_id: r.id }), t, k);
      }
      rec(CH.metrics, MetricBatchSchema, encodeBatch(MetricBatchSchema, {
        ...one(CH.metrics), name: [`${r.id}.cost`], value: [r.cost[k]], unit: ['m'] }), t, k);
    }
  }
  const channels = [...new Map(records.map((x) => [x.channel, x.schema.typeName])).entries()].map(([name, message]) => ({ name, message }));
  const manifest = create(ManifestSchema, {
    runId: await runId(manifestBytes, 0, engines), specFormat: SPEC_FORMAT, spec: manifestBytes, specSha256: spec, seed: 0n,
    tier: stack ? Tier.STACK : Tier.TRACE, evidenceClass: stack ? EvidenceClass.STACK : EvidenceClass.MODEL,
    engines: engines.map(([name, version]) => ({ name, version })), channels,
    provenance: { createdUtc: b.provenance.created_utc, tool: CONVERTER, gitSha: b.provenance.git_commit ?? '',
      gitDirty: b.provenance.git_dirty ?? false, source: `coco_lab.searchbundle ${b.contentHash}`,
      note: stack ? 'converted from searches recorded on the full ROS 2 stack in Gazebo' : 'converted from Sketch searches (coco_lab)' },
    schemaPackageVersion: '1.0.0',
  });
  return { manifest, records };
}

/** The v1 bundle back, from the channels alone: decoded (so hash-checked) by the v1 decoder. */
export async function toLab4(manifest: Manifest, messages: ReadMessage[]): Promise<DecodedSearchBundle> {
  if (manifest.specFormat !== SPEC_FORMAT) throw new Error(`not a converted Lab 4 bundle: ${manifest.specFormat}`);
  const parsed = parseSearchManifest(manifest.spec);
  const on = (ch: string) => messages.filter((m) => m.channel === ch);
  const ids = ((parsed.tree.get('problem') as { get(k: string): unknown }).get('regions') as Array<{ get(k: string): unknown }>)
    .map((r) => r.get('id') as string);
  const n = ids.length;
  const col: Record<string, number[]> = {};
  const put = (name: string, k: number, v: number) => { (col[name] ??= [])[k] = v; };
  const tr = on(CH.transition).map((m) => fromBinary(TransitionBatchSchema, m.data));
  for (const b of tr) {
    b.tick.forEach((t, i) => {
      const k = Number(t); const run = b.missionId;
      put(`run.${run}.kind`, k, EVENT_KINDS.indexOf(b.toState[i] as (typeof EVENT_KINDS)[number]));
      put(`run.${run}.region`, k, b.reason[i] ? ids.indexOf(b.reason[i]) : -1);
      put(`run.${run}.outcome`, k, b.result[i] === 'found' ? 1 : b.result[i] === 'miss' ? 0 : -1);
      put(`run.${run}.t`, k, b.tWorld[i]);
    });
  }
  for (const m of on(CH.belief)) {
    const b = fromBinary(BeliefBatchSchema, m.data);
    const k = Number(b.update);
    b.region.forEach((reg, i) => put(`run.${b.problemId}.belief`, k * n + reg, b.probability[i]));
  }
  // candidates: NaN except at a select
  const runs = new Set(tr.map((b) => b.missionId));
  for (const run of runs) {
    const ev = col[`run.${run}.kind`].length;
    col[`run.${run}.candidates`] = new Array(ev * n).fill(NaN);
  }
  for (const m of on(CH.action)) {
    const b = fromBinary(ActionBatchSchema, m.data);
    const k = Number(b.update);
    b.region.forEach((reg, i) => { col[`run.${b.problemId}.candidates`][k * n + reg] = b.expectedCost[i]; });
  }
  for (const m of on(CH.metrics)) {
    const b = fromBinary(MetricBatchSchema, m.data);
    b.name.forEach((name, i) => put(`run.${name.slice(0, -'.cost'.length)}.cost`, Number(b.tick[i]), b.value[i]));
  }
  return decodeSearch(parsed, rawFromColumns(parsed.tree, parsed.total, col));
}
