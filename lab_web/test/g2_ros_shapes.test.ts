// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.2: the page's ROS-shaped model (src/ros/shapes.ts) is a second implementation of
 * coco_lab.ros_shapes, so it must agree with Python's on recorded data (AGENTS.md).
 * The fixture (tools/g2/make_ros_parity_fixture.py, kept current by a pytest) is a Free
 * Drive session on the Depot played through the browser's own glue in CPython: per tick,
 * what the page receives and what ros_shapes built from the Arena. Every shape is compared
 * field by field and number by number (1e-12; the scan's ranges as the float32 the worker sends).
 */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { laserScan, occupancyGrid, odometry, path, twistStamped, type RosInfo, type TFMessage } from '../src/ros/shapes';

interface Row { page: { tick: number; t_world: number; v: number; w: number; ros: { tf: TFMessage }; plan: [number, number][] | null }; ranges?: (number | null)[]; want: Record<string, unknown> }
/** the fixture writes a no-return beam (+inf, as ROS does) as null: JSON has no infinity */
const beams = (r: (number | null)[]) => r.map((x) => (x === null ? Infinity : x));
const F = JSON.parse(readFileSync(new URL('./fixtures/ros_shapes_parity.json', import.meta.url), 'utf-8')) as {
  info: RosInfo; ticks: Row[];
  map: { width: number; height: number; resolution: number; origin: [number, number]; occupancy_rle: [number, number][]; occupancy_sha256: string; grid: Record<string, unknown>; grid_data_sha256: string };
};

/** Structural equality, numbers to 1e-12 (Python's -0.0 equals 0), same keys at every level. */
function same(got: unknown, want: unknown, at = '$'): void {
  if (typeof want === 'number') {
    expect(typeof got, at).toBe('number');
    if (!Number.isFinite(want)) { expect(got, at).toBe(want); return; }
    expect(Math.abs((got as number) - want), `${at}: ${got} vs ${want}`).toBeLessThanOrEqual(1e-12);
    return;
  }
  if (Array.isArray(want)) {
    expect(Array.isArray(got), at).toBe(true);
    expect((got as unknown[]).length, `${at}.length`).toBe(want.length);
    want.forEach((w, i) => same((got as unknown[])[i], w, `${at}[${i}]`));
    return;
  }
  if (want && typeof want === 'object') {
    expect(Object.keys(got as object).sort(), `${at} keys`).toEqual(Object.keys(want).sort());
    for (const k of Object.keys(want)) same((got as Record<string, unknown>)[k], (want as Record<string, unknown>)[k], `${at}.${k}`);
    return;
  }
  expect(got, at).toEqual(want);
}

describe('the page builds the same ROS 2 message shapes as coco_lab.ros_shapes', () => {
  it('has a session with driving and a plan', () => {
    expect(F.ticks.length).toBeGreaterThanOrEqual(20);
    expect(F.ticks.some((r) => r.page.plan)).toBe(true);
    expect(F.ticks.some((r) => Math.abs(r.page.v) > 0.1)).toBe(true);
  });

  it('LaserScan: every field; the ranges as the float32 the worker sends', () => {
    for (const r of F.ticks) {
      const sent = Float32Array.from(r.ranges ? beams(r.ranges) : new Array(480).fill(0));   // the worker's array('f')
      const got = laserScan(F.info.scan, sent, r.page.t_world);
      const ranges = got.ranges;
      const { ranges: _drop, ...rest } = got;
      same(rest, r.want.scan, `tick ${r.page.tick} scan`);
      if (r.ranges) same(ranges, beams(r.ranges).map(Math.fround), `tick ${r.page.tick} ranges`);
    }
  });

  it('Odometry, TF and cmd_vel (TwistStamped)', () => {
    for (const r of F.ticks) {
      same(r.page.ros.tf, r.want.tf, `tick ${r.page.tick} tf`);
      same(odometry(r.page.ros.tf, r.page.v, r.page.w), r.want.odom, `tick ${r.page.tick} odom`);
      same(twistStamped(r.page.v, r.page.w, r.page.t_world), r.want.cmd_vel, `tick ${r.page.tick} cmd_vel`);
    }
  });

  it('Path: the plan the planner found', () => {
    const rows = F.ticks.filter((r) => r.page.plan);
    for (const r of rows) same(path(r.page.plan!, r.page.t_world), r.want.plan, `tick ${r.page.tick} plan`);
  });

  it('OccupancyGrid: header, info and every cell', () => {
    const cells: number[] = [];
    for (const [v, n] of F.map.occupancy_rle) for (let k = 0; k < n; k++) cells.push(v);
    expect(createHash('sha256').update(Uint8Array.from(cells)).digest('hex')).toBe(F.map.occupancy_sha256);
    const g = occupancyGrid(F.map, cells, 0);
    const { data, ...rest } = g;
    same(rest, F.map.grid, 'map');
    expect(createHash('sha256').update(JSON.stringify(data)).digest('hex')).toBe(F.map.grid_data_sha256);
  });

  it('the graph and static frames come from Python, labelled MODEL', () => {
    expect(F.info.graph.evidence).toBe('MODEL');
    expect(F.info.graph.topics.map((t) => t.name)).toEqual(expect.arrayContaining(['/scan', '/odom', '/map', '/plan', '/cmd_vel', '/tf', '/tf_static']));
    expect(F.info.tf_static.transforms.map((t) => `${t.header.frame_id}>${t.child_frame_id}`)).toEqual(['base_footprint>base_link', 'base_link>lidar_link']);
    expect(F.info.scan.frame_id).toBe('lidar_link');
  });
});
