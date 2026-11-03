// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1: experiment specs on the page side. coco_lab.experiments is the authority (a spec
 * is validated and filled by `plan` in a worker); this file only knows the shape, the
 * defaults the form starts from and the tables in meta.json (tools/r1/build_meta.py).
 */
import meta from './meta.json';

export type Family = 'planning' | 'control' | 'localisation' | 'fulltask';
export interface ParamDef { type: 'float' | 'int' | 'str' | 'list'; default: number | string | number[]; min: number | null; max: number | null; choices: (number | string)[] | null; doc: string }
export interface MetricDef { id: string; label: string; unit: string; better: 'lower' | 'higher'; test: boolean; timing: boolean }
export interface WorldDef { id: string; title: string; spec_version: string; resolution: number; origin: [number, number]; width: number; height: number; regions: Record<string, [number, number, number, number]>; sha256: string }
export interface SuiteDef { id: string; version: number; title: string; world: string; families: Family[]; n: number | null; tests: string }
export interface AlgorithmSpec { name: string; id?: string; label?: string; params?: Record<string, number | string | number[]> }
export type Scenarios =
  | { kind: 'sampled'; n: number; seed?: number; min_separation_m?: number; min_clearance_m?: number; zones?: string[] | null; stratify?: 'none' | 'zone'; require_reachable?: boolean }
  | { kind: 'suite'; id: string; version?: number }
  | { kind: 'pairs'; pairs: { id?: string; start: number[]; goal: number[] }[]; seed?: number }
  | { kind: 'rounds'; game: 'fetch_rush' | 'fetch_colour'; rounds?: { seed: number; mode: string }[]; colours?: string[] };
export interface ExperimentSpec {
  schema: 'coco.experiment.v1'; title?: string; world?: string; family: Family; seed?: number;
  model?: { hash_version: number; experiment: number };
  algorithms: AlgorithmSpec[]; scenarios: Scenarios;
  sweep?: { params: { name: string; values: (number | string)[] }[] };
  limits?: { max_ticks: number }; options?: { kidnap_at_s?: number | null }; metrics?: string[];
  notes?: string; world_sha256?: string;
}

export const META = meta as unknown as {
  schema: string; model: { hash_version: number; experiment: number }; families: Family[];
  algorithms: Record<Family, string[]>; labels: Record<string, string>;
  params: Record<Family, Record<string, ParamDef>>; metrics: Record<Family, MetricDef[]>;
  statuses: Record<Family, string[]>; limits: Record<string, number>; worlds: WorldDef[]; suites: SuiteDef[];
  fulltask: { fetch_rush: { world: string; seeds: number[]; modes: string[]; rules: number }; fetch_colour: { world: string; colours: string[]; rules: number } };
};

export const FAMILY_LABEL: Record<Family, string> = {
  planning: 'Global planning', control: 'Local control', localisation: 'Localisation', fulltask: 'Full task (Fetch)',
};

/** What a run's success means, per family (shown beside every success rate). */
export const SUCCESS_MEANS: Record<Family, string> = {
  planning: 'a path was found',
  control: 'FollowPath succeeded (within 0.25 m and 0.25 rad)',
  localisation: 'reached the goal with the estimate within 0.5 m and 0.3 rad',
  fulltask: 'every order delivered before the timer',
};

export const label = (name: string) => META.labels[name] ?? name;
export const worldOf = (id: string | undefined) => META.worlds.find((w) => w.id === id);

/** Whether a parameter does anything for an algorithm (the model's rule, coco_lab.experiments._applies). */
export function applies(family: Family, algo: string, key: string): boolean {
  if (family === 'planning') return key !== 'heuristic_weight' || algo === 'weighted_astar';
  if (family === 'control') { const head = key.split('.')[0]; return head === 'planner' || head === 'window' || head === algo; }
  if (family === 'localisation') return key.startsWith(algo.startsWith('mcl') ? 'mcl.' : 'ekf.');
  return false;
}

