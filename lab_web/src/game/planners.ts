// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * The planner Play's AUTO uses (owner request, 2026-10-24). The model already holds a planner and
 * switches it on an input (`{kind: 'planner', choice}`, coco_lab.arena; the M5 Lab sends the same);
 * Play used A* only. A* stays the default and sends nothing, so every A* session, record, round
 * and golden is unchanged; another planner is sent as the run's first input, so its record says
 * so and replays (games.verify). The rounds' routes, ghost and reference bot stay A* (they are
 * the yardstick); stars and bests are kept per planner.
 */
import { readPref } from '../prefs';

/** coco_lab.arena.PLANNERS' ids, in the order offered */
export const PLAY_PLANNERS = ['astar', 'dijkstra', 'greedy', 'weighted_astar', 'bfs'] as const;
export type PlayPlanner = typeof PLAY_PLANNERS[number];

export const PLANNER_LABEL: Record<PlayPlanner, string> = {
  astar: 'A*', dijkstra: 'Dijkstra', greedy: 'Greedy best-first', weighted_astar: 'Weighted A* (w 2)', bfs: 'Breadth-first',
};

export const PLANNER_WHAT: Record<PlayPlanner, string> = {
  astar: 'Shortest path, guided by the distance still to go (octile).',
  dijkstra: 'Shortest path, searching evenly in every direction: no guess about the goal.',
  greedy: 'Heads straight for the goal by the distance still to go: fast to compute, routes can be longer.',
  weighted_astar: 'A* that trusts its guess twice as much: faster to compute, routes at most twice as long.',
  bfs: 'Counts steps, not metres: diagonal and straight moves cost the same.',
};

export const isPlayPlanner = (v: unknown): v is PlayPlanner => typeof v === 'string' && (PLAY_PLANNERS as readonly string[]).includes(v);

/** The URL's ?planner= when valid, else the saved choice, else A*. */
export function chosenPlanner(param: string | null): PlayPlanner {
  if (isPlayPlanner(param)) return param;
  return readPref<PlayPlanner>('planner', 'astar', isPlayPlanner);
}
