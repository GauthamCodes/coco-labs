// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * A converted Lab 5 drive in the Arena viewer (M2.7): one controller run
 * recorded on the full ROS 2 stack in Gazebo (src/convert/lab5.ts), played
 * through an ordinary ArenaSession with the Move lens reading NAV2'S OWN
 * candidates and chosen trajectories -- STACK, nothing computed here.
 *
 * World: the Nav2 map the stack localised against. Ticks: 0.1 s of sim time
 * from the first ground-truth sample; the robot is drawn where AMCL put it,
 * ground truth beside it; the actors where Gazebo moved them. Families:
 * control.local's header, candidates and commands, each at the tick of its
 * own t_world.
 */

import { fromBinary } from '@bufbuild/protobuf';

import { CandidateBatchSchema, CommandBatchSchema, ControllerHeaderSchema } from '../schemas/gen/coco/control/v1/control_pb';
import { MetricBatchSchema } from '../schemas/gen/coco/metrics/v1/metrics_pb';
import { RobotStateBatchSchema } from '../schemas/gen/coco/robot/v1/robot_pb';
import { ActorPoseBatchSchema, TruthPoseBatchSchema } from '../schemas/gen/coco/truth/v1/truth_pb';
import { WorldGridSchema } from '../schemas/gen/coco/world/v1/world_pb';
import { DRIVE_SPEC_FORMAT } from '../convert/lab5';
import type { ReadMessage } from '../schemas/mcap';
import type { Manifest } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import type { FamilyMessage, Tick, World } from './protocol';
import type { ConvertedRun } from './replay';

const DT = 0.1;
type Pose = [number, number, number];

export function isDrive(manifest: Manifest): boolean {
  return manifest.specFormat === DRIVE_SPEC_FORMAT;
}

