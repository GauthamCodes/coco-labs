// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The quiet Live probe: ask /healthz, back off while nothing answers, and
 * open the coco.v1 socket only after a coco.v1 server has answered.
 *
 * Why the socket waits: a WebSocket to a port nobody listens on is a
 * console error in every browser, on every reconnect attempt. A /healthz
 * fetch to a dead endpoint is ALSO a console error in Chromium (measured:
 * "Failed to load resource: net::ERR_CONNECTION_REFUSED", and
 * "...ERR_NAME_NOT_RESOLVED" for an unresolvable host), so the page only
 * probes an endpoint someone asked for: the `?live=` link, Connect, Watch,
 * or the scheduled demo's endpoint while a demo is on (LiveView.tsx).
 *
 * Retries run only while the view is open: `stop()` on unmount cancels the
 * pending timer, and a result that lands after `stop()` is dropped.
 */

import { check, type CheckResult, type FetchLike } from './status';

export interface Timers {
  setTimeout(fn: () => void, ms: number): unknown;
  clearTimeout(handle: unknown): void;
  now(): number;
}

const REAL: Timers = {
  setTimeout: (fn, ms) => setTimeout(fn, ms),
  clearTimeout: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
  now: () => Date.now(),
};

/** First retry after 2 s, doubling, capped at 30 s: 2, 4, 8, 16, 30, 30, … */
export const RETRY_FIRST_MS = 2000;
export const RETRY_CAP_MS = 30_000;
/** Once an endpoint answers, a watch that keeps going re-asks this often (the v1 card's rate). */
export const REFRESH_MS = 30_000;

/** The wait after the `failures`-th consecutive failure (failures ≥ 1). */
export function retryDelayMs(failures: number): number {
  return Math.min(RETRY_CAP_MS, RETRY_FIRST_MS * 2 ** Math.max(0, failures - 1));
}

/** One finished check, as the page shows it. */
export interface ProbeReport extends CheckResult {
  /** Wall-clock ms when the answer (or the failure) arrived. */
  at: number;
  /** Consecutive failures so far (0 after an answer). */
  failures: number;
  /** When the next check runs, or null if this watch has finished. */
  nextInMs: number | null;
}

export class HealthWatch {
  private timer: unknown = null;
  private stopped = true;
  private failures = 0;

  constructor(
    private readonly run: () => Promise<CheckResult>,
    private readonly report: (r: ProbeReport) => void,
    private readonly opts: { stopOnReachable?: boolean; refreshMs?: number } = {},
    private readonly timers: Timers = REAL,
  ) {}

  /** Check now, then keep checking on the schedule above. */
  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    this.failures = 0;
    void this.tick();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer != null) this.timers.clearTimeout(this.timer);
    this.timer = null;
  }

  get running(): boolean { return !this.stopped; }

  private async tick(): Promise<void> {
    this.timer = null;
    let r: CheckResult;
    try {
      r = await this.run();
    } catch {
      r = { reachable: false, verdict: { state: 'offline', why: 'the check failed' } };
    }
    if (this.stopped) return;
    let next: number | null;
    if (r.reachable) {
      this.failures = 0;
      next = this.opts.stopOnReachable ? null : (this.opts.refreshMs ?? REFRESH_MS);
    } else {
      this.failures += 1;
      next = retryDelayMs(this.failures);
    }
    if (next == null) this.stopped = true;
    else this.timer = this.timers.setTimeout(() => void this.tick(), next);
    this.report({ ...r, at: this.timers.now(), failures: this.failures, nextInMs: next });
  }
}

/**
 * Probe `ws`'s /healthz until a coco.v1 server answers, then call `open()`
 * once (the Live tab creates and connects its LiveClient there, exactly as
 * before). Returns the cancel function.
 */
export function openWhenReachable(
  ws: string, fetchFn: FetchLike, open: () => void, onReport: (r: ProbeReport) => void, timers: Timers = REAL,
): () => void {
  const w = new HealthWatch(() => check(ws, fetchFn), (r) => {
    onReport(r);
    if (r.reachable) open();
  }, { stopOnReachable: true }, timers);
  w.start();
  return () => w.stop();
}
