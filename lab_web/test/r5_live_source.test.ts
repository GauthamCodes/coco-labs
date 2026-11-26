// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R5.2: LIVE ticks from real ROS 2 messages (src/live/live_source.ts): COCO's pose is the real tf
 * chain map -> odom -> base_footprint composed (nothing invented while a link is missing), velocity is
 * /odom's, the plan is Nav2's /plan, the command source is the arbiter's (via the coco.v1 gateway),
 * and a LIVE tick carries no model hash. Messages arrive as CDR, as foxglove_bridge sends them.
 */
import { describe, expect, it } from 'vitest';
import { serialize } from '../src/ros/cdr';
import { apply, buildTick, emptyState, gatewayUrl, poseInMap, sourceOf } from '../src/live/live_source';
import { quaternion } from '../src/ros/shapes';
import type { Telemetry } from '../src/live/protocol';

const tf = (parent: string, child: string, x: number, y: number, yaw: number) => ({
  header: { stamp: { sec: 10, nanosec: 0 }, frame_id: parent }, child_frame_id: child,
  transform: { translation: { x, y, z: 0 }, rotation: quaternion(yaw) } });

const telemetry = (over: Partial<Telemetry['platform']> = {}, goal: Telemetry['nav']['goal'] = null): Telemetry => ({
  type: 'telemetry', seq: 1, t: 0, robot: { pose: null, frame: 'map', localised: true, velocity: null, online: true, truth: { x: 23.01, y: 6.02, yaw: 0.1 } },
  mission: null, nav: { online: true, path: [], active_source: null, goal }, sensors: {},
  platform: { pilot: null, health: 'ready', arbiter: { mode: 'teleop', active: 'teleop', online: true }, ...over },
});

describe('LIVE ticks', () => {
  it('composes map -> odom -> base_footprint from /tf, and waits while a link is missing', () => {
    const s = emptyState();
    apply(s, '/tf', 'tf2_msgs/msg/TFMessage', serialize('tf2_msgs/msg/TFMessage', { transforms: [tf('odom', 'base_footprint', 1, 0, Math.PI / 2)] }));
    expect(poseInMap(s)).toBeNull();                       // AMCL's map -> odom not seen yet: no pose
    expect(buildTick(s, 0)).toBeNull();
    apply(s, '/tf', 'tf2_msgs/msg/TFMessage', serialize('tf2_msgs/msg/TFMessage', { transforms: [tf('map', 'odom', 22, 6, Math.PI / 2)] }));
    const p = poseInMap(s)!;
    expect(p[0]).toBeCloseTo(22, 9);                       // 1 m along odom's x, which points along map's y
    expect(p[1]).toBeCloseTo(7, 9);
    expect(p[2]).toBeCloseTo(Math.PI, 9);
  });

  it('builds a tick: /odom velocity, Nav2 /plan, the arbiter source, no model hash', () => {
    const s = emptyState();
    apply(s, '/tf', 'tf2_msgs/msg/TFMessage', serialize('tf2_msgs/msg/TFMessage', { transforms: [tf('map', 'odom', 0, 0, 0), tf('odom', 'base_footprint', 23, 6, 0)] }));
    apply(s, '/odom', 'nav_msgs/msg/Odometry', serialize('nav_msgs/msg/Odometry', {
      header: { stamp: { sec: 12, nanosec: 500000000 }, frame_id: 'odom' }, child_frame_id: 'base_footprint',
      pose: { pose: { position: { x: 23, y: 6, z: 0 }, orientation: quaternion(0) }, covariance: new Array(36).fill(0) },
      twist: { twist: { linear: { x: 0.15, y: 0, z: 0 }, angular: { x: 0, y: 0, z: -0.2 } }, covariance: new Array(36).fill(0) } }));
    apply(s, '/plan', 'nav_msgs/msg/Path', serialize('nav_msgs/msg/Path', { header: { stamp: { sec: 12, nanosec: 0 }, frame_id: 'map' },
      poses: [[23, 6], [24, 6]].map(([x, y]) => ({ header: { stamp: { sec: 12, nanosec: 0 }, frame_id: 'map' }, pose: { position: { x, y, z: 0 }, orientation: quaternion(0) } })) }));
    s.telemetry = telemetry({}, { x: 24, y: 6, sent_at: 1, status: 'executing' });
    const t = buildTick(s, 7)!;
    expect(t.pose).toEqual([23, 6, 0]);
    expect(t.v).toBe(0.15); expect(t.w).toBe(-0.2);
    expect(t.t_world).toBeCloseTo(12.5, 9);
    expect(t.plans).toHaveLength(1);
    expect(t.plans[0].waypoints).toEqual([[23, 6], [24, 6]]);
    expect(t.plans[0].goal).toEqual([24, 6]);
    expect(t.plans[0].status).toBe('executing');
    expect(t.arrived).toBe(false);
    expect(t.source).toBe('teleop');
    expect(t.truth).toEqual([23.01, 6.02, 0.1]);         // Gazebo's truth, as the gateway reports it
    expect(t.hash).toBe(''); expect(t.chain).toBe('');   // not a model step
    expect(t.ros?.tf.transforms.map((x) => x.child_frame_id)).toEqual(['odom', 'base_footprint']);
  });

  it('reads the command source from the arbiter, STOP first', () => {
    expect(sourceOf(telemetry({ stop: { latched: true, since: 1, violations: 0 } }))).toBe('stop');
    expect(sourceOf(telemetry({ arbiter: { mode: 'nav', active: 'nav', online: true } }))).toBe('planner');
    expect(sourceOf(telemetry({ arbiter: { mode: 'idle', active: 'idle', online: true } }))).toBe('idle');
    expect(sourceOf(null)).toBeUndefined();
  });

  it('decodes /scan into a typed array of ranges', () => {
    const s = emptyState();
    apply(s, '/scan', 'sensor_msgs/msg/LaserScan', serialize('sensor_msgs/msg/LaserScan', {
      header: { stamp: { sec: 1, nanosec: 0 }, frame_id: 'lidar_link' }, angle_min: -2.0944, angle_max: 2.0944, angle_increment: 0.00874,
      time_increment: 0, scan_time: 0, range_min: 0.15, range_max: 12, ranges: [1.5, 2.25, Infinity], intensities: [] }));
    expect(Array.from(s.scan!.ranges)).toEqual([1.5, 2.25, Infinity]);
    expect(s.scan!.header.frame_id).toBe('lidar_link');
  });

  it('finds the gateway beside the bridge: same host, next port, /ws', () => {
    expect(gatewayUrl('ws://localhost:8765')).toBe('ws://localhost:8766/ws');
    expect(gatewayUrl('127.0.0.1:9000')).toBe('ws://127.0.0.1:9001/ws');
  });
});
