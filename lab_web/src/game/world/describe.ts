// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.5: what a level LOOKS like, described from its World Spec alone.
 *
 * Pure data, no three.js: the same description is drawn by the browser
 * (build3d.ts), baked into a floor light map at build time
 * (tools/g1/bake_worlds.mjs, run by Node directly) and checked for
 * decorative honesty (test/g1_honesty.test.ts). Presentation only (README §3
 * invariant 11): nothing here reaches the model or a state hash.
 *
 * Decorative honesty (G1 §0): every part is in one class, and the class says
 * why it may look solid:
 *
 * - `solid`     inside a collision footprint (a spec box, an elevation solid or an actor box)
 * - `wall`      on a wall's face: inside that wall's footprint grown by WALL_SKIN
 * - `overhead`  its lowest point at or above OVERHEAD_Z (ceiling, fixtures)
 * - `decal`     at most DECAL_Z tall, flat on the floor or on a solid's top
 * - `outside`   outside the level's drivable bounds
 * - `light`     a translucent light volume (never drawn opaque)
 *
 * Only erasable TypeScript here, so Node runs this file as is.
 */

export type V3 = [number, number, number];
export type PartClass = 'solid' | 'wall' | 'overhead' | 'decal' | 'outside' | 'light';
export type Shape = 'box' | 'cyl' | 'wedge';
/** Materials, drawn by build3d.ts; each (shape, material) pair is one instanced draw. */
export type Mat =
  | 'panel' | 'office' | 'fence' | 'trim' | 'column' | 'rollup' | 'exit' | 'fixture' | 'ceiling'
  | 'upright' | 'beam' | 'deck' | 'carton' | 'crate' | 'wrap' | 'wood' | 'cabinet' | 'benchtop'
  | 'railing' | 'mesh' | 'ramp' | 'mezz' | 'hazard'
  | 'labpanel' | 'labblock' | 'landmark' | 'labtrim'
  | 'body' | 'counter' | 'mast' | 'fork' | 'beacon' | 'glass' | 'vest' | 'skin' | 'dark';

export interface Part {
  id: string;
  shape: Shape;
  mat: Mat;
  cls: PartClass;
  /** the collision footprint a `solid` or `wall` part lies within */
  footprint?: string;
  /** axis-aligned bounds, map frame (an actor's parts: the actor's own frame) */
  min: V3;
  max: V3;
  /** a wedge's rise direction: +x (0) or -x (Math.PI) */
  yaw?: number;
  /** per-instance colour (0xRRGGBB), when the material allows it */
  tint?: number;
}

/** A collision footprint the model and Gazebo both hold (map frame). */
export interface Footprint {
  id: string;
  kind: 'box' | 'wedge' | 'platform';
  min: [number, number];
  max: [number, number];
  /** its height (a wedge: its rise) */
  top: number;
}

export interface Fixture { x: number; y: number; z: number; kind: 'strip' | 'dock' | 'lamp'; len: number; along: 'x' | 'y' }
export type Paint =
  | { kind: 'line'; from: [number, number]; to: [number, number]; width: number; color: string; dash?: number }
  | { kind: 'hazard'; min: [number, number]; max: [number, number] }
  | { kind: 'label'; at: [number, number]; text: string; size: number; color: string; rot?: number; align?: 'left' | 'center' }
  | { kind: 'rect'; min: [number, number]; max: [number, number]; color: string; width: number; dash?: number }
  | { kind: 'grid'; step: number; color: string; width: number }
  | { kind: 'cal'; at: [number, number]; size: number; color: string };

export interface Zone { id: string; role: string; label: string; min: [number, number]; max: [number, number] }
export interface ActorLook { id: string; actor: 'forklift' | 'walker'; length: number; width: number; height: number; parts: Part[] }

export interface WorldLook {
  id: string;
  theme: 'depot' | 'lab';
  /** drivable bounds, map frame */
  bounds: { minX: number; maxX: number; minY: number; maxY: number };
  /** the floor drawn (it may extend past the bounds: that rim is `outside`) */
  floor: { minX: number; maxX: number; minY: number; maxY: number };
  ceiling: number;
  parts: Part[];
  footprints: Footprint[];
  fixtures: Fixture[];
  paint: Paint[];
  zones: Zone[];
  actors: ActorLook[];
}

/** G2.1: the lane zones Fetch Rush's routes cross only at marked crossings (coco_lab.games.ROUND_LANES) */
export const CROSSING_ZONES = ['zone_forklift_lanes'];
export const WALL_SKIN = 0.05;
export const OVERHEAD_Z = 3.5;
export const DECAL_Z = 0.02;

