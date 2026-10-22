// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// G1.4: the chase camera never clips through walls. Twenty scripted paths hug
// walls, turn in corners, run maze corridors and rack aisles, back into walls
// and spin in place beside them; at every frame (60 Hz, after the spring has
// settled for 1 s) the camera must not be inside any solid part, and nothing
// solid may stand between it and COCO. The camera ray-casts against the same
// instance matrices the renderer draws (build3d.colliderMeshes).

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe as group, expect, it } from 'vitest';

import * as THREE from 'three';

import { GameCamera, CHASE } from '../src/game/render/camera';
import { colliderMeshes } from '../src/game/world/build3d';
import { describe, type Part, type Spec } from '../src/game/world/describe';
import { REPO } from './helpers';

type Pose = [number, number, number];
const load = (id: string) => JSON.parse(readFileSync(join(REPO, 'worlds', `${id}.json`), 'utf-8')) as Spec;

/** Whether the segment a->b passes through the box (slab test), ignoring the last `skip` metres at b. */
function segmentHits(a: number[], b: number[], p: Part): boolean {
  let t0 = 0, t1 = 1;
  for (let k = 0; k < 3; k++) {
    const d = b[k] - a[k];
    if (Math.abs(d) < 1e-12) { if (a[k] <= p.min[k] || a[k] >= p.max[k]) return false; continue; }
    let u = (p.min[k] - a[k]) / d, v = (p.max[k] - a[k]) / d;
    if (u > v) [u, v] = [v, u];
    t0 = Math.max(t0, u); t1 = Math.min(t1, v);
    if (t0 >= t1) return false;
  }
  return true;
}
const inside = (q: number[], p: Part, pad: number) => q[0] > p.min[0] - pad && q[0] < p.max[0] + pad && q[1] > p.min[1] - pad && q[1] < p.max[1] + pad && q[2] > p.min[2] - pad && q[2] < p.max[2] + pad;

/** A path: poses at 60 Hz from a start, driving at `v` with yaw rate `w` (piecewise), as the model would. */
function path(start: Pose, legs: [number, number, number][]): { pose: Pose; v: number }[] {
  const out: { pose: Pose; v: number }[] = [];
  let [x, y, th] = start;
  for (let k = 0; k < 60; k++) out.push({ pose: [x, y, th], v: 0 }); // settle
  for (const [v, w, s] of legs) for (let k = 0; k < s * 60; k++) { th += w / 60; x += v * Math.cos(th) / 60; y += v * Math.sin(th) / 60; out.push({ pose: [x, y, th], v }); }
  return out;
}

function run(look: ReturnType<typeof describe>, poses: { pose: Pose; v: number }[]) {
  const cam = new GameCamera();
  cam.colliders = colliderMeshes(look);
  cam.setAspect(915, 412);
  const solids = look.parts.filter((p) => p.cls === 'solid' || p.cls === 'wall');
  const robotBoxes = new Set<string>();
  const faults: string[] = [];
  let maxPull = 0, minDist = Infinity, minZ = Infinity, maxElev = 0;
  const screenY: number[] = [];
  poses.forEach(({ pose, v }, k) => {
    cam.update(1 / 60, pose, 0, v);
    if (k < 60) return;
    const c = cam.camera.position.toArray();
    const head = [pose[0], pose[1], 0.25];
    maxPull = Math.max(maxPull, cam.lastPull);
    maxElev = Math.max(maxElev, cam.lastElev);
    minDist = Math.min(minDist, Math.hypot(c[0] - head[0], c[1] - head[1], c[2] - head[2]));
    minZ = Math.min(minZ, c[2]);
    cam.camera.updateMatrixWorld();
    screenY.push(new THREE.Vector3(pose[0], pose[1], CHASE.bodyZ).project(cam.camera).y);
    for (const p of solids) {
      if (inside(c, p, 0.02)) faults.push(`frame ${k}: camera inside ${p.id}`);
      else if (!robotBoxes.has(p.id) && segmentHits(c, head, p)) faults.push(`frame ${k}: ${p.id} between the camera and COCO`);
    }
  });
  return { faults, maxPull, minDist, minZ, maxElev, screenY };
}

