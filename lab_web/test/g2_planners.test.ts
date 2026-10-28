// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
// The AUTO planner choice (owner request 2026-10-24): A* keeps every key it had; only real
// coco_lab planners are accepted; another planner's bests are kept apart.
import { describe, expect, it } from 'vitest';
import { chosenPlanner, isPlayPlanner, PLANNER_LABEL, PLAY_PLANNERS } from '../src/game/planners';
import { bestKey } from '../src/game/GameApp';

describe('AUTO planner choice', () => {
  it('offers exactly coco_lab.arena.PLANNERS, A* first', () => {
    expect([...PLAY_PLANNERS].sort()).toEqual(['astar', 'bfs', 'dijkstra', 'greedy', 'weighted_astar']);
    expect(PLAY_PLANNERS[0]).toBe('astar');
    for (const p of PLAY_PLANNERS) expect(PLANNER_LABEL[p]).toBeTruthy();
  });
  it('accepts only known planners from the URL, else the saved one, else A*', () => {
    expect(isPlayPlanner('greedy')).toBe(true);
    expect(isPlayPlanner('dstar_lite')).toBe(false);
    expect(chosenPlanner('dijkstra')).toBe('dijkstra');
    expect(chosenPlanner('rm -rf')).toBe('astar');
    expect(chosenPlanner(null)).toBe('astar');
  });
  it("keeps A*'s best key as it was and gives other planners their own", () => {
    expect(bestKey(1, 'phone')).toBe('coco.play.best.v1.g1-fetch-rush.r5-phone.seed-1');
    expect(bestKey(1, 'phone', 'astar')).toBe('coco.play.best.v1.g1-fetch-rush.r5-phone.seed-1');
    expect(bestKey(2, 'full', 'greedy')).toBe('coco.play.best.v1.g1-fetch-rush.r5-full.seed-2.planner-greedy');
  });
});
