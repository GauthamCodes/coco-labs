// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.1: what is painted is what the rule allows. Fetch Rush rules 4's routes may cross the
 * forklift lane only at a marked crossing (coco_lab.games.crossings, written into the rounds
 * file); the Depot's look (src/game/world/describe.ts) paints those crossings' hazard stripes.
 * The two are computed separately (Python and TypeScript), so they are compared here.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe as suite, expect, it } from 'vitest';
import { CROSSING_ZONES, describe, type Spec } from '../src/game/world/describe';

const REPO = join(__dirname, '..', '..');
const spec = JSON.parse(readFileSync(join(REPO, 'worlds', 'coco_depot_v1.json'), 'utf-8')) as Spec;
const r4 = JSON.parse(readFileSync(join(REPO, 'coco_lab', 'coco_lab', 'levels', 'coco_depot_v1.fetch_rush.r4.json'), 'utf-8')) as { crossings: [number, number, number, number][]; lanes: string[] };

suite('the Depot paints the crossings rules 4 allows', () => {
  it('names the same lane zone', () => {
    expect(CROSSING_ZONES).toEqual(r4.lanes);
  });

  it('paints a hazard stripe over every crossing, across the lane', () => {
    const look = describe(spec);
    const hazards = look.paint.filter((p) => p.kind === 'hazard').map((p) => {
      const h = p as { min: [number, number]; max: [number, number] };
      return [h.min[0], h.max[0], h.min[1], h.max[1]];
    });
    expect(r4.crossings.length).toBe(2);
    for (const c of r4.crossings) {
      const hit = hazards.find((h) => h.every((v, i) => Math.abs(v - c[i]) < 1e-9));
      expect(hit, `a stripe over ${c}`).toBeTruthy();
    }
  });
});
