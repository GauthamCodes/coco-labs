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
 *
 * G1.13: an ordinary tick is shown on a 0.1 s schedule, not when the worker
 * happens to finish it. Measured on the laptop (data/g113): sends kept a 100 ms
 * cadence (p95 107 ms), but each tick reached the page `step` ms after its send,
 * and a step 25-62 ms longer than the one before made a 130-168 ms gap (half of
 * all gaps exceeded 100 ms). So a tick is now sent `lead` ms before it is due
 * (the 90th percentile of recent send-to-arrival times, plus 5 ms) and, if it
 * arrives early, handed on at its due time. A tick an input starts is still
 * sent and shown at once (the schedule restarts from it), so a person's input
 * waits no longer than before. Presentation only: the model's inputs, ticks and
 * hashes are what they were.
 */

import type { PlayPlanner } from './planners';
import { ArenaClient } from '../arena/client';
import { SPEC_FILES, type FamilyMessage, type InputRow, type SpecFile, type Tick, type World } from '../arena/protocol';
import type { RosInfo, TFMessage } from '../ros/shapes';

export type GameKind = 'fetch_rush' | 'free';
export type WorldId = 'depot' | 'proving';
export const SPEC_FOR: Record<WorldId, SpecFile> = { depot: SPEC_FILES.depot, proving: SPEC_FILES.v1 };

export interface GameObject { id: string; item: string; label: string; shape: 'cylinder' | 'box'; diameter?: number; height: number; size?: number[]; colour: string; magnetic: boolean; x: number; y: number; z: number }
export interface GameZone { id: string; role: string; label?: string; center: [number, number]; size: [number, number] }
/** G1.11: a Fetch Rush rules-2 round: start zone, orders, each order's ghost length and route, the reference clock */
export interface GameRound { region: string; label: string; orders: [string, string][]; ghost_m: number[]; routes: [number, number][][]; reference_time_s: number | null; timer_s: number | null }
export interface GameInfo { game: string; v3: boolean; setup: Omit<InputRow, 'tick'>[]; seconds: number | null; round?: GameRound; objects?: GameObject[]; zones?: GameZone[]; actors?: { id: string; actor: 'forklift' | 'walker'; footprint: [number, number]; height: number }[];
  /** G2.2: the ROS-shaped model's constants (coco_lab.ros_shapes: graph, static frames, scan) */
  ros?: RosInfo }
export interface AssistState { phase: string; target: string | null; carried: string | null; want: string; reason: string; attempt: number }
export interface FetchState { t: number; seconds: number; over: boolean; order: [string, string] | null; k: number; orders: number; deliveries: number; contacts: number; ghost: number | null }
export interface GameBlock { assist?: AssistState; objects?: [string, number, number, number, string][]; actors?: [string, number, number, number][]; clearance?: number; fetch?: FetchState }
/** G2.2: `ros.tf` -- the model's dynamic frames this tick, as coco_lab.ros_shapes.tf built them */
export type GameTick = Tick & { game?: GameBlock; tilt?: [number, number, number]; ros?: { tf: TFMessage } };
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
/** the lead never exceeds this (ms): a step slower than it is simply shown late */
const MAX_LEAD_MS = 80;

export class GameSession {
  readonly client: ArenaClient;
  world: (World & { game: GameInfo }) | null = null;
  private queue: Omit<InputRow, 'tick'>[] = [];
  private inFlight = false;
  private last = 0;
  private timer = 0;
  private sentAt = 0;
  /** G1.13: when the next ordinary tick is due on screen (ms); its step is sent `lead` ms before */
  private due = 0;
  /** whether the tick in flight was started by an input (shown on arrival) */
  private immediate = false;
  /** the last send-to-arrival times (ms), for the lead */
  private latencies: number[] = [];
  /** a tick that arrived before it was due, and its timer */
  private held: { tick: GameTick; ranges: Float32Array; timer: number } | null = null;
  private ev: SessionEvents;
  /** G1.13: called as each tick is handed to the game (timing harnesses only) */
  presentHook: ((tick: GameTick, at: number) => void) | null = null;
  paused = true;
  latched = false;
  /** the last teleop sent (normalised), so a held stick is not re-sent every tick */
  private sent: [number, number] = [0, 0];
  lastTick: GameTick | null = null;
  ticks = 0;

