// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.3: the /rosout-style console (src/ros/rosout.ts). Only real model events become lines;
 * node names are the M6F.7 graph's; lengths are the planner's own (cells x resolution); the
 * stamp is the model's sim time; no tick without an event writes anything.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { formatLine, linesFor, nearestAhead, Rosout, type TickFacts } from '../src/ros/rosout';
import type { PlanInfo } from '../src/arena/protocol';

const GRID = { resolution: 0.1 };
const SCAN = { angle_min: -2.0944, angle_max: 2.0944, range_min: 0.15, range_max: 12 };
const base: TickFacts = { tick: 10, t_world: 1.0, source: 'idle', blocked: false, arrived: false, plans: [], pose: [1, 2, 0] };
const plan = (status: string, length: number | null, expansions: number): PlanInfo => ({
  search_id: 0, planner: 'astar', goal: [5, 6], tick: 10, status, waypoints: status === 'found' ? [[2, 2], [5, 6]] : [],
  summary: { status, expansions, path_length: length, pushes: 0, relaxes: 0, path_cost: null, path_steps: null },
});

describe('/rosout lines', () => {
  it('a found plan: global_planner, the length in metres (cells x resolution), the expansions', () => {
    const l = linesFor(base, { ...base, plans: [plan('found', 121.6, 22319)] }, null, SCAN, GRID);
    expect(l).toHaveLength(1);
    expect(formatLine(l[0])).toBe('[INFO] [1.000] [global_planner]: path found (astar): 12.16 m, 22,319 expansions');
  });

  it('no path is a WARN with the goal and the search effort', () => {
    const l = linesFor(base, { ...base, plans: [plan('no_path', null, 9001)] }, null, SCAN, GRID);
    expect(formatLine(l[0])).toBe('[WARN] [1.000] [global_planner]: no path to (5.00, 6.00): no_path after 9,001 expansions');
  });

  it('blocked: local_controller, with the nearest return in the front 40 degrees of /scan', () => {
    const ranges = new Float32Array(480).fill(5);
    ranges[240] = 0.32;     // straight ahead
    ranges[0] = 0.2;        // far to the side: not ahead
    expect(nearestAhead(ranges, SCAN)).toBeCloseTo(0.32, 6);
    const l = linesFor(base, { ...base, blocked: true }, ranges, SCAN, GRID);
    expect(formatLine(l[0])).toBe('[WARN] [1.000] [local_controller]: blocked: obstacle 0.32 m ahead');
    expect(linesFor({ ...base, blocked: true }, { ...base, blocked: true }, ranges, SCAN, GRID)).toEqual([]);   // only the moment it happens
  });

  it('the arbiter: STOP latched and released, and who has the wheels', () => {
    expect(formatLine(linesFor({ ...base, source: 'teleop' }, { ...base, source: 'stop' }, null, SCAN, GRID)[0])).toBe('[WARN] [1.000] [cmd_vel_arbiter]: STOP latched: zero to the wheels');
    expect(formatLine(linesFor({ ...base, source: 'stop' }, { ...base, source: 'teleop' }, null, SCAN, GRID)[0])).toBe('[INFO] [1.000] [cmd_vel_arbiter]: STOP released; passing teleop (/cmd_vel_teleop)');
    expect(formatLine(linesFor({ ...base, source: 'teleop' }, { ...base, source: 'planner' }, null, SCAN, GRID)[0])).toBe('[INFO] [1.000] [cmd_vel_arbiter]: passing navigation (/cmd_vel_nav)');
  });

  it('goal reached', () => {
    expect(formatLine(linesFor(base, { ...base, arrived: true }, null, SCAN, GRID)[0])).toBe('[INFO] [1.000] [local_controller]: goal reached at (1.00, 2.00)');
  });

  it('no event, no line', () => {
    expect(linesFor(base, { ...base, tick: 11, t_world: 1.1, pose: [1.2, 2, 0] }, new Float32Array(480).fill(3), SCAN, GRID)).toEqual([]);
  });

  it('every node is one of the M6F.7 graph\'s nodes', () => {
    const graph = JSON.parse(readFileSync(new URL('../../docs/v2/m6/data/ros_graph.json', import.meta.url), 'utf-8')) as { nodes: string[] };
    const r = new Rosout();
    const ticks: TickFacts[] = [base, { ...base, plans: [plan('found', 50, 10)] }, { ...base, source: 'planner' }, { ...base, source: 'stop', blocked: true },
      { ...base, source: 'teleop' }, { ...base, arrived: true }, { ...base, plans: [plan('no_path', null, 3)] }];
    for (const t of ticks) r.feed(t, new Float32Array(480).fill(1), SCAN, GRID);
    expect(r.lines.length).toBeGreaterThanOrEqual(6);
    for (const l of r.lines) expect(graph.nodes).toContain(l.node);
  });

  it('keeps the last lines only', () => {
    const r = new Rosout(3);
    for (let k = 0; k < 10; k++) r.feed({ ...base, tick: k, source: k % 2 ? 'teleop' : 'planner' }, null, SCAN, GRID);
    expect(r.lines).toHaveLength(3);
  });
});
