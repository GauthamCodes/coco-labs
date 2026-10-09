// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena's timeline (M1.7): two tracks over one run.
 *
 * - **World track**: ticks (the model's fixed steps). Every tick the worker
 *   reports is kept, so any past tick can be shown again exactly as it was.
 * - **Computation track**: ``seq`` within the selected tick -- the events of
 *   the search planned at (or most recently before) that tick, revealed or
 *   scrubbed through its PlanStore (keyframed, so seeking is fast).
 *
 * Play / pause / speed drive the WORLD clock: ``frame()`` says when the
 * next model step is due (pausing stops the simulation, not just the
 * view). Watching history never changes the run: the past is replayed from
 * what was recorded, and the model keeps its own state (README 5.2: a run
 * is reproduced from spec + seed + input log, not from the view).
 *
 * Pure: no DOM, no worker, no renderer -- test/session.test.ts drives it.
 */

import { FamilyStore } from './lens/store';
import type { FamilyMessage, PlanInfo, SearchColumns, Tick } from './protocol';
import { PlanStore } from './render/planStore';

export interface TickRecord {
  tick: number; t_world: number; pose: [number, number, number]; truth?: [number, number, number]; v: number; w: number;
  mode: string; hash: string; ranges: Float32Array | null; plans: PlanInfo[];
  /** M2.5: moving bodies (x, y, radius), when the Move pack's actors are out. */
  actors?: [number, number, number][];
}

/** Reveal a live search over about this many frames at speed 1. */
export const REVEAL_FRAMES = 90;
/** Keep ranges for this many recent ticks (poses for all). */
export const KEEP_RANGES = 12_000;
export const SPEEDS = [0.25, 0.5, 1, 2, 4];

export class ArenaSession {
  readonly history: TickRecord[] = [];
  readonly searches = new Map<number, PlanStore>();
  /** M2.2: the whole loop's family batches, by channel and tick (lens/store.ts). */
  readonly families = new FamilyStore();
  /** M2.2: each channel's static header (FilterHeader, ControllerHeader, ...), as the model sent it. */
  readonly headers = new Map<string, Record<string, unknown>>();
  /** M2.5: a global path handed to the robot whole (a Lab 5 scenario's frozen path), from the tick it was given. */
  readonly givenPaths: { tick: number; xy: number[] }[] = [];
  /** Search started at each tick (tick -> search ids), for the computation track. */
  private searchesAt: [number, number][] = [];
  /** null: follow the live head. Otherwise the tick being shown. */
  viewTick: number | null = null;
  /** null: follow the reveal. Otherwise the event count being shown. */
  viewSeq: number | null = null;
  playing = true;
  speed = 1;
  private clockMs = 0;

  constructor(readonly width: number, readonly height: number, readonly dt: number) {}

  /** A family batch or header from the model (M2.2). */
  onFamily(m: FamilyMessage) {
    if (m.header) { this.headers.set(m.channel, m.header); return; }
    if (m.columns && m.tick !== undefined) {
      this.families.add({ channel: m.channel, tick: m.tick, columns: m.columns, scalars: m.scalars ?? {} });
    }
  }

  // -- input from the worker -------------------------------------------------

  onTick(t: Tick, ranges: Float32Array) {
    this.history.push({ tick: t.tick, t_world: t.t_world, pose: t.pose, truth: t.truth, v: t.v, w: t.w, mode: t.mode, hash: t.hash,
      ranges, plans: t.plans, actors: t.actors });
    if (t.path) this.givenPaths.push({ tick: t.tick, xy: t.path });
    const drop = this.history.length - 1 - KEEP_RANGES;
    if (drop >= 0) this.history[drop].ranges = null;
  }

  onPlanBatch(meta: { search_id: number; planner: string; tick: number; final: boolean; cancelled?: boolean }, cols: SearchColumns) {
    if (meta.cancelled) {
      // M2.0: an input joined this search's tick and the model dropped it; so does the track
      this.searches.delete(meta.search_id);
      this.searchesAt = this.searchesAt.filter(([, sid]) => sid !== meta.search_id);
      return;
    }
    let s = this.searches.get(meta.search_id);
    if (!s) {
      s = new PlanStore(this.width, this.height);
      s.begin(meta.search_id, meta.planner);
      this.searches.set(meta.search_id, s);
      // a plan made at the START of tick k belongs to the tick it produces (k + 1)
      this.searchesAt.push([meta.tick + 1, meta.search_id]);
    }
    s.append(cols, meta.final);
    if (s.cursor === 0 && this.viewSeq === null) s.advance(1);
  }

  // -- what is shown -----------------------------------------------------------

  get head(): number {
    return this.history.length ? this.history[this.history.length - 1].tick : 0;
  }

  get live(): boolean {
    return this.viewTick === null;
  }

  /** The tick being shown. */
  get shownTick(): TickRecord | null {
    if (!this.history.length) return null;
    if (this.viewTick === null) return this.history[this.history.length - 1];
    return this.recordAt(this.viewTick);
  }

  recordAt(tick: number): TickRecord | null {
    const first = this.history[0]?.tick ?? 0;
    return this.history[tick - first] ?? null;
  }

  /**
   * The search on the computation track: the latest planned at or before
   * the shown tick. Live, that includes the search being computed NOW for
   * the tick in progress (head + 1), which streams in while the model is
   * still planning; waiting for its tick would hide it until the whole
   * search had finished (measured, M1.10).
   */
  get shownSearch(): PlanStore | null {
    const at = this.viewTick === null ? this.head + 1 : this.shownTick?.tick ?? 0;
    let id: number | null = null;
    for (const [k, sid] of this.searchesAt) if (k <= at) id = sid;
    if (id === null && this.viewTick === null && this.searchesAt.length) id = this.searchesAt[this.searchesAt.length - 1][1];
    return id === null ? null : this.searches.get(id) ?? null;
  }

  // -- controls ----------------------------------------------------------------

  /** World track: show tick ``k`` (clamped); at the head, follow live again. */
  seekTick(k: number) {
    const first = this.history[0]?.tick ?? 0;
    const t = Math.max(first, Math.min(Math.round(k), this.head));
    this.viewTick = t >= this.head ? null : t;
    // a tick's computation is shown complete unless the learner scrubs it
    this.viewSeq = null;
    const s = this.shownSearch;
    if (s && this.viewTick !== null) s.seek(s.received);
  }

  stepTick(d: number) {
    this.playing = false;
    this.seekTick((this.shownTick?.tick ?? 0) + d);
  }

  /** Computation track: show the first ``n`` events of the shown search. */
  seekSeq(n: number) {
    const s = this.shownSearch;
    if (!s) return;
    const t = Math.max(0, Math.min(Math.round(n), s.received));
    this.viewSeq = t;
    s.seek(t);
  }

  stepSeq(d: number) {
    const s = this.shownSearch;
    if (!s) return;
    this.playing = false;
    this.seekSeq((this.viewSeq ?? s.cursor) + d);
  }

  goLive() {
    this.viewTick = null;
    this.viewSeq = null;
    this.playing = true;
    const s = this.shownSearch;
    if (s) s.seek(s.received);
  }

  setSpeed(v: number) {
    this.speed = SPEEDS.includes(v) ? v : 1;
  }

  /**
   * Advance the view by one animation frame of ``frameMs`` wall time.
   * Returns how many model steps are due now (0 when paused or replaying).
   */
  frame(frameMs: number): number {
    // reveal the shown search at a pace tied to the speed
    const s = this.shownSearch;
    if (s && this.viewSeq === null && s.cursor < s.received && this.playing) {
      s.advance(s.cursor + Math.max(1, Math.ceil((s.received / REVEAL_FRAMES) * this.speed)));
    }
    if (!this.playing) return 0;
    if (this.viewTick !== null) {
      // replaying history: walk the world track forward at speed, then rejoin live
      this.clockMs += frameMs * this.speed;
      const ticks = Math.floor(this.clockMs / (this.dt * 1000));
      if (ticks > 0) {
        this.clockMs -= ticks * this.dt * 1000;
        this.seekTick(this.viewTick + ticks);
      }
      return 0;
    }
    this.clockMs += frameMs * this.speed;
    const due = Math.floor(this.clockMs / (this.dt * 1000));
    this.clockMs -= due * this.dt * 1000;
    return Math.min(due, 4); // never more than 4 steps owed after a stall
  }
}
