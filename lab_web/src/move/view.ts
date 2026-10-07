// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 5's display helpers: where things were at a time, and what the robot's
 * map held at a step. Bookkeeping over decoded bundles -- nothing here plans,
 * controls or scores; every plan, candidate and metric on the page came from
 * Nav2 (recorded) or coco_lab (computed).
 */

import type { DecodedReplanBundle, DriveRun, Rollouts } from './decode';
import { REPLAN_KINDS } from './decode';

/** The index of the last row (of `width` columns, time first) with t <= `t`; -1 if none. */
export function rowAt(series: Float64Array, width: number, t: number): number {
  let lo = 0;
  let hi = series.length / width - 1;
  if (hi < 0 || series[0] > t) return -1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (series[mid * width] <= t) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

/** The index of the last entry of a sorted time array with t <= `t`; -1 if none. */
export function indexAt(times: Float64Array, t: number): number {
  return rowAt(times, 1, t);
}

/** The row's values (without its time), or null. */
export function valuesAt(series: Float64Array, width: number, t: number): number[] | null {
  const i = rowAt(series, width, t);
  return i < 0 ? null : Array.from(series.subarray(i * width + 1, (i + 1) * width));
}

/** An actor track (t, x, y, yaw rows) linearly interpolated at `t`; null outside it (never extrapolated). */
export function trackAt(track: Float64Array, t: number): [number, number] | null {
  const n = track.length / 4;
  if (!n || t < track[0] || t > track[(n - 1) * 4]) return null;
  const i = rowAt(track, 4, t);
  if (i === n - 1 || track[i * 4] === t) return [track[i * 4 + 1], track[i * 4 + 2]];
  const f = (t - track[i * 4]) / (track[(i + 1) * 4] - track[i * 4]);
  return [track[i * 4 + 1] + f * (track[(i + 1) * 4 + 1] - track[i * 4 + 1]),
    track[i * 4 + 2] + f * (track[(i + 1) * 4 + 2] - track[i * 4 + 2])];
}

/** The footprint rectangle's corners at a pose (0.297 x 0.314 m, centred). Drawing only. */
export function footprint(x: number, y: number, yaw: number, size: [number, number] = [0.297, 0.314]): Array<[number, number]> {
  const [hl, hw] = [size[0] / 2, size[1] / 2];
  const c = Math.cos(yaw);
  const s = Math.sin(yaw);
  return ([[hl, hw], [-hl, hw], [-hl, -hw], [hl, -hw]] as const)
    .map(([px, py]) => [x + c * px - s * py, y + s * px + c * py] as [number, number]);
}

export interface Candidate { pts: Array<[number, number]>; valid: boolean | null; best: boolean; total: number }

/** The rollout frame at or before `t` (within `maxAge` seconds), as drawable candidates. */
export function candidatesAt(ro: Rollouts | null, t: number, maxAge = 1.5):
  { t: number; n: number; nValid: number | null; cands: Candidate[] } | null {
  if (!ro) return null;
  const f = indexAt(ro.t, t);
  if (f < 0 || t - ro.t[f] > maxAge) return null;
  const cands: Candidate[] = [];
  for (let c = ro.coff[f]; c < ro.coff[f + 1]; c++) {
    const pts: Array<[number, number]> = [];
    for (let p = ro.poff[c]; p < ro.poff[c + 1]; p++) pts.push([ro.pts[2 * p], ro.pts[2 * p + 1]]);
    const fl = ro.flags[c];
    cands.push({ pts, valid: (fl & 3) === 2 ? null : (fl & 1) === 1, best: (fl & 4) === 4, total: ro.total[c] });
  }
  return { t: ro.t[f], n: ro.n[2 * f], nValid: ro.n[2 * f + 1] < 0 ? null : ro.n[2 * f + 1], cands };
}

/** The controller's chosen trajectory at or before `t`. */
export function chosenAt(run: DriveRun, t: number): Array<[number, number]> | null {
  const i = indexAt(run.chosenT, t);
  if (i < 0) return null;
  const out: Array<[number, number]> = [];
  for (let p = run.chosenOff[i]; p < run.chosenOff[i + 1]; p++) out.push([run.chosenPts[2 * p], run.chosenPts[2 * p + 1]]);
  return out;
}

/** DWB's candidate counts at or before `t`: [n, n_valid], or null. */
export function evalAt(run: DriveRun, t: number): [number, number] | null {
  const v = valuesAt(run.eval, 3, t);
  return v ? [v[0], v[1]] : null;
}

const MONITOR = ['none', 'stop', 'slowdown', 'approach', 'limit'];

/** The collision monitor's state at `t`, in words. */
export function monitorAt(run: DriveRun, t: number): string {
  let state = 'none';
  let poly = '';
  for (const [tm, action, name] of run.monitor) {
    if (tm > t) break;
    state = MONITOR[action] ?? String(action);
    poly = name;
  }
  return state === 'none' ? 'not acting' : `${state} (${poly})`;
}

// -- replanning ------------------------------------------------------------------

/** The robot's cell at step `k`. */
export function robotAt(b: DecodedReplanBundle, k: number): [number, number] {
  const i = Math.max(0, Math.min(k, b.walk.length / 2 - 1));
  return [b.walk[2 * i], b.walk[2 * i + 1]];
}

/** The steps the robot took (walk length - 1). */
export function steps(b: DecodedReplanBundle): number {
  return b.walk.length / 2 - 1;
}

/** The index of the round in force at step `k` (the last made at or before it). */
export function roundAt(b: DecodedReplanBundle, k: number): number {
  let r = 0;
  for (let i = 0; i < b.rounds.length; i++) if (b.rounds[i].step <= k) r = i;
  return r;
}

/** The remaining plan at step `k`: the round's path from where the robot now stands. */
export function planAt(b: DecodedReplanBundle, k: number): Array<[number, number]> {
  const r = b.rounds[roundAt(b, k)];
  const from = Math.max(0, k - r.step);
  const out: Array<[number, number]> = [];
  for (let i = r.path_offset + from; i < r.path_offset + r.path_len; i++) out.push([b.paths[2 * i], b.paths[2 * i + 1]]);
  return out;
}

/** The world's occupancy at step `k`: the initial truth with the schedule applied up to `k`. */
export function truthAt(b: DecodedReplanBundle, k: number): Uint8Array {
  const t = b.truth.slice();
  for (const [step, cells] of b.world.schedule) {
    if (step > k) break;
    for (const [r, c, blocked] of cells) t[r * b.world.width + c] = blocked ? 1 : 0;
  }
  return t;
}

/** The robot's MAP at step `k`: what it started with, plus what it had sensed by then. */
export function knownAt(b: DecodedReplanBundle, k: number): Uint8Array {
  const m = b.known.slice();
  for (const r of b.rounds) {
    if (r.step > k) break;
    const truth = truthAt(b, r.step);
    for (const [row, col] of r.changed) m[row * b.world.width + col] = truth[row * b.world.width + col];
  }
  return m;
}

/** The cells a round popped (expanded or raised), each once, in order. */
export function expandedIn(b: DecodedReplanBundle, round: number): Array<[number, number]> {
  const seen = new Set<number>();
  const out: Array<[number, number]> = [];
  const { kind, row, col } = b.trace;
  const e = REPLAN_KINDS.indexOf('expand');
  const r = REPLAN_KINDS.indexOf('raise');
  for (let i = 0; i < b.trace.n; i++) {
    if (b.trace.round[i] !== round || (kind[i] !== e && kind[i] !== r)) continue;
    const key = row[i] * b.world.width + col[i];
    if (!seen.has(key)) {
      seen.add(key);
      out.push([row[i], col[i]]);
    }
  }
  return out;
}

export const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined || !Number.isFinite(v) ? '—' : v.toFixed(d));
