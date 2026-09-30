// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The settings panel's model. Every verdict it shows -- admissible,
 * consistent, the suboptimality bound -- is LOOKED UP in the table coco_lab
 * computed at site build time (catalog `settings`); nothing here decides
 * one. The search itself runs in coco_lab, in the worker.
 */

import type { ModelAnalysis, SettingsAnalysis } from '../bundle/load';
import type { DecodedBundle } from '../bundle/model';
import type { RunSettings } from '../worker/protocol';

export interface SearchSettings {
  algorithm: string;
  heuristic: string;
  weight: number; // the slider's value; sent only for weighted_astar
  tieBreak: string;
  connectivity: 4 | 8;
}

export const ALGORITHM_NAMES: Record<string, string> = {
  bfs: 'Breadth-first (BFS)',
  dijkstra: 'Dijkstra',
  astar: 'A*',
  greedy: 'Greedy best-first',
  weighted_astar: 'Weighted A*',
};

/** Why settings cannot change on this bundle, or null when they can. */
export function settingsLocked(b: DecodedBundle): string | null {
  if (b.provenance.source_kind === 'recorded-run') {
    return 'A recorded run is shown as it happened; its settings cannot change. ' +
      'The inflated-costmap rung of the ladder is the same map, editable.';
  }
  if (b.run.graph.kind !== 'grid') {
    return 'This exhibit searches a (cell, heading) graph and keeps its recorded settings. You can still paint it.';
  }
  return null;
}

/** The bundle's own settings, as the panel starts. */
export function settingsOf(b: DecodedBundle): SearchSettings {
  const conn = Number(b.run.graph.connectivity ?? 8) === 4 ? 4 : 8;
  return {
    algorithm: b.run.algorithm,
    heuristic: b.run.heuristic,
    weight: b.run.weight ?? 1,
    tieBreak: b.run.tie_break,
    connectivity: conn,
  };
}

export function sameAsBundle(s: SearchSettings, b: DecodedBundle): boolean {
  const o = settingsOf(b);
  return s.algorithm === o.algorithm && s.heuristic === o.heuristic && s.tieBreak === o.tieBreak &&
    s.connectivity === o.connectivity && (s.algorithm !== 'weighted_astar' || s.weight === o.weight);
}

/** The run the worker should do for these settings. */
export function toRun(s: SearchSettings): RunSettings {
  return {
    algorithm: s.algorithm,
    heuristic: s.heuristic,
    weight: s.algorithm === 'weighted_astar' ? s.weight : null,
    tie_break: s.tieBreak,
  };
}

/** coco_lab's verdict for this heuristic on this move model, if computed. */
export function analysisFor(sa: SettingsAnalysis, b: DecodedBundle, connectivity: 4 | 8,
  heuristic: string): ModelAnalysis | null {
  const diag = connectivity === 8 ? Number(b.run.graph.diagonal_cost) : null;
  return sa.models.find((m) => m.connectivity === connectivity && m.heuristic === heuristic &&
    (connectivity === 4 || m.diagonal_cost === diag)) ?? null;
}

/**
 * The bound coco_lab reported: a number, null (no guarantee), or undefined
 * when the table has no entry (the page then says it does not know).
 */
export function boundFor(sa: SettingsAnalysis, m: ModelAnalysis, algorithm: string,
  weight: number): number | null | undefined {
  if (algorithm === 'weighted_astar') {
    const i = sa.weights.indexOf(weight);
    return i < 0 ? undefined : m.bounds.weighted_astar[i];
  }
  return algorithm in m.bounds ? m.bounds[algorithm as keyof ModelAnalysis['bounds']] as number | null
    : undefined;
}

export function describeBound(algorithm: string, bound: number | null | undefined): string {
  if (bound === undefined) return 'not computed for this setting';
  if (bound === null) {
    if (algorithm === 'greedy') return 'no guarantee: greedy ignores the cost so far';
    if (algorithm === 'bfs') return 'no cost guarantee: BFS counts moves, not cost';
    return 'no guarantee: this heuristic can overestimate';
  }
  if (bound === 1) return 'optimal: cost = the optimum';
  return `cost ≤ ${bound} × the optimum`;
}
