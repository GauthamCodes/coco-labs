// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.3: Model vs LIVE -- the same goal, from the same pose, sent to the browser model and to COCO's
 * ROS 2 stack running now (the coco-ros2 container), drawn and measured side by side.
 *
 * MODEL: one run of R1's experiments (coco_lab.experiments, family `control`, an INLINE scenario:
 * start = the LIVE robot's pose when the goal was sent, goal = the goal; the controller `rpp`, the
 * model's Regulated Pure Pursuit, as COCO's Nav2 uses RPP), replayed in the game's own worker, so its
 * numbers are exactly an experiment record's. LIVE: the robot's Gazebo truth from that moment until
 * Nav2 reports the goal finished; time is the stack's sim time (both sides are simulated seconds).
 * Nothing here names a ROS topic (README invariant 2): the LIVE side reads Play's LIVE ticks.
 */

import type { GameTick } from '../game/session';

export const MODEL_CONTROLLER = 'rpp';
export const MODEL_WORLD: Record<string, string> = { depot: 'coco_depot_v1', proving: 'coco_arena_v1' };

/** The experiment spec for the MODEL side (R1's schema; one algorithm, one inline scenario). */
export function modelSpec(world: string, start: [number, number, number], goal: [number, number], schema = 'coco.experiment.v1') {
  return {
    schema, world, family: 'control', seed: 1,
    algorithms: [{ name: MODEL_CONTROLLER }],
    scenarios: { kind: 'inline', scenarios: [{ id: 'live-goal', seed: 1, start: start.map((x) => +x.toFixed(4)), goal: goal.map((x) => +x.toFixed(4)) }] },
  };
}

export interface Side { label: string; length_m: number | null; time_s: number | null; status: string; path: [number, number][] }
export interface Comparison { goal: [number, number]; start: [number, number, number]; model: Side | null; live: Side; done: boolean }

const STATUS_DONE = new Set(['succeeded', 'aborted', 'canceled', 'cancelled', 'failed', 'rejected']);

/** Follows one LIVE goal from the tick it was sent until Nav2 says it finished (or STOP ends it). */
export class LiveLeg {
  readonly path: [number, number][] = [];
  private t0: number | null = null;
  private tEnd: number | null = null;
  private dist = 0;
  private lastTruth: [number, number] | null = null;
  status = 'sent';

  constructor(readonly goal: [number, number], readonly start: [number, number, number], private readonly sentAtSim: number) {}

  /** Feed one LIVE tick; returns true once the leg is finished. */
  add(t: GameTick): boolean {
    if (this.tEnd !== null) return true;
    // drawn in the map frame (the stack's belief, where Play draws COCO); the distance DRIVEN is measured on
    // Gazebo's truth when the gateway reports it (a physical distance, not a belief)
    const b = t.pose;
    const last = this.path.at(-1);
    if (!last || Math.hypot(b[0] - last[0], b[1] - last[1]) > 0.02) this.path.push([b[0], b[1]]);
    const q = t.truth ?? t.pose;
    if (this.lastTruth) this.dist += Math.hypot(q[0] - this.lastTruth[0], q[1] - this.lastTruth[1]);
    this.lastTruth = [q[0], q[1]];
    if (this.t0 === null) this.t0 = this.sentAtSim;
    // only a verdict reported for THIS goal counts: right after it is sent, the gateway may still report
    // the previous goal's status (a stale 'succeeded' would end the leg at once)
    const plan = t.plans.at(-1);
    const mine = !!plan && Math.hypot(plan.goal[0] - this.goal[0], plan.goal[1] - this.goal[1]) < 0.05;
    const verdict = (plan?.summary?.nav_status as string | null | undefined) ?? null;
    if (mine && verdict) this.status = verdict;
    if (mine && t.arrived) this.status = 'succeeded';
    if (t.source === 'stop') this.status = 'stopped';
    if (STATUS_DONE.has(this.status) || this.status === 'stopped') this.tEnd = t.t_world;
    return this.tEnd !== null;
  }

  side(): Side {
    const time = this.t0 !== null && this.tEnd !== null ? +(this.tEnd - this.t0).toFixed(2) : null;
    return { label: "LIVE · Nav2 (RPP) in Gazebo", length_m: +this.dist.toFixed(3), time_s: time, status: this.status, path: this.path };
  }
}

/** The MODEL side from the replayed run's record and frames (truth poses). */
export function modelSide(record: { status: string; metrics: Record<string, number | null> } | null, frames: { truth: [number, number, number] }[]): Side | null {
  if (!record) return null;
  const path: [number, number][] = [];
  for (const f of frames) { const l = path.at(-1); if (!l || Math.hypot(f.truth[0] - l[0], f.truth[1] - l[1]) > 0.02) path.push([f.truth[0], f.truth[1]]); }
  return { label: 'MODEL · RPP, kinematic', length_m: record.metrics.path_length_m ?? null, time_s: record.metrics.time_s ?? null, status: record.status, path };
}

const n = (x: number | null, unit: string, d = 2) => (x === null ? '—' : `${x.toFixed(d)} ${unit}`);
/** One line per side, for the card. */
export function sideWords(s: Side | null, pending: string): string {
  if (!s) return pending;
  return `${s.label}: ${n(s.length_m, 'm')} driven, ${n(s.time_s, 's', 1)} (sim), ${s.status}`;
}
