// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The moments mission 7 scrubs to (M3.4) are derived, not typed: every
 * entry of the committed docs/v2/data/m3/m34/moments.json is re-derived
 * here from the committed Case File by src/arena/moments.ts, and the rule
 * itself is pinned on hand-built recordings.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { create } from '@bufbuild/protobuf';
import { describe, expect, it } from 'vitest';

import { DIVERGENCE_M, findMoments, type MomentsInput } from '../src/arena/moments';
import { parseConverted } from '../src/arena/replay';
import { WorldGridSchema } from '../src/schemas/gen/coco/world/v1/world_pb';
import { REPO } from './helpers';

const committed = JSON.parse(readFileSync(join(REPO, 'docs', 'v2', 'data', 'm3', 'm34', 'moments.json'), 'utf-8')) as {
  divergence_m: number; casefiles: Record<string, unknown>;
};
const grid = create(WorldGridSchema, { mapId: 'moments', width: 1, height: 1, resolution: 1,
  occupancy: new Uint8Array(1), blocked: new Uint8Array(1) });

describe('the committed moments are what the Case Files say', () => {
  it('uses the threshold the rule states', () => {
    expect(committed.divergence_m).toBe(DIVERGENCE_M);
  });
  for (const id of Object.keys(committed.casefiles)) {
    it(id, async () => {
      const bytes = new Uint8Array(readFileSync(join(REPO, 'lab_web', 'casefiles', `${id}.mcap`)));
      const got = findMoments(await parseConverted(bytes, grid));
      expect(JSON.parse(JSON.stringify(got))).toEqual(committed.casefiles[id]);
    }, 60_000);
  }
});

// -- the rule, on recordings built by hand -------------------------------------

function rec(n: number, truth: (t: number) => [number, number], extra: Partial<MomentsInput> = {}): MomentsInput {
  return {
    ticks: Array.from({ length: n }, (_, i) => ({ tick: i + 1, t_world: (i + 1) / 10, truth: truth(i + 1) })),
    families: new Map(), notes: [], ...extra,
  };
}
const est = (estimator: string, x: number, y: number) =>
  ({ channel: 'coco.estimate.pose.v1', scalars: { estimator }, columns: { x: [x], y: [y] } });

describe('findMoments', () => {
  it('a belief exactly DIVERGENCE_M off is not a divergence; one just past it is', () => {
    const r = rec(10, () => [0, 0], { families: new Map([[3, [est('amcl', DIVERGENCE_M, 0)]], [6, [est('amcl', DIVERGENCE_M + 0.01, 0)]]]) });
    const m = findMoments(r);
    expect(m.belief_source).toBe('estimate');
    expect(m.divergence?.tick).toBe(6);
    expect(m.divergence?.source).toBe('amcl');
  });

  it('holds the latest belief until the next, so the truth can walk away from it', () => {
    const r = rec(20, (t) => [t * 0.1, 0], { families: new Map([[1, [est('amcl', 0.1, 0)]]]) });
    // truth at tick t is 0.1 t; the belief stays at 0.1, so it is > 1 m off from tick 12 (1.2 - 0.1 = 1.1)
    expect(findMoments(r).divergence?.tick).toBe(12);
  });

  it("ignores an odometry-frame estimate: it is not a belief about the map", () => {
    const r = rec(5, () => [0, 0], { families: new Map([[2, [est('robot_localization@odom', 5, 5)]]]) });
    const m = findMoments(r);
    expect(m.divergence).toBeNull();
    expect(m.belief_source).toBe('none');
  });

  it('falls back to the start of each recorded global plan, and says so', () => {
    const r = rec(8, () => [0, 0]);
    r.ticks[1].path = [0.2, 0, 1, 1];
    r.ticks[4].path = [4.0, 3.0, 5, 5];
    const m = findMoments(r);
    expect(m.belief_source).toBe('global plan start');
    expect(m.beliefs).toBe(2);
    expect(m.divergence).toMatchObject({ tick: 5, source: 'global plan start', error_m: 5 });
  });

  it('a recording with neither has no divergence moment, and says so', () => {
    const m = findMoments(rec(5, () => [0, 0]));
    expect(m).toMatchObject({ belief_source: 'none', beliefs: 0, divergence: null, refusal: null });
  });

  it('the refusal is the first give-up, from either source', () => {
    const abort = { channel: 'coco.mission.fsm.transition.v1', scalars: {}, columns: { to_state: ['ABORT'], reason: ['RETURN_FAILED'] } };
    const notes = [{ tick: 7, text: '/lab/status: {"phase":"follow_failed","error_code":103}' }];
    expect(findMoments(rec(10, () => [0, 0], { families: new Map([[4, [abort]]]), notes })).refusal)
      .toEqual({ tick: 4, source: '/mission/state', what: 'ABORT (RETURN_FAILED)' });
    expect(findMoments(rec(10, () => [0, 0], { families: new Map([[9, [abort]]]), notes })).refusal)
      .toEqual({ tick: 7, source: '/lab/status', what: 'FollowPath failed, error code 103' });
  });
});
