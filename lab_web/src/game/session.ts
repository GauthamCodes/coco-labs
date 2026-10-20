// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1: one played session on the Arena model, in the worker.
 *
 * The page collects intents and hands them to the model as inputs; the model
 * (coco_lab, in Pyodide) decides everything. The priority is the arbiter's
 * (README §3 invariant 3): STOP > the person driving > assists and autonomy.
 * STOP is latched HERE (the page sends nothing else while latched), exactly
 * as M5's Play does; the model's own `stop` input zeroes the wheels.
 *
 * Pacing: one model tick per 0.1 s of wall time when the model keeps up; if a
 * tick takes longer, the game runs in slow motion (every timer is the model's
 * own clock, never wall time). An input is applied at once: it starts a tick
 * when none is in flight, or joins the one in flight (amend), as M5 does.
 */

import { ArenaClient } from '../arena/client';
import { SPEC_FILES, type FamilyMessage, type InputRow, type SpecFile, type Tick, type World } from '../arena/protocol';

export type GameKind = 'fetch_rush' | 'free';
export type WorldId = 'depot' | 'proving';
export const SPEC_FOR: Record<WorldId, SpecFile> = { depot: SPEC_FILES.depot, proving: SPEC_FILES.v1 };

export interface GameObject { id: string; item: string; label: string; shape: 'cylinder' | 'box'; diameter?: number; height: number; size?: number[]; colour: string; magnetic: boolean; x: number; y: number; z: number }
export interface GameZone { id: string; role: string; label?: string; center: [number, number]; size: [number, number] }
export interface GameInfo { game: string; v3: boolean; setup: Omit<InputRow, 'tick'>[]; seconds: number | null; objects?: GameObject[]; zones?: GameZone[]; actors?: { id: string; actor: 'forklift' | 'walker'; footprint: [number, number]; height: number }[] }
export interface AssistState { phase: string; target: string | null; carried: string | null; want: string; reason: string; attempt: number }
export interface FetchState { t: number; seconds: number; over: boolean; order: [string, string] | null; k: number; orders: number; deliveries: number; contacts: number; ghost: number | null }
export interface GameBlock { assist?: AssistState; objects?: [string, number, number, number, string][]; actors?: [string, number, number, number][]; clearance?: number; fetch?: FetchState }
export type GameTick = Tick & { game?: GameBlock; tilt?: [number, number, number] };
export interface Candidate { object_id: string; item: string; reason: string; rank: number; seen_by: string; dist: number; approach_x: number | null; approach_y: number | null }

export interface SessionEvents {
  onWorld(world: World & { game: GameInfo }, occupancy: Uint8Array): void;
  onTick(tick: GameTick, ranges: Float32Array): void;
  onError(stage: string, message: string): void;
  onStage?(stage: string): void;
  /** a model family batch (Grasp Assist's arm state, candidates and stages) */
  onFamily?(msg: FamilyMessage): void;
}

const STEP_MS = 100;

export class GameSession {
  readonly client: ArenaClient;
  world: (World & { game: GameInfo }) | null = null;
  private queue: Omit<InputRow, 'tick'>[] = [];
  private inFlight = false;
  private acc = 0;
  private last = 0;
  private timer = 0;
  private sentAt = 0;
  paused = true;
  latched = false;
  /** the last teleop sent (normalised), so a held stick is not re-sent every tick */
  private sent: [number, number] = [0, 0];
  lastTick: GameTick | null = null;
  ticks = 0;

  constructor(world: WorldId, readonly game: GameKind, readonly seed: number, ev: SessionEvents) {
    this.client = new ArenaClient({
      onWorld: (w, occ) => { this.world = w as World & { game: GameInfo }; ev.onWorld(this.world, occ); },
      onTick: (t, ranges) => { this.inFlight = false; this.lastTick = t as GameTick; this.ticks += 1; ev.onTick(t as GameTick, ranges); this.pump(); },
      onError: (stage, m) => { this.inFlight = false; ev.onError(stage, m); },
      onFamily: (msg) => ev.onFamily?.(msg),
    }, { hashVersion: 2, seed: 1, spec: SPEC_FOR[world], game: { game, arg: game === 'fetch_rush' ? seed : 0 } });
  }

