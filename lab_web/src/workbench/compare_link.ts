// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1: the link from a run in the results table to Compare. It carries the
 * experiment's spec and the run's index, so Compare replays that very run (the same
 * coco_lab.experiments run, its numbers identical to the table's), opening at the
 * tick where it failed; `world` and `goal` keep the link meaningful to a Compare that
 * only knows its live mode.
 */
import type { RunRecord } from './pool';
import { worldId, type ExperimentSpec } from './spec';

const BASE = import.meta.env.BASE_URL;
const COMPARE_WORLD: Record<string, string> = { coco_depot_v1: 'depot', coco_depot_colours_v1: 'depot_colours', coco_depot_clutter_v1: 'depot_clutter', coco_arena_v2: 'v2', coco_arena_v1: 'v1' };

const b64 = (s: string) => btoa(String.fromCharCode(...new TextEncoder().encode(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

export function compareHrefFor(spec: ExperimentSpec, r: RunRecord): string {
  const q = new URLSearchParams({ view: 'compare', world: COMPARE_WORLD[worldId(spec)] ?? 'v1', xrun: String(r.index) });
  if (r.fail_tick !== null && !r.success) q.set('t', String(r.fail_tick));
  return `${BASE}?${q.toString()}#xexp=${b64(JSON.stringify(spec))}`;
}
