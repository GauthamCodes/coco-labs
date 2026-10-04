// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Display arithmetic for Lab 2. Nothing here localises: it places what a
 * coco_lab trace already contains (an estimate, its covariance, a measured
 * scan) on the canvas, and reads a run's summary for the reveal.
 */

import type { DecodedLocBundle, LocRun } from './decode';
import { beamAngles } from './decode';

/** Okabe-Ito, as Lab 1 (src/render/palette.ts). */
export const RUN_STYLE: Record<string, { color: string; label: string; what: string }> = {
  mcl: { color: '#E69F00', label: 'MCL (your settings)',
    what: 'Monte Carlo localisation: a cloud of guesses, reweighted by every scan' },
  mcl_coco: { color: '#CC79A7', label: 'MCL, injection off (as COCO ships AMCL)',
    what: 'the same particle filter with recovery_alpha_slow/fast = 0' },
  ekf: { color: '#009E73', label: 'EKF',
    what: 'one Gaussian: a mean and a covariance ellipse' },
};
export const TRUTH_COLOR = '#0072B2';

export function runStyle(id: string) {
  return RUN_STYLE[id] ?? { color: '#000000', label: id, what: '' };
}

/**
 * The 2-sigma ellipse of a 2x2 covariance: semi-axes and rotation.
 * (The eigen-decomposition of [[a, b], [b, c]] -- geometry for drawing.)
 */
export function ellipse(a: number, b: number, c: number, k = 2): { rx: number; ry: number; angle: number } {
  const tr = (a + c) / 2;
  const det = Math.sqrt(Math.max(0, ((a - c) / 2) ** 2 + b * b));
  const l1 = Math.max(0, tr + det);
  const l2 = Math.max(0, tr - det);
  const angle = Math.abs(b) < 1e-15 ? (a >= c ? 0 : Math.PI / 2) : Math.atan2(l1 - a, b);
  return { rx: k * Math.sqrt(l1), ry: k * Math.sqrt(l2), angle };
}

/**
 * Where update `k`'s measured scan lands if the robot is at `pose`
 * (base_footprint): the sensor's mount, then each beam's measured range.
 * Drawn from the belief, a wrong pose shows as endpoints off the walls.
 */
export function scanEndpoints(b: DecodedLocBundle, k: number, pose: [number, number, number],
  every = 1): Array<[number, number]> {
  const l = b.scenario.lidar;
  const angles = beamAngles(l);
  const [x, y, th] = pose;
  const [mx, my, myaw] = l.mount;
  const c = Math.cos(th);
  const s = Math.sin(th);
  const sx = x + c * mx - s * my;
  const sy = y + s * mx + c * my;
  const out: Array<[number, number]> = [];
  const nb = b.world.nBeams;
  for (let i = 0; i < nb; i += every) {
    const r = b.world.ranges[k * nb + i];
    if (!Number.isFinite(r)) continue;
    const a = th + myaw + angles[i];
    out.push([sx + r * Math.cos(a), sy + r * Math.sin(a)]);
  }
  return out;
}

export function estimateAt(run: LocRun, k: number): [number, number, number] {
  return [run.cols.est_x[k], run.cols.est_y[k], run.cols.est_yaw[k]];
}

export function truthAtUpdate(b: DecodedLocBundle, k: number): [number, number, number] {
  const r = b.world.updates[k];
  return [b.world.gtX[r], b.world.gtY[r], b.world.gtYaw[r]];
}

/** The update index of the kidnap (first update at or after it), or null. */
export function kidnapUpdate(b: DecodedLocBundle): number | null {
  const kr = b.world.kidnapRow;
  if (kr === null) return null;
  const u = b.world.updates;
  for (let i = 0; i < u.length; i++) if (u[i] >= kr) return i;
  return null;
}

// -- predict, then reveal ---------------------------------------------------------

export type Answer = 'yes' | 'no';

export interface LocQuestion {
  runId: string;
  text: string;
}

/** What to ask before a run: one question per filter, about its outcome. */
export function questions(b: DecodedLocBundle): LocQuestion[] {
  const kidnap = b.world.kidnapRow !== null;
  const global = b.runs.some((r) => r.params.init === 'global');
  return b.runs.map((r) => ({
    runId: r.id,
    text: kidnap
      ? `Will ${runStyle(r.id).label} find the robot again after the kidnap?`
      : global
        ? `Will ${runStyle(r.id).label} find the robot from nowhere?`
        : `Will ${runStyle(r.id).label} stay within 0.5 m of the robot the whole way?`,
  }));
}

/** The answer coco_lab's summary gives to that question. */
export function outcome(b: DecodedLocBundle, run: LocRun): Answer {
  const s = run.summary;
  if (b.world.kidnapRow !== null) return s.recovered ? 'yes' : 'no';
  if (run.params.init === 'global') return s.converged_s !== null ? 'yes' : 'no';
  return s.max_err_xy !== null && s.max_err_xy < s.ok_xy ? 'yes' : 'no';
}

export function outcomeText(b: DecodedLocBundle, run: LocRun): string {
  const s = run.summary;
  const f = (v: number | null, d = 1) => (v === null ? '—' : v.toFixed(d));
  if (b.world.kidnapRow !== null) {
    return s.recovered
      ? `recovered ${f(s.recovery_s)} s after the kidnap (final error ${f(s.final_err_xy, 2)} m)`
      : `did not recover (final error ${f(s.final_err_xy, 2)} m)`;
  }
  if (run.params.init === 'global') {
    return s.converged_s !== null ? `converged at t = ${f(s.converged_s)} s` : `never converged (final error ${f(s.final_err_xy, 2)} m)`;
  }
  return `worst error ${f(s.max_err_xy, 2)} m, mean ${f(s.mean_err_xy, 2)} m`;
}
