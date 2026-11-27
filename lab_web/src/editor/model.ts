// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.5: the world editor's level -- a grid-snapped list of COCO Lab's kit pieces (World Spec v3,
 * docs/v2/m6/WORLD_SPEC_V3.md) plus the start and the goals, with undo and redo. Pure (tested);
 * `toSpec` writes the World Spec the Python reader validates (the editor never decides validity itself:
 * coco_lab.level_check does, in the worker). The robot and the arena block are the Depot's, so an
 * edited level is driven by the same COCO as every other level.
 */

export const SNAP = 0.5;
export const WALL = { thickness: 0.15, height: 2.0 };
export type PieceKind = 'wall' | 'door' | 'rack' | 'bench' | 'pallet' | 'box';
export const PIECES: PieceKind[] = ['wall', 'door', 'rack', 'bench', 'pallet', 'box'];
export type Side = '+x' | '-x' | '+y' | '-y';

export interface Wall { id: string; kind: 'wall'; from: [number, number]; to: [number, number] }
export interface Door { id: string; kind: 'door'; wall: string; at: number; width: number }
export interface Solid { id: string; kind: 'rack' | 'bench' | 'pallet' | 'box'; center: [number, number]; size: [number, number]; height: number; aisles?: Side[] }
export type Piece = Wall | Door | Solid;

export interface Level { title: string; w: number; h: number; start: { x: number; y: number; theta: number }; pieces: Piece[]; goals: [number, number][]; seq: number }

/** Default sizes (metres): a rack as the Depot's are deep, a bench, a loaded pallet, a box. */
export const DEFAULTS: Record<Solid['kind'], { size: [number, number]; height: number }> = {
  rack: { size: [3.0, 1.1], height: 2.2 }, bench: { size: [1.6, 0.8], height: 0.9 },
  pallet: { size: [1.2, 1.0], height: 1.4 }, box: { size: [1.0, 1.0], height: 1.0 },
};

export const snap = (v: number) => Math.round(v / SNAP) * SNAP;
const r3 = (v: number) => Math.round(v * 1000) / 1000;

export function newLevel(): Level {
  return { title: 'My level', w: 12, h: 9, start: { x: 1.5, y: 1.5, theta: 0 }, pieces: [], goals: [], seq: 1 };
}

const nextId = (l: Level, kind: string) => `${kind}_${l.seq}`;

/** A wall from a to b, snapped and made axis-aligned (the longer axis wins). Null if it has no length. */
export function addWall(l: Level, a: [number, number], b: [number, number]): Level | null {
  const p: [number, number] = [snap(a[0]), snap(a[1])];
  let q: [number, number] = [snap(b[0]), snap(b[1])];
  q = Math.abs(q[0] - p[0]) >= Math.abs(q[1] - p[1]) ? [q[0], p[1]] : [p[0], q[1]];
  if (p[0] === q[0] && p[1] === q[1]) return null;
  const from: [number, number] = p[0] < q[0] || p[1] < q[1] ? p : q, to = from === p ? q : p;
  return { ...l, seq: l.seq + 1, pieces: [...l.pieces, { id: nextId(l, 'wall'), kind: 'wall', from, to }] };
}

/** A solid piece centred at `at` (snapped), with its default size and height. */
export function addSolid(l: Level, kind: Solid['kind'], at: [number, number]): Level {
  const d = DEFAULTS[kind];
  const piece: Solid = { id: nextId(l, kind), kind, center: [snap(at[0]), snap(at[1])], size: [...d.size], height: d.height,
    ...(kind === 'rack' ? { aisles: ['+y' as Side] } : {}) };
  return { ...l, seq: l.seq + 1, pieces: [...l.pieces, piece] };
}

