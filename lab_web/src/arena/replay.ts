// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Converted Lab 1 runs in the Arena viewer (M1.9): `?view=arena&replay=<id>`
 * plays generated/v2/<id>.mcap (tools/build_v2_runs.mjs, src/convert/lab1.ts)
 * through an ordinary ArenaSession, so the timeline, scrubbing and the cell
 * inspector all work on them.
 *
 * A recorded run (TIER_STACK, evidence class STACK) is the full ROS 2 stack
 * in Gazebo: the world track steps 0.1 s of sim time per tick; the robot is
 * drawn where the STACK BELIEVED it was (AMCL) with ground truth beside it;
 * the search is shown at FollowPath acceptance. A glass-box trace
 * (TIER_TRACE, MODEL) has no world: one tick, the search, nothing else.
 * Nothing is computed here: every number shown is in the file.
 */

import { fromBinary } from '@bufbuild/protobuf';

import { AnnotationBatchSchema } from '../schemas/gen/coco/annotation/v1/annotation_pb';
import { EvidenceClass } from '../schemas/gen/coco/envelope/v1/manifest_pb';
import { SearchEventBatchSchema, SearchHeaderSchema, SearchStatus, SearchSummarySchema } from '../schemas/gen/coco/plan/v1/search_pb';
import { RobotStateBatchSchema } from '../schemas/gen/coco/robot/v1/robot_pb';
import { TruthPoseBatchSchema } from '../schemas/gen/coco/truth/v1/truth_pb';
import { WorldGridSchema } from '../schemas/gen/coco/world/v1/world_pb';
import { readRun } from '../schemas/mcap';
import { isDrive, parseDrive } from './replay_drive';
import type { Recording } from './attract';
import type { PlanInfo, SearchColumns, Tick, World } from './protocol';

export interface ConvertedRun extends Recording {
  evidence: 'STACK' | 'MODEL';
  title: string;
  /** Annotations (arbiter, collision monitor) by tick, in order. */
  notes: { tick: number; text: string }[];
  /** The recording's measured results, exactly as the bundle stores them. */
  results: Record<string, unknown> | null;
  /** The v1 bundle it came from (content hash). */
  bundle: string;
  /** M2.7: one line of what was measured in this recording, when the run's lab says it so. */
  card?: string;
}

type Pose = [number, number, number];
const DT = 0.1;

