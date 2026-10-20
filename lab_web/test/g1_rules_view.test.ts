// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// G1.3: the primary action only WORDS what the model reported (Grasp Assist's
// phase, its candidates and refusal codes, Fetch Rush's order, the drop zones).

import { describe, expect, it } from 'vitest';
import { LOAD_STAGES, REASON_SHORT, primaryAction } from '../src/game/rules_view';
import type { Candidate, GameTick, GameZone } from '../src/game/session';

const zones: GameZone[] = [{ id: 'dock_2', role: 'drop', label: 'Dock 2', center: [42, 1.3], size: [2.6, 2] }, { id: 'dispatch_drop', role: 'drop', label: 'Dispatch', center: [23, 1.4], size: [3, 2] }];
const tick = (o: { phase?: string; carried?: string | null; pose?: [number, number, number]; order?: [string, string] | null }) => ({
  tick: 1, t_world: 0.1, pose: o.pose ?? [23, 6, 0], v: 0, w: 0, mode: 'idle', blocked: false, arrived: false, hash: '', chain: '', plans: [],
  game: { assist: { phase: o.phase ?? 'idle', target: null, carried: o.carried ?? null, want: 'any', reason: '', attempt: 0 },
    fetch: o.order === undefined ? undefined : { t: 0, seconds: 180, over: false, order: o.order, k: 0, orders: 10, deliveries: 0, contacts: 0, ghost: null } },
}) as unknown as GameTick;
const cand = (id: string, reason = '', rank = 0) => ({ object_id: id, item: 'can_small', reason, rank, seen_by: 'camera', dist: 0.5, approach_x: 1, approach_y: 1 }) as Candidate;
const base = { game: 'fetch_rush' as const, zones, goal: null, auto: false, latched: false };

describe('G1 primary action', () => {
  it('GRAB lights only for a candidate Grasp Assist accepts, and for the order in Fetch Rush', () => {
    expect(primaryAction({ ...base, tick: tick({ order: ['obj_dock', 'dock_2'] }), cands: [cand('obj_dock')] })).toMatchObject({ kind: 'grab', enabled: true, target: 'obj_dock' });
    expect(primaryAction({ ...base, tick: tick({ order: ['obj_dock', 'dock_2'] }), cands: [cand('obj_other')] })).toMatchObject({ enabled: false, why: 'Not the order' });
    expect(primaryAction({ ...base, game: 'free', tick: tick({}), cands: [cand('a'), cand('b', '', 1)] })).toMatchObject({ enabled: true, target: 'a' });
  });
  it('a refusal greys GRAB with Grasp Assist\'s own reason', () => {
    for (const [code, words] of Object.entries(REASON_SHORT)) {
      expect(primaryAction({ ...base, game: 'free', tick: tick({}), cands: [cand('x', code)] })).toMatchObject({ enabled: false, why: words });
    }
  });
  it('DROP lights only while carrying inside the right drop zone', () => {
    const order: [string, string] = ['obj_dock', 'dock_2'];
    expect(primaryAction({ ...base, tick: tick({ carried: 'obj_dock', order, pose: [42, 1.3, 0] }), cands: [] })).toMatchObject({ kind: 'drop', enabled: true });
    expect(primaryAction({ ...base, tick: tick({ carried: 'obj_dock', order, pose: [23, 1.4, 0] }), cands: [] })).toMatchObject({ kind: 'drop', enabled: false, why: 'Go to DOCK 2' });
    expect(primaryAction({ ...base, game: 'free', tick: tick({ carried: 'x', pose: [23, 1.4, 0] }), cands: [] })).toMatchObject({ kind: 'drop', enabled: true });
  });
  it('GO when a goal is set and autonomy is off; busy while Grasp Assist works; nothing while STOP is latched', () => {
    expect(primaryAction({ ...base, game: 'free', tick: tick({}), cands: [], goal: [1, 2] })).toMatchObject({ kind: 'go', enabled: true });
    expect(primaryAction({ ...base, game: 'free', tick: tick({}), cands: [], goal: [1, 2], auto: true })).toMatchObject({ enabled: false });
    expect(primaryAction({ ...base, tick: tick({ phase: 'approach', order: ['a', 'dock_2'] }), cands: [] })).toMatchObject({ kind: 'busy', enabled: false });
    expect(primaryAction({ ...base, tick: tick({ order: ['a', 'dock_2'] }), cands: [cand('a')], latched: true })).toMatchObject({ enabled: false, why: 'STOPPED' });
  });
  it('the loading stages are the worker\'s real marks, in order', () => {
    expect(LOAD_STAGES.map((s) => s.id)).toEqual(['worker', 'pyodide', 'coco_lab', 'arena']);
    expect(LOAD_STAGES.flatMap((s) => s.marks)).toContain('arena_ready');
  });
});
