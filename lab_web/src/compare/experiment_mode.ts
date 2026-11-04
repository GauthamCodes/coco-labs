// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.7: Compare on chosen scenarios. Compare's panes and sliders become an experiment
 * spec (coco_lab.experiments), and a scenario -- a seeded random pair, a pair from a
 * benchmark suite, or a hand-placed pair -- picks which runs of it each pane replays.
 * The replay is the experiment's own run, so a pane's numbers are the Workbench
 * table's; a run opened from the table (`#xexp=...&xrun=i`) shows that very run.
 */
import type { CompareInflation, CompareResult, LoopFrame, ReplayFrame, SpecFile } from '../arena/protocol';
import { SPEC_FILES } from '../arena/protocol';
import { boundedJson } from '../links/bounds.mjs';
import type { RunRecord } from '../workbench/pool';
import type { ExperimentSpec, Family as XFamily, Scenarios } from '../workbench/spec';

export type CompareFamily = 'global' | 'control' | 'localise';
export const X_FAMILY: Record<CompareFamily, XFamily> = { global: 'planning', control: 'control', localise: 'localisation' };
export const C_FAMILY: Record<string, CompareFamily> = { planning: 'global', control: 'control', localisation: 'localise' };
export type Source = { kind: 'live' } | { kind: 'random'; seed: number } | { kind: 'suite'; id: string; index: number } | { kind: 'hand'; start: [number, number, number]; goal: [number, number] };

/** `?world=` names Compare accepts, and the World Spec each opens (G1.6 + R1.7: every shipped world). */
export const WORLD_PARAM: Record<string, SpecFile> = { v1: SPEC_FILES.v1, v2: SPEC_FILES.v2, depot: SPEC_FILES.depot, depot_colours: SPEC_FILES.depot_colours };
export const worldIdOf = (spec: SpecFile | undefined) => (spec ?? SPEC_FILES.v1).replace(/\.json$/, '');
export const WORLD_NAME: Record<string, string> = { coco_arena_v1: 'COCO arena (Proving Ground)', coco_arena_v2: 'Proving Ground with terrain', coco_depot_v1: 'COCO Depot', coco_depot_colours_v1: 'COCO Depot with colour rods' };

/** The panes' algorithms with the sliders' parameters, as experiment algorithms (ids unique per pane). */
export function paneAlgorithms(family: CompareFamily, names: string[], p: CompareInflation) {
  return names.map((name, i) => {
    const params: Record<string, number> = family === 'global'
      ? { inflation_radius: p.inflation_radius, cost_scaling_factor: p.cost_scaling_factor, robot_radius: p.robot_radius }
      : family === 'control' ? { 'window.inflation_radius': p.inflation_radius, 'window.cost_scaling_factor': p.cost_scaling_factor, 'window.robot_radius': p.robot_radius }
        : name.startsWith('mcl') ? { 'mcl.particles': 60, 'mcl.beams': 12 } : { 'ekf.beams': 12 };
    return { name, id: `${'ABCD'[i]}_${name}`, params };
  });
}

/** The spec a scenario source gives, and the run index each pane replays. */
export function scenarioSpec(family: CompareFamily, world: string, names: string[], p: CompareInflation, src: Exclude<Source, { kind: 'live' }>, suiteN: number): { spec: ExperimentSpec; indices: number[] } {
  const scenarios: Scenarios = src.kind === 'random' ? { kind: 'sampled', n: 1, seed: src.seed, min_separation_m: 3 }
    : src.kind === 'suite' ? { kind: 'suite', id: src.id } : { kind: 'pairs', pairs: [{ start: src.start, goal: src.goal }] };
  const n = src.kind === 'suite' ? suiteN : 1, at = src.kind === 'suite' ? src.index : 0;
  const spec: ExperimentSpec = { schema: 'coco.experiment.v1', title: 'From Compare', world, family: X_FAMILY[family], seed: 1,
    algorithms: paneAlgorithms(family, names, p), scenarios, ...(family === 'global' ? {} : { limits: { max_ticks: 1500 } }) };
  return { spec, indices: names.map((_, k) => k * n + at) };
}

