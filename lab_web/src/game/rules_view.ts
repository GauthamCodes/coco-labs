// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1: what the HUD says, as pure functions of what the model reported
 * (tested in test/g1_rules_view.test.ts). Nothing here decides a grasp, a
 * delivery or a score: it only words the model's own state.
 */

import type { Candidate, GameKind, GameTick, GameZone } from './session';

/** The real load stages, in order, and the worker marks that end each (arena.worker.ts). */
/**
 * G1.12: Fetch Rush's shifts; G2.1: rules 4's (coco_lab/levels/coco_depot_v1.fetch_rush.r4.json:
 * rules 3's rounds, with every route crossing the forklift lane only at a striped crossing).
 * Every round on file was finished by the reference bot (a round it could not finish
 * was rejected when the rounds were generated), so every shift is offered, in both
 * modes: 'phone' (2 orders, the default) and 'full' (the Full shift, 3 orders).
 */
export const FETCH_RUSH_SHIFTS = [1, 2, 3, 4, 5, 6];
export type FetchRushMode = 'phone' | 'full';
export const fetchRushMode = (v: string | null): FetchRushMode => (v === 'full' ? 'full' : 'phone');

export const LOAD_STAGES = [
  { id: 'worker', label: 'WORKER', marks: ['worker_boot'] },
  { id: 'pyodide', label: 'PYODIDE', marks: ['pyodide_module', 'pyodide_ready'] },
  { id: 'coco_lab', label: 'COCO_LAB', marks: ['coco_lab_ready', 'pack_game_ready'] },
  { id: 'arena', label: 'ARENA', marks: ['arena_ready'] },
] as const;

/** One-line tips for the loading screen: each names something the game really shows. */
export const TIPS = [
  'The magenta line is the plan COCO\'s planner found.',
  'Tap SIM to see the same moment as RViz would draw it: TF frames, LaserScan, costmaps, the plan.',
  'GRAB only lights when Grasp Assist can really pick the object.',
  'STOP always wins: over you, over the planner, over Grasp Assist.',
  'Two fingers and a magnet: the magnet does the holding.',
  'Forklifts never yield. Their lanes are painted yellow.',
  'The planner\'s routes cross the forklift lane only at the striped crossings.',
  'AUTO hands the wheels to the planner. Touch the stick to take them back.',
  'Everything here runs in your browser: Python, in a Web Worker.',
];

/** Grasp Assist's refusal codes, in a few words for a button. */
export const REASON_SHORT: Record<string, string> = {
  too_wide: 'Too wide', out_of_reach: 'Out of reach', not_magnetic: 'Not magnetic', blocked: 'Blocked',
};

export interface Primary {
  kind: 'grab' | 'drop' | 'go' | 'none' | 'busy';
  label: string;
  enabled: boolean;
  why?: string;
  target?: string;
  /** 0..1 while Grasp Assist approaches (the ring fills) */
  progress?: number;
}

const inside = (z: GameZone, x: number, y: number) =>
  Math.abs(x - z.center[0]) <= z.size[0] / 2 && Math.abs(y - z.center[1]) <= z.size[1] / 2;

const STAGES = ['approach', 'align', 'reach', 'release'];

/**
 * The primary button for this moment (G1 §1.2): GRAB when Grasp Assist has a
 * valid target, DROP when holding at a drop zone, GO when a goal is set and
 * autonomy is off; otherwise greyed with the reason, from Grasp Assist's own
 * refusal codes.
 */
export function primaryAction(o: { game: GameKind; tick: GameTick | null; cands: Candidate[]; zones: GameZone[]; goal: [number, number] | null; auto: boolean; latched: boolean }): Primary {
  const a = o.tick?.game?.assist;
  if (o.latched) return { kind: 'none', label: 'GRAB', enabled: false, why: 'STOPPED' };
  if (a && STAGES.includes(a.phase)) {
    return { kind: 'busy', label: a.phase === 'release' ? 'DROPPING' : 'GRABBING', enabled: false, why: a.phase, progress: (STAGES.indexOf(a.phase) + 1) / (STAGES.length + 1) };
  }
  const order = o.tick?.game?.fetch?.order ?? null;
  if (a?.carried) {
    const pose = o.tick!.pose;
    const drops = o.zones.filter((z) => z.role === 'drop' && (o.game !== 'fetch_rush' || z.id === order?.[1]));
    const at = drops.find((z) => inside(z, pose[0], pose[1]));
    if (at) return { kind: 'drop', label: 'DROP', enabled: true, target: at.id };
    const want = drops[0];
    return { kind: 'drop', label: 'DROP', enabled: false, why: want ? `Go to ${(want.label ?? want.id).toUpperCase()}` : 'Not at a drop zone' };
  }
  if (o.cands.length) {
    const mine = o.game === 'fetch_rush' ? o.cands.find((c) => c.object_id === order?.[0]) : o.cands.find((c) => c.rank === 0);
    if (mine && !mine.reason) return { kind: 'grab', label: 'GRAB', enabled: true, target: mine.object_id };
    if (mine) return { kind: 'grab', label: 'GRAB', enabled: false, why: REASON_SHORT[mine.reason] ?? mine.reason, target: mine.object_id };
    if (o.game === 'fetch_rush') return { kind: 'grab', label: 'GRAB', enabled: false, why: 'Not the order' };
  }
  if (o.goal && !o.auto) return { kind: 'go', label: 'GO', enabled: true };
  return { kind: 'none', label: 'GRAB', enabled: false, why: 'Nothing in range' };
}
