// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Floor decals that follow the terrain (M4.4; README §5.3).
 *
 * A computation layer drawn as a texture over the map (the M1 grid, a lens's
 * map) is one flat plane. In 3D on a World Spec v2 arena it would sit at the
 * floor, under the platforms. Draping gives the same mesh -- the same
 * material, the same texture -- a geometry shaped like the walkable surface:
 * the floor, every ramp's slope and every platform's top, each lifted a few
 * millimetres over the arena's own surface, with UVs from map coordinates so
 * a cell lands where it is. Geometry only (from the spec's elevation
 * primitives, as the arena asset is): it computes nothing the model does.
 */

import * as THREE from 'three';

/** A World Spec v2 elevation primitive (worlds/coco_arena_v2.yaml; ADR 0007), world frame. */
export interface Elevation {
  id: string; kind: 'wedge' | 'platform';
  foot?: [number, number]; yaw?: number; run?: number; rise?: number; width?: number;
  center?: [number, number]; size?: [number, number, number];
}

/** One walkable quad: four corners (x, y, z), map frame, in order around it. */
export type Quad = [number, number, number][];

/** The decal's height over the arena's own surface (m): clear of z-fighting, invisible as a gap. */
export const DRAPE_LIFT = 0.004;

/** The ramps' slopes and the platforms' tops, in the map frame. Wedges are axis-aligned (ADR 0007). */
export function surfaces(elevation: Elevation[], worldToMap: [number, number]): Quad[] {
  const [dx, dy] = worldToMap;
  const out: Quad[] = [];
  for (const e of elevation) {
    if (e.kind === 'wedge' && e.foot && e.run && e.rise && e.width) {
      const dir = Math.cos(e.yaw ?? 0) > 0 ? 1 : -1;
      const fx = e.foot[0] + dx, y0 = e.foot[1] + dy - e.width / 2, y1 = y0 + e.width, tx = fx + dir * e.run;
      out.push([[fx, y0, 0], [tx, y0, e.rise], [tx, y1, e.rise], [fx, y1, 0]]);
    } else if (e.kind === 'platform' && e.center && e.size) {
      const [cx, cy] = [e.center[0] + dx, e.center[1] + dy];
      const [sx, sy, h] = e.size;
      out.push([[cx - sx / 2, cy - sy / 2, h], [cx + sx / 2, cy - sy / 2, h], [cx + sx / 2, cy + sy / 2, h], [cx - sx / 2, cy + sy / 2, h]]);
    }
  }
  return out;
}

/**
 * The draped twin of a `width` x `height` plane centred at (cx, cy): the floor plane plus every quad,
 * in the plane's local frame (as PlaneGeometry is), UVs from map position (as PlaneGeometry's are).
 */
export function drapedPlane(width: number, height: number, cx: number, cy: number, quads: Quad[]): THREE.BufferGeometry {
  const x0 = cx - width / 2, y0 = cy - height / 2;
  const pos: number[] = [];
  const uv: number[] = [];
  const idx: number[] = [];
  const quad = (q: Quad, lift: number) => {
    const b = pos.length / 3;
    for (const [x, y, z] of q) {
      pos.push(x - cx, y - cy, z + lift);
      uv.push((x - x0) / width, (y - y0) / height);
    }
    // wound counter-clockwise seen from above (+z), as PlaneGeometry is
    const ccw = (q[1][0] - q[0][0]) * (q[2][1] - q[0][1]) - (q[1][1] - q[0][1]) * (q[2][0] - q[0][0]) > 0;
    idx.push(...(ccw ? [b, b + 1, b + 2, b, b + 2, b + 3] : [b, b + 2, b + 1, b, b + 3, b + 2]));
  };
  quad([[x0, y0, 0], [x0 + width, y0, 0], [x0 + width, y0 + height, 0], [x0, y0 + height, 0]], 0);
  for (const q of quads) quad(q, DRAPE_LIFT);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(new Array(pos.length).fill(0).map((_, i) => (i % 3 === 2 ? 1 : 0)), 3));
  g.setIndex(idx);
  return g;
}
