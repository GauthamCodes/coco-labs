// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// G1.5 decorative honesty (G1 prompt §0): a thing that looks solid is solid in
// the model and in Gazebo; a thing the robot can pass through does not look
// solid. Every decorative part either matches a collision footprint, sits on a
// wall's face, hangs overhead, is a flat decal (<= 2 cm), or lies outside the
// drivable area. The footprints are the World Spec's own boxes and elevation
// solids: the same ones the model rasterises and the SDF generator writes.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe as group, expect, it } from 'vitest';

import { DECAL_Z, OVERHEAD_Z, WALL_SKIN, describe, footprints, honestyViolations, type Spec, type WorldLook } from '../src/game/world/describe';
import { REPO } from './helpers';

const WORLDS = ['coco_depot_v1', 'coco_arena_v1', 'coco_arena_v2'];
const load = (id: string) => JSON.parse(readFileSync(join(REPO, 'worlds', `${id}.json`), 'utf-8')) as Spec;

group('G1.5 decorative honesty', () => {
  for (const id of WORLDS) {
    const spec = load(id);
    const look = describe(spec);
    it(`${id}: every decorative part is honest`, () => {
      expect(honestyViolations(look)).toEqual([]);
    });
    it(`${id}: every collision footprint is drawn (a solid with no look would be invisible)`, () => {
      const drawn = new Set(look.parts.filter((p) => p.cls === 'solid').map((p) => p.footprint));
      for (const f of footprints(spec)) expect(drawn.has(f.id), f.id).toBe(true);
    });
    it(`${id}: the classes mean what they say`, () => {
      for (const p of look.parts) {
        if (p.cls === 'overhead') expect(p.min[2]).toBeGreaterThanOrEqual(OVERHEAD_Z);
        if (p.cls === 'decal') expect(p.max[2] - p.min[2]).toBeLessThanOrEqual(DECAL_Z + 1e-9);
      }
    });
  }

  it('the checker catches each kind of dishonesty (it is not vacuous)', () => {
    const look = describe(load('coco_depot_v1'));
    const wall = look.parts.find((p) => p.cls === 'solid' && p.mat === 'panel')!;
    const bad = (mutate: (l: WorldLook) => void) => { const l: WorldLook = structuredClone(look); mutate(l); return honestyViolations(l); };
    // a crate standing in the open floor, claiming to be part of a rack
    expect(bad((l) => l.parts.push({ ...wall, id: 'fake', mat: 'crate', min: [23, 4, 0], max: [23.5, 4.5, 0.5] }))).not.toEqual([]);
    // a "decal" 10 cm tall
    expect(bad((l) => l.parts.push({ id: 'thick', shape: 'box', mat: 'hazard', cls: 'decal', min: [23, 4, 0], max: [24, 5, 0.1] }))).not.toEqual([]);
    // a wall fixture standing 20 cm off its wall
    expect(bad((l) => l.parts.push({ ...wall, id: 'off', cls: 'wall', min: [wall.min[0], wall.max[1] + 0.2, 1], max: [wall.min[0] + 1, wall.max[1] + 0.3, 2] }))).not.toEqual([]);
    // a low "overhead" sign the robot would drive under at head height
    expect(bad((l) => l.parts.push({ id: 'low', shape: 'box', mat: 'exit', cls: 'overhead', min: [23, 4, 1], max: [24, 5, 1.2] }))).not.toEqual([]);
    // a forklift part sticking out of its collision box
    expect(bad((l) => { l.actors[0].parts[0].max[0] = l.actors[0].length; })).not.toEqual([]);
    expect(WALL_SKIN).toBeLessThanOrEqual(0.05);
  });

  it('the Proving Ground keeps every one of its 70 boxes, exactly (visual restyle only)', () => {
    const spec = load('coco_arena_v1');
    const look = describe(spec);
    expect(spec.boxes.length).toBe(70);
    for (const b of spec.boxes) {
      const part = look.parts.find((p) => p.id === b.id)!;
      const [dx, dy] = spec.world_to_map;
      expect(part.min[0]).toBeCloseTo(b.center[0] - b.size[0] / 2 + dx, 9);
      expect(part.max[1]).toBeCloseTo(b.center[1] + b.size[1] / 2 + dy, 9);
      expect(part.max[2]).toBeCloseTo(b.height, 9);
    }
  });
});
