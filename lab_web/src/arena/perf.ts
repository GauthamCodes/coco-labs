// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * What `?perf` shows (M1.5): load timings, frame rate, event throughput and
 * step cost -- so Gautham can measure on his phone without remote DevTools
 * (docs/v2/PHONE_MEASURE.md). Plain numbers, measured here; nothing is
 * estimated. `window.__cocoPerf` exposes the same store to the harnesses.
 */

import { wallMs } from './protocol';

export interface PerfSnapshot {
  navStart: number;
  marks: Record<string, number>;        // wall ms
  fps: number;                          // rAF frames in the last second
  frameMsP95: number;
  eventsReceived: number;
  eventsPerSecond: number;              // over the last second
  firstPlanBatchAt: number | null;
  ticks: number;
  stepMsMedian: number | null;
  goalToFrontierMs: number[];
}

class Perf {
  readonly navStart = performance.timeOrigin;
  readonly marks: Record<string, number> = {};
  private frames: number[] = [];
  private eventTimes: [number, number][] = [];
  eventsReceived = 0;
  firstPlanBatchAt: number | null = null;
  private steps: number[] = [];
  private listeners = new Set<() => void>();

  mark(name: string, at: number) {
    if (!(name in this.marks)) this.marks[name] = at;
    this.emit();
  }

  /** Resolves once the mark `name` exists (at once if it already does). */
  when(name: string): Promise<number> {
    if (name in this.marks) return Promise.resolve(this.marks[name]);
    return new Promise((resolve) => {
      const check = () => {
        if (name in this.marks) { this.listeners.delete(check); resolve(this.marks[name]); }
      };
      this.listeners.add(check);
    });
  }

  frame(now = wallMs()) {
    this.frames.push(now);
    while (this.frames.length && now - this.frames[0] > 1000) this.frames.shift();
  }

  planBatch(rows: number, at: number) {
    this.eventsReceived += rows;
    this.eventTimes.push([at, rows]);
    if (this.firstPlanBatchAt === null) this.firstPlanBatchAt = at;
    this.emit();
  }

  /**
   * Goal click -> the frame that first DRAWS that goal's search's frontier.
   * The search on screen at the click is remembered: until a DIFFERENT
   * search is drawn, the old one's frames do not count.
   */
  readonly goalToFrontier: number[] = [];
  private goalAt: number | null = null;
  private goalPrevSearch: number | null = null;
  /** Every goal click, and the first frame that drew each search (for the harnesses). */
  readonly goalClicks: number[] = [];
  readonly firstDraw = new Map<number, number>();
  goalSent(at = wallMs(), shownSearch: number | null = null) {
    this.goalAt = at;
    this.goalPrevSearch = shownSearch;
    this.goalClicks.push(at);
  }
  frontierDrawn(searchId: number, at = wallMs()) {
    if (!this.firstDraw.has(searchId)) this.firstDraw.set(searchId, at);
    if (this.goalAt === null || searchId === this.goalPrevSearch) return;
    this.goalToFrontier.push(at - this.goalAt);
    this.goalAt = null;
    this.emit();
  }

  tick(stepMs: number) {
    this.steps.push(stepMs);
    if (this.steps.length > 600) this.steps.splice(0, 300);
  }

  snapshot(): PerfSnapshot {
    const now = wallMs();
    const recent = this.eventTimes.filter(([t]) => now - t <= 1000);
    const gaps = this.frames.slice(1).map((t, i) => t - this.frames[i]).sort((a, b) => a - b);
    const s = [...this.steps].sort((a, b) => a - b);
    return {
      navStart: this.navStart,
      marks: { ...this.marks },
      fps: this.frames.length,
      frameMsP95: gaps.length ? gaps[Math.min(gaps.length - 1, Math.floor(gaps.length * 0.95))] : 0,
      eventsReceived: this.eventsReceived,
      eventsPerSecond: recent.reduce((n, [, r]) => n + r, 0),
      firstPlanBatchAt: this.firstPlanBatchAt,
      ticks: this.steps.length,
      stepMsMedian: s.length ? s[s.length >> 1] : null,
      goalToFrontierMs: [...this.goalToFrontier],
    };
  }

  subscribe(f: () => void) {
    this.listeners.add(f);
    return () => this.listeners.delete(f);
  }

  private emit() {
    for (const f of this.listeners) f();
  }
}

export const perf = new Perf();

declare global {
  interface Window { __cocoPerf?: Perf }
}
if (typeof window !== 'undefined') window.__cocoPerf = perf;
