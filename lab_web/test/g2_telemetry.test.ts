// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.3: telemetry from the model's own numbers (src/ros/telemetry.ts): the strip reads the
 * command and odom -> base_footprint (the parity-tested frames), the clock measures real time
 * with pauses excluded and RTF over a window.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { clockText, signed, SimClock, strip, stripText } from '../src/ros/telemetry';
import type { TFMessage } from '../src/ros/shapes';

const F = JSON.parse(readFileSync(new URL('./fixtures/ros_shapes_parity.json', import.meta.url), 'utf-8')) as { ticks: { page: { v: number; w: number; t_world: number; ros: { tf: TFMessage } }; want: { odom: { pose: { pose: { position: { x: number; y: number } } } } } }[] };

describe('the telemetry strip', () => {
  it('shows /odom as ros_shapes.odometry has it, and the command applied', () => {
    for (const r of F.ticks) {
      const s = strip(r.page)!;
      expect(s.x).toBe(r.want.odom.pose.pose.position.x);
      expect(s.y).toBe(r.want.odom.pose.pose.position.y);
      expect(s.v).toBe(r.page.v);
      expect(s.sim).toBe(r.page.t_world);
    }
  });

  it('reads like the prompt\'s example, with real minus signs', () => {
    const F = '\u2007';
    expect(stripText({ v: 0.24, w: -0.1, x: 3.21, y: -1.04, thetaDeg: 92.2, sim: 67.6 })).toBe(`/cmd_vel v ${F}0.24 ω −0.10 · /odom x ${F}${F}3.21 y ${F}−1.04 θ ${F}92° · sim ${F}${F}67.6 s`);
    // one width whatever the values (figure spaces are a digit wide)
    const widths = [{ v: 0, w: 0, x: 0, y: 0, thetaDeg: 0, sim: 0 }, { v: -0.3, w: -1.2, x: -45.67, y: -12.5, thetaDeg: 357, sim: 1234.5 }].map((v) => [...stripText(v)].length);
    expect(widths[0]).toBe(widths[1]);
    expect(signed(-0.0001)).toBe('0.00');
  });

  it('is absent before the model has sent frames', () => {
    expect(strip({ v: 0, w: 0, t_world: 0 })).toBeNull();
  });
});

describe('the Gazebo-style clock', () => {
  it('real time excludes pauses; RTF is sim / real over the window', () => {
    const c = new SimClock();
    c.resume(0);
    for (let k = 1; k <= 30; k++) c.tick(k * 0.1, k, k * 100);   // real time: one tick per 100 ms
    expect(c.real(3000)).toBeCloseTo(3, 9);
    expect(c.rtf()).toBeCloseTo(1, 9);
    c.pause(3000);
    c.resume(60_000);   // a minute paused
    expect(c.real(60_000)).toBeCloseTo(3, 9);
    for (let k = 31; k <= 60; k++) c.tick(k * 0.1, k, 60_000 + (k - 30) * 200);   // slow motion: half speed
    expect(c.rtf()).toBeCloseTo(0.5, 9);
    expect(c.iterations).toBe(60);
  });

  it('formats like Gazebo\'s status bar', () => {
    expect(clockText(67.62)).toBe('1:07.6');
    expect(clockText(9.04)).toBe('9.0 s');
  });
});
