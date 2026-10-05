// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Catalog 1.3's `map` block (lab_web/tools/build_map.py). Types only. */

import type { Fidelity } from '../loc/catalog';
import type { AteSummary, MapScore } from './decode';
import type { MapSpec } from '../worker/protocol';

export interface MapRunEntry {
  id: string;
  algorithm: string;
  summary: { ate_online: AteSummary; ate_final: AteSummary; map: MapScore };
}

export interface MapExternalEntry {
  id: string; backend: string; arm: string;
  summary: { ate_online: AteSummary; map: MapScore };
  source: Record<string, unknown>;
}

export interface MapEntry {
  id: string;
  title: string;
  kind: 'sketch' | 'challenge' | 'replay';
  path: string;
  arrays_file: string;
  bytes: number;
  content_hash: string;
  map_id: string;
  /** the learner's starting settings (null for a recording: it cannot be redriven) */
  spec: (Omit<MapSpec, 'clicks'> & { clicks: Array<[number, number]> }) | null;
  lesson: string;
  runs: MapRunEntry[];
  external?: MapExternalEntry[];
  validated: { by: string; replay: string };
  cites: string[];
}

export interface Challenge {
  title: string;
  task: string;
  score: string;
  definition: Record<string, string>;
  algorithms: string[];
  noise_scale: number;
  cites: string[];
}

export type Measured<T> = ({ status: 'measured' } & T) | { status: 'not yet measured' };

export interface CountRow {
  n: number;
  [key: string]: unknown;
}

export type SketchCounts = Measured<{
  command: string;
  label: string;
  scenes: Record<string, {
    seeds: number[];
    loop_closed?: number;
    loop_improved?: number;
    runs: Record<string, { final_ate_median: number; final_ate_p10: number; final_ate_p90: number;
      f1_median: number; f1_p10: number; f1_p90: number; n: number }>;
  }>;
}>;

export interface BackendRow {
  drive: string; backend: string; arm: string; round: string;
  ate_online_rmse: number; ate_online_max: number; f1: number; precision: number | null;
  recall: number | null; coverage: number | null; loadavg_end: string; play_wall_s: number;
}

export interface CocoRow {
  drive: string; arm: string; seed: number | null;
  ate_online_rmse: number; ate_final_rmse: number; f1: number; wall_s: number;
}

export type RealResults = Measured<{
  command: string;
  label: string;
  drives: Array<{ id: string; session: string; length_m: number; scans: number; updates: number;
    wheel_odometry_ate_rmse: number }>;
  backends: BackendRow[];
  coco_lab: CocoRow[];
  notes: string[];
}>;

export interface MapPart {
  version: string;
  bundles: MapEntry[];
  challenge: Challenge;
  fidelity: Fidelity;
  sketch_counts: SketchCounts;
  real: RealResults;
  limits: { noise_scale: [number, number]; particles: [number, number]; clicks: number };
  run_ids: string[];
}
