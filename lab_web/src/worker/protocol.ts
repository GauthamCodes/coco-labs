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

export interface RecomputeRequest {
  id: number;
  type: 'recompute';
  /** The CURRENT bundle's files, byte for byte. */
  manifest: Uint8Array;
  arraysName: string;
  arraysFile: Uint8Array;
  spec: RecomputeSpec;
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
