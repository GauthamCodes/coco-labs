// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Messages between the page and the Pyodide worker. Bytes in, bytes out. */

export interface EditRequest {
  id: number;
  type: 'edit';
  /** The CURRENT bundle's files, byte for byte. */
  manifest: Uint8Array;
  arraysName: string;
  arraysFile: Uint8Array;
  /** The cell to toggle (occupied <-> free), [row, col]. */
  cell: [number, number];
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
  total_ms: number;
}

export type EditResponse =
  | {
    id: number; ok: true;
    manifest: Uint8Array; arraysFile: Uint8Array; arraysName: string;
    contentHash: string; cocoLabVersion: string; pythonVersion: string; pyodideVersion: string;
    timings: WorkerTimings;
  }
  | { id: number; ok: false; stage: 'load' | 'edit'; error: string; timings?: Partial<WorkerTimings> };
