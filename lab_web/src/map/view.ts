// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Display arithmetic for Lab 3. Nothing here maps or localises: it places
 * what a coco_lab map bundle already contains (estimates, scans, particles,
 * landmarks, graph edges, map snapshots, scores) on the canvas.
 */

import type { DecodedSlamBundle, ExternalRun, SlamRun } from './decode';
import { beamAngles } from './decode';

/** Okabe-Ito, as Labs 1 and 2. */
export const RUN_STYLE: Record<string, { color: string; label: string; what: string }> = {
  known: { color: '#0072B2', label: 'Known poses', what: 'occupancy mapping at the TRUE poses: what the map would be if localisation were solved' },
  odometry: { color: '#999999', label: 'Odometry only', what: 'the same mapping at the dead-reckoned poses: why SLAM exists' },
  ekf_slam: { color: '#009E73', label: 'EKF-SLAM (idealised landmarks)', what: 'one Gaussian over the pose and every landmark, on an IDEALISED landmark sensor' },
  fastslam: { color: '#E69F00', label: 'FastSLAM', what: 'a particle filter over trajectories; every particle carries its own map' },
  pose_graph: { color: '#CC79A7', label: 'Pose graph', what: 'scan matching between poses, loop closures, and an optimiser over the whole graph' },
  pose_graph_noloop: { color: '#D55E00', label: 'Pose graph, loop closure off', what: 'the same pose graph, never closing a loop' },
  slam_toolbox_loop: { color: '#56B4E9', label: 'slam_toolbox', what: "ROS 2's slam_toolbox (Karto), the project's configuration" },
  slam_toolbox_noloop: { color: '#3A96CF', label: 'slam_toolbox, loop closing off', what: 'the same, do_loop_closing false' },
  cartographer_loop: { color: '#F0E442', label: 'Cartographer', what: "Google Cartographer's released 2D configuration" },
  cartographer_noloop: { color: '#B8A800', label: 'Cartographer, global SLAM off', what: 'the same, optimize_every_n_nodes 0' },
};
export const TRUTH_COLOR = '#0072B2';

export function runStyle(id: string) {
  return RUN_STYLE[id] ?? { color: '#000000', label: id, what: '' };
}

export type Pose = [number, number, number];

export function estimateAt(run: SlamRun, k: number): Pose {
  return [run.cols.est_x[k], run.cols.est_y[k], run.cols.est_yaw[k]];
}

/** The trajectory as the algorithm finally believes it (revised where it revises). */
export function finalAt(run: SlamRun, k: number): Pose {
  const a = run.arrays;
  if ('final.x' in a) return [a['final.x'][k], a['final.y'][k], a['final.yaw'][k]];
  return estimateAt(run, k);
}

export function truthAtUpdate(b: DecodedSlamBundle, k: number): Pose {
  const r = b.world.updates[k];
  return [b.world.gtX[r], b.world.gtY[r], b.world.gtYaw[r]];
}

/** Move a pose by a rigid 2D alignment [tx, ty, theta] (for drawing an external run). */
export function aligned(T: [number, number, number], p: Pose): Pose {
  const c = Math.cos(T[2]);
  const s = Math.sin(T[2]);
  return [T[0] + c * p[0] - s * p[1], T[1] + s * p[0] + c * p[1], p[2] + T[2]];
}

export function externalAt(e: ExternalRun, k: number): Pose {
  return aligned(e.summary.ate_online.alignment, [e.estX[k], e.estY[k], e.estYaw[k]]);
}