/** "Turn this into an experiment": the panes over 20 seeded pairs (or the suite / the hand-placed pair). */
export function experimentFromCompare(family: CompareFamily, world: string, names: string[], p: CompareInflation, src: Source): ExperimentSpec {
  const unique = names.filter((n, i) => names.indexOf(n) === i);
  const algos = paneAlgorithms(family, unique, p).map((a) => ({ ...a, id: undefined }));
  const scenarios: Scenarios = src.kind === 'suite' ? { kind: 'suite', id: src.id }
    : src.kind === 'hand' ? { kind: 'pairs', pairs: [{ start: src.start, goal: src.goal }] }
      : { kind: 'sampled', n: 20, seed: src.kind === 'random' ? src.seed : 1, min_separation_m: 3 };
  return { schema: 'coco.experiment.v1', title: `${unique.join(' vs ')} (from Compare)`, world, family: X_FAMILY[family], seed: 1,
    algorithms: algos, scenarios, ...(family === 'global' ? {} : { limits: { max_ticks: 1500 } }) };
}

/** Which runs a table link's run index shares a scenario with: its own first, up to four. */
export function runsLike(index: number, nAlgorithms: number, nScenarios: number): number[] {
  const perPoint = nAlgorithms * nScenarios, point = Math.floor(index / perPoint), scen = index % nScenarios;
  const own = Math.floor((index % perPoint) / nScenarios);
  const order = [own, ...[...Array(nAlgorithms).keys()].filter((a) => a !== own)];
  const count = Math.min(order.length, 4) === 3 ? 2 : Math.min(order.length, 4);
  return order.slice(0, count).map((a) => point * perPoint + a * nScenarios + scen);
}

/** A record as a Compare pane's result (the results strip reads these keys). */
export function asCompareSide(r: RunRecord, resolution: number) {
  const m = r.metrics;
  const summary = r.metrics.expansions !== undefined && 'path_cost' in m
    ? { expansions: m.expansions, path_length_m: m.path_length_m, path_cost: m.path_cost, minimum_clearance_m: m.min_clearance_m, compute_ms: m.compute_ms }
    : { expansions: null, path_length_m: m.path_length_m, path_cost: null, minimum_clearance_m: m.min_clearance_m, compute_ms: m.compute_ms, pose_error_m: m.final_err_xy_m ?? null, success: r.success };
  return { planner: r.name, status: r.status, summary, resolution } as unknown as CompareResult['A'];
}

/** Lockstep history from each pane's frames (a finished pane holds its last frame). */
export function lockstep(frames: ReplayFrame[][], records: RunRecord[]): LoopFrame[][] {
  const n = Math.max(0, ...frames.map((f) => f.length));
  return Array.from({ length: n }, (_, t) => frames.map((f, k) => {
    const fr = f[Math.min(t, f.length - 1)];
    const last = t >= f.length - 1, r = records[k];
    return { pose: fr.pose, truth: fr.truth, particles: null, chosen: null, hash: fr.hash, tick: fr.tick,
      summary: last && r ? { path_length_m: r.metrics.path_length_m as number, minimum_clearance_m: r.metrics.min_clearance_m as number, compute_ms: r.metrics.compute_ms as number, success: r.success } : {},
      status: last && r ? r.status : 'running' } as LoopFrame;
  }));
}

/** The spec a `#xexp=` fragment carries (M5's bounded decoder; never an unbounded parse). */
export const fragmentSpec = (s: string): ExperimentSpec => {
  const spec = boundedJson(s, false) as ExperimentSpec;
  if (!spec || spec.schema !== 'coco.experiment.v1') throw new Error('the link does not carry a coco.experiment.v1 spec');
  return spec;
};
