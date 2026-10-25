// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1: what the HUD says, as pure functions of what the model reported
 * (tested in test/g1_rules_view.test.ts). Nothing here decides a grasp, a
 * delivery or a score: it only words the model's own state.
 */

import type { Candidate, FetchColourId, GameKind, GameTick, GameZone } from './session';

/** The real load stages, in order, and the worker marks that end each (arena.worker.ts). */
/**
 * G1.12: Fetch Rush's shifts; G2.1: rules 4's (coco_lab/levels/coco_depot_v1.fetch_rush.r4.json:
 * rules 3's rounds, with every route crossing the forklift lane only at a striped crossing);
 * G2 rules 5 (…fetch_rush.r5.json): rules 4's rounds, with the actors stopping for COCO and AUTO
 * waiting for them or re-planning around them.
 * Every round on file was finished by the reference bot (a round it could not finish
 * was rejected when the rounds were generated), so every shift is offered, in both
 * modes: 'phone' (2 orders, the default) and 'full' (the Full shift, 3 orders).
 */
export const FETCH_RUSH_SHIFTS = [1, 2, 3, 4, 5, 6];
/** the rules the worker plays (coco_lab.games.FETCH_RUSH_RULES; a test keeps them equal) */
export const FETCH_RUSH_RULES = 5;
export type FetchRushMode = 'phone' | 'full';
export const fetchRushMode = (v: string | null): FetchRushMode => (v === 'full' ? 'full' : 'phone');

/** Fetch Rush or Fetch by colour: the games with orders (one object to one drop zone at a time) */
export const isFetch = (g: GameKind) => g === 'fetch_rush' || g === 'fetch_colour';

/**
 * Owner request 2026-10-24, Fetch by colour: COCO's original Gazebo fetch had four rods, one per
 * colour (coco_config/coco_config/robot.py TARGETS: 20/24/28/32 mm, 0.158 m tall); the
 * player picks one. The chips carry the colour's NAME and diameter, so colour is never the only cue.
 */
export const FETCH_COLOURS: { id: FetchColourId; label: string; mm: number }[] = [
  { id: 'red', label: 'RED', mm: 20 }, { id: 'green', label: 'GREEN', mm: 24 },
  { id: 'blue', label: 'BLUE', mm: 28 }, { id: 'yellow', label: 'YELLOW', mm: 32 },
];
/** `&colour=` parsed: one of the four, or null (the page then shows the choice) */
export const fetchColour = (v: string | null): FetchColourId | null => (FETCH_COLOURS.find((c) => c.id === v)?.id ?? null);
export const colourChip = (c: FetchColourId) => { const k = FETCH_COLOURS.find((x) => x.id === c)!; return `${k.label} · ${k.mm} mm`; };
/** the HUD objective while the order is open: "FETCH THE RED ROD → DISPATCH" */
export const colourObjective = (c: FetchColourId, carried: boolean, drop = 'DISPATCH') =>
  carried ? `CARRY THE ${c.toUpperCase()} ROD → ${drop.toUpperCase()}` : `FETCH THE ${c.toUpperCase()} ROD → ${drop.toUpperCase()}`;

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
  'Forklifts and walkers stop for COCO (a safety stop). Their lanes are painted yellow.',
  'AUTO waits for a forklift in its path, or plans a new route around one.',
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
    const drops = o.zones.filter((z) => z.role === 'drop' && (!isFetch(o.game) || z.id === order?.[1]));
    const at = drops.find((z) => inside(z, pose[0], pose[1]));
    if (at) return { kind: 'drop', label: 'DROP', enabled: true, target: at.id };
    const want = drops[0];
    return { kind: 'drop', label: 'DROP', enabled: false, why: want ? `Go to ${(want.label ?? want.id).toUpperCase()}` : 'Not at a drop zone' };
  }
  if (o.cands.length) {
    const mine = isFetch(o.game) ? o.cands.find((c) => c.object_id === order?.[0]) : o.cands.find((c) => c.rank === 0);
    if (mine && !mine.reason) return { kind: 'grab', label: 'GRAB', enabled: true, target: mine.object_id };
    if (mine) return { kind: 'grab', label: 'GRAB', enabled: false, why: REASON_SHORT[mine.reason] ?? mine.reason, target: mine.object_id };
    if (isFetch(o.game)) return { kind: 'grab', label: 'GRAB', enabled: false, why: o.game === 'fetch_colour' ? 'Not that colour' : 'Not the order' };
  }
  if (o.goal && !o.auto) return { kind: 'go', label: 'GO', enabled: true };
  return { kind: 'none', label: 'GRAB', enabled: false, why: 'Nothing in range' };
}
