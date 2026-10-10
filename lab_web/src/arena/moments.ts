// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The moments a learner scrubs to in a Case File (M3.4 mission 7, M3.5's
 * Case File detective), found in the recording exactly as the viewer
 * plays it (src/arena/replay_case.ts). Pure: no I/O, no simulation.
 *
 * - **divergence**: the first tick at which the stack's belief about where
 *   the robot is lies more than {@link DIVERGENCE_M} from ground truth at
 *   that tick, the belief being the latest recorded at or before the tick.
 *   The belief is the stack's map-frame estimate (AMCL) when the recording
 *   has one; when it does not, it is the first pose of each recorded global
 *   plan, which Nav2 starts at the pose it believes the robot is at.
 *   Recordings that hold neither have no divergence moment, and say so.
 * - **refusal**: the first tick at which the stack recorded that it gave up:
 *   a `/lab/status` line with phase `follow_failed`, or a mission
 *   transition into ABORT / failed.
 *
 * Nothing about the robot is computed beyond the distance between two
 * recorded poses. The threshold is stated here, in docs/v2/CHALLENGES.md
 * and in every output that uses it.
 */

import type { FamilyMessage } from './protocol';

/** metres between belief and truth that count as "the stack is wrong about where it is" */
export const DIVERGENCE_M = 1.0;

export type BeliefSource = 'estimate' | 'global plan start' | 'none';

export interface Divergence {
  tick: number; t_world: number; error_m: number; source: string;
  belief: [number, number]; truth: [number, number];
}
export interface Refusal { tick: number; source: '/lab/status' | '/mission/state'; what: string }
export interface Moments {
  ticks: number; belief_source: BeliefSource; beliefs: number;
  divergence: Divergence | null; refusal: Refusal | null;
}

/** The parts of a parsed recording this reads (a ConvertedRun has them all). */
export interface MomentsInput {
  ticks: { tick: number; t_world: number; truth?: ArrayLike<number> | null; path?: ArrayLike<number> | null }[];
  families?: Map<number, Pick<FamilyMessage, 'channel' | 'scalars' | 'columns'>[]>;
  notes: { tick: number; text: string }[];
}

const ESTIMATE = 'coco.estimate.pose.v1';
const TRANSITION = 'coco.mission.fsm.transition.v1';
/** a map-frame estimate: AMCL by name, or any estimator re-expressed in the map frame */
const MAP_FRAME = /^amcl$|@map$/;

export function findMoments(rec: MomentsInput): Moments {
  const byTick = [...(rec.families ?? new Map()).entries()].sort((a, b) => a[0] - b[0]);
  let beliefs: { tick: number; source: string; x: number; y: number }[] = [];
  for (const [tick, fs] of byTick) {
    for (const f of fs) {
      if (f.channel === ESTIMATE && f.columns && MAP_FRAME.test(String(f.scalars?.estimator))) {
        beliefs.push({ tick, source: String(f.scalars?.estimator), x: Number(f.columns.x[0]), y: Number(f.columns.y[0]) });
      }
    }
  }
  let belief_source: BeliefSource = 'estimate';
  if (!beliefs.length) {
    belief_source = 'global plan start';
    beliefs = rec.ticks.filter((t) => t.path && t.path.length >= 2)
      .map((t) => ({ tick: t.tick, source: 'global plan start', x: Number(t.path![0]), y: Number(t.path![1]) }));
    if (!beliefs.length) belief_source = 'none';
  }

  let divergence: Divergence | null = null;
  let i = -1;
  for (const t of rec.ticks) {
    while (i + 1 < beliefs.length && beliefs[i + 1].tick <= t.tick) i += 1;
    if (i < 0 || !t.truth) continue;
    const b = beliefs[i];
    const e = Math.hypot(b.x - t.truth[0], b.y - t.truth[1]);
    if (e > DIVERGENCE_M) {
      divergence = { tick: t.tick, t_world: t.t_world, error_m: e, source: b.source,
        belief: [b.x, b.y], truth: [t.truth[0], t.truth[1]] };
      break;
    }
  }

  let refusal: Refusal | null = null;
  for (const n of rec.notes) {
    if (/"phase":"follow_failed"/.test(n.text)) {
      const code = /"error_code":(\d+)/.exec(n.text);
      refusal = { tick: n.tick, source: '/lab/status', what: `FollowPath failed${code ? `, error code ${code[1]}` : ''}` };
      break;
    }
  }
  outer: for (const [tick, fs] of byTick) {
    if (refusal && refusal.tick <= tick) break;
    for (const f of fs) {
      if (f.channel !== TRANSITION || !f.columns) continue;
      const to = String(f.columns.to_state[0]);
      if (to === 'ABORT' || to === 'failed') {
        const why = String(f.columns.reason?.[0] ?? '');
        refusal = { tick, source: '/mission/state', what: `${to}${why ? ` (${why})` : ''}` };
        break outer;
      }
    }
  }
  return { ticks: rec.ticks.length, belief_source, beliefs: beliefs.length, divergence, refusal };
}
