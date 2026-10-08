// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Attract mode (M1.8; README 5.5): the build-time recording
 * (generated/arena/attract.mcap, tools/build_attract.mjs) played through an
 * ordinary ArenaSession while Pyodide loads -- so a visitor sees the robot
 * move and the planner compute within moments of opening the page. It is a
 * MODEL recording made by the same coco_lab the live model runs, and the
 * page says so.
 *
 * Decoding uses the v2 container and coco_schemas' generated TypeScript:
 * the first real consumer of the M1.1 formats on the page.
 */

import { fromBinary } from '@bufbuild/protobuf';

import { SearchEventBatchSchema, SearchHeaderSchema, SearchSummarySchema, SearchStatus } from '../schemas/gen/coco/plan/v1/search_pb';
import { RobotStateBatchSchema } from '../schemas/gen/coco/robot/v1/robot_pb';
import { ScanBatchSchema } from '../schemas/gen/coco/sensor/v1/scan_pb';
import { WorldGridSchema } from '../schemas/gen/coco/world/v1/world_pb';
import { readRun } from '../schemas/mcap';
import type { PlanInfo, SearchColumns, Tick, World } from './protocol';
import type { ArenaSession } from './session';

export interface Recording {
  world: World;
  occupancy: Uint8Array;
  ticks: Tick[];
  ranges: Map<number, Float32Array>;
  /** Plan batches keyed by the tick at whose START they were planned. */
  batches: Map<number, { meta: { search_id: number; planner: string; tick: number; final: boolean }; cols: SearchColumns }[]>;
  runId: string;
  source: string;
}

export function parseRecording(bytes: Uint8Array): Promise<Recording> {
  return readRun(bytes).then(({ manifest, messages }) => {
    const spec = JSON.parse(new TextDecoder().decode(manifest.spec));
    let grid: ReturnType<typeof fromBinary<typeof WorldGridSchema>> | null = null;
    const ticks: Tick[] = [];
    const ranges = new Map<number, Float32Array>();
    const batches: Recording['batches'] = new Map();
    const headers = new Map<number, { planner: string; tick: number }>();
    const summaries = new Map<number, ReturnType<typeof fromBinary<typeof SearchSummarySchema>>>();
    for (const m of messages) {
      if (m.channel === 'coco.world.grid.v1') grid = fromBinary(WorldGridSchema, m.data);
      else if (m.channel === 'coco.plan.search.header.v1') {
        const h = fromBinary(SearchHeaderSchema, m.data);
        headers.set(Number(h.searchId), { planner: h.algorithm, tick: Number(h.tick) });
      } else if (m.channel === 'coco.plan.search.summary.v1') {
        const s = fromBinary(SearchSummarySchema, m.data);
        summaries.set(Number(s.searchId), s);
      }
    }
    if (!grid) throw new Error('the recording has no coco.world.grid.v1');
    for (const m of messages) {
      if (m.channel === 'coco.robot.state.v1') {
        const b = fromBinary(RobotStateBatchSchema, m.data);
        b.tick.forEach((t, i) => ticks.push({ tick: Number(t), t_world: b.tWorld[i], pose: [b.x[i], b.y[i], b.theta[i]], v: b.v[i],
          w: b.omega[i], mode: 'goal', blocked: false, arrived: false, hash: '', chain: '', plans: [] }));
      } else if (m.channel === 'coco.sensor.scan.lidar.v1') {
        const b = fromBinary(ScanBatchSchema, m.data);
        ranges.set(Number(b.tick[0]), Float32Array.from(b.ranges));
      } else if (m.channel === 'coco.plan.search.events.v1') {
        const b = fromBinary(SearchEventBatchSchema, m.data);
        const id = Number(b.searchId);
        const h = headers.get(id);
        const tick = h?.tick ?? Number(b.tick[0] ?? 0n);
        const cols: SearchColumns = {
          seq: BigUint64Array.from(b.seq), tick: BigUint64Array.from(b.tick), t_world: Float64Array.from(b.tWorld),
          kind: Int32Array.from(b.kind), row: Int32Array.from(b.row), col: Int32Array.from(b.col), sub: Int32Array.from(b.sub),
          g: Float64Array.from(b.g), h: Float64Array.from(b.h), f: Float64Array.from(b.f),
          parent_row: Int32Array.from(b.parentRow), parent_col: Int32Array.from(b.parentCol), parent_sub: Int32Array.from(b.parentSub),
        };
        if (!batches.has(tick)) batches.set(tick, []);
        batches.get(tick)!.push({ meta: { search_id: id, planner: h?.planner ?? '', tick, final: false }, cols });
      }
    }
    // mark each search's last batch final; attach plan summaries to the tick they produced
    for (const list of batches.values()) {
      const last = new Map<number, number>();
      list.forEach((b, i) => last.set(b.meta.search_id, i));
      for (const i of last.values()) list[i].meta.final = true;
    }
    for (const [id, s] of summaries) {
      const h = headers.get(id);
      const t = ticks.find((x) => x.tick === (h?.tick ?? -1) + 1);
      if (t) {
        const info: PlanInfo = { search_id: id, planner: h?.planner ?? '', goal: [0, 0], tick: h?.tick ?? 0,
          status: s.status === SearchStatus.FOUND ? 'found' : 'no_path',
          summary: { expansions: Number(s.expansions), pushes: Number(s.pushes), relaxes: Number(s.relaxes),
            path_cost: s.pathCost ?? null, path_length: s.pathLength ?? null, path_steps: s.pathSteps != null ? Number(s.pathSteps) : null },
          waypoints: [] };
        t.plans.push(info);
      }
    }
    const li = spec.robot.lidar;
    const world: World = {
      id: grid.mapId, width: grid.width, height: grid.height, resolution: grid.resolution,
      origin: [grid.originX, grid.originY], frame: 'map',
      start: [spec.start.x + spec.world_to_map[0], spec.start.y + spec.world_to_map[1], spec.start.theta],
      dt: spec.arena.dt, radius: spec.robot.radius, limits: spec.robot.limits,
      lidar: { samples: li.samples, angle_min: li.angle_min, angle_max: li.angle_max, range_max: li.range_max, mount: [li.mount[0], li.mount[1], 0] },
      planners: ['bfs', 'dijkstra', 'astar', 'greedy', 'weighted_astar'], planner: 'astar', hash: '',
    };
    return { world, occupancy: grid.occupancy, ticks, ranges, batches, runId: manifest.runId,
      source: manifest.provenance?.source ?? '' };
  });
}

/** Feed a recording into a session, one tick per model step, looping at the end. */
export class AttractPlayer {
  private i = 0;
  private lastRanges: Float32Array | null = null;

  constructor(readonly rec: Recording, public session: ArenaSession) {}

  /** Push the next recorded tick (its plans first, as the model produced them). */
  step() {
    if (this.i >= this.rec.ticks.length) return false;
    const t = this.rec.ticks[this.i];
    for (const b of this.rec.batches.get(t.tick - 1) ?? []) this.session.onPlanBatch(b.meta, b.cols);
    this.lastRanges = this.rec.ranges.get(t.tick) ?? this.lastRanges;
    this.session.onTick(t, this.lastRanges ?? new Float32Array(this.rec.world.lidar.samples).fill(Infinity));
    this.i += 1;
    return true;
  }

  get done(): boolean {
    return this.i >= this.rec.ticks.length;
  }
}