/** A door on the wall nearest `at` (within 0.5 m), centred where clicked; null if no wall is near. */
export function addDoor(l: Level, at: [number, number], width = 1.2): Level | null {
  let best: { w: Wall; d: number; along: number } | null = null;
  for (const p of l.pieces) {
    if (p.kind !== 'wall') continue;
    const horiz = p.from[1] === p.to[1];
    const along = horiz ? at[0] - p.from[0] : at[1] - p.from[1];
    const len = horiz ? p.to[0] - p.from[0] : p.to[1] - p.from[1];
    const d = horiz ? Math.abs(at[1] - p.from[1]) : Math.abs(at[0] - p.from[0]);
    if (along < width / 2 || along > len - width / 2 || d > 0.5) continue;
    if (!best || d < best.d) best = { w: p, d, along };
  }
  if (!best) return null;
  return { ...l, seq: l.seq + 1, pieces: [...l.pieces, { id: nextId(l, 'door'), kind: 'door', wall: best.w.id, at: r3(snap(best.along)), width }] };
}

const ROT: Record<Side, Side> = { '+x': '+y', '+y': '-x', '-x': '-y', '-y': '+x' };

/** Move a piece by (dx, dy), snapped. Doors move with their wall. */
export function move(l: Level, id: string, dx: number, dy: number): Level {
  const sx = snap(dx), sy = snap(dy);
  return { ...l, pieces: l.pieces.map((p) => (p.id !== id ? p
    : p.kind === 'wall' ? { ...p, from: [p.from[0] + sx, p.from[1] + sy], to: [p.to[0] + sx, p.to[1] + sy] }
    : p.kind === 'door' ? p
    : { ...p, center: [p.center[0] + sx, p.center[1] + sy] })) };
}

/** Rotate a piece 90° about its centre (a wall about its midpoint, snapped). */
export function rotate(l: Level, id: string): Level {
  return { ...l, pieces: l.pieces.map((p) => {
    if (p.id !== id || p.kind === 'door') return p;
    if (p.kind === 'wall') {
      const cx = (p.from[0] + p.to[0]) / 2, cy = (p.from[1] + p.to[1]) / 2, half = (Math.abs(p.to[0] - p.from[0]) + Math.abs(p.to[1] - p.from[1])) / 2;
      const horiz = p.from[1] === p.to[1];
      const a: [number, number] = horiz ? [snap(cx), snap(cy - half)] : [snap(cx - half), snap(cy)];
      const b: [number, number] = horiz ? [snap(cx), snap(cy + half)] : [snap(cx + half), snap(cy)];
      return { ...p, from: a, to: b };
    }
    return { ...p, size: [p.size[1], p.size[0]], ...(p.aisles ? { aisles: p.aisles.map((s) => ROT[s]) } : {}) };
  }) };
}

/** Delete a piece; deleting a wall deletes its doors. */
export function remove(l: Level, id: string): Level {
  return { ...l, pieces: l.pieces.filter((p) => p.id !== id && !(p.kind === 'door' && p.wall === id)) };
}

export const setStart = (l: Level, at: [number, number], theta = l.start.theta): Level => ({ ...l, start: { x: snap(at[0]), y: snap(at[1]), theta } });
export const turnStart = (l: Level): Level => ({ ...l, start: { ...l.start, theta: r3(((l.start.theta + Math.PI / 2 + Math.PI) % (2 * Math.PI)) - Math.PI) } });
export const addGoal = (l: Level, at: [number, number]): Level => ({ ...l, goals: [...l.goals, [snap(at[0]), snap(at[1])]] });
export const removeGoal = (l: Level, k: number): Level => ({ ...l, goals: l.goals.filter((_, i) => i !== k) });
export const resize = (l: Level, w: number, h: number): Level => ({ ...l, w: Math.max(4, Math.min(60, snap(w))), h: Math.max(4, Math.min(60, snap(h))) });

/** The level's id as World Spec and package names allow: editor_<slug>. */
export function levelId(l: Level): string {
  const slug = l.title.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 30) || 'level';
  return `editor_${slug}`;
}

