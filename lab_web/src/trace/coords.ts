// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Map coordinates, exactly as `coco_lab.maps.LabMap` defines them
 * (MAP_FORMAT.md): cells are [row, col] with row 0 the TOP row; the metric
 * origin is the map's BOTTOM-left corner, y up.
 *
 *     centre(row, col) = (ox + (col + .5) res,  oy + (H - 1 - row + .5) res)
 *     cell_at(x, y)    = (H - 1 - floor((y - oy)/res),  floor((x - ox)/res))
 *
 * The session log writes cells as (col, y-up) -- e.g. (130, 190) -- while a
 * bundle stores [row, col] -- [189, 130], 189 = 379 - 190. This UI shows the
 * bundle's [row, col] and metric (x, y), never the log's form. A map
 * without geo cannot place a metric point; that is an error, not a guess.
 */

import type { MapLayer } from '../bundle/model';

export class NoGeoError extends Error {
  constructor(mapId: string) {
    super(`map ${JSON.stringify(mapId)} has no geo (resolution/origin): a metric pose cannot be placed on it`);
    this.name = 'NoGeoError';
  }
}

function geo(m: MapLayer) {
  if (!m.geo) throw new NoGeoError(m.id);
  return m.geo;
}

export function cellCentre(m: MapLayer, row: number, col: number): [number, number] {
  const g = geo(m);
  const r = g.resolution;
  return [g.origin[0] + (col + 0.5) * r, g.origin[1] + (m.height - 1 - row + 0.5) * r];
}

export function cellAt(m: MapLayer, x: number, y: number): [number, number] | null {
  const g = geo(m);
  const col = Math.floor((x - g.origin[0]) / g.resolution);
  const up = Math.floor((y - g.origin[1]) / g.resolution);
  const row = m.height - 1 - up;
  return row >= 0 && row < m.height && col >= 0 && col < m.width ? [row, col] : null;
}

/** A metric point in CELL units of the canvas (x right, y down; row 0 at top). */
export function metricToCell(m: MapLayer, x: number, y: number): [number, number] {
  const g = geo(m);
  return [(x - g.origin[0]) / g.resolution, m.height - (y - g.origin[1]) / g.resolution];
}
