// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.2: LIVE — COCO's ROS 2 stack running now (the coco-ros2 container: a Gazebo simulation,
 * never hardware), as the same ticks Play draws from the browser model.
 *
 * Two connections, by design (Gautham, 2026-11-26):
 *   - READ: foxglove_bridge, read-only (src/ros/foxglove.ts): /tf, /scan, /plan, /odom, /amcl_pose;
 *   - CONTROL: COCO's coco.v1 gateway (coco_web platform_server, remote mode, code access;
 *     src/live/client.ts): drive, STOP, set_mode and nav_goal. The browser names no ROS topic to
 *     command COCO, and every wheel command goes through cmd_vel_arbiter (README invariants 2, 3).
 *
 * The level the container runs is one of COCO Lab's own World Specs, whose Nav2 map frame equals
 * the World Spec frame (`world_to_map` [0, 0] for the Depot), so a LIVE pose is drawn in Play's
 * world as it is. `buildTick` is pure (tested); `LiveSource` holds the sockets.
 */

import type { GameTick } from '../game/session';
import type { PlanInfo } from '../arena/protocol';
import { deserialize, type LaserScanIn, type PoseWithCovarianceStamped } from '../ros/cdr_read';
import { FoxgloveClient, normaliseUrl, type FoxgloveFailure, type LiveGraph } from '../ros/foxglove';
import { yawOf, type Odometry, type Path, type TFMessage, type TransformStamped } from '../ros/shapes';
import { LiveClient } from './client';
import type { Telemetry, Welcome } from './protocol';

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

/** The control gateway's URL from the bridge URL a visitor typed: the same host, the next port, /ws. */
export function gatewayUrl(bridgeUrl: string): string {
  const u = new URL(normaliseUrl(bridgeUrl));
  u.port = String(Number(u.port || (u.protocol === 'wss:' ? 443 : 80)) + 1);
  u.pathname = '/ws';
  return u.toString();
}

export type LivePhase = 'connecting' | 'live' | 'failed' | 'closed';

export interface LiveSourceEvents {
  onTick(tick: GameTick, ranges: Float32Array): void;
  onPhase?(phase: LivePhase, words: string): void;
  onGraph?(g: LiveGraph): void;
  onFailure?(f: FoxgloveFailure | { kind: 'control'; detail: string }): void;
  onControl?(words: string): void;
}

/** The two LIVE connections and a 10 Hz tick, as Play's session would give them. */
export class LiveSource {
  readonly state = emptyState();
  readonly bridge: FoxgloveClient;
  readonly control: LiveClient;
  welcome: Welcome | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private k = 0;
  lastTick: GameTick | null = null;
  latched = false;

  constructor(readonly url: string, private code: string, private ev: LiveSourceEvents) {
    this.bridge = new FoxgloveClient(normaliseUrl(url), {
      onOpen: () => ev.onPhase?.('connecting', 'connected to the bridge; waiting for COCO\'s pose'),
      onMessage: (topic, type, payload, ns) => {
        try { apply(this.state, topic, type, payload); } catch (e) { ev.onControl?.(`could not decode ${topic}: ${String(e)}`); }
        if (topic === '/scan' && this.state.clockNs === null) this.state.clockNs = ns;
      },
      onTime: (ns) => { this.state.clockNs = ns; },
      onGraph: (g) => ev.onGraph?.(g),
      onFailure: (f) => { this.stopTimer(); ev.onFailure?.(f); ev.onPhase?.('failed', f.detail); },
    });
    this.control = new LiveClient(gatewayUrl(url), {
      onWelcome: (w) => {
        this.welcome = w;
        if (w.protocol !== 'coco.v1') ev.onFailure?.({ kind: 'control', detail: `the gateway speaks ${w.protocol}, not coco.v1` });
        if (this.code) this.control.send({ type: 'claim', code: this.code });
      },
      onTelemetry: (t) => { this.state.telemetry = t; this.latched = !!t.platform.stop?.latched; },
      onError: (code, message) => ev.onControl?.(`${code}: ${message}`),
    });
  }

  connect(): void {
    this.bridge.connect();
    this.bridge.subscribe(LIVE_TOPICS);
    this.control.connect();
    this.timer = setInterval(() => this.emit(), 100);
  }

  private emit() {
    const t = buildTick(this.state, this.k);
    if (!t) return;
    this.k += 1;
    if (this.k === 1) this.ev.onPhase?.('live', 'LIVE: COCO\'s ROS 2 stack, running now (a Gazebo simulation)');
    this.lastTick = t;
    this.ev.onTick(t, this.state.scan?.ranges ?? new Float32Array(0));
  }

  private stopTimer() { if (this.timer) clearInterval(this.timer); this.timer = null; }

  /** Driving: a coco.v1 intent to the gateway (it publishes the arbiter's teleop input). */
  drive(linear: number, angular: number) { this.control.send({ type: 'drive', linear, angular }); }
  stop() { this.control.send({ type: 'stop' }); }
  /** Picking a mode is what releases a latched STOP (coco_web stop_latch). */
  manual() { this.control.send({ type: 'set_mode', mode: 'teleop' }); }
  goal(x: number, y: number) { this.control.send({ type: 'set_mode', mode: 'auto' }); this.control.send({ type: 'nav_goal', x, y }); }
  claim(code: string) { this.code = code; this.control.send({ type: 'claim', code }); }

  close(): void {
    this.stopTimer();
    this.bridge.close();
    this.control.close();
    this.ev.onPhase?.('closed', 'disconnected: back to the browser model (MODEL)');
  }
}
