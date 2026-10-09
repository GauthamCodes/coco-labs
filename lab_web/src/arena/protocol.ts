// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Messages between the Arena page and its worker (arena.worker.ts). */

export interface InputRow {
  tick: number;
  kind: 'goal' | 'teleop' | 'stop' | 'planner' | 'reset';
  x?: number; y?: number; theta?: number; has_theta?: boolean;
  linear?: number; angular?: number; choice?: string;
}

export interface BootRequest {
  type: 'boot';
  /** Where pyodide.mjs and its files are: the self-hosted copy, or the CDN. */
  pyodideBase: string;
  /** Where arena/coco_lab.zip, the spec and the manifest are. */
  assetsBase: string;
  seed: number;
  planner: string;
  batchSize: number;
}

export interface StepRequest { type: 'step'; inputs: InputRow[] }
/**
 * Inputs sent while a step is in flight (M2.0). The worker handles them at
 * once, not behind the step: if that step is still planning they join its
 * tick (the search in flight is cancelled); otherwise they open the next
 * tick. The worker stamps every input with the model's tick and reports it
 * in `Tick.inputs`, which is the run's input log.
 */
export interface AmendRequest { type: 'amend'; inputs: InputRow[] }
/** Two planners from the robot's cell to (x, y); the model is not changed (M1.8). */
export interface CompareRequest { type: 'compare'; a: string; b: string; x: number; y: number }
/** M2.2: load a lens's Python pack (tools/arena_packs.json) if it is not loaded yet. */
export interface LoadPackRequest { type: 'load_pack'; pack: string }
export type ToWorker = BootRequest | StepRequest | AmendRequest | CompareRequest | LoadPackRequest;

export interface CompareSide { planner: string; status: string; summary: Record<string, number | string | null>; resolution: number }

/** Wall-clock milliseconds (timeOrigin + now), comparable across page and worker. */
export const wallMs = () => performance.timeOrigin + performance.now();

export interface World {
  id: string; width: number; height: number; resolution: number;
  origin: [number, number]; frame: string; start: [number, number, number];
  dt: number; radius: number; limits: Record<string, number>;
  lidar: { samples: number; angle_min: number; angle_max: number; range_max: number; mount: number[] };
  planners: string[]; planner: string; hash: string;
}

export interface PlanInfo {
  search_id: number; planner: string; goal: [number, number]; tick: number; status: string;
  summary: Record<string, number | string | null>; waypoints: [number, number][];
}

export interface Tick {
  tick: number; t_world: number; pose: [number, number, number]; v: number; w: number;
  /** Ground truth when it differs from `pose` (a recorded stack run: pose = its belief). */
  truth?: [number, number, number];
  mode: string; blocked: boolean; arrived: boolean; hash: string; chain: string; plans: PlanInfo[];
  /** The inputs this tick applied, stamped by the model (M2.0; absent in recordings made before). */
  inputs?: InputRow[];
}

/** SearchEventBatch columns (coco.plan.search.events.v1), as typed arrays. */
export interface SearchColumns {
  seq: BigUint64Array; tick: BigUint64Array; t_world: Float64Array; kind: Int32Array;
  row: Int32Array; col: Int32Array; sub: Int32Array; g: Float64Array; h: Float64Array; f: Float64Array;
  parent_row: Int32Array; parent_col: Int32Array; parent_sub: Int32Array;
}

/** M2.2: one whole-loop family batch (coco_lab.columns), or a channel's static header. */
export interface FamilyMessage {
  type: 'family';
  channel: string;
  tick?: number;
  /** numeric columns (transferred typed arrays) and plain ones (strings, bools) together */
  columns?: Record<string, ArrayLike<number> | ArrayLike<bigint> | boolean[] | string[]>;
  scalars?: Record<string, number | string | boolean>;
  header?: Record<string, unknown>;
}

export type FromWorker =
  | FamilyMessage
  | { type: 'pack_ready'; pack: string; ms: number }
  | { type: 'mark'; name: string; at: number }
  | { type: 'world'; world: World; occupancy: Uint8Array; at: number }
  | { type: 'plan_batch'; meta: { search_id: number; planner: string; tick: number; final: boolean; compare?: 'A' | 'B';
    /** M2.0: the search was cancelled by an input that joined its tick; drop what was shown of it. */
    cancelled?: boolean };
      columns: SearchColumns; at: number }
  | { type: 'tick'; tick: Tick; ranges: Float32Array; stepMs: number; at: number }
  | { type: 'compare_done'; result: { A: CompareSide; B: CompareSide } }
  | { type: 'error'; stage: string; message: string };
