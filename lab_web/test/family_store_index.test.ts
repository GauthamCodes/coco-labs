// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The family store's per-estimator index (M3.3): "the latest estimate of
 * estimator E at or before tick T" is a binary search over E's own batches,
 * and gives the same answer the old walk back through every estimator did.
 * A Case File's recorded estimators (amcl, robot_localization@odom,
 * wheel_odometry@map) are names the Localise lens never looked for; the
 * walk then ran 4,000 ticks deep on every redraw (seek 574 ms, measured).
 */

import { describe, expect, it } from 'vitest';

import { FamilyStore, type FamilyBatch } from '../src/arena/lens/store';

const CH = 'coco.estimate.pose.v1';
const est = (tick: number, estimator: string, x: number): FamilyBatch => ({
  channel: CH, tick, columns: { x: Float64Array.from([x]), y: Float64Array.from([0]), theta: Float64Array.from([0]) }, scalars: { estimator },
});

/** The answer the lens used to compute: walk back tick by tick through every estimator's batches. */
function walkBack(s: FamilyStore, estimator: string, tick: number): FamilyBatch | null {
  for (let t = tick; t >= 0;) {
    const b = s.latest(CH, t);
    if (!b) return null;
    const same = s.at(CH, b.tick).filter((x) => x.scalars.estimator === estimator);
    if (same.length) return same.at(-1)!;
    t = b.tick - 1;
  }
  return null;
}

describe('the per-estimator index', () => {
  const s = new FamilyStore();
  // interleaved: amcl every 7 ticks, wheel odometry every tick, an EKF from tick 50
  for (let k = 1; k <= 300; k += 1) {
    if (k % 7 === 0) s.add(est(k, 'amcl', k));
    s.add(est(k, 'wheel_odometry@map', -k));
    if (k >= 50 && k % 3 === 0) s.add(est(k, 'ekf', 1000 + k));
  }

  it('lists the estimators seen, in first-seen order', () => {
    expect(s.scalarValues(CH)).toEqual(['wheel_odometry@map', 'amcl', 'ekf']);
  });

  it('answers what the walk back answered, at every tick, for every estimator', () => {
    for (const e of ['amcl', 'wheel_odometry@map', 'ekf', 'mcl']) {
      for (let t = 0; t <= 310; t += 1) expect(s.latestWhere(CH, e, t)).toBe(walkBack(s, e, t));
    }
  });

  it('returns an estimator\'s own trajectory up to a tick', () => {
    const tr = s.beforeWhere(CH, 'amcl', 30);
    expect(tr.map((b) => b.tick)).toEqual([7, 14, 21, 28]);
    expect(s.beforeWhere(CH, 'nobody', 30)).toEqual([]);
    expect(s.beforeWhere(CH, 'ekf', 10)).toEqual([]);
  });

  it('is cleared with the store', () => {
    const t = new FamilyStore();
    t.add(est(1, 'amcl', 0));
    t.clear();
    expect(t.scalarValues(CH)).toEqual([]);
    expect(t.latestWhere(CH, 'amcl', 5)).toBeNull();
  });
});
