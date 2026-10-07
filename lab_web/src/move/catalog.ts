// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Catalog 1.5's `move` block (lab_web/tools/build_move.py). Types only. */

import type { DriveMetrics, ReplanSummary, ReplanWorldInfo } from './decode';

export interface ReplanEntry {
  id: string; title: string; kind: 'sketch' | 'glass-box'; path: string; arrays_file: string;
  bytes: number; content_hash: string; summary: ReplanSummary; world: ReplanWorldInfo;
  validated: { by: string; replay: string }; lesson: string; cites: string[];
}

export interface DriveEntry {
  id: string; title: string; kind: 'replay'; path: string; arrays_file: string; bytes: number;
  content_hash: string;
  runs: Array<{ id: string; controller: string; outcome: string; metrics: DriveMetrics; has_rollouts: boolean }>;
  validated: { by: string; replay: string }; lesson: string; cites: string[];
}

export interface Dist { n: number; min: number | null; median: number | null; max: number | null }

export interface ControllerResult {
  runs: number;
  outcomes: Record<string, number>;
  error_codes: number[];
  tracking_mean_m: Dist; tracking_max_m: Dist; time_s_succeeded: Dist;
  rms_linear_accel: Dist; rms_angular_accel: Dist;
  min_clearance_m: Dist; min_clearance_static_m: Dist; min_clearance_actor_m: Dist;
  contacts: number;
  /** DWB only: per run, cycles where it scored candidates and rejected all (run 15's "0 of 819") */
  dwb_all_rejected_cycles: number[] | null;
  /** DWB only: per run, cycles with nothing to score (n = 0) */
  dwb_empty_cycles: number[] | null;
  /** supplementary: runs where the actor touched the robot at ANY time in the recording */
  actor_contacts_whole_recording: number;
  /** supplementary: of those, how many with the wheels already commanded to 0 m/s */
  actor_contacts_while_wheels_stopped: number;
  /** apron scenarios: per run, the largest |x - x_start| in the window (the path is the line x = x_start) */
  max_lateral_m: Dist | null;
}

export type ScenarioResult =
  | { status: 'not yet measured' }
  | { status: 'measured'; title: string; bundle: string; content_hash: string; bytes: number;
    path_sha256: string; controllers: Record<string, ControllerResult> };

export type Results =
  | { status: 'not yet measured' }
  | { status: 'measured'; matrix: string; git: { commit: string; dirty: boolean } | null;
    scenarios: Record<string, ScenarioResult>; void: Array<{ run: string; reason: string | null }> };

export interface ControllerInfo { id: string; name: string; colour: string; how: string; shows: string; cites: string[] }

export interface Claim { id: string; text: string; cites: string[] }

export interface SketchStats {
  seeds: number; sense_radius: number; reached: number; costs_agree_all: boolean;
  episode_ratio_dstar_over_astar: Dist; episodes_dstar_less_total: number; replans: number; replans_dstar_more: number;
}

export interface ExperimentC {
  grid: [number, number]; resolution_m: number; window_map_frame: number[]; cells_changed: number;
  newly_blocked: number; before: string; after: string; content_hash: string;
  summary: ReplanSummary;
  rounds: Array<{ step: number; cost: number | null; dstar_expansions: number; dstar_reexpansions: number;
    astar_expansions: number; astar_cost: number | null }>;
}

export interface MovePart {
  version: string;
  replan: { bundles: ReplanEntry[]; limits: { seed: [number, number]; sense_radius: [number, number];
    max_painted: number; width: number; height: number };
    experiment_c: ExperimentC | null; sketch_stats: SketchStats | null };
  drive: { bundles: DriveEntry[]; results: Results };
  controllers: ControllerInfo[];
  claims: Claim[];
  run15: { quotes: string[]; source: string; reproduced: string };
}