/** The World Spec v3 the Python reader validates: the four outer walls on the bounds, then the pieces. */
export function toSpec(l: Level, depot: { robot: unknown; arena: unknown }): Record<string, unknown> {
  const wall = (id: string, from: [number, number], to: [number, number]) => ({ id, kind: 'wall', from, to, ...WALL });
  const kit: Record<string, unknown>[] = [
    wall('outer_s', [0, 0], [l.w, 0]), wall('outer_n', [0, l.h], [l.w, l.h]),
    wall('outer_w', [0, 0], [0, l.h]), wall('outer_e', [l.w, 0], [l.w, l.h]),
  ];
  for (const p of l.pieces) {
    if (p.kind === 'wall') kit.push(wall(p.id, p.from, p.to));
    else if (p.kind === 'door') kit.push({ id: p.id, kind: 'door', wall: p.wall, at: p.at, width: p.width });
    else if (p.kind === 'rack') kit.push({ id: p.id, kind: 'rack', center: p.center, size: p.size, height: p.height,
      shelves: [0.3, 1.0, 1.7].filter((h) => h < p.height), aisle: 1.2, aisles: p.aisles ?? ['+y'] });
    else kit.push({ id: p.id, kind: p.kind, center: p.center, size: p.size, height: p.height });
  }
  return { spec_version: 'coco.world_spec.v3', id: levelId(l), title: l.title.slice(0, 80) || 'My level', frame: 'world',
    world_to_map: [0.0, 0.0], bounds: { x_min: 0.0, x_max: l.w, y_min: 0.0, y_max: l.h }, robot: depot.robot,
    start: { ...l.start }, arena: depot.arena, kit, sources: { editor: 'COCO Lab world editor (R5.5)' } };
}

const num = (v: unknown, lo = -1e6, hi = 1e6): v is number => typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi;
const pt = (v: unknown): v is [number, number] => Array.isArray(v) && v.length === 2 && num(v[0]) && num(v[1]);
const ID = /^[a-z][a-z0-9_]{0,39}$/;
const SIDES = new Set(['+x', '-x', '+y', '-y']);

/**
 * A level from a share link (untrusted), or null: every field type- and range-checked, so a hostile link
 * cannot crash the editor. (The World Spec it makes is still validated by the Python reader.)
 */
export function asLevel(x: unknown): Level | null {
  if (!x || typeof x !== 'object') return null;
  const l = x as Record<string, unknown>;
  const s = l.start as Record<string, unknown> | undefined;
  if (typeof l.title !== 'string' || l.title.length > 80 || !num(l.w, 4, 60) || !num(l.h, 4, 60) || !Number.isInteger(l.seq) || !num(l.seq, 1, 1e6)) return null;
  if (!s || !num(s.x) || !num(s.y) || !num(s.theta, -4, 4)) return null;
  if (!Array.isArray(l.goals) || l.goals.length > 50 || !l.goals.every(pt)) return null;
  if (!Array.isArray(l.pieces) || l.pieces.length > 400) return null;
  for (const p of l.pieces as Record<string, unknown>[]) {
    if (!p || typeof p !== 'object' || typeof p.id !== 'string' || !ID.test(p.id)) return null;
    if (p.kind === 'wall') { if (!pt(p.from) || !pt(p.to)) return null; }
    else if (p.kind === 'door') { if (typeof p.wall !== 'string' || !ID.test(p.wall) || !num(p.at, 0, 60) || !num(p.width, 0.5, 5)) return null; }
    else if (p.kind === 'rack' || p.kind === 'bench' || p.kind === 'pallet' || p.kind === 'box') {
      if (!pt(p.center) || !Array.isArray(p.size) || p.size.length !== 2 || !p.size.every((v) => num(v, 0.1, 20)) || !num(p.height, 0.05, 5)) return null;
      if (p.aisles !== undefined && (!Array.isArray(p.aisles) || !p.aisles.every((a) => SIDES.has(a as string)))) return null;
    } else return null;
  }
  return x as Level;
}

/** Undo/redo over whole-level snapshots (a level is small). */
export class History {
  private past: Level[] = [];
  private future: Level[] = [];
  constructor(public now: Level) {}
  push(next: Level | null): boolean {
    if (!next || next === this.now) return false;
    this.past.push(this.now); this.now = next; this.future = [];
    if (this.past.length > 200) this.past.shift();
    return true;
  }
  undo(): boolean { const p = this.past.pop(); if (!p) return false; this.future.push(this.now); this.now = p; return true; }
  redo(): boolean { const f = this.future.pop(); if (!f) return false; this.past.push(this.now); this.now = f; return true; }
  get canUndo() { return this.past.length > 0; }
  get canRedo() { return this.future.length > 0; }
}
