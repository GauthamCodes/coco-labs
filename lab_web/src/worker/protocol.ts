// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Messages between the page and the Pyodide worker. Bytes in, bytes out. */

/** One brush stroke: the cells it covered, all set to one value. */
export interface Stroke {
  value: 'occupied' | 'free';
  cells: Array<[number, number]>; // [row, col]
}

/** The inputs of one search the page asks coco_lab to run. */
export interface RunSettings {
  algorithm: string;
  heuristic: string;
  weight: number | null; // only for weighted_astar
  tie_break: string;
}

/** What to do to the current bundle (see src/worker/recompute.py). */
export interface RecomputeSpec {
  strokes: Stroke[];
  connectivity: 4 | 8 | null; // null: the bundle's own
  runs: RunSettings[] | null; // null: rerun the bundle's own settings; else 1-4
  optimal: boolean; // also run coco_lab's Dijkstra for the optimum
}

/**
 * Lab 2: the learner's localisation settings. coco_lab simulates ONE Sketch
 * world from the current bundle's scenario with these and runs every
 * filter on it (src/worker/recompute.py `localise`).
 */
export interface LocSpec {
  particles: number; // 10..2000
  motion_noise: number; // x Sketch's default odometry alphas (world AND filters), 0..5
  sensor_sigma: number; // range noise, metres, 0..0.5
  injection: 'none' | 'augmented' | 'fixed';
  alpha_slow: number;
  alpha_fast: number;
  inject_fraction: number; // 0..0.5
  init: 'tracking' | 'global';
  kidnap: { t: number; to: [number, number, number] } | null;
  seed: number; // the world's
  filter_seed: number; // the particle filter's
}

export interface RecomputeRequest {
  id: number;
  /** 'recompute': Lab 1's search glue; 'localise': Lab 2's (recompute.py `localise`). */
  type: 'recompute' | 'localise';
  /** The CURRENT bundle's files, byte for byte. */
  manifest: Uint8Array;
  arraysName: string;
  arraysFile: Uint8Array;
  spec: RecomputeSpec | LocSpec;
  /** Absolute URL of coco_lab's wheel on this site, and its sha256. */
  wheelUrl: string;
  wheelSha256: string;
  pyodideIndexUrl: string;
}

export interface WorkerTimings {
  /** Only on the first request: the cold start, in ms. */
  pyodide_load_ms?: number;
  micropip_ms?: number;
  wheel_install_ms?: number;
  import_ms?: number;
  /** Every request: coco_lab's own steps, in ms (measured in Python). */
  load_bundle_ms: number;
  search_ms: number;
  write_bundle_ms: number;
  optimal_ms: number;
  runs: number;
  total_ms: number;
}

export interface WorkerBundle {
  manifest: Uint8Array;
  arraysFile: Uint8Array;
  arraysName: string;
  contentHash: string;
}

export type RecomputeResponse =
  | {
    id: number; ok: true;
    bundles: WorkerBundle[];
    optimalCost: number | null;
    cocoLabVersion: string; pythonVersion: string; pyodideVersion: string;
    timings: WorkerTimings;
  }
  | {
    id: number; ok: false; stage: 'load' | 'edit';
    /** true when coco_lab's glue refused the edit with a learner-facing reason */
    refused: boolean;
    error: string;
  };
