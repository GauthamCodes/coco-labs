// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * A Case File in the Arena viewer (M3.3): a recording of the full ROS 2 stack
 * in Gazebo, converted by coco_lab_ros's ROS-to-event adapter
 * (docs/v2/ADAPTER.md), played through an ordinary ArenaSession. STACK:
 * nothing is computed here -- every pose, scan, path, candidate, estimate and
 * transition drawn is one the stack recorded.
 *
 * World: the Nav2 map the stack localised against (generated/casefiles/
 * world.grid.bin, written once beside the Case Files). Ticks: 0.1 s of
 * simulation time from the window's start to the last ground-truth sample;
 * the robot is drawn where the stack believed it was (AMCL) when it had a
 * belief, with ground truth beside it; LiDAR is the latest recorded scan at
 * each tick; a global path is shown from the tick it arrived.
 */

import { fromBinary } from '@bufbuild/protobuf';

import { AnnotationBatchSchema } from '../schemas/gen/coco/annotation/v1/annotation_pb';
import { CandidateBatchSchema, CommandBatchSchema, ControllerHeaderSchema } from '../schemas/gen/coco/control/v1/control_pb';
import { EstimateBatchSchema } from '../schemas/gen/coco/estimate/v1/estimate_pb';
import { MetricBatchSchema } from '../schemas/gen/coco/metrics/v1/metrics_pb';
import { MissionHeaderSchema, TransitionBatchSchema } from '../schemas/gen/coco/mission/v1/mission_pb';
import { PathBatchSchema } from '../schemas/gen/coco/plan/v1/path_pb';
import { RobotStateBatchSchema } from '../schemas/gen/coco/robot/v1/robot_pb';
import { ScanBatchSchema } from '../schemas/gen/coco/sensor/v1/scan_pb';
import { ActorPoseBatchSchema, TruthPoseBatchSchema } from '../schemas/gen/coco/truth/v1/truth_pb';
import type { WorldGrid } from '../schemas/gen/coco/world/v1/world_pb';
import type { Manifest } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import type { ReadMessage } from '../schemas/mcap';
import type { FamilyMessage, Tick, World } from './protocol';
import type { ConvertedRun } from './replay';

export const CASE_SPEC_FORMAT = 'coco_lab_ros.case_spec.v1+json';
const DT = 0.1;
type Pose = [number, number, number];

export function isCaseFile(manifest: Manifest): boolean {
  return manifest.specFormat === CASE_SPEC_FORMAT;
}

/** Which lens a Case File opens on: the computation it has most to show. */
export function caseLens(rec: ConvertedRun): 'move' | 'decide' | 'localise' | 'plan' {
  const has = (ch: string) => [...(rec.families?.values() ?? [])].some((fs) => fs.some((f) => f.channel === ch));
  if (has('coco.control.local.candidates.v1')) return 'move';
  if (has('coco.mission.fsm.transition.v1')) return 'decide';
  if (has('coco.estimate.pose.v1')) return 'localise';
  return 'plan';
}