// Twenty paths: [world, start pose (map frame), legs of (v m/s, w rad/s, seconds)]
const PATHS: [string, string, Pose, [number, number, number][]][] = [
  ['depot', 'along the south wall, west', [30, 0.6, Math.PI], [[0.5, 0, 6]]],
  ['depot', 'along the south wall, east, turning out', [20, 0.6, 0], [[0.5, 0, 4], [0.3, 0.8, 2]]],
  ['depot', 'into the west hall corner', [16.2, 2.0, Math.PI * 0.75], [[0.5, 0, 2.5], [0, 1.2, 2.6]]],
  ['depot', 'reverse into the south wall', [26, 1.2, Math.PI / 2], [[-0.3, 0, 2.5]]],
  ['depot', 'spin in place beside the south wall', [28, 0.55, 0], [[0, 1.2, 5.3]]],
  ['depot', 'down high-bay aisle 1', [16.5, 17.3, 0], [[0.5, 0, 8]]],
  ['depot', 'down high-bay aisle 2, turning', [31, 21.9, Math.PI], [[0.5, 0, 6], [0.3, -0.6, 2]]],
  ['depot', 'along a rack face, close', [18, 16.4, 0], [[0.4, 0, 6]]],
  ['depot', 'the maze entrance and a corridor', [15.2, 3, Math.PI], [[0.5, 0, 3], [0.2, 0.9, 2]]],
  ['depot', 'a maze cell, spinning', [11, 1, 0], [[0, 1.0, 6.3]]],
  ['depot', 'through the office entrance', [15.5, 26.5, Math.PI], [[0.4, 0, 4]]],
  ['depot', 'along the pallet staging row', [37.6, 3.6, 0], [[0.4, 0, 8]]],
  ['depot', 'beside the mezzanine rail', [37, 23.65, 0], [[0.4, 0, 6]]],
  ['depot', 'beside the east hall wall, north', [47.4, 12, Math.PI / 2], [[0.5, 0, 6]]],
  ['depot', 'into the dock\'s east corner', [45.5, 1.5, 0], [[0.5, 0, 3], [0, 1.2, 2]]],
  ['proving_v1', 'along the arena wall', [0, 0, 0], [[0.5, 0, 5]]],
  ['proving_v1', 'spin at the start', [0, 0, 0], [[0, 1.2, 5.3]]],
  ['proving_v1', 'reverse in the arena', [1, -1, Math.PI], [[-0.3, 0, 3]]],
  ['proving_v1', 'arc from the start', [0, 0, 0], [[0.3, 0.3, 4]]],
  ['proving_v1', 'into a bay', [-2, 2, Math.PI], [[0.4, 0, 4]]],
];

group('G1.4 chase camera: 20 scripted paths, no clipping', () => {
  const looks = { depot: describe(load('coco_depot_v1')), proving_v1: describe(load('coco_arena_v1')) };
  const solidsAt = (look: ReturnType<typeof describe>, x: number, y: number) => look.footprints.filter((f) => f.kind === 'box' && x > f.min[0] - 0.22 && x < f.max[0] + 0.22 && y > f.min[1] - 0.22 && y < f.max[1] + 0.22);
  it('has twenty paths', () => expect(PATHS.length).toBe(20));
  for (const [world, name, start, legs] of PATHS) {
    it(`${world}: ${name}`, () => {
      const look = looks[world as keyof typeof looks];
      const poses = path(start, legs);
      // a path must keep COCO's circle in free space, as the model would
      const blocked = poses.flatMap(({ pose }) => solidsAt(look, pose[0], pose[1]).map((f) => f.id));
      expect(blocked, 'the scripted path itself drives into a solid').toEqual([]);
      const { faults, minDist, minZ, screenY } = run(look, poses);
      expect(faults.slice(0, 5)).toEqual([]);
      // G1.12: never closer than minDist nor lower than minHeight; COCO in the upper-middle third
      expect(minDist).toBeGreaterThanOrEqual(CHASE.minDist - 1e-6);
      expect(minZ).toBeGreaterThanOrEqual(CHASE.minHeight - 1e-6);
      const off = screenY.filter((y) => y < 0 || y > 1 / 3);
      expect(off.length, `COCO left the upper-middle third on ${off.length} frames (e.g. ${off[0]})`).toBe(0);
    });
  }
  it('a wide orbit beside a wall stays inside the hall', () => {
    const look = looks.depot;
    const cam = new GameCamera();
    cam.colliders = colliderMeshes(look);
    cam.setMode('orbit');
    const solids = look.parts.filter((p) => p.cls === 'solid' || p.cls === 'wall');
    const faults: string[] = [];
    for (let k = 0; k < 72; k++) {
      cam.orbit.yaw = (k / 72) * Math.PI * 2; cam.orbit.dist = 13; cam.orbit.pitch = 0.42;
      for (let f = 0; f < 30; f++) cam.update(1 / 60, [24, 0.6, 0], 0, 0);
      const c = cam.camera.position.toArray();
      for (const p of solids) if (inside(c, p, 0.02) || segmentHits(c, [24, 0.6, 0.2], p)) faults.push(`yaw ${k * 5}: ${p.id}`);
    }
    expect(faults.slice(0, 5)).toEqual([]);
  });
  it('beside a wall the boom rises instead of moving in (the test is not vacuous)', () => {
    const look = looks.depot;
    // facing away from the south wall: the camera's resting spot is inside the wall
    const { faults, maxPull, maxElev, minDist } = run(look, path([24, 0.6, Math.PI / 2], [[0, 0, 1]]));
    expect(faults).toEqual([]);
    expect(maxElev).toBeGreaterThan(CHASE.elev + 0.1);
    expect(minDist).toBeGreaterThanOrEqual(CHASE.minDist - 1e-6);
    expect(maxPull).toBeLessThanOrEqual(CHASE.dist - CHASE.minDist + 1e-6);
  });
  it('at rest in the open, COCO\'s centre sits at CHASE.screenY', () => {
    const { screenY } = run(looks.depot, path([30, 12, 0], [[0, 0, 1]]));
    expect(Math.abs(screenY[screenY.length - 1] - CHASE.screenY)).toBeLessThan(0.01);
  });
});
