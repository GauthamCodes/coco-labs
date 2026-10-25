// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.3: a /rosout-style console of the browser model's own events (MODEL), written as ROS 2
 * log lines (`[LEVEL] [stamp] [node]: message`, stamped with the model's sim time).
 *
 * Only real model events, each from a tick the model produced: a plan found (or not), a goal
 * reached, COCO blocked, the wheels' command source changing, STOP; G2 rules 5: AUTO holding for
 * an actor, re-planning around one, backing away or going on (coco_lab.games.ActorAvoid's state). The node names are the
 * M6F.7 ROS graph's (coco_lab.ros_shapes.ros_graph: global_planner, local_controller,
 * cmd_vel_arbiter, ...; Gautham, 2026-10-24) -- the model's roles, never ROS processes.
 * Grasp Assist and the game rules have no node in that graph, so they are not written here.
 */

import type { PlanInfo } from '../arena/protocol';

export type Level = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
export interface LogLine { level: Level; t: number; node: string; msg: string; tick: number }

/** What a tick tells the console (a GameTick's fields). */
export interface TickFacts {
  tick: number; t_world: number; source: string; blocked: boolean; arrived: boolean;
  plans: PlanInfo[]; pose: [number, number, number];
  /** G2 rules 5: AUTO's reaction to the actors (coco_lab.games.ActorAvoid), when it is on */
  avoid?: { state: string; actor: string; waypoints?: [number, number][] } | null;
}

/** The scan's fixed fields the WARN line needs (from the ROS info). */
export interface ScanFacts { angle_min: number; angle_max: number; range_min: number; range_max: number }
/** The planner's grid: its summary measures a path in cells (coco_lab.search), so lengths are x resolution (m). */
export interface GridFacts { resolution: number }

/** How far ahead (rad either side of straight ahead) "obstacle ahead" looks: the front 40 degrees. */
export const AHEAD_HALF_ANGLE = (20 * Math.PI) / 180;

/** The nearest return in the front sector (m), or null when the sector sees nothing in range. */
export function nearestAhead(ranges: ArrayLike<number>, scan: ScanFacts): number | null {
  const n = ranges.length;
  if (n < 2) return null;
  const inc = (scan.angle_max - scan.angle_min) / (n - 1);
  let best: number | null = null;
  for (let i = 0; i < n; i++) {
    const a = scan.angle_min + i * inc;
    if (Math.abs(a) > AHEAD_HALF_ANGLE) continue;
    const r = ranges[i];
    if (r >= scan.range_min && r <= scan.range_max && (best === null || r < best)) best = r;
  }
  return best;
}

const fmtNum = (x: number, d = 2) => x.toFixed(d);
const thousands = (x: number) => Math.round(x).toLocaleString('en-US');

/** The model's wheel sources, as the arbiter would name the input it passes on. */
const SOURCE: Record<string, string> = { teleop: 'teleop (/cmd_vel_teleop)', planner: 'navigation (/cmd_vel_nav)', mission: 'navigation (/cmd_vel_nav)', stop: 'STOP', idle: 'nothing (zero)' };

/**
 * The lines one tick adds, from the previous tick's facts and this one's. Pure: the same ticks
 * give the same lines (tested in test/g2_rosout.test.ts).
 */
export function linesFor(prev: TickFacts | null, cur: TickFacts, ranges: ArrayLike<number> | null, scan: ScanFacts | null, grid: GridFacts): LogLine[] {
  const out: LogLine[] = [];
  const line = (level: Level, node: string, msg: string) => out.push({ level, t: cur.t_world, node, msg, tick: cur.tick });
  for (const p of cur.plans) {
    const s = p.summary as Record<string, number | string | null>;
    const len = typeof s.path_length === 'number' ? s.path_length * grid.resolution : null;
    const exp = typeof s.expansions === 'number' ? s.expansions : null;
    if (p.status === 'found') {
      line('INFO', 'global_planner', `path found (${p.planner}): ${len !== null ? `${fmtNum(len)} m` : `${p.waypoints.length} waypoints`}${exp !== null ? `, ${thousands(exp)} expansions` : ''}`);
    } else {
      line('WARN', 'global_planner', `no path to (${fmtNum(p.goal[0])}, ${fmtNum(p.goal[1])}): ${p.status}${exp !== null ? ` after ${thousands(exp)} expansions` : ''}`);
    }
  }
  const av = cur.avoid, bav = prev?.avoid;
  if (av && av.state !== bav?.state) {
    if (av.state === 'waiting') line('WARN', 'local_controller', `${av.actor} in the path ahead: holding`);
    else if (av.state === 'replanned') line('INFO', 'global_planner', `re-planned around ${av.actor}${av.waypoints ? `: ${av.waypoints.length} waypoints` : ''}`);
    else if (av.state === 'blocked') line('WARN', 'local_controller', `${av.actor} stopped in the path and no detour: holding`);
    else if (av.state === 'backing') line('INFO', 'local_controller', `backing away from ${av.actor}`);
    else if (av.state === 'go') line('INFO', 'local_controller', `${av.actor} still in the way: going on (the actors stop for COCO)`);
  }
  if (cur.arrived && !prev?.arrived) line('INFO', 'local_controller', `goal reached at (${fmtNum(cur.pose[0])}, ${fmtNum(cur.pose[1])})`);
  if (cur.blocked && !prev?.blocked) {
    const ahead = ranges && scan ? nearestAhead(ranges, scan) : null;
    line('WARN', 'local_controller', ahead !== null ? `blocked: obstacle ${fmtNum(ahead)} m ahead` : 'blocked: the next step would collide');
  }
  if (prev && cur.source !== prev.source) {
    if (cur.source === 'stop') line('WARN', 'cmd_vel_arbiter', 'STOP latched: zero to the wheels');
    else if (prev.source === 'stop') line('INFO', 'cmd_vel_arbiter', `STOP released; passing ${SOURCE[cur.source] ?? cur.source}`);
    else line('INFO', 'cmd_vel_arbiter', `passing ${SOURCE[cur.source] ?? cur.source}`);
  }
  return out;
}

/** A line as ROS 2's console prints it: `[INFO] [67.600] [global_planner]: message` (sim-time stamp). */
export const formatLine = (l: LogLine) => `[${l.level}] [${l.t.toFixed(3)}] [${l.node}]: ${l.msg}`;

/** The console's memory: the last `max` lines. */
export class Rosout {
  lines: LogLine[] = [];
  private prev: TickFacts | null = null;
  constructor(readonly max = 200) {}
  feed(cur: TickFacts, ranges: ArrayLike<number> | null, scan: ScanFacts | null, grid: GridFacts): LogLine[] {
    const add = linesFor(this.prev, cur, ranges, scan, grid);
    this.prev = cur;
    if (add.length) { this.lines.push(...add); if (this.lines.length > this.max) this.lines.splice(0, this.lines.length - this.max); }
    return add;
  }
}
