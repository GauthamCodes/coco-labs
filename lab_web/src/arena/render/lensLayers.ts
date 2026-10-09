// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The lenses' drawing vocabulary (M2.2; README 5.2 "Visual primitives"):
 * instanced points, poses, line sets, ellipses, polygons and a scalar grid,
 * drawn into the Arena's Three.js scene beside the M1 layers. Each primitive
 * belongs to one layer id (lens/registry.ts) and takes its colour from the
 * palette by key -- never a literal. Uncertainty is translucent by
 * construction here (ellipses are always filled at the palette's alpha);
 * truth is never drawn by this module (the M1 renderer's dashed outline is
 * truth's only drawing).
 *
 * Geometry only: a covariance's ellipse axes are computed from the 2x2 the
 * model emitted (an eigen-decomposition for drawing), and a log-odds cell's
 * shade from its value. No algorithm runs here.
 */

import * as THREE from 'three';

import type { Palette } from './palette';

/** Above the M1 path (0.02), below the robot (0.05). */
const Z = 0.035;

type Obj = THREE.Mesh | THREE.LineSegments | THREE.InstancedMesh | THREE.Group;

interface Entry { obj: Obj; baseOpacity: number[]; colour: keyof Palette }

function materials(o: THREE.Object3D): THREE.Material[] {
  const out: THREE.Material[] = [];
  o.traverse((c) => {
    const m = (c as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
    if (Array.isArray(m)) out.push(...m); else if (m) out.push(m);
  });
  return out;
}

/** Half-axes and angle of the 95 % ellipse of a 2x2 covariance [[a, b], [b, c]] (chi2(2) = 5.991). */
export function ellipseAxes(a: number, b: number, c: number): [number, number, number] {
  const tr = (a + c) / 2;
  const d = Math.sqrt(Math.max(0, ((a - c) / 2) ** 2 + b * b));
  const l1 = Math.max(0, tr + d);
  const l2 = Math.max(0, tr - d);
  const ang = Math.abs(b) < 1e-15 && a >= c ? 0 : Math.atan2(l1 - a, b);
  const k = Math.sqrt(5.991);
  return [k * Math.sqrt(l1), k * Math.sqrt(l2), ang];
}

export class LensLayers {
  private entries = new Map<string, Entry>();
  private visible = new Map<string, boolean>();
  private dim = new Map<string, number>();

  constructor(private readonly scene: THREE.Scene, private palette: Palette) {}

  setPalette(p: Palette) {
    this.palette = p;
    for (const [id, e] of this.entries) this.recolour(id, e);
  }

  private recolour(id: string, e: Entry) {
    const c = new THREE.Color(this.palette[e.colour] as string);
    for (const m of materials(e.obj)) {
      const mm = m as THREE.MeshBasicMaterial;
      if (!(mm as unknown as { vertexColors: boolean }).vertexColors) mm.color?.set(c);
    }
    this.applyOpacity(id, e);
  }

  private put(id: string, obj: Obj, colour: keyof Palette) {
    this.remove(id);
    obj.position.z = Z;
    obj.renderOrder = 2;
    const e: Entry = { obj, colour, baseOpacity: materials(obj).map((m) => m.opacity) };
    this.entries.set(id, e);
    this.scene.add(obj);
    this.applyOpacity(id, e);
  }

  private applyOpacity(id: string, e: Entry) {
    const f = this.dim.get(id) ?? 1;
    materials(e.obj).forEach((m, i) => {
      m.opacity = (e.baseOpacity[i] ?? 1) * f;
      m.transparent = m.opacity < 1 || e.baseOpacity[i] < 1;
    });
    e.obj.visible = this.visible.get(id) ?? true;
  }

  remove(id: string) {
    const e = this.entries.get(id);
    if (!e) return;
    this.scene.remove(e.obj);
    e.obj.traverse((c) => {
      (c as THREE.Mesh).geometry?.dispose();
    });
    for (const m of materials(e.obj)) m.dispose();
    this.entries.delete(id);
  }

  has(id: string): boolean {
    return this.entries.has(id);
  }

  setVisible(id: string, v: boolean) {
    this.visible.set(id, v);
    const e = this.entries.get(id);
    if (e) e.obj.visible = v;
  }

  /** Focus: multiply a layer's opacity (1 = as drawn). */
  setDim(id: string, factor: number) {
    this.dim.set(id, factor);
    const e = this.entries.get(id);
    if (e) this.applyOpacity(id, e);
  }

  /** Instanced discs at (x, y), radius r[i] metres (or `r0`). */
  points(id: string, xs: ArrayLike<number>, ys: ArrayLike<number>, colour: keyof Palette,
    alpha: number, r0 = 0.03, r?: ArrayLike<number>) {
    const n = xs.length;
    const mat = new THREE.MeshBasicMaterial({ color: this.palette[colour] as string, transparent: alpha < 1, opacity: alpha, depthWrite: false });
    const mesh = new THREE.InstancedMesh(new THREE.CircleGeometry(1, 10), mat, Math.max(1, n));
    const m = new THREE.Matrix4();
    for (let i = 0; i < n; i += 1) {
      const s = r ? r[i] : r0;
      m.makeScale(s, s, 1).setPosition(xs[i], ys[i], 0);
      mesh.setMatrixAt(i, m);
    }
    mesh.count = n;
    mesh.instanceMatrix.needsUpdate = true;
    this.put(id, mesh, colour);
  }

  /** Arrows for poses (x, y, theta), `len` metres long. */
  poses(id: string, poses: [number, number, number][], colour: keyof Palette, len = 0.25, alpha = 1) {
    const pos: number[] = [];
    for (const [x, y, t] of poses) {
      const hx = x + len * Math.cos(t); const hy = y + len * Math.sin(t);
      pos.push(x, y, 0, hx, hy, 0);
      for (const s of [2.6, -2.6]) pos.push(hx, hy, 0, hx + 0.35 * len * Math.cos(t + s), hy + 0.35 * len * Math.sin(t + s), 0);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    this.put(id, new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: this.palette[colour] as string, transparent: alpha < 1, opacity: alpha })), colour);
  }

  /**
   * 95 % ellipses of 2x2 covariances, FILLED translucent (uncertainty) with
   * an outline at twice the alpha. `alpha` must be < 1: uncertainty is never solid.
   */
  ellipses(id: string, items: { x: number; y: number; cxx: number; cxy: number; cyy: number }[],
    colour: keyof Palette, alpha: number) {
    if (!(alpha < 1)) throw new Error(`${id}: an uncertainty ellipse must be translucent (alpha ${alpha})`);
    const N = 36;
    const tri: number[] = [];
    const line: number[] = [];
    for (const e of items) {
      const [a, b, ang] = ellipseAxes(e.cxx, e.cxy, e.cyy);
      const ca = Math.cos(ang); const sa = Math.sin(ang);
      const pt = (k: number): [number, number] => {
        const u = (2 * Math.PI * k) / N;
        const px = a * Math.cos(u); const py = b * Math.sin(u);
        return [e.x + ca * px - sa * py, e.y + sa * px + ca * py];
      };
      for (let k = 0; k < N; k += 1) {
        const [x0, y0] = pt(k); const [x1, y1] = pt(k + 1);
        tri.push(e.x, e.y, 0, x0, y0, 0, x1, y1, 0);
        line.push(x0, y0, 0, x1, y1, 0);
      }
    }
    const grp = new THREE.Group();
    const tg = new THREE.BufferGeometry();
    tg.setAttribute('position', new THREE.Float32BufferAttribute(tri, 3));
    grp.add(new THREE.Mesh(tg, new THREE.MeshBasicMaterial({ color: this.palette[colour] as string, transparent: true, opacity: alpha, depthWrite: false, side: THREE.DoubleSide })));
    const lg = new THREE.BufferGeometry();
    lg.setAttribute('position', new THREE.Float32BufferAttribute(line, 3));
    grp.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: this.palette[colour] as string, transparent: true, opacity: Math.min(0.95, alpha * 2) })));
    this.put(id, grp, colour);
  }

  /**
   * Line segments: `pos` = x0, y0, x1, y1, ... ; one shade per segment
   * (0..1 mixes the layer colour toward the background), or all full.
   */
  segments(id: string, pos: ArrayLike<number>, colour: keyof Palette, alpha: number, shade?: ArrayLike<number>) {
    const n = Math.floor(pos.length / 4);
    const p = new Float32Array(n * 6);
    const c = new Float32Array(n * 6);
    const fg = new THREE.Color(this.palette[colour] as string);
    const bg = new THREE.Color(this.palette.background);
    const tmp = new THREE.Color();
    for (let i = 0; i < n; i += 1) {
      p.set([pos[4 * i], pos[4 * i + 1], 0, pos[4 * i + 2], pos[4 * i + 3], 0], 6 * i);
      tmp.copy(fg).lerp(bg, shade ? Math.min(0.85, Math.max(0, shade[i])) : 0);
      c.set([tmp.r, tmp.g, tmp.b, tmp.r, tmp.g, tmp.b], 6 * i);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(p, 3));
    g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    this.put(id, new THREE.LineSegments(g, new THREE.LineBasicMaterial({ vertexColors: true, transparent: alpha < 1, opacity: alpha })), colour);
  }

  /** Filled polygons, each at its own alpha (e.g. a belief: alpha = probability x the palette's). */
  polygons(id: string, polys: [number, number][][], colour: keyof Palette, alphas: number[]) {
    const grp = new THREE.Group();
    polys.forEach((poly, i) => {
      const shape = new THREE.Shape(poly.map(([x, y]) => new THREE.Vector2(x, y)));
      const a = Math.max(0, Math.min(0.95, alphas[i] ?? 0.5));
      grp.add(new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({ color: this.palette[colour] as string, transparent: true, opacity: a, depthWrite: false })));
      const lg = new THREE.BufferGeometry().setFromPoints([...poly, poly[0]].map(([x, y]) => new THREE.Vector3(x, y, 0)));
      grp.add(new THREE.Line(lg, new THREE.LineBasicMaterial({ color: this.palette[colour] as string })));
    });
    this.put(id, grp, colour);
  }

  /**
   * A scalar grid as a texture: log-odds per cell (row 0 at the bottom
   * unless `row0IsBottom` is false), shaded from the palette's mapFree (l << 0) to mapOccupied (l >> 0);
   * unknown (l == 0) is transparent. One plane over the map's extent.
   */
  mapTexture(id: string, width: number, height: number, resolution: number, origin: [number, number],
    logodds: ArrayLike<number>, row0IsBottom = true) {
    const rgba = new Uint8Array(width * height * 4);
    const free = new THREE.Color(this.palette.mapFree);
    const occ = new THREE.Color(this.palette.mapOccupied);
    const t = new THREE.Color();
    for (let i = 0; i < width * height; i += 1) {
      // texture rows go bottom-up; a top-down grid (a LabMap's) is flipped
      const src = row0IsBottom ? i : (height - 1 - Math.floor(i / width)) * width + (i % width);
      const l = logodds[src];
      if (l === 0) continue;
      const p = 1 / (1 + Math.exp(-l));
      t.copy(free).lerp(occ, p);
      rgba.set([Math.round(t.r * 255), Math.round(t.g * 255), Math.round(t.b * 255), Math.round(255 * Math.min(1, 0.25 + Math.abs(p - 0.5) * 1.5))], i * 4);
    }
    const tex = new THREE.DataTexture(rgba, width, height, THREE.RGBAFormat, THREE.UnsignedByteType);
    tex.magFilter = THREE.NearestFilter; tex.minFilter = THREE.NearestFilter;
    tex.needsUpdate = true;
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(width * resolution, height * resolution),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 1, depthWrite: false }));
    plane.position.set(origin[0] + (width * resolution) / 2, origin[1] + (height * resolution) / 2, 0);
    const grp = new THREE.Group();
    grp.add(plane);
    this.put(id, grp, 'mapOccupied');
  }

  ids(): string[] {
    return [...this.entries.keys()];
  }

  dispose() {
    for (const id of [...this.entries.keys()]) this.remove(id);
  }
}
