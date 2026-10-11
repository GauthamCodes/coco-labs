// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/** Decals that follow the terrain (M4.4): the walkable quads of World Spec v2, and a plane's draped twin. */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import * as THREE from 'three';
import { describe, expect, it } from 'vitest';

import { DRAPE_LIFT, drapedPlane, surfaces, type Elevation } from '../src/arena/render/drape';
import { REPO } from './helpers';

const spec = JSON.parse(readFileSync(join(REPO, 'worlds', 'coco_arena_v2.json'), 'utf-8')) as
  { elevation: Elevation[]; world_to_map: [number, number] };

describe('draped decals', () => {
  const quads = surfaces(spec.elevation, spec.world_to_map);

  it('every ramp and every platform top is a walkable quad, in the map frame', () => {
    expect(quads.length).toBe(spec.elevation.length);              // 8 wedges + 4 platforms
    const rise = spec.elevation.find((e) => e.kind === 'platform')!.size![2];
    for (const q of quads) {
      const zs = q.map((c) => c[2]);
      expect(Math.max(...zs)).toBeCloseTo(rise, 9);                  // every quad reaches the platform height
    }
    // bay 3's up-ramp: world foot (1, 2) -> map (3, 2), rising to map x 5
    const up = quads.find((q) => q[0][0] === 3 && q[0][1] === 2 - 1.25)!;
    expect(up.map((c) => [c[0], c[2]])).toEqual([[3, 0], [5, rise], [5, rise], [3, 0]]);
  });

  it('a draped plane samples the texture where the flat plane does', () => {
    const [w, h, cx, cy] = [24, 18, 2 + 4, 0];
    const g = drapedPlane(w, h, cx, cy, quads);
    const flat = new THREE.PlaneGeometry(w, h);
    const fp = flat.getAttribute('position'); const fu = flat.getAttribute('uv');
    const uvAt = (lx: number, ly: number) => {
      // the flat plane's uv is linear in its local x, y: interpolate from its corners
      const u0 = fu.getX(0), v0 = fu.getY(0), x0 = fp.getX(0), y0 = fp.getY(0);
      const u1 = fu.getX(3), v1 = fu.getY(3), x1 = fp.getX(3), y1 = fp.getY(3);
      return [u0 + ((lx - x0) / (x1 - x0)) * (u1 - u0), v0 + ((ly - y0) / (y1 - y0)) * (v1 - v0)];
    };
    const p = g.getAttribute('position'); const u = g.getAttribute('uv');
    for (let i = 0; i < p.count; i += 1) {
      const [eu, ev] = uvAt(p.getX(i), p.getY(i));
      expect(u.getX(i)).toBeCloseTo(eu, 6);   // float32 attributes
      expect(u.getY(i)).toBeCloseTo(ev, 6);
    }
    expect(p.count).toBe(4 * (1 + quads.length));
    let zmax = 0;
    for (let i = 0; i < p.count; i += 1) zmax = Math.max(zmax, p.getZ(i));
    expect(zmax).toBeCloseTo(spec.elevation.find((e) => e.kind === 'platform')!.size![2] + DRAPE_LIFT, 6);
  });

  it('every triangle faces up, as the flat plane does (no face culled from above)', () => {
    const g = drapedPlane(24, 18, 6, 0, quads);
    const p = g.getAttribute('position');
    const idx = g.getIndex()!;
    const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
    for (let k = 0; k < idx.count; k += 3) {
      a.fromBufferAttribute(p, idx.getX(k)); b.fromBufferAttribute(p, idx.getX(k + 1)); c.fromBufferAttribute(p, idx.getX(k + 2));
      expect(b.clone().sub(a).cross(c.clone().sub(a)).z).toBeGreaterThan(0);
    }
  });

  it('a flat world has nothing to drape', () => {
    expect(surfaces([], [2, 0])).toEqual([]);
  });
});
