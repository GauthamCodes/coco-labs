// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.2: the READ side of LIVE -- the ROS 2 topics read from the visitor's own foxglove_bridge
 * (read-only) and the Play tick built from them. Topic names live here, in src/ros, and never in
 * src/live: the code that COMMANDS COCO (src/live) names no ROS topic and speaks coco.v1 only
 * (README invariant 2; test/live.test.ts). Reading a visitor-owned bridge is outside that boundary
 * (AGENTS.md).
 *
 * The level the container runs is one of COCO Lab's own World Specs, whose Nav2 map frame equals
 * the World Spec frame (`world_to_map` [0, 0] for the Depot), so a LIVE pose is drawn in Play's world
 * as it is. Pure (tested in test/r5_live_source.test.ts).
 */

import type { GameTick } from '../game/session';
import type { PlanInfo } from '../arena/protocol';
import type { Telemetry } from '../live/protocol';
import { deserialize, type LaserScanIn, type PoseWithCovarianceStamped } from './cdr_read';
import { yawOf, type Odometry, type Path, type TFMessage, type TransformStamped } from './shapes';

export const LIVE_TOPICS = ['/tf', '/tf_static', '/scan', '/plan', '/odom', '/amcl_pose'] as const;

/** The latest of everything LIVE, as received (nothing interpolated or invented). */
export interface LiveState {
  tf: Map<string, TransformStamped>;          // child frame -> its latest transform (dynamic)
  tfStatic: Map<string, TransformStamped>;
  scan: LaserScanIn | null;
  plan: Path | null;
  odom: Odometry | null;
  amcl: PoseWithCovarianceStamped | null;
  telemetry: Telemetry | null;
  clockNs: bigint | null;
}

export const emptyState = (): LiveState => ({ tf: new Map(), tfStatic: new Map(), scan: null, plan: null, odom: null, amcl: null, telemetry: null, clockNs: null });

type P2 = [number, number, number];
const compose = (a: P2, b: P2): P2 => [a[0] + Math.cos(a[2]) * b[0] - Math.sin(a[2]) * b[1], a[1] + Math.sin(a[2]) * b[0] + Math.cos(a[2]) * b[1], a[2] + b[2]];
const planar = (t: TransformStamped): P2 => [t.transform.translation.x, t.transform.translation.y, yawOf(t.transform.rotation)];
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));

/** map -> base_footprint from the real tf tree (AMCL's map -> odom, the controller's odom -> base_footprint). */
export function poseInMap(s: LiveState): P2 | null {
  const odomBase = s.tf.get('base_footprint');
  const mapOdom = s.tf.get('odom');
  if (!odomBase || odomBase.header.frame_id !== 'odom' || !mapOdom || mapOdom.header.frame_id !== 'map') return null;
  const p = compose(planar(mapOdom), planar(odomBase));
  return [p[0], p[1], wrap(p[2])];
}

/** Who the wheels obey, in Tick.source's words, from the gateway's arbiter report. */
export function sourceOf(t: Telemetry | null): GameTick['source'] {
  if (!t) return undefined;
  if (t.platform.stop?.latched) return 'stop';
  const a = t.platform.arbiter.active ?? t.platform.arbiter.mode;
  return a === 'teleop' ? 'teleop' : a === 'nav' || a === 'auto' ? 'planner' : a === 'mission' ? 'mission' : 'idle';
}

/**
 * One Play tick from the LIVE state, or null while the robot's pose is not yet known.
 * hash and chain are empty: a LIVE tick is not a model step and has no model hash.
 */
export function buildTick(s: LiveState, k: number): GameTick | null {
  const pose = poseInMap(s);
  if (!pose) return null;
  const tw = s.odom?.twist.twist;
  const t = s.telemetry;
  const goal = t?.nav.goal ?? null;
  const plans: PlanInfo[] = [];
  if (s.plan && s.plan.poses.length) {
    plans.push({ search_id: 0, planner: 'Nav2', goal: goal ? [goal.x, goal.y] : [s.plan.poses.at(-1)!.pose.position.x, s.plan.poses.at(-1)!.pose.position.y],
      tick: k, status: goal?.status ?? 'live', summary: {}, waypoints: s.plan.poses.map((p) => [p.pose.position.x, p.pose.position.y]) });
  }
  const truth = t?.robot.truth;
  const tf: TFMessage = { transforms: [s.tf.get('odom'), s.tf.get('base_footprint')].filter((x): x is TransformStamped => !!x) };
  const sec = s.clockNs !== null ? Number(s.clockNs) / 1e9 : s.odom ? s.odom.header.stamp.sec + s.odom.header.stamp.nanosec / 1e9 : 0;
  return {
    tick: k, t_world: sec, pose, v: tw?.linear.x ?? 0, w: tw?.angular.z ?? 0,
    ...(truth ? { truth: [truth.x, truth.y, truth.yaw] as P2 } : {}),
    mode: 'live', blocked: false, arrived: goal?.status === 'succeeded', hash: '', chain: '', plans,
    source: sourceOf(t), ros: { tf },
  };
}

/** Apply one decoded LIVE message to the state. Unknown topics are ignored. */
export function apply(s: LiveState, topic: string, type: string, payload: Uint8Array): void {
  switch (topic) {
    case '/tf': case '/tf_static': {
      const m = deserialize<TFMessage>(type, payload);
      const into = topic === '/tf' ? s.tf : s.tfStatic;
      for (const t of m.transforms) into.set(t.child_frame_id, t);
      break;
    }
    case '/scan': s.scan = deserialize<LaserScanIn>(type, payload); break;
    case '/plan': s.plan = deserialize<Path>(type, payload); break;
    case '/odom': s.odom = deserialize<Odometry>(type, payload); break;
    case '/amcl_pose': s.amcl = deserialize<PoseWithCovarianceStamped>(type, payload); break;
    default: break;
  }
}
