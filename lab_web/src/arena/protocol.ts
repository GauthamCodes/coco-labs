// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Messages between the Arena page and its worker (arena.worker.ts). */

export interface InputRow {
  tick: number;
  kind: 'goal' | 'teleop' | 'stop' | 'planner' | 'reset' | 'kidnap' | 'config' | 'autonomy' | 'grasp';
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
  /** M4.3: the World Spec to build (a file in generated/arena/); absent = coco_arena_v1.json. */
  spec?: SpecFile;
}

/** The World Specs the site ships (tools/build_arena_assets.mjs); v1 is every default. */
export const SPEC_FILES = { v1: 'coco_arena_v1.json', v2: 'coco_arena_v2.json' } as const;
export type SpecFile = (typeof SPEC_FILES)[keyof typeof SPEC_FILES];
/** `?world=v2` picks World Spec v2; anything else (or nothing) is v1. */
export const specFileFor = (world: string | null): SpecFile => (world === 'v2' ? SPEC_FILES.v2 : SPEC_FILES.v1);

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
/** M3.5: Play -- coco_lab.play, through arena_glue.play (a JSON request; the reply is JSON). */
export interface PlayRequest { type: 'play'; id: number; request: string }
export type ToWorker = BootRequest | StepRequest | AmendRequest | CompareRequest | LoadPackRequest | PlayRequest;

export interface CompareSide { planner: string; status: string; summary: Record<string, number | string | null>; resolution: number }

/** Wall-clock milliseconds (timeOrigin + now), comparable across page and worker. */
export const wallMs = () => performance.timeOrigin + performance.now();

export interface World {
  id: string; width: number; height: number; resolution: number;
  origin: [number, number]; frame: string; start: [number, number, number];
  dt: number; radius: number; limits: Record<string, number>;
  lidar: { samples: number; angle_min: number; angle_max: number; range_max: number; mount: number[] };
  planners: string[]; planner: string; hash: string;
  /** M4.6: the LiDAR's beam height over the surface the robot stands on (m; coco_lab.worldspec.scan_height). */
  beam_height?: number;
  /** M4.3: the fetch targets on the platforms (World Spec v2 only); map frame, z the surface under each. */
  targets?: { colour: string; x: number; y: number; z: number; diameter: number; height: number }[];
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
  /** M2.5: moving bodies (x, y, radius); absent when there are none. */
  actors?: [number, number, number][];
  /** M2.5: a global path given whole on this tick (x0, y0, x1, y1, ...): a Lab 5 scenario's frozen path. */
  path?: number[];
  /** M3.5: a map challenge's ground-truth distance against its budget (coco_lab.play.MapBudget). */
  play?: { path_m: number; budget_m: number; done: boolean };
  /** M4.3: [z, pitch, roll] on the terrain (World Spec v2 sessions only; ROS signs). */
  tilt?: [number, number, number];
  /** M4.3: left and right wheel speeds (rad/s). */
  wheels?: [number, number];
  /** M4.3: who the wheels obeyed (STOP > TELEOP > MISSION or PLANNER; coco_lab.arena.COMMAND_SOURCES). */
  source?: 'idle' | 'stop' | 'teleop' | 'mission' | 'planner';
  /** M4.3: the gated grasp, once there is one (coco_lab.arena.Arena.grasp_view). */
  grasp?: { phase: string; target?: string | null; reason: string; targets?: Record<string, [number, number]>;
    arm?: Record<string, number | boolean | string> | null };
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
  | { type: 'play_done'; id: number; result?: string; error?: string }
  | { type: 'error'; stage: string; message: string };