/** The parameters the form shows first for a family (the rest are under "all parameters"). */
export const COMMON_PARAMS: Record<Family, string[]> = {
  planning: ['inflation_radius', 'cost_scaling_factor', 'robot_radius', 'heuristic_weight'],
  control: ['planner', 'window.inflation_radius', 'window.cost_scaling_factor', 'window.robot_radius',
    'dwa.v_max', 'dwa.sim_time', 'rpp.lookahead_dist', 'rpp.desired_linear_vel', 'mppi.batch_size', 'mppi.temperature'],
  localisation: ['mcl.particles', 'mcl.beams', 'mcl.sigma_hit', 'mcl.init', 'ekf.beams', 'ekf.sigma_hit', 'ekf.init'],
  fulltask: [],
};

/** A small, fast starting experiment for each family (the form opens on one). */
export function defaultSpec(family: Family = 'planning'): ExperimentSpec {
  const base = { schema: 'coco.experiment.v1' as const, seed: 1 };
  if (family === 'planning') return { ...base, title: 'Is A* always faster than Dijkstra?', world: 'coco_depot_v1', family,
    algorithms: [{ name: 'astar' }, { name: 'dijkstra' }], scenarios: { kind: 'sampled', n: 20, seed: 1, min_separation_m: 5 } };
  if (family === 'control') return { ...base, title: 'Local controllers on the Proving Ground', world: 'coco_arena_v1', family,
    algorithms: [{ name: 'dwa' }, { name: 'rpp' }], scenarios: { kind: 'sampled', n: 10, seed: 1, min_separation_m: 3 }, limits: { max_ticks: 1500 } };
  if (family === 'localisation') return { ...base, title: 'MCL against the EKF', world: 'coco_arena_v1', family,
    algorithms: [{ name: 'mcl', params: { 'mcl.particles': 60, 'mcl.beams': 12 } }, { name: 'ekf', params: { 'ekf.beams': 12 } }],
    scenarios: { kind: 'sampled', n: 6, seed: 1, min_separation_m: 3 }, limits: { max_ticks: 1200 } };
  return { ...base, title: 'Fetch by colour with two planners', family, algorithms: [{ name: 'astar' }, { name: 'greedy' }],
    scenarios: { kind: 'rounds', game: 'fetch_colour', colours: ['red', 'green', 'blue', 'yellow'] } };
}

/** The world id a spec runs on (a full task's is its game's). */
export function worldId(spec: ExperimentSpec): string {
  if (spec.family === 'fulltask') {
    const g = spec.scenarios.kind === 'rounds' ? spec.scenarios.game : 'fetch_colour';
    return META.fulltask[g].world;
  }
  if (spec.scenarios.kind === 'suite') return META.suites.find((s) => s.id === (spec.scenarios as { id: string }).id)?.world ?? spec.world ?? '';
  return spec.world ?? '';
}

/** How many runs a spec makes, from its own fields (before the worker has planned it). */
export function runCount(spec: ExperimentSpec): number {
  const sc = spec.scenarios;
  let n = 0;
  if (sc.kind === 'sampled') n = sc.n;
  else if (sc.kind === 'pairs') n = sc.pairs.length;
  else if (sc.kind === 'suite') n = META.suites.find((s) => s.id === sc.id)?.n ?? 0;
  else n = sc.game === 'fetch_rush' ? (sc.rounds?.length ?? 12) : (sc.colours?.length ?? 4);
  const points = (spec.sweep?.params ?? []).reduce((acc, p) => acc * Math.max(1, p.values.length), 1);
  return n * spec.algorithms.length * points;
}

/**
 * A rough cost per run (model-seconds of work) from measured native timings
 * (docs/v2/r1/data/r12/): a planning run is cheap, a localisation run with MCL is not.
 * Used only to warn before a long experiment, never shown as a measurement.
 */
export function heavy(spec: ExperimentSpec, phone: boolean): { runs: number; warn: boolean; reason: string } {
  const runs = runCount(spec);
  const weight = { planning: 1, control: 20, localisation: 60, fulltask: 40 }[spec.family];
  const budget = phone ? 120 : 2400;
  const warn = runs * weight > budget;
  return { runs, warn, reason: warn ? `${runs} runs of ${FAMILY_LABEL[spec.family].toLowerCase()} may take a long time${phone ? ' on a phone' : ''}; try fewer scenarios first.` : '' };
}
