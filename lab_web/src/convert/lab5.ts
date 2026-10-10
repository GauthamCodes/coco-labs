// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 5 drive bundles -> v2 runs (M2.7), and back, with nothing lost.
 *
 * A drive bundle (coco_lab.movebundle, one scenario, every controller run
 * recorded on the full ROS 2 stack in Gazebo) becomes ONE v2 run file PER
 * DRIVE: a run is one robot on one timeline. Every file carries the
 * bundle's manifest.json byte for byte as its spec; `toLab5Drive` needs all
 * of a bundle's files to rebuild its arrays, and hands them to the site's
 * v1 decoder, which re-checks the content hash.
 *
 *   world.grid            the map the stack localised against (Nav2's
 *                         saved map, passed in by the build; not from the
 *                         bundle, which has none)
 *   plan.path             the frozen global path (scenario.path)
 *   truth.pose            ground truth (run.gt)
 *   robot.state           AMCL (run.amcl; v, omega NaN)
 *   truth.actors          the actors as Gazebo moved them (run.actor.*),
 *                         at the scenario's actor radius
 *   metrics               cmd.v / cmd.w (the controller's output) and
 *                         wheel.v / wheel.w (what reached the wheels)
 *   control.local.header  the run: controller_id = run id, kind = DWB, MPPI
 *                         or RPP, evidence STACK
 *   control.local.candidates  Nav2's own candidates where the run recorded
 *                         them (run.roll.*): valid / invalid / unknown, the
 *                         total cost; and, controller_id "<run>/chosen", the
 *                         trajectory the controller chose each cycle
 *                         (run.chosen.*)
 *   control.local.command  status "rollout": the cycle's candidate counts as
 *                         Nav2 logged them and its best candidate; status
 *                         "eval": DWB's per-cycle counts (run.eval)
 *
 * Times are the recording's simulator seconds; tick = 0.1 s bins from the
 * first ground-truth sample. Nothing is computed: the overlays ARE the
 * stack's.
 */

import { create, fromBinary, toBinary, type DescMessage } from '@bufbuild/protobuf';

import { encodeBatch, type Column } from '../schemas/columns';
import { ControllerHeaderSchema, CandidateBatchSchema, CommandBatchSchema } from '../schemas/gen/coco/control/v1/control_pb';
import { ManifestSchema, Tier, EvidenceClass, type Manifest } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import { ParamsSchema } from '../schemas/gen/coco/common/v1/common_pb';
import { MetricBatchSchema } from '../schemas/gen/coco/metrics/v1/metrics_pb';
import { PathBatchSchema } from '../schemas/gen/coco/plan/v1/path_pb';
import { RobotStateBatchSchema } from '../schemas/gen/coco/robot/v1/robot_pb';
import { ActorPoseBatchSchema, TruthPoseBatchSchema } from '../schemas/gen/coco/truth/v1/truth_pb';
import { WorldGridSchema, type WorldGrid } from '../schemas/gen/coco/world/v1/world_pb';
import { decodeDrive, parseMoveManifest, DRIVE_SCHEMA, type DecodedDriveBundle, type DriveRun } from '../move/decode';
import type { ReadMessage, RunRecord } from '../schemas/mcap';
import { runId, specSha256 } from '../schemas/runid';
import { arrayNames, rawFromColumns } from './raw';

export const DRIVE_SPEC_FORMAT = 'coco_lab.drive_bundle.v1+json';
export const CONVERTER = 'lab_web/src/convert/lab5.ts';
const DT = 0.1;
const PER_BATCH = 512;
export const CH = {
  grid: 'coco.world.grid.v1', path: 'coco.plan.path.poses.v1', truth: 'coco.truth.pose.v1', amcl: 'coco.robot.state.v1',
  actors: 'coco.truth.actors.v1', metrics: 'coco.metrics.values.v1', header: 'coco.control.local.header.v1',
  candidates: 'coco.control.local.candidates.v1', command: 'coco.control.local.command.v1',
} as const;

export interface Converted { id: string; manifest: Manifest; records: RunRecord[] }

const sameBytes = (a: Uint8Array, b: Uint8Array) => a.length === b.length && a.every((v, i) => v === b[i]);
const tickOf = (t: number, t0: number) => Math.max(0, Math.floor((t - t0) / DT + 1e-9));
const big = (n: number) => BigInt(n);

/** Rows of `width` values starting with t, in batches; seq is the row index. */
function rows(a: Float64Array, width: number, t0: number, emit: (s: number, e: number, k: number) => void) {
  const n = a.length / width;
  let s = 0;
  while (s < n) {
    const k = tickOf(a[s * width], t0);
    let e = s + 1;
    while (e < n && e - s < PER_BATCH && tickOf(a[e * width], t0) === k) e += 1;
    emit(s, e, k);
    s = e;
  }
}

const col = (a: Float64Array, width: number, j: number, s: number, e: number) =>
  Array.from({ length: e - s }, (_, i) => a[(s + i) * width + j]);

function runRecords(b: DecodedDriveBundle, r: DriveRun, world: WorldGrid | null): RunRecord[] {
  const out: RunRecord[] = [];
  const rec = (channel: string, schema: DescMessage, data: Uint8Array, tWorld: number, seq = 0) => out.push({ channel, schema, data, tWorld, seq });
  const t0 = r.gt[0];
  const clocks = (t: number[], s: number, k: number[]) => ({ seq: t.map((_, i) => big(s + i)), tick: k.map(big), t_world: t });
  if (world) rec(CH.grid, WorldGridSchema, toBinary(WorldGridSchema, world), 0);
  rec(CH.header, ControllerHeaderSchema, toBinary(ControllerHeaderSchema, create(ControllerHeaderSchema, {
    controllerId: r.id, kind: r.controller, critics: [], evidence: 'STACK',
    params: create(ParamsSchema, { items: [['outcome', r.outcome], ['scenario', b.scenario.id]]
      .map(([key, value]) => ({ key, value: { value: { case: 'stringValue' as const, value } } })) }),
  })), 0);
  const p = b.scenario.path;
  const np = p.length / 3;
  rec(CH.path, PathBatchSchema, encodeBatch(PathBatchSchema, {
    seq: Array.from({ length: np }, (_, i) => big(i)), tick: new Array(np).fill(0n), t_world: new Array(np).fill(r.window[0]),
    x: col(p, 3, 0, 0, np), y: col(p, 3, 1, 0, np), theta: col(p, 3, 2, 0, np) }, { search_id: 0n }), r.window[0]);
  rows(r.gt, 4, t0, (s, e, k) => {
    const t = col(r.gt, 4, 0, s, e);
    rec(CH.truth, TruthPoseBatchSchema, encodeBatch(TruthPoseBatchSchema, { ...clocks(t, s, new Array(e - s).fill(k)),
      x: col(r.gt, 4, 1, s, e), y: col(r.gt, 4, 2, s, e), theta: col(r.gt, 4, 3, s, e) }), t[0], s);
  });
  rows(r.amcl, 4, t0, (s, e, k) => {
    const t = col(r.amcl, 4, 0, s, e);
    rec(CH.amcl, RobotStateBatchSchema, encodeBatch(RobotStateBatchSchema, { ...clocks(t, s, new Array(e - s).fill(k)),
      x: col(r.amcl, 4, 1, s, e), y: col(r.amcl, 4, 2, s, e), theta: col(r.amcl, 4, 3, s, e),
      v: new Array(e - s).fill(NaN), omega: new Array(e - s).fill(NaN) }), t[0], s);
  });
  let mseq = 0;
  for (const [name, a] of [['cmd', r.cmd], ['wheel', r.wheel]] as const) {
    rows(a, 3, t0, (s, e, k) => {
      const n = e - s;
      const t = col(a, 3, 0, s, e);
      const idx = Array.from({ length: 2 * n }, (_, i) => i);
      rec(CH.metrics, MetricBatchSchema, encodeBatch(MetricBatchSchema, {
        seq: idx.map((i) => big(mseq + i)), tick: idx.map(() => big(k)), t_world: idx.map((i) => t[i >> 1]),
        name: idx.map((i) => `${name}.${i & 1 ? 'w' : 'v'}`), value: idx.map((i) => a[(s + (i >> 1)) * 3 + 1 + (i & 1)]),
        unit: idx.map((i) => (i & 1 ? 'rad/s' : 'm/s')) }), t[0], mseq);
      mseq += 2 * n;
    });
  }
  let aseq = 0;
  for (const [aid, a] of Object.entries(r.actors)) {
    rows(a, 4, t0, (s, e, k) => {
      const t = col(a, 4, 0, s, e);
      rec(CH.actors, ActorPoseBatchSchema, encodeBatch(ActorPoseBatchSchema, { ...clocks(t, aseq, new Array(e - s).fill(k)),
        actor_id: new Array(e - s).fill(aid), x: col(a, 4, 1, s, e), y: col(a, 4, 2, s, e), theta: col(a, 4, 3, s, e),
        radius: new Array(e - s).fill(b.scenario.actor_radius) }), t[0], aseq);
      aseq += e - s;
    });
  }
  // the controller's chosen trajectory, cycle by cycle
  let cseq = 0;
  for (let k = 0; k < r.chosenT.length; k += 1) {
    const t = r.chosenT[k];
    const a = r.chosenOff[k]; const z = r.chosenOff[k + 1];
    rec(CH.candidates, CandidateBatchSchema, encodeBatch(CandidateBatchSchema, {
      seq: [big(cseq)], tick: [big(tickOf(t, t0))], t_world: [t], candidate: [0], v: [NaN], w: [NaN], valid: [true],
      rejection: [''], cost: [NaN], traj_offset: [0], traj_len: [z - a],
      traj_x: Array.from({ length: z - a }, (_, i) => r.chosenPts[2 * (a + i)]),
      traj_y: Array.from({ length: z - a }, (_, i) => r.chosenPts[2 * (a + i) + 1]) } as Record<string, Column>,
    { cycle: big(k), controller_id: `${r.id}/chosen` }), t, cseq);
    cseq += 1;
  }
  // Nav2's own candidates, where recorded
  let kseq = 0; let qseq = 0;
  const ro = r.rollouts;
  if (ro) {
    for (let f = 0; f < ro.t.length; f += 1) {
      const t = ro.t[f];
      const a = ro.coff[f]; const z = ro.coff[f + 1];
      const flags = Array.from(ro.flags.subarray(a, z));
      const best = flags.flatMap((fl, i) => (fl & 4 ? [i] : []));
      if (best.length > 1 || flags.some((fl) => (fl & ~7) !== 0 || (fl & 3) === 3)) throw new Error(`${r.id}: rollout flags`);
      const offs = Array.from({ length: z - a }, (_, i) => ro.poff[a + i] - ro.poff[a]);
      const lens = Array.from({ length: z - a }, (_, i) => ro.poff[a + i + 1] - ro.poff[a + i]);
      const p0 = ro.poff[a]; const p1 = ro.poff[z];
      rec(CH.candidates, CandidateBatchSchema, encodeBatch(CandidateBatchSchema, {
        seq: offs.map((_, i) => big(kseq + i)), tick: offs.map(() => big(tickOf(t, t0))), t_world: offs.map(() => t),
        candidate: offs.map((_, i) => i), v: offs.map(() => NaN), w: offs.map(() => NaN),
        valid: flags.map((fl) => (fl & 3) === 1), rejection: flags.map((fl) => ((fl & 3) === 0 ? 'invalid' : (fl & 3) === 2 ? 'unknown' : '')),
        cost: Array.from(ro.total.subarray(a, z)), traj_offset: offs, traj_len: lens,
        traj_x: Array.from({ length: p1 - p0 }, (_, i) => ro.pts[2 * (p0 + i)]),
        traj_y: Array.from({ length: p1 - p0 }, (_, i) => ro.pts[2 * (p0 + i) + 1]) } as Record<string, Column>,
      { cycle: big(f), controller_id: r.id }), t, kseq);
      kseq += z - a;
      const nValid = ro.n[2 * f + 1];
      rec(CH.command, CommandBatchSchema, encodeBatch(CommandBatchSchema, {
        seq: [big(qseq)], tick: [big(tickOf(t, t0))], t_world: [t], cycle: [big(f)], chosen: [best.length ? best[0] : -1],
        v: [NaN], w: [NaN], status: [nValid < 0 ? 'rollout:n_valid_unknown' : 'rollout'], n_candidates: [ro.n[2 * f]],
        n_valid: [Math.max(0, nValid)], lookahead_x: [NaN], lookahead_y: [NaN] }, { controller_id: r.id }), t, qseq);
      qseq += 1;
    }
  }
  for (let i = 0; i < r.eval.length / 3; i += 1) {
    const [t, n, nv] = [r.eval[3 * i], r.eval[3 * i + 1], r.eval[3 * i + 2]];
    if (!(Number.isInteger(n) && Number.isInteger(nv) && n >= 0 && nv >= 0)) throw new Error(`${r.id}: eval counts`);
    rec(CH.command, CommandBatchSchema, encodeBatch(CommandBatchSchema, {
      seq: [big(qseq)], tick: [big(tickOf(t, t0))], t_world: [t], cycle: [big(i)], chosen: [-1], v: [NaN], w: [NaN],
      status: ['eval'], n_candidates: [n], n_valid: [nv], lookahead_x: [NaN], lookahead_y: [NaN] }, { controller_id: r.id }), t, qseq);
    qseq += 1;
  }
  return out;
}

/** One v2 run per drive; `world` is the map the stack localised against. */
export async function fromLab5Drive(b: DecodedDriveBundle, manifestBytes: Uint8Array, world: WorldGrid | null): Promise<Converted[]> {
  const spec = await specSha256(manifestBytes);
  const out: Converted[] = [];
  for (const r of b.runs) {
    const engines: [string, string][] = [['coco_lab', b.provenance.coco_lab_version], ['converter', `${CONVERTER} 1`], ['run', r.id]];
    const records = runRecords(b, r, world);
    records.sort((x, y) => x.tWorld - y.tWorld);
    const channels = [...new Map(records.map((x) => [x.channel, x.schema.typeName])).entries()].map(([name, message]) => ({ name, message }));
    out.push({ id: r.id, records, manifest: create(ManifestSchema, {
      runId: await runId(manifestBytes, 0, engines), specFormat: DRIVE_SPEC_FORMAT, spec: manifestBytes, specSha256: spec, seed: 0n,
      tier: Tier.STACK, evidenceClass: EvidenceClass.STACK, engines: engines.map(([name, version]) => ({ name, version })), channels,
      provenance: { createdUtc: b.provenance.created_utc, tool: CONVERTER, gitSha: b.provenance.git_commit ?? '',
        gitDirty: b.provenance.git_dirty ?? false, source: `coco_lab.drive_bundle ${b.contentHash} run ${r.id}`,
        note: `Lab 5, ${b.scenario.id}, ${r.controller} run ${r.id}: recorded on the full ROS 2 stack in Gazebo` },
      schemaPackageVersion: '1.0.0',
    }) });
  }
  return out;
}

/** The drive bundle back, from ALL its runs' channels: decoded (hash-checked) by the v1 decoder. */
export async function toLab5Drive(files: { manifest: Manifest; messages: ReadMessage[] }[]): Promise<DecodedDriveBundle> {
  if (!files.length) throw new Error('no runs');
  const spec = files[0].manifest.spec;
  for (const f of files) {
    if (f.manifest.specFormat !== DRIVE_SPEC_FORMAT) throw new Error(`not a converted Lab 5 drive: ${f.manifest.specFormat}`);
    if (!sameBytes(f.manifest.spec, spec)) throw new Error('runs of different bundles');
  }
  const parsed = parseMoveManifest(spec, DRIVE_SCHEMA);
  const cols: Record<string, number[]> = {};
  const listed = new Set(arrayNames(parsed.tree));
  const push = (name: string, ...v: number[]) => { (cols[name] ??= []).push(...v); };
  for (const f of files) {
    const on = (ch: string) => f.messages.filter((m) => m.channel === ch);
    const head = fromBinary(ControllerHeaderSchema, on(CH.header)[0].data);
    const R = head.controllerId;
    if (!cols.path) {
      for (const m of on(CH.path)) {
        const pb = fromBinary(PathBatchSchema, m.data);
        pb.x.forEach((x, i) => push('path', x, pb.y[i], pb.theta[i]));
      }
    }
    const bySeq = <T extends { seq: bigint[] }>(ch: string, schema: DescMessage) =>
      on(ch).map((m) => fromBinary(schema, m.data) as unknown as T).sort((a, b) => Number(a.seq[0] - b.seq[0]));
    type Pose = { seq: bigint[]; tWorld: number[]; x: number[]; y: number[]; theta: number[] };
    for (const b of bySeq<Pose>(CH.truth, TruthPoseBatchSchema)) b.x.forEach((x, i) => push(`run.${R}.gt`, b.tWorld[i], x, b.y[i], b.theta[i]));
    for (const b of bySeq<Pose>(CH.amcl, RobotStateBatchSchema)) b.x.forEach((x, i) => push(`run.${R}.amcl`, b.tWorld[i], x, b.y[i], b.theta[i]));
    type Met = { seq: bigint[]; tWorld: number[]; name: string[]; value: number[] };
    const mets = bySeq<Met>(CH.metrics, MetricBatchSchema);
    for (const which of ['cmd', 'wheel']) {
      const rowsOf: [number, number, number][] = [];
      for (const b of mets) {
        for (let i = 0; i < b.name.length; i += 2) {
          if (b.name[i] === `${which}.v`) rowsOf.push([b.tWorld[i], b.value[i], b.value[i + 1]]);
        }
      }
      for (const r of rowsOf) push(`run.${R}.${which}`, ...r);
    }
    type Act = { seq: bigint[]; tWorld: number[]; actorId: string[]; x: number[]; y: number[]; theta: number[] };
    for (const b of bySeq<Act>(CH.actors, ActorPoseBatchSchema)) {
      b.x.forEach((x, i) => push(`run.${R}.actor.${b.actorId[i]}`, b.tWorld[i], x, b.y[i], b.theta[i]));
    }
    type Cand = ReturnType<typeof fromBinary<typeof CandidateBatchSchema>>;
    const cands = on(CH.candidates).map((m) => fromBinary(CandidateBatchSchema, m.data) as Cand);
    const chosen = cands.filter((c) => c.controllerId === `${R}/chosen`).sort((a, b) => Number(a.cycle - b.cycle));
    push(`run.${R}.chosen.off`, 0);
    let off = 0;
    for (const c of chosen) {
      push(`run.${R}.chosen.t`, c.tWorld[0]);
      c.trajX.forEach((x, i) => push(`run.${R}.chosen.pts`, x, c.trajY[i]));
      off += c.trajLen[0];
      push(`run.${R}.chosen.off`, off);
    }
    if (!chosen.length) cols[`run.${R}.chosen.t`] ??= [];
    cols[`run.${R}.chosen.pts`] ??= [];
    type Cmd = ReturnType<typeof fromBinary<typeof CommandBatchSchema>>;
    const cmds = on(CH.command).map((m) => fromBinary(CommandBatchSchema, m.data) as Cmd);
    const evals = cmds.filter((c) => c.status[0] === 'eval').sort((a, b) => Number(a.cycle[0] - b.cycle[0]));
    cols[`run.${R}.eval`] = evals.flatMap((c) => [c.tWorld[0], c.nCandidates[0], c.nValid[0]]);
    const frames = cands.filter((c) => c.controllerId === R).sort((a, b) => Number(a.cycle - b.cycle));
    if (frames.length || listed.has(`run.${R}.roll.coff`)) {
      const rollCmd = new Map(cmds.filter((c) => c.status[0].startsWith('rollout')).map((c) => [Number(c.cycle[0]), c]));
      let coff = 0; let poff = 0;
      push(`run.${R}.roll.coff`, 0); push(`run.${R}.roll.poff`, 0);
      for (const fr of frames) {
        const c = rollCmd.get(Number(fr.cycle))!;
        push(`run.${R}.roll.t`, fr.tWorld[0]);
        push(`run.${R}.roll.n`, c.nCandidates[0], c.status[0] === 'rollout:n_valid_unknown' ? -1 : c.nValid[0]);
        fr.candidate.forEach((_, i) => {
          const base = fr.rejection[i] === 'invalid' ? 0 : fr.rejection[i] === 'unknown' ? 2 : 1;
          push(`run.${R}.roll.flags`, base | (c.chosen[0] === i ? 4 : 0));
          push(`run.${R}.roll.total`, fr.cost[i]);
          poff += fr.trajLen[i];
          push(`run.${R}.roll.poff`, poff);
        });
        coff += fr.candidate.length;
        push(`run.${R}.roll.coff`, coff);
        fr.trajX.forEach((x, i) => push(`run.${R}.roll.pts`, x, fr.trajY[i]));
      }
    }
  }
  return decodeDrive(parsed, rawFromColumns(parsed.tree, parsed.total, cols));
}
