// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.4 / G2.5: the run as the model produced it, tick by tick, for the Plot panel and the
 * rosbag2 export; and each topic's live rate, for the ROS 2 graph panel (MODEL).
 *
 * A topic counts a message only when the model produced one, by ros_shapes.ros_graph's rules:
 * /scan, /odom, /tf and /cmd_vel every tick (10 Hz of sim time); /cmd_vel_nav while the planner
 * drives; /cmd_vel_teleop on a teleop input; /plan on a new plan; /map and /tf_static once
 * (latched). Rates are measured on the wall clock, so a slow model shows a slow rate.
 */

import type { TFMessage } from './shapes';

export interface Frame {
  tick: number; t: number; pose: [number, number, number]; v: number; w: number; source: string;
  tf: TFMessage | null; ranges: Float32Array; plan: [number, number][] | null; goal: [number, number] | null;
  /** the teleop input this tick applied (m/s, rad/s), if any */
  teleop: [number, number] | null; arm: Record<string, number> | null;
}

/** The run's frames; at most MAX_FRAMES (the last 20 minutes of sim time, ~23 MB of scans), oldest dropped first. */
export const MAX_FRAMES = 12_000;

export class Recorder {
  frames: Frame[] = [];
  dropped = 0;
  arm: Record<string, number> | null = null;
  push(f: Frame) {
    this.frames.push(f);
    if (this.frames.length > MAX_FRAMES) { this.frames.shift(); this.dropped += 1; }
  }
  /** Grasp Assist's arm joint angles (coco.arm.state.v1), kept with the next frame. */
  setArm(row: Record<string, number>) { this.arm = row; }
}

/** The topics a tick publishes (ros_graph's rates): the messages the model really produced. */
export function topicsOf(f: Frame, first: boolean): string[] {
  const out = ['/scan', '/odom', '/tf', '/cmd_vel'];
  if (f.source === 'planner' || f.source === 'mission') out.push('/cmd_vel_nav');
  if (f.teleop) out.push('/cmd_vel_teleop');
  if (f.plan) out.push('/plan');
  if (first) out.push('/map', '/tf_static');
  return out;
}

export class TopicStats {
  private at = new Map<string, number[]>();
  private lastSim = new Map<string, number>();
  private lastWall = new Map<string, number>();
  readonly count = new Map<string, number>();

  mark(topic: string, wall: number, sim: number) {
    const a = this.at.get(topic) ?? [];
    a.push(wall);
    while (a.length && wall - a[0] > 2000) a.shift();
    this.at.set(topic, a);
    this.lastSim.set(topic, sim);
    this.lastWall.set(topic, wall);
    this.count.set(topic, (this.count.get(topic) ?? 0) + 1);
  }

  /** Messages per second over the last 2 s of wall time (null: none in that window). */
  rate(topic: string, wall: number): number | null {
    const a = (this.at.get(topic) ?? []).filter((t) => wall - t <= 2000);
    if (a.length < 2) return null;
    return (a.length - 1) / ((a[a.length - 1] - a[0]) / 1000 || 1);
  }

  /** The sim time of the topic's last message, and how long ago it came (wall, ms). */
  last(topic: string, wall: number): { sim: number; agoMs: number } | null {
    const s = this.lastSim.get(topic), w = this.lastWall.get(topic);
    return s === undefined || w === undefined ? null : { sim: s, agoMs: wall - w };
  }
}
