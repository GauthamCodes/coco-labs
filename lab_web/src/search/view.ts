// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lab 4's display arithmetic: what to DRAW at event k of a decoded search.
 *
 * Indexing and wording only. Every belief, cost and choice shown is read
 * from the bundle, where coco_lab put it; nothing here updates a belief,
 * costs an order or chooses a bay (CLAUDE.md rule 8, tested by
 * tools/test_tools.py's no-algorithm guard).
 */

import { EVENT_KINDS, type EventKind, type Problem, type SearchRun } from './decode';

export function kindAt(run: SearchRun, e: number): EventKind {
  return EVENT_KINDS[run.kinds[e]];
}

/** The belief as the robot held it after event `e` (one entry per region). */
export function beliefAt(run: SearchRun, nRegions: number, e: number): number[] {
  const k = Math.max(0, Math.min(run.n - 1, e));
  return Array.from(run.belief.subarray(k * nRegions, (k + 1) * nRegions));
}

/** coco_lab's candidate expected costs at the select at or before `e`. */
export function candidatesAt(run: SearchRun, nRegions: number, e: number): Array<number | null> {
  for (let k = Math.min(e, run.n - 1); k >= 0; k--) {
    if (kindAt(run, k) === 'select') {
      return Array.from(run.candidates.subarray(k * nRegions, (k + 1) * nRegions), (v) => (Number.isNaN(v) ? null : v));
    }
  }
  return Array(nRegions).fill(null);
}

export interface Bookkeeping {
  searched: number[];
  current: number | null;
  discovered: number | null;
  order: number[];
  surveys: number;
}

/** Regions marked searched, being surveyed, and found, by event `e` (inclusive). */
export function bookkeepingAt(run: SearchRun, e: number): Bookkeeping {
  const out: Bookkeeping = { searched: [], current: null, discovered: null, order: [], surveys: 0 };
  for (let k = 0; k <= Math.min(e, run.n - 1); k++) {
    const kind = kindAt(run, k);
    const r = run.region[k];
    if (kind === 'select') out.current = r;
    else if (kind === 'survey') { out.order.push(r); out.surveys++; }
    else if (kind === 'mark') { out.searched.push(r); out.current = null; }
    else if (kind === 'discover') { out.discovered = r; out.current = r; }
    else out.current = null;
  }
  return out;
}

/** Where the robot is after event `e`: home, or the approach of the last region surveyed. */
export function positionAt(problem: Problem, run: SearchRun, e: number): [number, number] {
  const b = bookkeepingAt(run, e);
  if (!b.order.length) return problem.start_xy;
  const r = problem.regions[b.order[b.order.length - 1]];
  return kindAt(run, Math.min(e, run.n - 1)) === 'survey' || kindAt(run, Math.min(e, run.n - 1)) === 'discover'
    ? [r.survey_pose[0], r.survey_pose[1]] : r.exit;
}

/** The legs driven by event `e`, as polylines (home -> approach -> survey pose -> exit ...). */
export function pathAt(problem: Problem, run: SearchRun, e: number): Array<[number, number]> {
  const b = bookkeepingAt(run, e);
  const pts: Array<[number, number]> = [problem.start_xy];
  for (const i of b.order) {
    const r = problem.regions[i];
    pts.push(r.approach, [r.survey_pose[0], r.survey_pose[1]], r.exit);
  }
  return pts;
}

export function regionLabel(problem: Problem, i: number | null): string {
  return i === null || i < 0 ? '—' : problem.regions[i].label;
}

/** One sentence for event `e`, from what the bundle says happened. */
export function narrate(problem: Problem, run: SearchRun, e: number, colour = 'the target'): string {
  const kind = kindAt(run, e);
  const r = regionLabel(problem, run.region[e]);
  const m = run.cost[e].toFixed(1);
  switch (kind) {
    case 'select': return `Chooses ${r} next (${m} m driven so far).`;
    case 'survey': return run.outcome[e] === 1 ? `Climbs ${r} and looks: ${colour} is there.`
      : `Climbs ${r} and looks: no ${colour}.`;
    case 'mark': return `Marks ${r} searched and backs down the ramp; the belief moves to the other bays.`;
    case 'discover': return `Discovered in ${r} after ${m} m. The search is over.`;
    case 'exhausted': return 'Every bay in the order has been searched: the target was not found.';
    case 'stopped': return 'Stopped before finding it — the challenge is failed, whatever it saved.';
  }
  return '';
}

export function fmt(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined || !Number.isFinite(v) ? '—' : v.toFixed(digits);
}

export function pct(v: number | null | undefined): string {
  return v === null || v === undefined || !Number.isFinite(v) ? '—' : `${Math.round(v * 100)}%`;
}

/** Run styles: one colour per policy, Okabe–Ito. */
export const RUN_STYLE: Record<string, { label: string; color: string; what: string }> = {
  expected_cost: { label: "the robot's policy", color: '#0072B2',
    what: 'every remaining order costed exactly; the cheapest expected search, re-planned after each look' },
  given: { label: 'your order', color: '#D55E00', what: 'the bays in the order you chose' },
  nearest: { label: 'nearest first', color: '#009E73', what: 'always the cheapest next bay' },
  most_likely: { label: 'most likely first', color: '#CC79A7', what: 'always the bay with the most belief × detection' },
};

export function styleOf(policy: string) {
  return RUN_STYLE[policy] ?? { label: policy, color: '#555', what: '' };
}

/** A matrix row's outcome in words: a COMPLETE that relocalised is not a failure. */
export function outcomeWords(outcome: string, reason: string | null): string {
  const r = reason && reason !== '--' ? reason : null;
  if (outcome === 'COMPLETE') return r === 'LOCALIZATION_DEGRADED' ? 'COMPLETE (after a relocalisation)' : 'COMPLETE';
  return r ? `${outcome} (${r})` : outcome;
}