/** A small seeded generator for VARIETY only (which carton goes where); never the model's RNG. */
export function variety(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface SpecBox { id: string; kind: string; center: [number, number]; size: [number, number]; height: number; z?: number }
interface SpecElev { id: string; kind: string; foot?: [number, number]; yaw?: number; run?: number; rise?: number; width?: number; center?: [number, number]; size?: number[] }
interface KitItem { id: string; kind: string; [k: string]: unknown }
export interface Spec {
  id: string;
  spec_version: string;
  world_to_map: [number, number];
  bounds: { x_min: number; x_max: number; y_min: number; y_max: number };
  boxes: SpecBox[];
  elevation?: SpecElev[];
  kit?: KitItem[];
}

const box = (id: string, mat: Mat, cls: PartClass, min: V3, max: V3, footprint?: string, tint?: number): Part =>
  ({ id, shape: 'box', mat, cls, min, max, ...(footprint ? { footprint } : {}), ...(tint !== undefined ? { tint } : {}) });

/** The spec's solids as footprints, map frame. */
export function footprints(spec: Spec): Footprint[] {
  const [dx, dy] = spec.world_to_map;
  const out: Footprint[] = spec.boxes.map((b) => ({
    id: b.id, kind: 'box' as const,
    min: [b.center[0] - b.size[0] / 2 + dx, b.center[1] - b.size[1] / 2 + dy] as [number, number],
    max: [b.center[0] + b.size[0] / 2 + dx, b.center[1] + b.size[1] / 2 + dy] as [number, number],
    top: b.height,
  }));
  for (const e of spec.elevation ?? []) {
    if (e.kind === 'wedge') {
      const fx = e.foot![0] + dx, fy = e.foot![1] + dy, run = e.run!, w = e.width!;
      const x0 = e.yaw && Math.abs(e.yaw) > 1 ? fx - run : fx;
      out.push({ id: e.id, kind: 'wedge', min: [x0, fy - w / 2], max: [x0 + run, fy + w / 2], top: e.rise! });
    } else if (e.kind === 'platform') {
      const [sx, sy, top] = e.size as number[];
      out.push({ id: e.id, kind: 'platform', min: [e.center![0] - sx / 2 + dx, e.center![1] - sy / 2 + dy],
        max: [e.center![0] + sx / 2 + dx, e.center![1] + sy / 2 + dy], top });
    }
  }
  return out;
}

const kit = (spec: Spec, kind: string) => (spec.kit ?? []).filter((k) => k.kind === kind);

/** Uprights, beams, decks and loads of one rack, all inside its box. */
function rackParts(r: KitItem, fp: Footprint, rnd: () => number): Part[] {
  const parts: Part[] = [];
  const [x0, y0] = fp.min, [x1, y1] = fp.max, h = r.height as number;
  const shelves = (r.shelves as number[]) ?? [];
  const along = x1 - x0 >= y1 - y0 ? 'x' : 'y';
  const len = along === 'x' ? x1 - x0 : y1 - y0;
  const bays = Math.max(1, Math.round(len / 2.7));
  const bay = len / bays, u = 0.09;
  const at = (a: number, b: number, z0: number, z1: number, a2: number, b2: number): [V3, V3] =>
    along === 'x' ? [[a, b, z0], [a2, b2, z1]] : [[b, a, z0], [b2, a2, z1]];
  const lo = along === 'x' ? y0 : x0, hi = along === 'x' ? y1 : x1, s0 = along === 'x' ? x0 : y0;
  for (let k = 0; k <= bays; k++) {
    const a = Math.min(Math.max(s0 + k * bay - u / 2, s0), s0 + len - u);
    for (const [b, b2] of [[lo, lo + u], [hi - u, hi]]) {
      const [mn, mx] = at(a, b, 0, h, a + u, b2);
      parts.push(box(`${r.id}/up${k}${b === lo ? 'f' : 'b'}`, 'upright', 'solid', mn, mx, r.id));
    }
  }
  const levels = [...shelves];
  levels.forEach((z, i) => {
    for (const [b, b2, side] of [[lo, lo + 0.06, 'f'], [hi - 0.06, hi, 'b']] as [number, number, string][]) {
      const [mn, mx] = at(s0, b, z - 0.12, z, s0 + len, b2);
      parts.push(box(`${r.id}/beam${i}${side}`, 'beam', 'solid', mn, mx, r.id));
    }
    const [dmn, dmx] = at(s0, lo + 0.06, z - 0.03, z, s0 + len, hi - 0.06);
    parts.push(box(`${r.id}/deck${i}`, 'deck', 'solid', dmn, dmx, r.id));
    const clear = (levels[i + 1] ?? h) - 0.18 - z;
    for (let k = 0; k < bays; k++) {
      const pick = rnd();
      const a0 = s0 + k * bay + u + 0.08, a1 = s0 + (k + 1) * bay - u - 0.08;
      if (pick < 0.12 || clear < 0.3) continue;
      const depth0 = lo + 0.1, depth1 = hi - 0.1;
      if (pick < 0.45) {
        // shrink-wrapped pallet: a wooden base and a wrapped load
        const [pmn, pmx] = at(a0, depth0, z, z + 0.14, a1, depth1);
        parts.push(box(`${r.id}/pal${i}_${k}`, 'wood', 'solid', pmn, pmx, r.id));
        const top = z + 0.14 + Math.min(clear - 0.14, 0.6 + rnd() * 0.6);
        const [wmn, wmx] = at(a0 + 0.04, depth0 + 0.04, z + 0.14, top, a1 - 0.04, depth1 - 0.04);
        parts.push(box(`${r.id}/wrap${i}_${k}`, 'wrap', 'solid', wmn, wmx, r.id));
      } else {
        // cartons and crates, a few per bay
        let a = a0;
        let n = 0;
        while (a < a1 - 0.3) {
          const w = Math.min(a1 - a, 0.4 + rnd() * 0.5);
          const tall = Math.min(clear, 0.3 + rnd() * 0.7);
          const crate = rnd() < 0.3;
          const tint = crate ? undefined : [0xa77c4f, 0x9a6f43, 0xb88a58, 0x8e6a45][Math.floor(rnd() * 4)];
          const [cmn, cmx] = at(a, depth0 + rnd() * 0.08, z, z + tall, a + w - 0.04, depth1 - rnd() * 0.08);
          parts.push(box(`${r.id}/c${i}_${k}_${n++}`, crate ? 'crate' : 'carton', 'solid', cmn, cmx, r.id, tint));
          a += w + 0.02;
        }
      }
    }
  });
  return parts;
}

/** A forklift or a walker in its own frame (x forward, centred), every part inside its box. */
export function actorLook(id: string, actor: 'forklift' | 'walker', length: number, width: number, height: number): ActorLook {
  const L = length / 2, W = width / 2, p: Part[] = [];
  const b = (n: string, mat: Mat, min: V3, max: V3) => p.push(box(`${id}/${n}`, mat, 'solid', min, max, id));
  if (actor === 'forklift') {
    b('chassis', 'body', [-L, -W, 0.08], [L * 0.45, W, 0.75]);
    b('counter', 'counter', [-L, -W * 0.95, 0.08], [-L * 0.55, W * 0.95, 1.05]);
    b('wheels', 'dark', [-L * 0.85, -W, 0], [L * 0.35, W, 0.3]);
    b('seat', 'dark', [-L * 0.45, -W * 0.45, 0.75], [-L * 0.1, W * 0.45, 1.15]);
    b('mast', 'mast', [L * 0.45, -W * 0.8, 0.05], [L * 0.6, W * 0.8, height * 0.95]);
    b('forkL', 'fork', [L * 0.6, -W * 0.65, 0.05], [L, -W * 0.4, 0.12]);
    b('forkR', 'fork', [L * 0.6, W * 0.4, 0.05], [L, W * 0.65, 0.12]);
    for (const [n, x, y] of [['pFL', 0.3, -1], ['pFR', 0.3, 1], ['pBL', -0.6, -1], ['pBR', -0.6, 1]] as [string, number, number][]) {
      const px = L * x, py = W * 0.88 * y;
      b(n, 'dark', [px - 0.03, py - 0.03, 0.75], [px + 0.03, py + 0.03, height * 0.9]);
    }
    b('roof', 'dark', [-L * 0.65, -W * 0.92, height * 0.9], [L * 0.35, W * 0.92, height * 0.94]);
    b('beacon', 'beacon', [-L * 0.2 - 0.06, -0.06, height * 0.94], [-L * 0.2 + 0.06, 0.06, height]);
  } else {
    const s = Math.min(L, W);
    b('legL', 'dark', [-s * 0.3, -s * 0.5, 0], [s * 0.3, -s * 0.1, height * 0.48]);
    b('legR', 'dark', [-s * 0.3, s * 0.1, 0], [s * 0.3, s * 0.5, height * 0.48]);
    b('torso', 'vest', [-s * 0.4, -s * 0.75, height * 0.48], [s * 0.4, s * 0.75, height * 0.82]);
    b('armL', 'vest', [-s * 0.25, -s * 0.98, height * 0.5], [s * 0.25, -s * 0.76, height * 0.8]);
    b('armR', 'vest', [-s * 0.25, s * 0.76, height * 0.5], [s * 0.25, s * 0.98, height * 0.8]);
    b('head', 'skin', [-s * 0.3, -s * 0.3, height * 0.84], [s * 0.3, s * 0.3, height * 0.97]);
    b('hat', 'beacon', [-s * 0.34, -s * 0.34, height * 0.95], [s * 0.34, s * 0.34, height]);
  }
  return { id, actor, length, width, height, parts: p };
}

/** The Depot's look (theme 'depot'): any World Spec v3 level. */
export function describeDepot(spec: Spec): WorldLook {
  const fps = footprints(spec);
  const fp = new Map(fps.map((f) => [f.id, f]));
  const [dx, dy] = spec.world_to_map;
  const b = spec.bounds;
  const bounds = { minX: b.x_min + dx, maxX: b.x_max + dx, minY: b.y_min + dy, maxY: b.y_max + dy };
  const parts: Part[] = [];
  const rnd = variety(20261020);
  const ceiling = Math.max(...spec.boxes.map((x) => x.height));
  // walls: exactly their boxes; the hall gets panels, a trim line and columns; the office plaster; the maze fence
  for (const w of spec.boxes.filter((x) => x.kind === 'wall')) {
    const f = fp.get(w.id)!;
    const mat: Mat = w.height >= 5 ? 'panel' : w.height <= 2.1 ? 'fence' : 'office';
    parts.push(box(w.id, mat, 'solid', [f.min[0], f.min[1], 0], [f.max[0], f.max[1], w.height], w.id));
    const lenX = f.max[0] - f.min[0], lenY = f.max[1] - f.min[1];
    const s = WALL_SKIN * 0.6;
    if (mat === 'panel' || mat === 'office') {
      const tz = mat === 'panel' ? 1.1 : 0.9;
      parts.push(box(`${w.id}/trim`, 'trim', 'wall', [f.min[0] - (lenX < lenY ? s : 0), f.min[1] - (lenX >= lenY ? s : 0), tz],
        [f.max[0] + (lenX < lenY ? s : 0), f.max[1] + (lenX >= lenY ? s : 0), tz + 0.08], w.id));
      parts.push(box(`${w.id}/kick`, 'trim', 'wall', [f.min[0] - (lenX < lenY ? s : 0), f.min[1] - (lenX >= lenY ? s : 0), 0],
        [f.max[0] + (lenX < lenY ? s : 0), f.max[1] + (lenX >= lenY ? s : 0), 0.12], w.id));
    }
    if (mat === 'panel') {
      const n = Math.floor(Math.max(lenX, lenY) / 6);
      for (let k = 1; k < n; k++) {
        if (lenX >= lenY) {
          const x = f.min[0] + (k * lenX) / n;
          parts.push(box(`${w.id}/col${k}`, 'column', 'wall', [x - 0.15, f.min[1] - s, 0], [x + 0.15, f.max[1] + s, w.height], w.id));
        } else {
          const y = f.min[1] + (k * lenY) / n;
          parts.push(box(`${w.id}/col${k}`, 'column', 'wall', [f.min[0] - s, y - 0.15, 0], [f.max[0] + s, y + 0.15, w.height], w.id));
        }
      }
    }
  }
  // racks: frames and loads inside each box
  for (const r of kit(spec, 'rack')) parts.push(...rackParts(r, fp.get(r.id)!, rnd));
  // pallets: a wooden base and a wrapped or stacked load, inside the box
  for (const p of kit(spec, 'pallet')) {
    const f = fp.get(p.id)!, h = p.height as number;
    parts.push(box(`${p.id}/base`, 'wood', 'solid', [f.min[0], f.min[1], 0], [f.max[0], f.max[1], 0.14], p.id));
    if (rnd() < 0.5) parts.push(box(`${p.id}/load`, 'wrap', 'solid', [f.min[0] + 0.04, f.min[1] + 0.04, 0.14], [f.max[0] - 0.04, f.max[1] - 0.04, h], p.id));
    else {
      const mx = (f.min[0] + f.max[0]) / 2, my = (f.min[1] + f.max[1]) / 2;
      for (const [i, [x0, x1, y0, y1]] of [[f.min[0], mx, f.min[1], my], [mx, f.max[0], f.min[1], my], [f.min[0], mx, my, f.max[1]], [mx, f.max[0], my, f.max[1]]].entries())
        parts.push(box(`${p.id}/c${i}`, 'carton', 'solid', [x0 + 0.02, y0 + 0.02, 0.14], [x1 - 0.02, y1 - 0.02, h - rnd() * 0.25], p.id, [0xa77c4f, 0x9a6f43, 0xb88a58][i % 3]));
    }
  }
  // benches and desks: a closed cabinet (so it looks as solid as the model holds it) and a top
  for (const d of kit(spec, 'bench')) {
    const f = fp.get(d.id)!, h = d.height as number;
    parts.push(box(`${d.id}/body`, 'cabinet', 'solid', [f.min[0] + 0.03, f.min[1] + 0.03, 0], [f.max[0] - 0.03, f.max[1] - 0.03, h - 0.05], d.id));
    parts.push(box(`${d.id}/top`, 'benchtop', 'solid', [f.min[0], f.min[1], h - 0.05], [f.max[0], f.max[1], h], d.id));
  }
  // other boxes (guards: railings with a kick panel; anything else: a crate stack)
  for (const g of kit(spec, 'box')) {
    const f = fp.get(g.id)!, h = g.height as number;
    if (g.role === 'guard') {
      parts.push(box(`${g.id}/rail`, 'railing', 'solid', [f.min[0], f.min[1], h - 0.06], [f.max[0], f.max[1], h], g.id));
      parts.push(box(`${g.id}/mid`, 'railing', 'solid', [f.min[0], f.min[1], h * 0.55], [f.max[0], f.max[1], h * 0.55 + 0.05], g.id));
      parts.push(box(`${g.id}/panel`, 'mesh', 'solid', [f.min[0], f.min[1], 0], [f.max[0], f.max[1], h * 0.55], g.id));
      const lx = f.max[0] - f.min[0], ly = f.max[1] - f.min[1], n = Math.max(1, Math.round(Math.max(lx, ly) / 1.5));
      for (let k = 0; k <= n; k++) {
        const t = k / n;
        const x = lx >= ly ? f.min[0] + Math.min(t * lx, lx - 0.06) : f.min[0];
        const y = lx >= ly ? f.min[1] : f.min[1] + Math.min(t * ly, ly - 0.06);
        parts.push(box(`${g.id}/post${k}`, 'railing', 'solid', [x, y, 0], [lx >= ly ? x + 0.06 : f.max[0], lx >= ly ? f.max[1] : y + 0.06, h], g.id));
      }
    } else {
      parts.push(box(`${g.id}/stack`, 'crate', 'solid', [f.min[0], f.min[1], 0], [f.max[0], f.max[1], h], g.id));
    }
  }
  // elevation: the ramp and the deck, exactly their solids, edged in hazard paint
  for (const f of fps.filter((x) => x.kind !== 'box')) {
    if (f.kind === 'wedge') {
      const e = spec.elevation!.find((x) => x.id === f.id)!;
      parts.push({ id: f.id, shape: 'wedge', mat: 'ramp', cls: 'solid', footprint: f.id, min: [f.min[0], f.min[1], 0], max: [f.max[0], f.max[1], f.top], yaw: e.yaw ?? 0 });
    } else {
      parts.push(box(f.id, 'mezz', 'solid', [f.min[0], f.min[1], 0], [f.max[0], f.max[1], f.top], f.id));
      parts.push(box(`${f.id}/edge`, 'hazard', 'decal', [f.min[0], f.min[1], f.top], [f.max[0], f.max[1], f.top + 0.004], f.id));
    }
  }
  // the dock: roll-up doors and a lamp on the south wall's inner face, behind each dock zone
  const south = spec.boxes.find((x) => x.kind === 'wall' && x.center[1] + dy <= bounds.minY + 0.5 && x.size[0] > 20);
  const zones: Zone[] = kit(spec, 'zone').map((z) => {
    const c = z.center as [number, number], s = z.size as [number, number];
    return { id: z.id, role: z.role as string, label: (z.label as string) ?? z.id,
      min: [c[0] - s[0] / 2 + dx, c[1] - s[1] / 2 + dy], max: [c[0] + s[0] / 2 + dx, c[1] + s[1] / 2 + dy] };
  });
  const fixtures: Fixture[] = [];
  if (south) {
    const f = fp.get(south.id)!;
    for (const z of zones.filter((x) => x.role === 'drop' && x.id.startsWith('dock'))) {
      const cx = (z.min[0] + z.max[0]) / 2;
      parts.push(box(`${z.id}/rollup`, 'rollup', 'wall', [cx - 1.4, f.max[1], 0], [cx + 1.4, f.max[1] + 0.03, 3.4], south.id));
      parts.push(box(`${z.id}/lamp`, 'fixture', 'wall', [cx - 0.3, f.max[1], 3.65], [cx + 0.3, f.max[1] + 0.04, 3.75], south.id));
      fixtures.push({ x: cx, y: f.max[1] + 0.5, z: 3.7, kind: 'dock', len: 0.6, along: 'x' });
    }
  }
  // EXIT signs on the hall walls' inner faces, above head height, by each long wall's midpoint
  for (const w of spec.boxes.filter((x) => x.kind === 'wall' && x.height >= 5)) {
    const f = fp.get(w.id)!, lx = f.max[0] - f.min[0], ly = f.max[1] - f.min[1];
    const inner = (v: number, lo: number, hi: number) => (v - lo < hi - v ? 'max' : 'min');
    if (lx >= ly) {
      const side = inner((f.min[1] + f.max[1]) / 2, bounds.minY, bounds.maxY);
      const y0 = side === 'max' ? f.max[1] : f.min[1] - 0.04, cx = f.min[0] + lx * 0.3;
      parts.push(box(`${w.id}/exit`, 'exit', 'wall', [cx - 0.3, y0, 2.7], [cx + 0.3, y0 + 0.04, 2.95], w.id));
    } else {
      const side = inner((f.min[0] + f.max[0]) / 2, bounds.minX, bounds.maxX);
      const x0 = side === 'max' ? f.max[0] : f.min[0] - 0.04, cy = f.min[1] + ly * 0.5;
      parts.push(box(`${w.id}/exit`, 'exit', 'wall', [x0, cy - 0.3, 2.7], [x0 + 0.04, cy + 0.3, 2.95], w.id));
    }
  }
  // overhead: LED strips on a grid over the open floor and down the aisles, below a dark ceiling
  for (let x = bounds.minX + 4; x < bounds.maxX - 2; x += 6) {
    for (let y = bounds.minY + 3; y < bounds.maxY - 2; y += 5) {
      fixtures.push({ x, y, z: Math.min(ceiling - 0.5, 5.5), kind: 'strip', len: 2.4, along: 'x' });
      parts.push(box(`fix_${x.toFixed(1)}_${y.toFixed(1)}`, 'fixture', 'overhead', [x - 1.2, y - 0.07, 5.45], [x + 1.2, y + 0.07, 5.55]));
    }
  }
  parts.push(box('ceiling', 'ceiling', 'overhead', [bounds.minX - 1, bounds.minY - 1, ceiling], [bounds.maxX + 1, bounds.maxY + 1, ceiling + 0.05]));
  // floor paint (decals: flat, in the floor texture)
  const paint: Paint[] = [];
  const actors = kit(spec, 'actor');
  for (const a of actors) {
    const path = (a.path as [number, number][]).map(([x, y]) => [x + dx, y + dy] as [number, number]);
    const w = (a.footprint as [number, number])[1] / 2 + 0.25;
    for (let k = 0; k + 1 < path.length; k++) {
      const [p, q] = [path[k], path[k + 1]];
      const horiz = Math.abs(q[1] - p[1]) < 1e-9;
      for (const s of [-w, w]) {
        paint.push({ kind: 'line', from: horiz ? [p[0], p[1] + s] : [p[0] + s, p[1]], to: horiz ? [q[0], q[1] + s] : [q[0] + s, q[1]],
          width: 0.12, color: a.actor === 'forklift' ? '#d8b23a' : '#e8e8e8', dash: a.actor === 'walker' ? 0.6 : undefined });
      }
    }
  }
  // hazard stripes where a forklift lane meets another actor's lane. G2.1: where that meeting
  // lies in a round lane zone (CROSSING_ZONES), the stripes run across the zone's whole depth:
  // that is the marked crossing Fetch Rush's routes may use (coco_lab.games.crossings, rules 4;
  // a test checks the two agree)
  const lanes = actors.map((a) => {
    const path = a.path as [number, number][], w = (a.footprint as [number, number])[1] / 2 + 0.25;
    const xs = path.map((p) => p[0] + dx), ys = path.map((p) => p[1] + dy);
    return { id: a.id, forklift: a.actor === 'forklift', minX: Math.min(...xs) - w, maxX: Math.max(...xs) + w, minY: Math.min(...ys) - w, maxY: Math.max(...ys) + w };
  });
  const crossingZones = zones.filter((z) => CROSSING_ZONES.includes(z.id));
  for (let i = 0; i < lanes.length; i++) for (let j = i + 1; j < lanes.length; j++) {
    const a = lanes[i], c = lanes[j];
    const mn: [number, number] = [Math.max(a.minX, c.minX), Math.max(a.minY, c.minY)];
    const mx: [number, number] = [Math.min(a.maxX, c.maxX), Math.min(a.maxY, c.maxY)];
    if (!(mn[0] < mx[0] && mn[1] < mx[1])) continue;
    const z = (a.forklift || c.forklift) ? crossingZones.find((q) => mn[0] < q.max[0] && q.min[0] < mx[0] && mn[1] < q.max[1] && q.min[1] < mx[1]) : undefined;
    if (!z) { paint.push({ kind: 'hazard', min: mn, max: mx }); continue; }
    const across = z.max[0] - z.min[0] >= z.max[1] - z.min[1];
    paint.push(across
      ? { kind: 'hazard', min: [Math.max(mn[0], z.min[0]), z.min[1]], max: [Math.min(mx[0], z.max[0]), z.max[1]] }
      : { kind: 'hazard', min: [z.min[0], Math.max(mn[1], z.min[1])], max: [z.max[0], Math.min(mx[1], z.max[1])] });
  }
  for (const z of zones) {
    const c: [number, number] = [(z.min[0] + z.max[0]) / 2, (z.min[1] + z.max[1]) / 2];
    if (z.role === 'drop') {
      paint.push({ kind: 'rect', min: z.min, max: z.max, color: '#34D399', width: 0.08, dash: 0.3 });
      paint.push({ kind: 'label', at: c, text: z.label.toUpperCase(), size: 0.42, color: '#34D399' });
    } else if (z.role === 'start') {
      paint.push({ kind: 'rect', min: z.min, max: z.max, color: '#FF7A1A', width: 0.05 });
    } else if (z.role === 'region') {
      // G2.9 (Gautham's review: "…P MAZE", "…RKLIFT LANES"): a region's name starts inside its corner;
      // centred 1.6 m in, a long name ran out of the zone, under its walls
      paint.push({ kind: 'label', at: [z.min[0] + 0.6, z.min[1] + 0.9], text: z.label.toUpperCase(), size: 0.5, color: 'rgba(220,226,236,0.32)', align: 'left' });
    }
  }
  // aisle numbers at the ends of the high-bay aisles (between back-to-back rack pairs)
  const racks = kit(spec, 'rack').map((r) => fp.get(r.id)!).sort((p, q) => p.min[1] - q.min[1] || p.min[0] - q.min[0]);
  const rows = [...new Set(racks.map((r) => r.min[1].toFixed(2)))].map((y) => racks.filter((r) => r.min[1].toFixed(2) === y));
  let aisle = 0;
  for (let k = 0; k + 1 < rows.length; k++) {
    const gap0 = Math.max(...rows[k].map((r) => r.max[1])), gap1 = Math.min(...rows[k + 1].map((r) => r.min[1]));
    if (gap1 - gap0 > 1.5) {
      aisle += 1;
      const x0 = Math.min(...rows[k].map((r) => r.min[0]));
      paint.push({ kind: 'label', at: [x0 - 0.9, (gap0 + gap1) / 2], text: `A${aisle}`, size: 0.9, color: 'rgba(250,204,21,0.55)', rot: -Math.PI / 2 });
    }
  }
  const looks = actors.map((a) => actorLook(a.id, a.actor as 'forklift' | 'walker', (a.footprint as number[])[0], (a.footprint as number[])[1], a.height as number));
  return { id: spec.id, theme: 'depot', bounds, floor: { minX: bounds.minX - 0.5, maxX: bounds.maxX + 0.5, minY: bounds.minY - 0.5, maxY: bounds.maxY + 0.5 },
    ceiling, parts, footprints: fps, fixtures, paint, zones, actors: looks };
}

/** The Proving Ground's "test lab" look (theme 'lab'): World Spec v1 or v2, boxes and elevation only. */
export function describeLab(spec: Spec): WorldLook {
  const fps = footprints(spec);
  const [dx, dy] = spec.world_to_map;
  const b = spec.bounds;
  const bounds = { minX: b.x_min + dx, maxX: b.x_max + dx, minY: b.y_min + dy, maxY: b.y_max + dy };
  const parts: Part[] = [];
  const landmarkTints = [0x22d3ee, 0xf43f8e, 0xfacc15, 0x34d399, 0xff7a1a];
  let li = 0;
  for (const s of spec.boxes) {
    const f = fps.find((x) => x.id === s.id)!;
    const mat: Mat = s.kind === 'wall' ? 'labpanel' : s.kind === 'landmark' ? 'landmark' : 'labblock';
    parts.push(box(s.id, mat, 'solid', [f.min[0], f.min[1], 0], [f.max[0], f.max[1], s.height], s.id,
      mat === 'landmark' ? landmarkTints[li++ % landmarkTints.length] : undefined));
    if (mat === 'labpanel' && s.height > 0.6) {
      const lx = f.max[0] - f.min[0], ly = f.max[1] - f.min[1], sk = WALL_SKIN * 0.6;
      const gx = lx < ly ? sk : 0, gy = lx >= ly ? sk : 0;
      parts.push(box(`${s.id}/trim`, 'labtrim', 'wall', [f.min[0] - gx, f.min[1] - gy, s.height * 0.42], [f.max[0] + gx, f.max[1] + gy, s.height * 0.42 + 0.05], s.id));
    } else if (mat === 'labblock') {
      parts.push(box(`${s.id}/cap`, 'hazard', 'decal', [f.min[0], f.min[1], s.height], [f.max[0], f.max[1], s.height + 0.004], s.id));
    }
  }
  for (const f of fps.filter((x) => x.kind !== 'box')) {
    if (f.kind === 'wedge') {
      const e = spec.elevation!.find((x) => x.id === f.id)!;
      parts.push({ id: f.id, shape: 'wedge', mat: 'ramp', cls: 'solid', footprint: f.id, min: [f.min[0], f.min[1], 0], max: [f.max[0], f.max[1], f.top], yaw: e.yaw ?? 0 });
    } else parts.push(box(f.id, 'mezz', 'solid', [f.min[0], f.min[1], 0], [f.max[0], f.max[1], f.top], f.id));
  }
  const ceiling = 4;
  const fixtures: Fixture[] = [];
  for (let x = bounds.minX + 2; x < bounds.maxX - 1; x += 4) for (let y = bounds.minY + 2; y < bounds.maxY - 1; y += 4) {
    fixtures.push({ x, y, z: 3.6, kind: 'lamp', len: 1.2, along: 'y' });
    parts.push(box(`lamp_${x.toFixed(1)}_${y.toFixed(1)}`, 'fixture', 'overhead', [x - 0.08, y - 0.6, 3.6], [x + 0.08, y + 0.6, 3.66]));
  }
  const paint: Paint[] = [{ kind: 'grid', step: 1, color: 'rgba(40,52,70,0.30)', width: 0.02 }];
  for (let x = Math.ceil(bounds.minX / 2) * 2; x <= bounds.maxX; x += 2)
    for (let y = Math.ceil(bounds.minY / 2) * 2; y <= bounds.maxY; y += 2) paint.push({ kind: 'cal', at: [x, y], size: 0.18, color: 'rgba(255,122,26,0.65)' });
  return { id: spec.id, theme: 'lab', bounds, floor: { minX: bounds.minX - 1, maxX: bounds.maxX + 1, minY: bounds.minY - 1, maxY: bounds.maxY + 1 },
    ceiling, parts, footprints: fps, fixtures, paint, zones: [], actors: [] };
}

/** Pick the look a spec gets. */
export function describe(spec: Spec): WorldLook {
  return spec.spec_version === 'coco.world_spec.v3' ? describeDepot(spec) : describeLab(spec);
}

/**
 * Decorative honesty (G1 §0): every reason a part breaks the rule, empty when it is honest.
 * Used by the test and by the bake (which refuses to write a dishonest world).
 */
export function honestyViolations(look: WorldLook): string[] {
  const fp = new Map(look.footprints.map((f) => [f.id, f]));
  const out: string[] = [];
  const eps = 1e-6;
  const within = (p: Part, f: Footprint, grow: number) =>
    p.min[0] >= f.min[0] - grow - eps && p.max[0] <= f.max[0] + grow + eps && p.min[1] >= f.min[1] - grow - eps && p.max[1] <= f.max[1] + grow + eps;
  const outside = (p: Part) => p.max[0] <= look.bounds.minX + eps || p.min[0] >= look.bounds.maxX - eps || p.max[1] <= look.bounds.minY + eps || p.min[1] >= look.bounds.maxY - eps;
  for (const p of look.parts) {
    const f = p.footprint ? fp.get(p.footprint) : undefined;
    switch (p.cls) {
      case 'solid':
        if (!f) out.push(`${p.id}: solid with no footprint`);
        else if (!within(p, f, 0)) out.push(`${p.id}: solid outside its footprint ${f.id}`);
        else if (p.max[2] > Math.max(f.top, 0) + eps && f.kind === 'box' && p.max[2] > f.top + eps) out.push(`${p.id}: taller than ${f.id}`);
        break;
      case 'wall':
        if (!f || f.kind !== 'box') out.push(`${p.id}: wall part with no wall`);
        else if (!within(p, f, WALL_SKIN)) out.push(`${p.id}: more than ${WALL_SKIN} m off its wall ${f.id}`);
        break;
      case 'overhead':
        if (p.min[2] < OVERHEAD_Z - eps) out.push(`${p.id}: overhead part below ${OVERHEAD_Z} m`);
        break;
      case 'decal': {
        const base = f ? f.top : 0;
        if (p.max[2] - p.min[2] > DECAL_Z + eps) out.push(`${p.id}: a decal ${(p.max[2] - p.min[2]).toFixed(3)} m thick`);
        if (Math.abs(p.min[2] - base) > eps) out.push(`${p.id}: a decal not on its surface`);
        if (f && !within(p, f, 0)) out.push(`${p.id}: a decal off its surface ${f.id}`);
        break;
      }
      case 'outside':
        if (!outside(p)) out.push(`${p.id}: 'outside' part inside the bounds`);
        break;
      case 'light':
        break;
    }
  }
  for (const a of look.actors) {
    for (const p of a.parts) {
      if (p.min[0] < -a.length / 2 - eps || p.max[0] > a.length / 2 + eps || p.min[1] < -a.width / 2 - eps || p.max[1] > a.width / 2 + eps
        || p.min[2] < -eps || p.max[2] > a.height + eps) out.push(`${p.id}: outside its actor's box`);
    }
  }
  return out;
}
