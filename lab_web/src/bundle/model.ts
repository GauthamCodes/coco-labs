// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The normalized, decoded form of one bundle -- what every renderer reads.
 *
 * Nothing in it is recomputed or rounded: typed columns hold the exact
 * values of the bundle's arrays, header/summary/run/provenance/meta are the
 * manifest's own values (as plain JS), and the parsed manifest tree itself
 * is kept (`manifest`) so no field the first UI does not show is lost.
 */

import type { JObject } from './json';

export type SourceKind = 'glass-box' | 'recorded-run' | 'sketch';

export interface Provenance {
  source_kind: SourceKind;
  coco_lab_version: string;
  git_commit: string | null;
  git_dirty: boolean | null;
  created_utc: string;
  seed: number | null;
  episode_spec_hash: string | null;
  rosbag: { sha256: string; sim_time_start: number; sim_time_end: number } | null;
  tool: string | null;
  [extra: string]: unknown; // a MINOR version may add fields; kept, not shown
}

export interface Geo {
  resolution: number;
  origin: [number, number];
  frame: string | null;
}

export interface MapLayer {
  id: string;
  width: number;
  height: number;
  /** Row-major from the TOP-left: 0 free, 1 occupied, 2 unknown. */
  occupancy: Uint8Array;
  cost: Float64Array | null;
  geo: Geo | null;
  meta: Record<string, unknown>;
  contentHash: string;
}

export interface TraceEvents {
  kind: Uint8Array; // 0 push, 1 expand, 2 relax, 3 path
  row: Int32Array;
  col: Int32Array;
  sub: Int32Array;
  g: Float64Array;
  h: Float64Array;
  f: Float64Array;
  parent_row: Int32Array;
  parent_col: Int32Array;
  parent_sub: Int32Array;
}

export const TRACE_COLUMNS = [
  'kind', 'row', 'col', 'sub', 'g', 'h', 'f', 'parent_row', 'parent_col', 'parent_sub',
] as const;
export const EVENT_KINDS = ['push', 'expand', 'relax', 'path'] as const;
export type EventKind = (typeof EVENT_KINDS)[number];

export interface TraceHeader {
  schema: string;
  version: string;
  algorithm: string;
  heuristic: string;
  weight: number | null;
  tie_break: string;
  start: [number, number, number];
  goal: [number, number, number];
  graph: Record<string, unknown> & { kind: string };
  [extra: string]: unknown;
}

export interface TraceSummary {
  status: 'found' | 'no_path';
  expansions: number;
  pushes: number;
  relaxes: number;
  path_cost: number | null;
  path_length: number | null;
  path_steps: number | null;
  [extra: string]: unknown;
}

export interface Trace {
  header: TraceHeader;
  summary: TraceSummary;
  n: number;
  events: TraceEvents;
}

export interface RunBlock {
  algorithm: string;
  heuristic: string;
  weight: number | null;
  tie_break: string;
  start: [number, number];
  goal: [number, number];
  graph: Record<string, unknown> & { kind: string };
  model: Record<string, unknown>;
  map_hash: string;
  [extra: string]: unknown;
}

export const RECORDING_GROUPS = {
  gt: ['t', 'x', 'y', 'yaw'],
  amcl: ['t', 'x', 'y', 'yaw'],
  plan: ['x', 'y', 'yaw'],
  cmd: ['t', 'v', 'w'],
} as const;
export type RecordingGroup = keyof typeof RECORDING_GROUPS;

export interface Recording {
  groups: Partial<Record<RecordingGroup, { frame: string; source: string; count: number }>>;
  missing: RecordingGroup[];
  runId: string;
  /** The exporter's measured results, exactly as stored (never recomputed). */
  meta: Record<string, unknown>;
  /** Raw f64 columns of every PRESENT group. A missing group has none. */
  streams: Partial<Record<RecordingGroup, Record<string, Float64Array>>>;
}

export interface ArrayEntry {
  name: string;
  dtype: 'u8' | 'i32' | 'f64';
  count: number;
  offset: number;
  byteLength: number;
}

/** Who validated this bundle's SEMANTICS (the browser checks structure only). */
export type ValidatedBy =
  | { by: 'catalog'; detail: string } // coco_lab load_bundle at site build time
  | { by: 'pyodide'; detail: string } // coco_lab in this browser, just now
  | null; // structurally decoded only: not drawable

export interface DecodedBundle {
  version: string;
  minor: number;
  contentHash: string;
  compression: 'none' | 'gzip';
  provenance: Provenance;
  run: RunBlock;
  map: MapLayer;
  trace: Trace;
  recording: Recording | null;
  arrays: ArrayEntry[];
  /** The parsed manifest, lossless; nothing the UI ignores is discarded. */
  manifest: JObject;
  rawBytes: number;
}
