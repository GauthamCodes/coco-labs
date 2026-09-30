// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Colours. Search states and markers use the Okabe–Ito palette (Okabe &
 * Ito, "Color Universal Design", 2008), which stays distinguishable under
 * the common colour-vision deficiencies. The assignment is fixed here and
 * pinned by `test/render.test.ts`.
 */

export const OKABE_ITO = {
  black: '#000000',
  orange: '#E69F00',
  skyBlue: '#56B4E9',
  bluishGreen: '#009E73',
  yellow: '#F0E442',
  blue: '#0072B2',
  vermillion: '#D55E00',
  reddishPurple: '#CC79A7',
} as const;

export const PALETTE = {
  open: OKABE_ITO.skyBlue,
  closed: OKABE_ITO.orange,
  path: OKABE_ITO.vermillion,
  start: OKABE_ITO.bluishGreen,
  goal: OKABE_ITO.reddishPurple,
  // recorded-run overlays
  groundTruth: OKABE_ITO.blue,
  amcl: OKABE_ITO.yellow,
  plan: OKABE_ITO.black,
  // the map
  free: '#FFFFFF',
  occupied: '#000000',
  unknown: '#8C8C8C',
  /** Cost layer on free cells: white (0) to this at the map's maximum cost. */
  costMax: '#C9C1B1',
  /** The edge of COCO's footprint swept along the path (Okabe–Ito blue). */
  sweepEdge: OKABE_ITO.blue,
} as const;

export function rgb(hex: string): [number, number, number] {
  const v = parseInt(hex.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}