export async function parseConverted(bytes: Uint8Array): Promise<ConvertedRun> {
  const { manifest, messages } = await readRun(bytes);
  // M2.7: a converted Lab 5 drive (one controller run on the full stack)
  if (isDrive(manifest)) return parseDrive(manifest, messages);
  const v1 = JSON.parse(new TextDecoder().decode(manifest.spec));
  const stack = manifest.evidenceClass === EvidenceClass.STACK;
  const on = (ch: string) => messages.filter((m) => m.channel === ch);
  const gridMsg = on('coco.world.grid.v1')[0];
  if (!gridMsg) throw new Error('the run has no coco.world.grid.v1');
  const grid = fromBinary(WorldGridSchema, gridMsg.data);
  const header = fromBinary(SearchHeaderSchema, on('coco.plan.search.header.v1')[0].data);
  const summary = fromBinary(SearchSummarySchema, on('coco.plan.search.summary.v1')[0].data);
  const r = grid.resolution || 1; // a bare trace has no geometry: draw it at 1 m a cell
  const centre = (row: number, col: number): [number, number] =>
    [grid.originX + (col + 0.5) * r, grid.originY + (grid.height - 1 - row + 0.5) * r];
  const start = centre(header.start!.row, header.start!.col);
  const goal = centre(header.goal!.row, header.goal!.col);
  const world: World = {
    id: grid.mapId, width: grid.width, height: grid.height, resolution: r, origin: [grid.originX, grid.originY], frame: 'map',
    start: [start[0], start[1], 0], dt: DT, radius: 0, limits: {},
    lidar: { samples: 0, angle_min: 0, angle_max: 0, range_max: 0, mount: [0, 0, 0] },
    planners: [header.algorithm], planner: header.algorithm, hash: '',
  };

  // the search, keyed by the tick it was planned at
  const kPlan = Number(header.tick);
  const list: Recording['batches'] extends Map<number, infer V> ? V : never = [];
  const evMsgs = on('coco.plan.search.events.v1');
  evMsgs.forEach((m, i) => {
    const b = fromBinary(SearchEventBatchSchema, m.data);
    const cols: SearchColumns = {
      seq: BigUint64Array.from(b.seq), tick: BigUint64Array.from(b.tick), t_world: Float64Array.from(b.tWorld),
      kind: Int32Array.from(b.kind), row: Int32Array.from(b.row), col: Int32Array.from(b.col), sub: Int32Array.from(b.sub),
      g: Float64Array.from(b.g), h: Float64Array.from(b.h), f: Float64Array.from(b.f),
      parent_row: Int32Array.from(b.parentRow), parent_col: Int32Array.from(b.parentCol), parent_sub: Int32Array.from(b.parentSub),
    };
    list.push({ meta: { search_id: 0, planner: header.algorithm, tick: kPlan, final: i === evMsgs.length - 1 }, cols });
  });
  list.sort((a, b) => Number(a.cols.seq[0] - b.cols.seq[0]));
  const plan: PlanInfo = {
    search_id: 0, planner: header.algorithm, goal, tick: kPlan, status: summary.status === SearchStatus.FOUND ? 'found' : 'no_path',
    summary: { expansions: Number(summary.expansions), pushes: Number(summary.pushes), relaxes: Number(summary.relaxes),
      path_cost: summary.pathCost ?? null, path_length: summary.pathLength ?? null,
      path_steps: summary.pathSteps != null ? Number(summary.pathSteps) : null },
    waypoints: [],
  };

  // the world track
  const ticks: Tick[] = [];
  const blank = (k: number, pose: Pose, truth?: Pose): Tick => ({ tick: k, t_world: 0, pose, truth, v: 0, w: 0, mode: stack ? 'goal' : 'trace',
    blocked: false, arrived: false, hash: '', chain: '', plans: [] });
  if (stack) {
    const series = (ch: string, schema: typeof TruthPoseBatchSchema | typeof RobotStateBatchSchema) => {
      const t: number[] = []; const p: Pose[] = [];
      for (const m of on(ch)) {
        const b = fromBinary(schema, m.data);
        b.tWorld.forEach((tw, i) => { t.push(tw); p.push([b.x[i], b.y[i], b.theta[i]]); });
      }
      return { t, p };
    };
    const gt = series('coco.truth.pose.v1', TruthPoseBatchSchema);
    const amcl = series('coco.robot.state.v1', RobotStateBatchSchema);
    if (!gt.t.length) throw new Error('a STACK run with no ground truth');
    const t0 = v1.provenance.rosbag.sim_time_start as number;
    const tEnd = gt.t[gt.t.length - 1];
    let ig = 0; let ia = -1;
    for (let k = 1; t0 + k * DT <= tEnd + 1e-9; k += 1) {
      const t = t0 + k * DT;
      while (ig + 1 < gt.t.length && gt.t[ig + 1] <= t) ig += 1;
      while (ia + 1 < amcl.t.length && amcl.t[ia + 1] <= t) ia += 1;
      const truth = gt.p[ig];
      // before the stack's first belief, only the truth is known: draw that
      const tk = blank(k, ia >= 0 ? amcl.p[ia] : truth, truth);
      tk.t_world = t;
      if (k === kPlan + 1) tk.plans.push(plan);
      ticks.push(tk);
    }
  } else {
    const tk = blank(1, [start[0], start[1], 0]);
    tk.plans.push(plan);
    ticks.push(tk);
  }

  const notes: ConvertedRun['notes'] = [];
  for (const m of on('coco.annotation.text.v1')) {
    const b = fromBinary(AnnotationBatchSchema, m.data);
    b.text.forEach((text, i) => notes.push({ tick: Number(b.tick[i]), text }));
  }
  const meta = v1.recording?.meta ?? null;
  return {
    world, occupancy: grid.occupancy, ticks, ranges: new Map(), batches: new Map([[kPlan, list]]), runId: manifest.runId,
    source: manifest.provenance?.source ?? '', evidence: stack ? 'STACK' : 'MODEL',
    title: `${header.algorithm} · ${v1.map.id}${stack ? ` · ${v1.recording.meta.result?.run_id ?? ''}` : ''}`,
    notes, results: meta, bundle: v1.content_hash,
  };
}