export function parseDrive(manifest: Manifest, messages: ReadMessage[]): ConvertedRun {
  const on = (ch: string) => messages.filter((m) => m.channel === ch);
  const head = fromBinary(ControllerHeaderSchema, on('coco.control.local.header.v1')[0].data);
  const gridMsg = on('coco.world.grid.v1')[0];
  if (!gridMsg) throw new Error('a drive run with no map');
  const grid = fromBinary(WorldGridSchema, gridMsg.data);
  const v1 = JSON.parse(new TextDecoder().decode(manifest.spec));
  const run = (v1.runs as Array<Record<string, any>>).find((r) => r.id === head.controllerId)!; // eslint-disable-line @typescript-eslint/no-explicit-any
  const series = (ch: string, schema: typeof TruthPoseBatchSchema | typeof RobotStateBatchSchema) => {
    const t: number[] = []; const p: Pose[] = [];
    for (const m of on(ch)) {
      const b = fromBinary(schema, m.data);
      b.tWorld.forEach((tw, i) => { t.push(tw); p.push([b.x[i], b.y[i], b.theta[i]]); });
    }
    const order = t.map((_, i) => i).sort((a, b) => t[a] - t[b]);
    return { t: order.map((i) => t[i]), p: order.map((i) => p[i]) };
  };
  const gt = series('coco.truth.pose.v1', TruthPoseBatchSchema);
  const amcl = series('coco.robot.state.v1', RobotStateBatchSchema);
  if (!gt.t.length) throw new Error('a STACK drive with no ground truth');
  const t0 = gt.t[0];
  const tickOf = (t: number) => Math.max(1, Math.floor((t - t0) / DT + 1e-9) + 1);
  // actors: every sample, by actor, in time order
  const actorRows: { id: string; t: number; x: number; y: number; r: number }[] = [];
  for (const m of on('coco.truth.actors.v1')) {
    const b = fromBinary(ActorPoseBatchSchema, m.data);
    b.tWorld.forEach((tw, i) => actorRows.push({ id: b.actorId[i], t: tw, x: b.x[i], y: b.y[i], r: b.radius[i] }));
  }
  actorRows.sort((a, b) => a.t - b.t);
  const world: World = {
    id: grid.mapId, width: grid.width, height: grid.height, resolution: grid.resolution, origin: [grid.originX, grid.originY],
    frame: 'map', start: [gt.p[0][0], gt.p[0][1], gt.p[0][2]], dt: DT, radius: 0.22, limits: {},
    lidar: { samples: 0, angle_min: 0, angle_max: 0, range_max: 0, mount: [0, 0, 0] }, planners: [], planner: '', hash: '',
  };
  const ticks: Tick[] = [];
  const tEnd = gt.t[gt.t.length - 1];
  let ig = 0; let ia = -1; let iact = 0;
  const actorsNow = new Map<string, [number, number, number]>();
  for (let k = 1; t0 + (k - 1) * DT <= tEnd + 1e-9; k += 1) {
    const t = t0 + (k - 1) * DT;
    while (ig + 1 < gt.t.length && gt.t[ig + 1] <= t) ig += 1;
    while (ia + 1 < amcl.t.length && amcl.t[ia + 1] <= t) ia += 1;
    while (iact < actorRows.length && actorRows[iact].t <= t) {
      const a = actorRows[iact];
      actorsNow.set(a.id, [a.x, a.y, a.r]);
      iact += 1;
    }
    const truth = gt.p[ig];
    ticks.push({ tick: k, t_world: t, pose: ia >= 0 ? amcl.p[ia] : truth, truth, v: 0, w: 0, mode: 'goal', blocked: false,
      arrived: false, hash: '', chain: '', plans: [], actors: [...actorsNow.values()] });
  }
  // the controller's families, at the tick of their own time
  const families = new Map<number, FamilyMessage[]>();
  const add = (tick: number, f: FamilyMessage) => (families.get(tick) ?? families.set(tick, []).get(tick)!).push(f);
  for (const m of on('coco.control.local.candidates.v1')) {
    const b = fromBinary(CandidateBatchSchema, m.data);
    const tick = tickOf(b.tWorld[0]);
    add(tick, { type: 'family', channel: 'coco.control.local.candidates.v1', tick, scalars: { cycle: Number(b.cycle), controller_id: b.controllerId },
      columns: { candidate: Float64Array.from(b.candidate), v: Float64Array.from(b.v), w: Float64Array.from(b.w), valid: b.valid,
        rejection: b.rejection, cost: Float64Array.from(b.cost), critic_scores: Float64Array.from(b.criticScores),
        traj_offset: Float64Array.from(b.trajOffset), traj_len: Float64Array.from(b.trajLen), traj_x: Float64Array.from(b.trajX),
        traj_y: Float64Array.from(b.trajY) } });
  }
  for (const m of on('coco.control.local.command.v1')) {
    const b = fromBinary(CommandBatchSchema, m.data);
    const tick = tickOf(b.tWorld[0]);
    add(tick, { type: 'family', channel: 'coco.control.local.command.v1', tick, scalars: { controller_id: b.controllerId },
      columns: { cycle: Float64Array.from(b.cycle, Number), chosen: Float64Array.from(b.chosen), v: Float64Array.from(b.v),
        w: Float64Array.from(b.w), status: b.status, n_candidates: Float64Array.from(b.nCandidates), n_valid: Float64Array.from(b.nValid),
        lookahead_x: Float64Array.from(b.lookaheadX), lookahead_y: Float64Array.from(b.lookaheadY) } });
    // Nav2's own counts as charts: candidates scored, valid
    b.status.forEach((st, i) => {
      if (st === 'eval' || st.startsWith('rollout')) {
        add(tick, { type: 'family', channel: 'coco.metrics.values.v1', tick, scalars: {},
          columns: { tick: Float64Array.from([tick]), name: ['n_valid'], value: Float64Array.from([b.nValid[i]]), unit: [''] } });
      }
    });
  }
  for (const m of on('coco.metrics.values.v1')) {
    const b = fromBinary(MetricBatchSchema, m.data);
    b.name.forEach((nm, i) => {
      if (nm !== 'cmd.v') return;
      const tick = tickOf(b.tWorld[i]);
      add(tick, { type: 'family', channel: 'coco.metrics.values.v1', tick, scalars: {},
        columns: { tick: Float64Array.from([tick]), name: ['cmd_v'], value: Float64Array.from([b.value[i]]), unit: ['m/s'] } });
    });
  }
  const headers: FamilyMessage[] = [{ type: 'family', channel: 'coco.control.local.header.v1', header: {
    controller_id: head.controllerId, kind: head.kind, critics: head.critics, evidence: 'STACK' } }];
  const met = run.metrics as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const m2 = (v: unknown) => (typeof v === 'number' ? `${v.toFixed(3)} m` : '—');
  return {
    world, occupancy: grid.occupancy, ticks, ranges: new Map(), batches: new Map(), runId: manifest.runId,
    source: manifest.provenance?.source ?? '', evidence: 'STACK',
    title: `Lab 5 · ${v1.scenario.title} · ${head.kind} run ${head.controllerId}`, notes: [],
    results: null, bundle: v1.content_hash, families, headers,
    card: `${run.outcome}${run.record?.error_code ? ` (code ${run.record.error_code})` : ''} · tracking error mean ${m2(met?.tracking_m?.mean)} · `
      + `min clearance ${m2(met?.clearance?.min_m)}${met?.clearance?.contact ? ' (contact)' : ''} — Lab 5 measured these from this recording`,
  };
}
