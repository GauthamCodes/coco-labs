// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R5.3: Model vs LIVE (src/live/model_vs_live.ts): the MODEL side is an R1 experiment spec the
 * Python model accepts (one controller, one inline scenario from the LIVE pose), and the LIVE side
 * measures the driven distance on Gazebo truth and the sim time from the goal to Nav2's verdict.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { LiveLeg, modelSide, modelSpec, sideWords } from '../src/live/model_vs_live';
import type { GameTick } from '../src/game/session';

const tick = (k: number, t: number, x: number, status: string | null, extra: Partial<GameTick> = {}): GameTick => ({
  tick: k, t_world: t, pose: [x, 6, 0], v: 0.3, w: 0, truth: [x, 6, 0], mode: 'live', blocked: false, arrived: false, hash: '', chain: '',
  plans: status ? [{ search_id: 0, planner: 'Nav2', goal: [26, 6], tick: k, status: 'found', summary: { nav_status: status }, waypoints: [] }] : [], ...extra });

describe('Model vs LIVE', () => {
  it('builds the R1 experiment the Python model accepts', () => {
    const s = modelSpec('coco_depot_v1', [23, 6, 0.123456789], [26, 6.5]);
    const py = readFileSync(new URL('../../coco_lab/coco_lab/experiments.py', import.meta.url), 'utf-8');
    expect(py).toContain(`SCHEMA = '${s.schema}'`);
    expect(s.family).toBe('control');
    expect(s.algorithms).toEqual([{ name: 'rpp' }]);
    expect(s.scenarios.scenarios[0]).toEqual({ id: 'live-goal', seed: 1, start: [23, 6, 0.1235], goal: [26, 6.5] });
  });

  it('measures the LIVE leg on truth, in sim time, until Nav2 finishes', () => {
    const leg = new LiveLeg([26, 6], [23, 6, 0], 100);
    expect(leg.add(tick(0, 100.0, 23.0, 'executing'))).toBe(false);
    expect(leg.add(tick(1, 101.0, 23.3, 'executing'))).toBe(false);
    expect(leg.add(tick(2, 102.0, 23.31, 'executing'))).toBe(false);   // < 2 cm: not a new drawn point (still driven)
    expect(leg.add(tick(3, 110.5, 26.0, 'succeeded'))).toBe(true);
    const s = leg.side();
    expect(s.status).toBe('succeeded');
    expect(s.time_s).toBe(10.5);
    expect(s.length_m).toBeCloseTo(3.0, 3);                          // on truth: 0.3 + 0.01 + 2.69
    expect(s.path).toEqual([[23, 6], [23.3, 6], [26, 6]]);
  });

  it('ignores the previous goal\'s verdict', () => {
    const leg = new LiveLeg([26, 6], [23, 6, 0], 10);
    const stale = tick(0, 10, 23, 'succeeded');
    stale.plans[0].goal = [24, 9];                                   // the last goal's status, not this one's
    expect(leg.add(stale)).toBe(false);
    expect(leg.add(tick(1, 11, 23.4, 'executing'))).toBe(false);
    expect(leg.add(tick(2, 19, 26, 'succeeded'))).toBe(true);
    expect(leg.side().time_s).toBe(9);
  });

  it('ends a LIVE leg on STOP, and says so', () => {
    const leg = new LiveLeg([26, 6], [23, 6, 0], 50);
    leg.add(tick(0, 50, 23, 'executing'));
    expect(leg.add(tick(1, 52, 23.5, 'executing', { source: 'stop' }))).toBe(true);
    expect(leg.side().status).toBe('stopped');
    expect(leg.side().time_s).toBe(2);
  });

  it('takes the MODEL side from an experiment record and its frames', () => {
    const m = modelSide({ status: 'succeeded', metrics: { time_s: 10.6, path_length_m: 2.888 } },
      [{ truth: [23, 6, 0] }, { truth: [23.01, 6, 0] }, { truth: [24, 6.2, 0] }]);
    expect(m).toEqual({ label: 'MODEL · RPP, kinematic', length_m: 2.888, time_s: 10.6, status: 'succeeded', path: [[23, 6], [24, 6.2]] });
    expect(sideWords(m, '…')).toBe('MODEL · RPP, kinematic: 2.89 m driven, 10.6 s (sim), succeeded');
    expect(sideWords(null, 'MODEL: running…')).toBe('MODEL: running…');
  });
});
