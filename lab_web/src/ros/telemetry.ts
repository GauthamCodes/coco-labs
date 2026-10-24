// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.3: telemetry -- the model's own numbers, by the M6F.7 topic names (MODEL).
 *
 * - the strip: /cmd_vel (the command the model applied: v, ω) · /odom (the robot in the odom
 *   frame, from coco_lab.ros_shapes' odom -> base_footprint) · the model's sim time;
 * - the Gazebo-style clock: Sim time (the model's), Real time (wall time this run has been
 *   playing, pauses excluded), RTF (sim time / real time over the last RTF_WINDOW_S seconds,
 *   as Gazebo reports its real-time factor), Iterations (the model's ticks, 0.1 s each).
 */

import type { TFMessage } from './shapes';

export interface Strip { v: number; w: number; x: number; y: number; thetaDeg: number; sim: number }

/** The strip's numbers from a tick: the command, and odom -> base_footprint (null before the first tick with frames). */
export function strip(t: { v: number; w: number; t_world: number; ros?: { tf: TFMessage } }): Strip | null {
  const ob = t.ros?.tf.transforms.find((x) => x.header.frame_id === 'odom' && x.child_frame_id === 'base_footprint');
  if (!ob) return null;
  const q = ob.transform.rotation;
  const th = 2 * Math.atan2(q.z, q.w);
  let deg = (th * 180) / Math.PI;
  deg = ((deg % 360) + 360) % 360;
  return { v: t.v, w: t.w, x: ob.transform.translation.x, y: ob.transform.translation.y, thetaDeg: deg, sim: t.t_world };
}

/** −0.10, never "-0.10": a real minus sign, and no "−0.00". */
export function signed(x: number, d = 2): string {
  const s = x.toFixed(d);
  if (Number(s) === 0) return (0).toFixed(d);
  return s.replace('-', '−');
}

/**
 * Right-aligned in a fixed width with figure spaces (U+2007, a digit's width): the monospace strip
 * keeps one width whatever the values, so it never grows into its neighbours (on the real phone
 * it reached /rosout at θ 357°, G2.8).
 */
const pad = (text: string, width: number) => text.padStart(width, '\u2007');

export function stripText(s: Strip): string {
  return `/cmd_vel v ${pad(signed(s.v), 5)} ω ${pad(signed(s.w), 5)} · /odom x ${pad(signed(s.x), 6)} y ${pad(signed(s.y), 6)} θ ${pad(String(Math.round(s.thetaDeg) % 360), 3)}° · sim ${pad(s.sim.toFixed(1), 6)} s`;
}

export const RTF_WINDOW_S = 2;

/** The Gazebo-style clock: fed every presented tick, paused with the game. */
export class SimClock {
  private realMs = 0;
  private runningSince: number | null = null;
  private samples: { real: number; sim: number }[] = [];
  sim = 0;
  iterations = 0;

  /** The run plays (or plays again after a pause) from `now` (ms). */
  resume(now: number) { if (this.runningSince === null) this.runningSince = now; }
  pause(now: number) { if (this.runningSince !== null) { this.realMs += now - this.runningSince; this.runningSince = null; } this.samples = []; }

  /** Real time this run has played (s). */
  real(now: number): number { return (this.realMs + (this.runningSince !== null ? now - this.runningSince : 0)) / 1000; }

  /** A tick was presented: the model's sim time and its tick count. */
  tick(simTime: number, iterations: number, now: number) {
    this.sim = simTime;
    this.iterations = iterations;
    const real = this.real(now);
    this.samples.push({ real, sim: simTime });
    while (this.samples.length > 2 && real - this.samples[0].real > RTF_WINDOW_S) this.samples.shift();
  }

  /** Sim time / real time over the window; null until the window holds two ticks a meaningful time apart. */
  rtf(): number | null {
    if (this.samples.length < 2) return null;
    const a = this.samples[0], b = this.samples[this.samples.length - 1];
    const dr = b.real - a.real;
    return dr > 0.25 ? (b.sim - a.sim) / dr : null;
  }
}

/** "1:07.6" style for long times; seconds with one decimal under a minute. */
export function clockText(s: number): string {
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, '0')}`;
}
