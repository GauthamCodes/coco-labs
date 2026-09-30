// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The robot's footprint swept along a path, as polygons in canvas CELL
 * units, for drawing. The dimensions come from the catalog (derived from
 * coco_config at site build time); the map's resolution places them. A
 * map without geo cannot place a metric footprint, and says so.
 */

import type { Footprint } from '../bundle/load';
import type { Geo } from '../bundle/model';

export type Point = [number, number]; // [x, y] in cell units, x = col
export type Swept =
  | { placed: true; polygons: Point[][]; halfLength: number; halfWidth: number }
  | { placed: false; reason: string };

/**
 * One rectangle per path cell, centred on the cell and turned to the path's
 * local direction (the chord from the previous cell to the next).
 */
export function sweptFootprint(path: Array<[number, number]>, geo: Geo | null,
  fp: Footprint | undefined): Swept {
  if (!fp) return { placed: false, reason: 'this site was built without the footprint' };
  if (!geo) return { placed: false, reason: 'no geo — cannot place a metric footprint on this map' };
  if (path.length === 0) return { placed: false, reason: 'no path to sweep' };
  const hl = fp.length_m / 2 / geo.resolution;
  const hw = fp.width_m / 2 / geo.resolution;
  const polygons: Point[][] = [];
  for (let i = 0; i < path.length; i++) {
    const a = path[Math.max(0, i - 1)];
    const b = path[Math.min(path.length - 1, i + 1)];
    const theta = Math.atan2(b[0] - a[0], b[1] - a[1]);
    const cx = path[i][1] + 0.5;
    const cy = path[i][0] + 0.5;
    const c = Math.cos(theta);
    const s = Math.sin(theta);
    polygons.push([[hl, hw], [hl, -hw], [-hl, -hw], [-hl, hw]].map(
      ([u, v]) => [cx + u * c - v * s, cy + u * s + v * c] as Point));
  }
  return { placed: true, polygons, halfLength: hl, halfWidth: hw };
}
