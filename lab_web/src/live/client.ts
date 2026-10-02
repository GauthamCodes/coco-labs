// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Live tab's coco.v1 connection: hello, heartbeat, silence watchdog,
 * reconnect, and a send log the measurement harness reads.
 *
 * Behaviour ported from coco_web's own page transport (app.js), which a
 * real browser has driven: telemetry is the 10 Hz heartbeat, and 4 s of
 * silence means the server is gone even if the socket says open. Binary
 * sensor frames are decoded by coco_web's web/frame.js (`./frame.ts`).
 */

import { decodeFrame, type DecodedFrame } from './frame';
import type { Intent, MapFrame, ServerFrame, Telemetry, Welcome } from './protocol';

export interface LiveEvents {
  onState?(state: ConnState): void;
  onWelcome?(w: Welcome): void;
  onTelemetry?(t: Telemetry): void;
  onMap?(m: MapFrame): void;
  onSensor?(f: DecodedFrame): void;
  onError?(code: string, message: string, id: string | number | null): void;
}

export type ConnState = 'connecting' | 'open' | 'silent' | 'closed';

/** One sent frame, stamped on the wall clock (ms) as it left the page. */
export interface SendRecord { id: number; type: string; t: number; linear?: number; angular?: number }

const SILENCE_MS = 4000;
const PING_MS = 2000;
const LOG_MAX = 20000;

/** Wall-clock milliseconds, comparable with a ROS recorder's time.time(). */
export const wallMs = () => performance.timeOrigin + performance.now();

export class LiveClient {
  private ws: WebSocket | null = null;
  private nextId = 1;
  private lastRx = 0;
  private lastPing = 0;
  private timers: ReturnType<typeof setInterval>[] = [];
  private retry = 0;
  private closedByUser = false;
  readonly log: SendRecord[] = [];
  /** Telemetry arrival times (ms), for the measured received rate. */
  readonly telemetryRx: number[] = [];
  rttMs: number | null = null;
  state: ConnState = 'closed';

  constructor(readonly url: string, private readonly ev: LiveEvents) {}

  connect(): void {
    this.closedByUser = false;
    this.setState('connecting');
    const ws = new WebSocket(this.url);
    ws.binaryType = 'arraybuffer';
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.lastRx = performance.now();
      this.setState('open');
      this.send({ type: 'hello', client: 'coco-lab-live', binary: true });
    };
    ws.onmessage = (e) => this.receive(e.data);
    ws.onclose = () => {
      this.ws = null;
      this.setState('closed');
      if (!this.closedByUser) this.scheduleReconnect();
    };
    ws.onerror = () => { /* onclose follows and reconnects */ };
    this.timers.push(setInterval(() => this.heartbeat(), 500));
  }

  close(): void {
    this.closedByUser = true;
    for (const t of this.timers) clearInterval(t);
    this.timers = [];
    this.ws?.close();
    this.ws = null;
    this.setState('closed');
  }

  /** Send one intent. Returns its id, or null if nothing was sent. */
  send(intent: Intent): number | null {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return null;
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ ...intent, id }));
    const rec: SendRecord = { id, type: intent.type, t: wallMs() };
    if (intent.type === 'drive') { rec.linear = intent.linear; rec.angular = intent.angular; }
    if (this.log.length >= LOG_MAX) this.log.splice(0, LOG_MAX / 2);
    this.log.push(rec);
    return id;
  }

  private receive(data: unknown): void {
    this.lastRx = performance.now();
    if (this.state === 'silent') this.setState('open');
    if (data instanceof ArrayBuffer) {
      try {
        this.ev.onSensor?.(decodeFrame(data));
      } catch {
        // A refused frame costs only itself (coco_web's rule); count nothing.
      }
      return;
    }
    let f: ServerFrame;
    try {
      f = JSON.parse(String(data)) as ServerFrame;
    } catch {
      return;
    }
    switch (f.type) {
      case 'welcome': this.ev.onWelcome?.(f); break;
      case 'telemetry':
        this.telemetryRx.push(wallMs());
        if (this.telemetryRx.length > 2000) this.telemetryRx.splice(0, 1000);
        this.ev.onTelemetry?.(f);
        break;
      case 'map': this.ev.onMap?.(f); break;
      case 'pong': this.rttMs = performance.now() - f.t; break;
      case 'error': this.ev.onError?.(f.code, f.message, f.id); break;
      default: break;
    }
  }

  private heartbeat(): void {
    const now = performance.now();
    if (this.state === 'open' && now - this.lastRx > SILENCE_MS) {
      // The socket may still read "open"; the server has stopped talking.
      this.setState('silent');
    }
    if (this.state === 'open' && now - this.lastPing >= PING_MS) {
      this.lastPing = now;
      this.send({ type: 'ping', t: now });
    }
  }

  private scheduleReconnect(): void {
    for (const t of this.timers) clearInterval(t);
    this.timers = [];
    const wait = Math.min(10000, 1000 * 2 ** this.retry++);
    setTimeout(() => { if (!this.closedByUser) this.connect(); }, wait);
  }

  private setState(s: ConnState): void {
    this.state = s;
    this.ev.onState?.(s);
  }

  /** Telemetry frames per second over the last `windowMs` (measured). */
  telemetryRate(windowMs = 5000): number {
    const now = wallMs();
    const n = this.telemetryRx.filter((t) => now - t <= windowMs).length;
    return n / (windowMs / 1000);
  }
}
