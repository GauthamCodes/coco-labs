// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.2: SIM view's costmaps and map, drawn as RViz's Map display draws an OccupancyGrid.
 *
 * The costs are the model's own (coco_lab.costmap, Nav2's convention: LETHAL 254, INSCRIBED
 * 253, inflation 1..252, free 0), the same cells Robot vision received
 * (`coco.costmap.layers.cells.v1`). Nav2 publishes a costmap as an OccupancyGrid by translating
 * each cost (254 -> 100, 253 -> 99, 1..252 -> 1..98, 255 -> -1); RViz's "costmap" colour scheme
 * then draws 0 transparent, 1..98 blue to red, 99 (inscribed) cyan, 100 (lethal) purple. The
 * "map" scheme draws free light grey, occupied black, unknown grey-green. Presentation only.
 *
 * One texture of costs feeds two layers: the global costmap (the whole map) and the local
 * costmap (the same cells inside a window that moves with COCO, as Nav2's rolling local costmap).
 */

import * as THREE from 'three';

/** Nav2's cost -> OccupancyGrid value (nav2_costmap_2d's cost translation table). */
export function costToGrid(c: number): number {
  if (c === 0) return 0;
  if (c === 253) return 99;
  if (c === 254) return 100;
  if (c === 255) return -1;
  return 1 + Math.floor((97 * (c - 1)) / 251);
}

/** RViz's "costmap" scheme: an OccupancyGrid value -> RGBA 0..255 (alpha 0: not drawn). */
export function costmapColour(v: number): [number, number, number, number] {
  if (v === 0) return [0, 0, 0, 0];
  if (v === 99) return [0, 255, 255, 255];
  if (v === 100) return [255, 0, 255, 255];
  if (v === -1) return [0, 0, 0, 0];
  const k = Math.floor((255 * v) / 100);
  return [k, 0, 255 - k, 255];
}

const COSTMAP_GLSL = `
  float grid(float c) {   // Nav2 cost (0..255) -> OccupancyGrid value
    if (c < 0.5) return 0.0;
    if (c > 254.5) return -1.0;
    if (c > 253.5) return 100.0;
    if (c > 252.5) return 99.0;
    return 1.0 + floor(97.0 * (c - 1.0) / 251.0);
  }
  vec4 palette(float v) {  // RViz's costmap scheme
    if (v < 0.5) return vec4(0.0);
    if (v > 99.5) return vec4(1.0, 0.0, 1.0, 1.0);
    if (v > 98.5) return vec4(0.0, 1.0, 1.0, 1.0);
    float k = floor(255.0 * v / 100.0) / 255.0;
    return vec4(k, 0.0, 1.0 - k, 1.0);
  }`;

export class CostLayers {
  readonly global: THREE.Mesh;
  readonly local: THREE.Mesh;
  private readonly data: Uint8Array;
  private readonly tex: THREE.DataTexture;
  private readonly g: Record<string, { value: unknown }>;
  private readonly l: Record<string, { value: unknown }>;
  /** the local costmap's half size (m): Nav2's local costmap is 3 x 3 m in COCO's params */
  static readonly LOCAL_HALF = 1.5;

  constructor(readonly width: number, readonly height: number, readonly resolution: number, origin: [number, number]) {
    this.data = new Uint8Array(width * height);
    this.tex = new THREE.DataTexture(this.data, width, height, THREE.RedFormat, THREE.UnsignedByteType);
    this.tex.magFilter = THREE.NearestFilter; this.tex.minFilter = THREE.NearestFilter;
    this.tex.unpackAlignment = 1;
    this.tex.needsUpdate = true;
    const W = width * resolution, H = height * resolution;
    const common = () => ({ uCost: { value: this.tex }, uOrigin: { value: new THREE.Vector2(origin[0], origin[1]) }, uSize: { value: new THREE.Vector2(W, H) }, uAlpha: { value: 0.5 } });
    this.g = common();
    this.l = { ...common(), uCentre: { value: new THREE.Vector2() }, uHalf: { value: CostLayers.LOCAL_HALF } };
    const vertex = `varying vec2 vW; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xy; gl_Position = projectionMatrix * viewMatrix * w; }`;
    const make = (u: Record<string, { value: unknown }>, local: boolean) => new THREE.ShaderMaterial({
      uniforms: u, transparent: true, depthWrite: false, toneMapped: false,
      vertexShader: vertex,
      fragmentShader: `uniform sampler2D uCost; uniform vec2 uOrigin; uniform vec2 uSize; uniform float uAlpha; ${local ? 'uniform vec2 uCentre; uniform float uHalf;' : ''} varying vec2 vW;
        ${COSTMAP_GLSL}
        void main() {
          ${local ? 'if (abs(vW.x - uCentre.x) > uHalf || abs(vW.y - uCentre.y) > uHalf) discard;' : ''}
          vec2 uv = (vW - uOrigin) / uSize;
          if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) discard;
          vec4 c = palette(grid(texture2D(uCost, vec2(uv.x, 1.0 - uv.y)).r * 255.0));
          if (c.a < 0.5) discard;
          gl_FragColor = vec4(c.rgb, uAlpha);
        }`,
    });
    this.global = new THREE.Mesh(new THREE.PlaneGeometry(W, H), make(this.g, false));
    this.global.position.set(origin[0] + W / 2, origin[1] + H / 2, 0.006);
    this.global.renderOrder = 3;
    this.global.name = 'sim:global_costmap';
    this.local = new THREE.Mesh(new THREE.PlaneGeometry(W, H), make(this.l, true));
    this.local.position.set(origin[0] + W / 2, origin[1] + H / 2, 0.009);
    this.local.renderOrder = 4;
    this.local.name = 'sim:local_costmap';
  }

  /** One batch of the model's cells (rows, cols, combined costs). */
  apply(rows: ArrayLike<number>, cols: ArrayLike<number>, costs: ArrayLike<number>) {
    for (let k = 0; k < rows.length; k++) this.data[Number(rows[k]) * this.width + Number(cols[k])] = Number(costs[k]);
    this.tex.needsUpdate = true;
  }

  /** The local window follows COCO. */
  follow(x: number, y: number) { (this.l.uCentre.value as THREE.Vector2).set(x, y); }
  alpha(global: number, local: number) { this.g.uAlpha.value = global; this.l.uAlpha.value = local; }

  dispose() { this.tex.dispose(); for (const m of [this.global, this.local]) { m.geometry.dispose(); (m.material as THREE.Material).dispose(); } }
}

/** RViz's "map" scheme for an OccupancyGrid value: free light grey, occupied black, unknown grey-green. */
export function mapColour(v: number): [number, number, number] {
  if (v === 0) return [254, 254, 254];
  if (v === 100) return [0, 0, 0];
  if (v < 0) return [0x70, 0x89, 0x86];
  const k = 255 - Math.floor((255 * v) / 100);
  return [k, k, k];
}

/** The Map display: the world's LabMap (codes 0 free, 1 occupied, 2 unknown) as a texture plane. */
export function mapPlane(map: { width: number; height: number; resolution: number; origin: [number, number] }, occupancy: ArrayLike<number>): THREE.Mesh {
  const { width: w, height: h } = map;
  const rgba = new Uint8Array(w * h * 4);
  for (let row = 0; row < h; row++) {
    for (let c = 0; c < w; c++) {
      const code = occupancy[row * w + c];
      const [r, g, b] = mapColour(code === 0 ? 0 : code === 1 ? 100 : -1);
      const k = ((h - 1 - row) * w + c) * 4;   // texture row 0 at the origin (a LabMap's row 0 is the top)
      rgba[k] = r; rgba[k + 1] = g; rgba[k + 2] = b; rgba[k + 3] = 255;
    }
  }
  const tex = new THREE.DataTexture(rgba, w, h, THREE.RGBAFormat, THREE.UnsignedByteType);
  tex.magFilter = THREE.NearestFilter; tex.minFilter = THREE.NearestFilter;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.needsUpdate = true;
  const W = w * map.resolution, H = h * map.resolution;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(W, H), new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0.7, depthWrite: false, toneMapped: false }));
  m.position.set(map.origin[0] + W / 2, map.origin[1] + H / 2, 0.003);
  m.renderOrder = 2;
  m.name = 'sim:map';
  return m;
}
