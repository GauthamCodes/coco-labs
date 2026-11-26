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
 * What is read (the topics) and how a tick is built from it live in src/ros/live_read.ts: this
 * file names no ROS topic (README invariant 2). `LiveSource` holds the two sockets.
 */

import type { GameTick } from '../game/session';
import { FoxgloveClient, normaliseUrl, type FoxgloveFailure, type LiveGraph } from '../ros/foxglove';
import { apply, buildTick, emptyState, LIVE_TOPICS } from '../ros/live_read';
import { LiveClient } from './client';
import type { Welcome } from './protocol';

/** The control gateway's URL from the bridge URL a visitor typed: the same host, the next port, /ws. */
export function gatewayUrl(bridgeUrl: string): string {
  const u = new URL(normaliseUrl(bridgeUrl));
  u.port = String(Number(u.port || (u.protocol === 'wss:' ? 443 : 80)) + 1);
  u.pathname = 'ws';                    // the URL API makes it /ws: the gateway's WebSocket route
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
  /** the stick as last set: coco_web zeroes a driver whose drive frames stop (its dead-man), so it is re-sent at 10 Hz */
  private held: [number, number] = [0, 0];

  constructor(readonly url: string, private code: string, private ev: LiveSourceEvents) {
    this.bridge = new FoxgloveClient(normaliseUrl(url), {
      onOpen: () => ev.onPhase?.('connecting', 'connected to the bridge; waiting for COCO\'s pose'),
      onMessage: (topic, type, payload) => {
        try { apply(this.state, topic, type, payload); } catch (e) { ev.onControl?.(`could not decode ${topic}: ${String(e)}`); }
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
    if (this.held[0] || this.held[1]) this.control.send({ type: 'drive', linear: this.held[0], angular: this.held[1] });
    const t = buildTick(this.state, this.k);
    if (!t) return;
    this.k += 1;
    if (this.k === 1) this.ev.onPhase?.('live', 'LIVE: COCO\'s ROS 2 stack, running now (a Gazebo simulation)');
    this.lastTick = t;
    this.ev.onTick(t, this.state.scan?.ranges ?? new Float32Array(0));
  }

  private stopTimer() { if (this.timer) clearInterval(this.timer); this.timer = null; }

  /**
   * Driving: coco.v1 `drive` intents to the gateway (it publishes the arbiter's teleop input). A held
   * stick is re-sent every 100 ms by the tick timer, as coco_web's own page sends 10 Hz: its dead-man
   * zeroes the stick when frames stop (measured: one frame moved COCO 0.013 m). Starting to drive
   * picks teleop first, the explicit manual choice the gateway expects.
   */
  drive(linear: number, angular: number) {
    const was = this.held;
    this.held = [linear, angular];
    const moving = linear !== 0 || angular !== 0;
    if (moving && !was[0] && !was[1] && this.state.telemetry?.platform.arbiter.mode !== 'teleop') this.control.send({ type: 'set_mode', mode: 'teleop' });
    if (moving || was[0] || was[1]) this.control.send({ type: 'drive', linear, angular });
  }
  stop() { this.held = [0, 0]; this.control.send({ type: 'stop' }); }
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