export function parseCase(manifest: Manifest, messages: ReadMessage[], grid: WorldGrid): ConvertedRun {
  const spec = JSON.parse(new TextDecoder().decode(manifest.spec));
  const on = (ch: string) => messages.filter((m) => m.channel === ch);
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
  const belief = series('coco.robot.state.v1', RobotStateBatchSchema);
  if (!gt.t.length) throw new Error('a Case File with no ground truth');
  const t0 = typeof spec.adapter?.t0 === 'number' ? Math.min(spec.adapter.t0, gt.t[0]) : gt.t[0];
  const tickOf = (t: number) => Math.max(1, Math.floor((t - t0) / DT + 1e-9) + 1);

  // the recorded scans, by the tick they belong to (the latest wins)
  const scans: { t: number; ranges: Float32Array }[] = [];
  let lidar: World['lidar'] = { samples: 0, angle_min: 0, angle_max: 0, range_max: 0, mount: [0, 0, 0] };
  for (const m of on('coco.sensor.scan.lidar.v1')) {
    const b = fromBinary(ScanBatchSchema, m.data);
    let off = 0;
    b.count.forEach((n, i) => {
      if (!lidar.samples) {
        lidar = { samples: n, angle_min: b.angleMin[i], angle_max: b.angleMin[i] + b.angleIncrement[i] * (n - 1),
          range_max: b.rangeMax[i], mount: [0, 0, 0] };
      }
      scans.push({ t: b.tWorld[i], ranges: Float32Array.from(b.ranges.slice(off, off + n)) });
      off += n;
    });
  }
  scans.sort((a, b) => a.t - b.t);
  // the recorded global paths, by search id (1 the lab's own plan, 2 Nav2's received plan, 3 Nav2's)
  const paths: { t: number; xy: number[] }[] = [];
  for (const m of on('coco.plan.path.poses.v1')) {
    const b = fromBinary(PathBatchSchema, m.data);
    const xy: number[] = [];
    b.x.forEach((x, i) => xy.push(x, b.y[i]));
    if (xy.length) paths.push({ t: b.tWorld[0], xy });
  }
  paths.sort((a, b) => a.t - b.t);
  const actorRows: { id: string; t: number; x: number; y: number; r: number }[] = [];
  for (const m of on('coco.truth.actors.v1')) {
    const b = fromBinary(ActorPoseBatchSchema, m.data);
    b.tWorld.forEach((tw, i) => actorRows.push({ id: b.actorId[i], t: tw, x: b.x[i], y: b.y[i],
      r: Number.isFinite(b.radius[i]) ? b.radius[i] : 0.25 }));
  }
  actorRows.sort((a, b) => a.t - b.t);

  const world: World = {
    id: grid.mapId, width: grid.width, height: grid.height, resolution: grid.resolution, origin: [grid.originX, grid.originY],
    frame: 'map', start: [gt.p[0][0], gt.p[0][1], gt.p[0][2]], dt: DT, radius: 0.22, limits: {}, lidar,
    planners: [], planner: '', hash: '',
  };
  const ticks: Tick[] = [];
  const ranges = new Map<number, Float32Array>();
  const tEnd = gt.t[gt.t.length - 1];
  let ig = 0; let ib = -1; let is = -1; let ip = -1; let iact = 0;
  const actorsNow = new Map<string, [number, number, number]>();
  for (let k = 1; t0 + (k - 1) * DT <= tEnd + 1e-9; k += 1) {
    const t = t0 + (k - 1) * DT;
    while (ig + 1 < gt.t.length && gt.t[ig + 1] <= t) ig += 1;
    while (ib + 1 < belief.t.length && belief.t[ib + 1] <= t) ib += 1;
    let newScan = false;
    while (is + 1 < scans.length && scans[is + 1].t <= t) { is += 1; newScan = true; }
    let newPath = false;
    while (ip + 1 < paths.length && paths[ip + 1].t <= t) { ip += 1; newPath = true; }
    while (iact < actorRows.length && actorRows[iact].t <= t) {
      const a = actorRows[iact];
      actorsNow.set(a.id, [a.x, a.y, a.r]);
      iact += 1;
    }
    const truth = gt.p[ig];
    const tk: Tick = { tick: k, t_world: t, pose: ib >= 0 ? belief.p[ib] : truth, truth, v: 0, w: 0, mode: 'goal', blocked: false,
      arrived: false, hash: '', chain: '', plans: [], actors: actorsNow.size ? [...actorsNow.values()] : undefined };
    if (newPath) tk.path = paths[ip].xy;
    if (is >= 0 && (newScan || k === 1)) ranges.set(k, scans[is].ranges);
    ticks.push(tk);
  }

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
    b.tWorld.forEach((tw, i) => {
      const tick = tickOf(tw);
      add(tick, { type: 'family', channel: 'coco.control.local.command.v1', tick, scalars: { controller_id: b.controllerId },
        columns: { cycle: Float64Array.from([Number(b.cycle[i])]), chosen: Float64Array.from([b.chosen[i]]), v: Float64Array.from([b.v[i]]),
          w: Float64Array.from([b.w[i]]), status: [b.status[i]], n_candidates: Float64Array.from([b.nCandidates[i]]),
          n_valid: Float64Array.from([b.nValid[i]]), lookahead_x: Float64Array.from([b.lookaheadX[i]]),
          lookahead_y: Float64Array.from([b.lookaheadY[i]]) } });
      add(tick, { type: 'family', channel: 'coco.metrics.values.v1', tick, scalars: {},
        columns: { tick: Float64Array.from([tick]), name: ['cmd_v'], value: Float64Array.from([b.v[i]]), unit: ['m/s'] } });
    });
  }
  for (const m of on('coco.estimate.pose.v1')) {
    const b = fromBinary(EstimateBatchSchema, m.data);
    b.tWorld.forEach((tw, i) => {
      const tick = tickOf(tw);
      add(tick, { type: 'family', channel: 'coco.estimate.pose.v1', tick, scalars: { estimator: b.estimator },
        columns: { x: Float64Array.from([b.x[i]]), y: Float64Array.from([b.y[i]]), theta: Float64Array.from([b.theta[i]]),
          cov_xx: Float64Array.from([b.covXx[i]]), cov_xy: Float64Array.from([b.covXy[i]]), cov_xt: Float64Array.from([b.covXt[i]]),
          cov_yy: Float64Array.from([b.covYy[i]]), cov_yt: Float64Array.from([b.covYt[i]]), cov_tt: Float64Array.from([b.covTt[i]]) } });
    });
  }
  for (const m of on('coco.mission.fsm.transition.v1')) {
    const b = fromBinary(TransitionBatchSchema, m.data);
    b.tWorld.forEach((tw, i) => {
      const tick = tickOf(tw);
      add(tick, { type: 'family', channel: 'coco.mission.fsm.transition.v1', tick, scalars: { mission_id: b.missionId },
        columns: { from_state: [b.fromState[i]], to_state: [b.toState[i]], event: [b.event[i]], reason: [b.reason[i]], result: [b.result[i]] } });
    });
  }
  for (const m of on('coco.metrics.values.v1')) {
    const b = fromBinary(MetricBatchSchema, m.data);
    b.name.forEach((nm, i) => {
      const tick = tickOf(b.tWorld[i]);
      add(tick, { type: 'family', channel: 'coco.metrics.values.v1', tick, scalars: {},
        columns: { tick: Float64Array.from([tick]), name: [nm], value: Float64Array.from([b.value[i]]), unit: [b.unit[i]] } });
    });
  }
  const headers: FamilyMessage[] = [];
  const ctl = on('coco.control.local.header.v1')[0];
  if (ctl) {
    const h = fromBinary(ControllerHeaderSchema, ctl.data);
    headers.push({ type: 'family', channel: 'coco.control.local.header.v1', header: { controller_id: h.controllerId, kind: h.kind,
      critics: h.critics, evidence: 'STACK' } });
  }
  const fsm = on('coco.mission.fsm.header.v1')[0];
  if (fsm) {
    const h = fromBinary(MissionHeaderSchema, fsm.data);
    headers.push({ type: 'family', channel: 'coco.mission.fsm.header.v1', header: { mission_id: h.missionId, states: h.states, evidence: 'STACK' } });
  }
  const notes: ConvertedRun['notes'] = [];
  for (const m of on('coco.annotation.text.v1')) {
    const b = fromBinary(AnnotationBatchSchema, m.data);
    b.text.forEach((text, i) => notes.push({ tick: tickOf(b.tWorld[i]), text: `${b.source[i]}: ${text}` }));
  }
  notes.sort((a, b) => a.tick - b.tick);
  const src = spec.source?.bag ?? (spec.source?.bags ?? []).map((x: { bag: string }) => x.bag).join(' + ');
  return {
    world, occupancy: grid.occupancy, ticks, ranges, batches: new Map(), runId: manifest.runId,
    source: manifest.provenance?.source ?? '', evidence: 'STACK', title: spec.case?.title ?? manifest.runId, notes,
    results: null, bundle: '', families, headers,
    card: `Recorded on the full ROS 2 stack in Gazebo · ${src} · converted by ${spec.adapter?.name ?? 'the adapter'} ${spec.adapter?.version ?? ''} (${spec.adapter?.detail ?? ''} detail)`,
  };
}
