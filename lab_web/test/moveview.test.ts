// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// Lab 5's display bookkeeping against the golden bundles coco_lab wrote: what
// the page draws at a step or a time is read from the bundle, never planned
// or controlled here.

import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { loadDriveBytes, loadReplanBytes } from '../src/move/decode';
import {
  candidatesAt, chosenAt, evalAt, expandedIn, footprint, indexAt, knownAt, monitorAt, planAt, robotAt, roundAt,
  rowAt, steps, trackAt, truthAt, valuesAt,
} from '../src/move/view';
import { readBundleDir, REPO } from './helpers';

const DIR = 'coco_lab/test/fixtures/move_bundles';

async function small() {
  const { manifest, arrays } = readBundleDir(join(REPO, DIR, 'replan_small'));
  return loadReplanBytes(manifest, arrays);
}

async function toy() {
  const { manifest, arrays } = readBundleDir(join(REPO, DIR, 'drive_toy_gz'));
  return loadDriveBytes(manifest, arrays);
}

describe('Lab 5 replanning view', () => {
  it('ends with the map coco_lab ended with', async () => {
    const b = await small();
    expect(Array.from(knownAt(b, steps(b)))).toEqual(Array.from(b.knownFinal));
  });

  it('starts the walk at the start and follows each plan from where the robot stands', async () => {
    const b = await small();
    expect(robotAt(b, 0)).toEqual(b.world.start);
    expect(robotAt(b, steps(b))).toEqual(b.world.goal);
    for (let k = 0; k < steps(b); k++) {
      const plan = planAt(b, k);
      expect(plan[0]).toEqual(robotAt(b, k));        // the plan starts at the robot
      expect(plan[plan.length - 1]).toEqual(b.world.goal);
    }
  });

  it('puts each round in force from its step', async () => {
    const b = await small();
    b.rounds.forEach((r, i) => expect(roundAt(b, r.step)).toBe(i));
    expect(roundAt(b, 0)).toBe(0);
  });

  it('applies the schedule to the world, not to the map', async () => {
    const b = await small();
    const [step, cells] = b.world.schedule[0];
    const [r, c] = cells[0];
    const i = r * b.world.width + c;
    expect(truthAt(b, step - 1)[i]).toBe(b.truth[i]);
    expect(truthAt(b, step)[i]).toBe(1);
  });

  it('counts the cells each round touched, as the trace does', async () => {
    const b = await small();
    b.rounds.forEach((r, i) => {
      const cells = expandedIn(b, i);
      expect(cells.length).toBeLessThanOrEqual(r.dstar_expansions);
      if (r.dstar_expansions > 0) expect(cells.length).toBeGreaterThan(0);
    });
  });
});

describe('Lab 5 drive view', () => {
  it('finds rows by time without interpolating', async () => {
    const b = await toy();
    const r = b.runs[0];
    expect(rowAt(r.gt, 4, -1)).toBe(-1);
    expect(rowAt(r.gt, 4, 0)).toBe(0);
    expect(rowAt(r.gt, 4, 0.55)).toBe(5);
    expect(valuesAt(r.gt, 4, 0.55)).toEqual(Array.from(r.gt.subarray(21, 24)));
    expect(indexAt(r.chosenT, 0.4)).toBe(-1);
    expect(chosenAt(r, 0.6)).toEqual([[0.05, 0], [0.2, 0]]);
  });

  it('interpolates an actor only inside its track', async () => {
    const b = await toy();
    const tr = b.runs[0].actors.actor_0;
    expect(trackAt(tr, 1.0)).toEqual([1.5, 0]);
    expect(trackAt(tr, 3.0)).toBeNull();
  });

  it('reads candidates, counts and the monitor from the bundle', async () => {
    const b = await toy();
    const r = b.runs[0];
    const c = candidatesAt(r.rollouts, 0.6)!;
    expect(c.n).toBe(819);
    expect(c.nValid).toBe(400);
    expect(c.cands.map((x) => [x.valid, x.best])).toEqual([[true, true], [false, false]]);
    expect(candidatesAt(r.rollouts, 5.0)).toBeNull();     // too old to show
    expect(evalAt(r, 1.2)).toEqual([819, 0]);
    expect(monitorAt(r, 0.5)).toBe('not acting');
    expect(monitorAt(r, 1.5)).toBe('slowdown (PolygonSlow)');
  });

  it('draws the footprint Lab 1 sweeps', () => {
    const f = footprint(0, 0, 0);
    expect(f[0][0]).toBeCloseTo(0.1485);
    expect(f[0][1]).toBeCloseTo(0.157);
  });
});
