// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Catalog 1.4's `search` block (lab_web/tools/build_search.py). Types only. */

import type { SearchSummary } from './decode';

export interface SearchRunEntry {
  id: string;
  kind: 'sketch' | 'recorded';
  policy: string;
  summary: SearchSummary & { plan: { order: string[]; expected_cost: number; p_find: number } };
}

export interface SearchEntry {
  id: string;
  title: string;
  kind: 'sketch' | 'replay';
  path: string;
  arrays_file: string;
  bytes: number;
  content_hash: string;
  runs: SearchRunEntry[];
  validated: { by: string; replay: string };
  lesson: string;
  cites: string[];
}

export interface Claim { id: string; text: string; cites: string[] }

export type Measured<T> = ({ status: 'measured' } & T) | { status: 'not yet measured' };

export interface MatrixRow {
  run: string; group: string; level: string; seed: number; colour: string;
  truth_region: string; order_arg: string; order: string[]; discovered: string | null;
  discovered_at: number | null; outcome: string; reason: string | null; lifted: boolean | null;
  home_error_m: number | null; relocalisations: number; recoveries: number;
  sim_s: number | null; wall_s: number | null; runner_checks_pass: boolean;
}

export type Matrix = Measured<{ command: string; label: string; rows: MatrixRow[]; notes: string[] }>;

export interface SearchPart {
  version: string;
  bundles: SearchEntry[];
  claims: Claim[];
  matrix: Matrix;
  policies: string[];
  limits: { detection: [number, number]; max_surveys: [number, number]; seed: [number, number] };
  challenge: { title: string; task: string; score: string; cites: string[] };
}