  whenReady() { return this.client.whenReady(); }

  /** Start ticking (the setup inputs go on the first tick). */
  start() {
    if (!this.world) return;
    if (this.ticks === 0 && this.queue.length === 0) this.queue.push(...this.world.game.setup);
    this.paused = false;
    this.last = performance.now();
    // a timer, not the frame loop: the model's pace must not depend on the drawing's frame rate
    clearInterval(this.timer);
    this.timer = window.setInterval(() => this.pump(), 10);
  }

  /** Step when a tick is owed (0.1 s of wall time), or at once when an input waits. */
  private pump() {
    const now = performance.now();
    const dt = Math.min(300, now - this.last);
    this.last = now;
    if (this.paused) return;
    this.acc = Math.min(this.acc + dt, 3 * STEP_MS);
    if (!this.inFlight && (this.acc >= STEP_MS || this.queue.length)) {
      this.acc = Math.max(0, this.acc - STEP_MS);
      this.inFlight = true;
      this.sentAt = now;
      this.client.step(this.queue.splice(0));
    }
  }

  /** How long the tick in flight has taken so far (ms; 0 when none is in flight). */
  stepAge() { return this.inFlight ? performance.now() - this.sentAt : 0; }

  pause() { this.paused = true; }
  resume() { this.paused = false; this.last = performance.now(); }

  /** Send inputs now (they join the tick in flight, or start the next one). */
  send(rows: Omit<InputRow, 'tick'>[]) {
    if (!rows.length) return;
    if (this.inFlight) this.client.amend(rows);
    else this.queue.push(...rows);
  }

  /** The person drives: (forward, turn) in [-1, 1], scaled to the robot's real teleop limits. */
  drive(forward: number, turn: number) {
    if (this.latched || !this.world) return;
    const f = Math.max(-1, Math.min(1, forward)), t = Math.max(-1, Math.min(1, turn));
    if (Math.abs(f - this.sent[0]) < 0.02 && Math.abs(t - this.sent[1]) < 0.02) return;
    this.sent = [f, t];
    const lim = this.world.limits as unknown as { teleop_linear: number; teleop_angular: number };
    this.send([{ kind: 'teleop', linear: f * lim.teleop_linear, angular: t * lim.teleop_angular } as Omit<InputRow, 'tick'>]);
  }

  stop() {
    this.latched = true;
    this.sent = [0, 0];
    this.send([{ kind: 'stop' } as Omit<InputRow, 'tick'>]);
  }

  release() { this.latched = false; }

  goal(x: number, y: number) {
    if (this.latched) return;
    this.sent = [0, 0];
    this.send([{ kind: 'goal', x, y } as Omit<InputRow, 'tick'>]);
  }

  /** Hand the wheels back to autonomy (the planner's last goal). */
  autonomy() { if (!this.latched) this.send([{ kind: 'autonomy' } as Omit<InputRow, 'tick'>]); }

  /** Grasp Assist: press (grab, or put down what is carried); optionally restricted to one object. */
  grasp(target?: string) {
    if (this.latched) return;
    this.sent = [0, 0];
    const rows: Omit<InputRow, 'tick'>[] = [];
    if (target) rows.push({ kind: 'config', choice: `assist.target=${target}` } as Omit<InputRow, 'tick'>);
    rows.push({ kind: 'config', choice: 'assist.grasp=go' } as Omit<InputRow, 'tick'>);
    this.send(rows);
  }

  /** Ask the worker's game glue (read-only queries; nothing in the model changes). */
  query<T>(op: 'preview' | 'auto_goal' | 'record' | 'stars' | 'ghost', arg?: unknown): Promise<T> { return this.client.game<T>(op, arg); }

  /** Take the wheels back from autonomy: a zero teleop (the person drives, standing still). */
  manual() {
    if (this.latched) return;
    this.sent = [0, 0];
    this.send([{ kind: 'teleop', linear: 0, angular: 0 } as Omit<InputRow, 'tick'>]);
  }

  close() { clearInterval(this.timer); this.client.close(); }
}
