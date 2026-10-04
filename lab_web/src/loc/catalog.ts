// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** The catalog's `localise` block (catalog 1.2), written by tools/build_localise.py. */

import type { LocSpec } from '../worker/protocol';
import type { LocSummary } from './decode';

export interface LocEntry {
  id: string;
  title: string;
  path: string;
  arrays_file: string;
  bytes: number;
  content_hash: string;
  map_id: string;
  source_kind: 'sketch';
  spec: LocSpec;
  lesson: string;
  runs: Array<{ id: string; kind: 'mcl' | 'ekf'; summary: LocSummary }>;
  validated: { by: string; replay: string };
  cites: string[];
}

export interface Dist {
  n: number; mean?: number; sd?: number; min?: number; p05?: number; p25?: number;
  median?: number; p75?: number; p95?: number; p99?: number; max?: number;
}

export interface FidelityDrive {
  session: string;
  drive: string;
  distance_m: number;
  rotation_rad: number;
  gazebo: { final_pos_err_m: number; final_yaw_err_rad: number; max_pos_err_m: number;
    pos_err_per_m: number | null; yaw_err_per_rad: number | null };
  gazebo_truth_vs_commanded_unicycle_m: number;
  sketch_zero_noise_final_pos_err_m: number;
  sketch_default_noise: { alphas: number[]; seeds: number; final_pos_err_m: Dist; final_yaw_err_rad: Dist };
}

export type Measured<T> = ({ status: 'measured' } & T) | { status: 'not yet measured' };

export type Fidelity = Measured<{
  cite: string;
  command: string;
  sessions: string[];
  scans_used: number;
  scans_recorded: number;
  beams_both: number;
  classes: Record<string, number>;
  error_m: Dist;
  abs_error_m: Dist;
  frac_abs_below: Record<string, number>;
  histogram: { edges_m: number[]; counts: number[]; below: number; above: number };
  drives: FidelityDrive[];
}>;

export interface RateRun {
  kind: 'mcl' | 'ekf'; n: number; deterministic: boolean; converged: number; recovered: number;
  final_err_over_2m: number; recovery_s_sorted: number[];
}

export type SketchRates = Measured<{
  label: string;
  cite: string;
  definition: { ok_xy_m: number; ok_yaw_rad: number; hold_updates: number };
  experiments: Record<string, { world_seed: number; kidnap_s: number | null; runs: Record<string, RateRun> }>;
}>;

export interface ABTrial {
  arm: 'shipped' | 'recovery';
  target: string;
  to_map: [number, number, number];
  recovered: boolean | null;
  recovery_s: number | null;
  void: string | null;
  t: number[];
  err_xy: number[];
}

export type KidnapAB = Measured<{
  cite: string;
  definition: string;
  arms: Record<string, { alpha_slow: number; alpha_fast: number; n: number; recovered: number;
    void: number; recovery_s: number[] }>;
  trials: ABTrial[];
}>;

export type EkfDrift = Measured<{
  cite: string;
  config: string;
  drives: Array<{ session: string; drive: string; distance_m: number; rotation_rad: number;
    wheel_odom: { final_pos_err_m: number; final_yaw_err_rad: number; max_pos_err_m: number };
    ekf: { final_pos_err_m: number; final_yaw_err_rad: number; max_pos_err_m: number } }>;
}>;

export type AmclOdom = Measured<{
  cite: string;
  definition: string;
  drives: Array<{ session: string; drive: string; arm: 'wheel' | 'ekf'; n: number;
    mean_err_xy: number; max_err_xy: number; final_err_xy: number }>;
}>;

export interface LocalisePart {
  version: string;
  bundles: LocEntry[];
  exhibits: string;
  fidelity: Fidelity;
  sketch_rates: SketchRates;
  kidnap_ab: KidnapAB;
  ekf_drift: EkfDrift;
  amcl_odom?: AmclOdom;
  limits: { particles: [number, number]; motion_noise: [number, number];
    sensor_sigma: [number, number]; inject_fraction: [number, number] };
}