/** Where update `k`'s measured scan lands if the robot is at `pose`. */
export function scanEndpoints(b: DecodedSlamBundle, k: number, pose: Pose, every = 1): Array<[number, number]> {
  const l = b.world.lidar;
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

/** The idealised sensor's observations at update `k`: [landmark id, range, bearing]. */
export function observationsAt(b: DecodedSlamBundle, k: number): Array<[number, number, number]> {
  const w = b.world;
  const out: Array<[number, number, number]> = [];
  for (let i = w.obsOffset[k]; i < w.obsOffset[k + 1]; i++) out.push([w.obsId[i], w.obsR[i], w.obsB[i]]);
  return out;
}

/** EKF-SLAM's landmark estimates at update `k`: [id, x, y, cxx, cxy, cyy]. */
export function landmarksAt(run: SlamRun, k: number): Array<[number, number, number, number, number, number]> {
  const a = run.arrays;
  if (!('lm.offset' in a)) return [];
  const off = a['lm.offset'];
  const out: Array<[number, number, number, number, number, number]> = [];
  for (let i = off[k]; i < off[k + 1]; i++) {
    out.push([a['lm.id'][i], a['lm.x'][i], a['lm.y'][i], a['lm.cxx'][i], a['lm.cxy'][i], a['lm.cyy'][i]]);
  }
  return out;
}

/** FastSLAM's weighted particles at update `k`. */
export function particlesAt(run: SlamRun, k: number): Array<[number, number, number]> {
  const a = run.arrays;
  if (!('particles.offset' in a)) return [];
  const off = a['particles.offset'];
  const out: Array<[number, number, number]> = [];
  for (let i = off[k]; i < off[k + 1]; i++) out.push([a['particles.x'][i], a['particles.y'][i], a['particles.w'][i]]);
  return out;
}

/** The pose graph's edges whose newer node is at or before update `k`. */
export function edgesUpTo(run: SlamRun, k: number): Array<{ i: number; j: number; kind: 'odom' | 'icp' | 'loop' }> {
  const a = run.arrays;
  if (!('edges.i' in a)) return [];
  const kinds = (run.header.edge_kinds as string[]) ?? ['odom', 'icp', 'loop'];
  const out: Array<{ i: number; j: number; kind: 'odom' | 'icp' | 'loop' }> = [];
  for (let e = 0; e < a['edges.i'].length; e++) {
    const j = a['edges.j'][e];
    if (j <= k) out.push({ i: a['edges.i'][e], j, kind: kinds[a['edges.kind'][e]] as 'odom' | 'icp' | 'loop' });
  }
  return out;
}

/** The ellipse of a 2x2 covariance (k sigma): semi-axes and rotation, for drawing. */
export function ellipse(a: number, b: number, c: number, k = 2): { rx: number; ry: number; angle: number } {
  const tr = (a + c) / 2;
  const det = Math.sqrt(Math.max(0, ((a - c) / 2) ** 2 + b * b));
  const l1 = Math.max(0, tr + det);
  const l2 = Math.max(0, tr - det);
  const angle = Math.abs(b) < 1e-15 ? (a >= c ? 0 : Math.PI / 2) : Math.atan2(l1 - a, b);
  return { rx: k * Math.sqrt(l1), ry: k * Math.sqrt(l2), angle };
}

/**
 * RGBA for an OccupancyGrid snapshot (north row first): grey by P(occupied),
 * 255 (never observed) as the "unknown" tint. Colours only -- the thresholds
 * that score a map are coco_lab's.
 */
export function occupancyRGBA(cells: Uint8Array): Uint8ClampedArray {
  const out = new Uint8ClampedArray(cells.length * 4);
  for (let i = 0; i < cells.length; i++) {
    const v = cells[i];
    let g: number;
    let a = 255;
    if (v === 255) { g = 236; a = 0; } else g = Math.round(250 - 2.3 * v);
    out[4 * i] = g; out[4 * i + 1] = g; out[4 * i + 2] = g; out[4 * i + 3] = a;
  }
  return out;
}

/** The truth map, faint: its walls as a light tint (the learner's reference). */
export function truthRGBA(occ: Uint8Array): Uint8ClampedArray {
  const out = new Uint8ClampedArray(occ.length * 4);
  for (let i = 0; i < occ.length; i++) {
    const wall = occ[i] === 1;
    out[4 * i] = wall ? 150 : 246; out[4 * i + 1] = wall ? 186 : 246;
    out[4 * i + 2] = wall ? 222 : 243; out[4 * i + 3] = 255;
  }
  return out;
}

/** coco_lab's map-vs-truth classes (mapeval.diff_raster): found, false, missed. */
export const DIFF_COLORS: Record<number, [number, number, number]> = {
  1: [0, 158, 115], 2: [213, 94, 0], 3: [86, 180, 233],
};

export function diffRGBA(diff: Uint8Array): Uint8ClampedArray {
  const out = new Uint8ClampedArray(diff.length * 4);
  for (let i = 0; i < diff.length; i++) {
    const c = DIFF_COLORS[diff[i]];
    if (!c) continue;
    out[4 * i] = c[0]; out[4 * i + 1] = c[1]; out[4 * i + 2] = c[2]; out[4 * i + 3] = 255;
  }
  return out;
}

/** The challenge's documented score: round(100 x F1), from coco_lab's summary. */
export function challengeScore(f1: number): number {
  return Math.round(100 * f1);
}

export const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? '—' : v.toFixed(d));
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${(100 * v).toFixed(0)} %`);