  constructor(world: WorldId, readonly game: GameKind, readonly seed: number, ev: SessionEvents,
    readonly mode: 'phone' | 'full' = 'phone', readonly planner: PlayPlanner = 'astar') {
    this.ev = ev;
    this.client = new ArenaClient({
      onWorld: (w, occ) => { this.world = w as World & { game: GameInfo }; ev.onWorld(this.world, occ); },
      onTick: (t, ranges) => this.arrived(t as GameTick, ranges),
      onError: (stage, m) => { this.inFlight = false; ev.onError(stage, m); },
      onFamily: (msg) => ev.onFamily?.(msg),
    }, { hashVersion: 3, seed: 1, spec: SPEC_FOR[world], game: { game, arg: game === 'fetch_rush' ? seed : 0, ...(game === 'fetch_rush' ? { mode } : {}) } });
  }

  whenReady() { return this.client.whenReady(); }

  /** Start ticking (the setup inputs go on the first tick). */
  start() {
    if (!this.world) return;
    if (this.ticks === 0 && this.queue.length === 0) {
      this.queue.push(...this.world.game.setup);
      // the AUTO planner (src/game/planners.ts): A* is the model's own default and sends nothing,
      // so an A* session is byte-identical to before; another is the run's first input, on record
      if (this.planner !== 'astar') this.queue.push({ kind: 'planner', choice: this.planner });
    }
    this.paused = false;
    this.last = performance.now();
    this.due = this.last;
    // a timer, not the frame loop: the model's pace must not depend on the drawing's frame rate
    clearInterval(this.timer);
    this.timer = window.setInterval(() => this.pump(), 10);
  }

  /**
   * Step when the next tick is due within `lead` ms (0.1 s of wall time per tick), or at
   * once when an input waits.
   */
  private pump() {
    const now = performance.now();
    this.last = now;
    if (this.paused) return;
    if (this.inFlight || this.held && !this.queue.length) return;
    if (this.queue.length) {
      this.flush();
      this.sendStep(now, true);
    } else if (now >= this.due - this.lead()) {
      this.sendStep(now, false);
    }
  }

  private sendStep(now: number, immediate: boolean) {
    this.inFlight = true;
    this.immediate = immediate;
    this.sentAt = now;
    this.client.step(this.queue.splice(0));
  }

  /** The send lead (ms): the 90th percentile of the last 32 send-to-arrival times, plus 5 ms. */
  private lead() {
    if (!this.latencies.length) return 0;
    const s = [...this.latencies].sort((a, b) => a - b);
    return Math.min(MAX_LEAD_MS, s[Math.floor(0.9 * (s.length - 1))] + 5);
  }

  private arrived(t: GameTick, ranges: Float32Array) {
    const now = performance.now();
    this.inFlight = false;
    this.latencies.push(now - this.sentAt);
    if (this.latencies.length > 32) this.latencies.shift();
    if (this.immediate || now >= this.due || this.paused) this.present(t, ranges, now);
    else this.held = { tick: t, ranges, timer: window.setTimeout(() => this.flush(), this.due - now) };
    this.pump();
  }

  /** Hand a held tick to the game now (it is due, or an input needs the next tick). */
  private flush() {
    if (!this.held) return;
    const h = this.held;
    this.held = null;
    clearTimeout(h.timer);
    this.present(h.tick, h.ranges, performance.now());
    this.pump();
  }

  private present(t: GameTick, ranges: Float32Array, now: number) {
    this.lastTick = t;
    this.ticks += 1;
    // the next tick is due 0.1 s after this one was; after an input's tick, or when the model
    // fell behind (slow motion), 0.1 s after now
    this.due = this.immediate || now > this.due + STEP_MS ? now + STEP_MS : this.due + STEP_MS;
    this.immediate = false;
    this.ev.onTick(t, ranges);
    this.presentHook?.(t, now);
  }

  /** How long the tick in flight has taken so far (ms; 0 when none is in flight). */
  stepAge() { return this.inFlight ? performance.now() - this.sentAt : 0; }

  pause() { this.paused = true; }
  resume() { this.paused = false; this.last = performance.now(); this.due = this.last; }

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

  close() { clearInterval(this.timer); if (this.held) clearTimeout(this.held.timer); this.client.close(); }
}
