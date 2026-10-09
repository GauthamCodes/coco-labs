// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena renderer (M1.6): Three.js on WebGL 2, beside React (React draws
 * only panels). Orthographic, top-down ("2.5D": layers stacked in z), with
 * pan and zoom by mouse, wheel and touch.
 *
 * Layers, bottom to top (fixed colours: render/palette.ts,
 * docs/v2/VISUAL_SYSTEM.md):
 *   occupancy + search state  one quad, two DATA TEXTURES (occupancy; per-cell
 *                             state and expansion order) and one shader:
 *                             closed set tinted, or the expansion heatmap
 *   frontier                  INSTANCED quads, one per frontier cell
 *   path                      a line
 *   LiDAR fan                 MERGED line segments, one buffer for all beams
 *   footprint                 the collision circle, dashed
 *   robot                     COCO's outline from the Gazebo chassis mesh,
 *                             with a heading mark
 *   truth                     ALWAYS an outline (dashed), never a fill
 *   goal, pick                markers
 *
 * World units are metres in the map frame. Grid cells follow coco_lab's
 * LabMap: row 0 at the top, x = ox + (col + 0.5) r, y = oy + (H - 1 - row
 * + 0.5) r.
 */

import * as THREE from 'three';

import type { World } from '../protocol';
import { PALETTES, VIRIDIS, type Palette, type Theme } from './palette';
import { CLOSED, FRONTIER, PATH, type PlanStore } from './planStore';

export interface LayerVisibility {
  occupancy: boolean; closed: boolean; heatmap: boolean; frontier: boolean; path: boolean;
  lidar: boolean; robot: boolean; footprint: boolean; truth: boolean;
}

export const DEFAULT_LAYERS: LayerVisibility = {
  occupancy: true, closed: true, heatmap: false, frontier: true, path: true,
  lidar: true, robot: true, footprint: true, truth: true,
};

const Z = { grid: 0, frontier: 0.01, path: 0.02, lidar: 0.03, footprint: 0.04, robot: 0.05, truth: 0.06, marker: 0.07 };

const VERT = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;

const FRAG = /* glsl */ `
precision highp float;
uniform sampler2D uOcc;
uniform sampler2D uState;
uniform vec3 uFree, uOccupied, uUnknown, uClosed, uPath;
uniform vec3 uViridis[5];
uniform float uClosedAlpha, uMaxOrder;
uniform bool uShowOcc, uShowClosed, uHeat, uShowPath;
varying vec2 vUv;
vec3 viridis(float t) {
  t = clamp(t, 0.0, 1.0) * 4.0;
  int i = int(floor(min(t, 3.999)));
  float f = t - float(i);
  vec3 a = uViridis[0], b = uViridis[1];
  if (i == 1) { a = uViridis[1]; b = uViridis[2]; }
  else if (i == 2) { a = uViridis[2]; b = uViridis[3]; }
  else if (i == 3) { a = uViridis[3]; b = uViridis[4]; }
  return mix(a, b, f);
}
void main() {
  float occ = texture2D(uOcc, vUv).r * 255.0;
  vec3 c = uShowOcc ? (occ < 0.5 ? uFree : occ < 1.5 ? uOccupied : uUnknown) : uFree;
  vec4 st = texture2D(uState, vUv) * 255.0;
  float s = st.r;
  float order = st.g * 65536.0 + st.b * 256.0 + st.a;
  bool expanded = s > 1.5;
  if (uHeat && expanded) c = viridis(uMaxOrder > 0.0 ? order / uMaxOrder : 0.0);
  else if (uShowClosed && s > 1.5 && s < 2.5) c = mix(c, uClosed, uClosedAlpha);
  if (uShowPath && s > 2.5) c = mix(c, uPath, uHeat ? 0.0 : 0.25);
  gl_FragColor = vec4(c, 1.0);
}`;

function col(hex: string): THREE.Color {
  return new THREE.Color(hex);
}

export class ArenaRenderer {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -10, 10);
  layers: LayerVisibility = { ...DEFAULT_LAYERS };
  private palette: Palette;
  private world: World | null = null;
  private occTex: THREE.DataTexture | null = null;
  private stateTex: THREE.DataTexture | null = null;
  private stateData: Uint8Array | null = null;
  private gridMat: THREE.ShaderMaterial | null = null;
  private frontier: THREE.InstancedMesh | null = null;
  private pathLine: THREE.Line | null = null;
  private lidar: THREE.LineSegments | null = null;
  private robot = new THREE.Group();
  private truth: THREE.LineLoop | null = null;
  private footprint: THREE.LineLoop | null = null;
  private goal: THREE.Mesh | null = null;
  private pickBox: THREE.LineLoop | null = null;
  private stress: THREE.Object3D[] = [];
  private view = { cx: 0, cy: 0, scale: 50 }; // pixels per metre
  private store: PlanStore | null = null;
  private raf = 0;
  onFrame?: () => void;
  /** Called after each frame is submitted (the measurement hook for "drawn"). */
  onAfterRender?: () => void;

  constructor(readonly canvas: HTMLCanvasElement, theme: Theme) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
    if (!this.renderer.capabilities.isWebGL2) throw new Error('WebGL 2 is required');
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.palette = PALETTES[theme];
    this.scene.background = col(this.palette.background);
    this.robot.position.z = Z.robot;
    this.scene.add(this.robot);
    this.attachInput();
  }

  // -- world ---------------------------------------------------------------

  setWorld(world: World, occupancy: Uint8Array, robotOutline: [number, number][]) {
    this.world = world;
    const { width: W, height: H, resolution: r, origin } = world;
    // texture rows go bottom-up; LabMap rows go top-down
    const occ = new Uint8Array(W * H);
    for (let row = 0; row < H; row += 1) occ.set(occupancy.subarray(row * W, (row + 1) * W), (H - 1 - row) * W);
    this.occTex = new THREE.DataTexture(occ, W, H, THREE.RedFormat, THREE.UnsignedByteType);
    this.stateData = new Uint8Array(W * H * 4);
    this.stateTex = new THREE.DataTexture(this.stateData, W, H, THREE.RGBAFormat, THREE.UnsignedByteType);
    for (const t of [this.occTex, this.stateTex]) {
      t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestFilter; t.generateMipmaps = false;
      t.needsUpdate = true;
    }
    const p = this.palette;
    this.gridMat = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG,
      uniforms: {
        uOcc: { value: this.occTex }, uState: { value: this.stateTex },
        uFree: { value: col(p.free) }, uOccupied: { value: col(p.occupied) }, uUnknown: { value: col(p.unknown) },
        uClosed: { value: col(p.closed) }, uPath: { value: col(p.path) },
        uViridis: { value: VIRIDIS.map(col) }, uClosedAlpha: { value: p.closedAlpha }, uMaxOrder: { value: 1 },
        uShowOcc: { value: true }, uShowClosed: { value: true }, uHeat: { value: false }, uShowPath: { value: true },
      },
    });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(W * r, H * r), this.gridMat);
    plane.position.set(origin[0] + (W * r) / 2, origin[1] + (H * r) / 2, Z.grid);
    this.scene.add(plane);

    // frontier: instanced squares, capacity grows
    this.frontier = this.makeFrontier(4096, r);

    this.pathLine = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: p.path, linewidth: 2 }));
    this.pathLine.position.z = Z.path;
    this.scene.add(this.pathLine);

    const beams = world.lidar.samples;
    const lg = new THREE.BufferGeometry();
    lg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(beams * 6), 3).setUsage(THREE.DynamicDrawUsage));
    this.lidar = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: p.lidar, transparent: true, opacity: p.lidarAlpha }));
    this.lidar.position.z = Z.lidar;
    this.scene.add(this.lidar);

    // the robot, from the chassis mesh outline (base_link frame)
    const shape = new THREE.Shape(robotOutline.map(([x, y]) => new THREE.Vector2(x, y)));
    this.robot.add(new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({ color: p.robot })));
    const nose = new THREE.Shape([new THREE.Vector2(0.11, 0), new THREE.Vector2(0.03, 0.05), new THREE.Vector2(0.03, -0.05)]);
    const noseMesh = new THREE.Mesh(new THREE.ShapeGeometry(nose), new THREE.MeshBasicMaterial({ color: p.heading }));
    noseMesh.position.z = 0.001;
    this.robot.add(noseMesh);

    this.footprint = this.dashedLoop(this.circle(world.radius, 48), p.footprint, 0.04);
    this.footprint.position.z = Z.footprint;
    this.truth = this.dashedLoop(robotOutline.map(([x, y]) => new THREE.Vector3(x, y, 0)), p.truth, 0.03);
    this.truth.position.z = Z.truth;

    this.goal = new THREE.Mesh(new THREE.RingGeometry(0.12, 0.18, 32), new THREE.MeshBasicMaterial({ color: p.goal }));
    this.goal.position.z = Z.marker;
    this.goal.visible = false;
    this.scene.add(this.goal);
    this.pickBox = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-r / 2, -r / 2, 0), new THREE.Vector3(r / 2, -r / 2, 0),
      new THREE.Vector3(r / 2, r / 2, 0), new THREE.Vector3(-r / 2, r / 2, 0)]),
    new THREE.LineBasicMaterial({ color: p.pick }));
    this.pickBox.position.z = Z.marker;
    this.pickBox.visible = false;
    this.scene.add(this.pickBox);

    this.fit();
    this.setPose(world.start);
  }

  private circle(r: number, n: number) {
    return Array.from({ length: n }, (_, i) => new THREE.Vector3(r * Math.cos((2 * Math.PI * i) / n), r * Math.sin((2 * Math.PI * i) / n), 0));
  }

  private dashedLoop(points: THREE.Vector3[], color: string, dash: number) {
    const g = new THREE.BufferGeometry().setFromPoints([...points, points[0]]);
    const l = new THREE.LineLoop(g, new THREE.LineDashedMaterial({ color, dashSize: dash, gapSize: dash * 0.7 }));
    l.computeLineDistances();
    this.scene.add(l);
    return l;
  }

  private makeFrontier(capacity: number, r: number) {
    if (this.frontier) { this.scene.remove(this.frontier); this.frontier.dispose(); }
    const m = new THREE.InstancedMesh(new THREE.PlaneGeometry(r * 0.7, r * 0.7),
      new THREE.MeshBasicMaterial({ color: this.palette.frontier }), capacity);
    m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    m.count = 0;
    m.frustumCulled = false;
    m.position.z = Z.frontier;
    this.scene.add(m);
    return m;
  }

  // -- state from the model -------------------------------------------------

  /** COCO's pose (map frame): the robot, its footprint and the truth outline. */
  setPose(pose: [number, number, number], truth: [number, number, number] = pose) {
    this.robot.position.set(pose[0], pose[1], Z.robot);
    this.robot.rotation.z = pose[2];
    this.footprint?.position.set(pose[0], pose[1], Z.footprint);
    if (this.truth) {
      this.truth.position.set(truth[0], truth[1], Z.truth);
      this.truth.rotation.z = truth[2];
    }
  }

  setScan(pose: [number, number, number], ranges: Float32Array) {
    if (!this.lidar || !this.world) return;
    const { angle_min, angle_max, samples, mount, range_max } = this.world.lidar;
    const c = Math.cos(pose[2]);
    const s = Math.sin(pose[2]);
    const sx = pose[0] + c * mount[0] - s * mount[1];
    const sy = pose[1] + s * mount[0] + c * mount[1];
    const step = samples > 1 ? (angle_max - angle_min) / (samples - 1) : 0;
    const pos = this.lidar.geometry.getAttribute('position') as THREE.BufferAttribute;
    const a = pos.array as Float32Array;
    let k = 0;
    for (let i = 0; i < ranges.length; i += 1) {
      const rr = Number.isFinite(ranges[i]) ? ranges[i] : 0; // no return: no beam drawn
      const th = pose[2] + angle_min + i * step;
      a[k++] = sx; a[k++] = sy; a[k++] = 0;
      a[k++] = sx + Math.cos(th) * Math.min(rr, range_max); a[k++] = sy + Math.sin(th) * Math.min(rr, range_max); a[k++] = 0;
    }
    pos.needsUpdate = true;
  }

  setGoal(goal: [number, number] | null) {
    if (!this.goal) return;
    this.goal.visible = goal !== null;
    if (goal) this.goal.position.set(goal[0], goal[1], Z.marker);
  }

  /** The search layers read this store; call after it changes. */
  setPlan(store: PlanStore | null) {
    this.store = store;
    if (store) store.dirty = true;
    if (!store && this.stateData && this.stateTex) {
      this.stateData.fill(0);
      this.stateTex.needsUpdate = true;
      if (this.frontier) this.frontier.count = 0;
      this.pathLine?.geometry.setFromPoints([]);
    }
  }

  private syncPlan() {
    const st = this.store;
    if (!st || !st.dirty || !this.world || !this.stateData || !this.stateTex) return;
    const { width: W, height: H, resolution: r, origin } = this.world;
    const d = this.stateData;
    let fcount = 0;
    const cells: number[] = [];
    for (let row = 0; row < H; row += 1) {
      const t = (H - 1 - row) * W;
      for (let c = 0; c < W; c += 1) {
        const i = row * W + c;
        const s = st.state[i];
        const o = (t + c) * 4;
        d[o] = s;
        const ord = st.order[i];
        if (ord >= 0) { d[o + 1] = (ord >> 16) & 255; d[o + 2] = (ord >> 8) & 255; d[o + 3] = ord & 255; } else { d[o + 1] = 0; d[o + 2] = 0; d[o + 3] = 0; }
        if (s === FRONTIER) { fcount += 1; cells.push(i); }
      }
    }
    this.stateTex.needsUpdate = true;
    if (this.gridMat) this.gridMat.uniforms.uMaxOrder.value = Math.max(1, st.expansions - 1);
    // frontier instances
    if (!this.frontier || fcount > this.frontier.instanceMatrix.count) this.frontier = this.makeFrontier(Math.max(fcount, 4096) * 2, r);
    const m = new THREE.Matrix4();
    for (let k = 0; k < cells.length; k += 1) {
      const row = Math.floor(cells[k] / W);
      const c = cells[k] % W;
      m.makeTranslation(origin[0] + (c + 0.5) * r, origin[1] + (H - 1 - row + 0.5) * r, 0);
      this.frontier.setMatrixAt(k, m);
    }
    this.frontier.count = fcount;
    this.frontier.instanceMatrix.needsUpdate = true;
    // path, in event order
    const pts = st.pathCells.map((i) => new THREE.Vector3(origin[0] + ((i % W) + 0.5) * r, origin[1] + (H - 1 - Math.floor(i / W) + 0.5) * r, 0));
    this.pathLine?.geometry.setFromPoints(pts);
    st.dirty = false;
  }

  setLayers(v: Partial<LayerVisibility>) {
    this.layers = { ...this.layers, ...v };
    const L = this.layers;
    if (this.gridMat) {
      const u = this.gridMat.uniforms;
      u.uShowOcc.value = L.occupancy; u.uShowClosed.value = L.closed; u.uHeat.value = L.heatmap; u.uShowPath.value = L.path;
    }
    if (this.frontier) this.frontier.visible = L.frontier;
    if (this.pathLine) this.pathLine.visible = L.path;
    if (this.lidar) this.lidar.visible = L.lidar;
    this.robot.visible = L.robot;
    if (this.footprint) this.footprint.visible = L.footprint;
    if (this.truth) this.truth.visible = L.truth;
  }

  // -- camera and input -----------------------------------------------------

  fit() {
    if (!this.world) return;
    const { width: W, height: H, resolution: r, origin } = this.world;
    const w = this.canvas.clientWidth || 1;
    const h = this.canvas.clientHeight || 1;
    this.view.cx = origin[0] + (W * r) / 2;
    this.view.cy = origin[1] + (H * r) / 2;
    this.view.scale = Math.min(w / (W * r), h / (H * r)) * 0.98;
    this.applyView();
  }

  private applyView() {
    const w = this.canvas.clientWidth || 1;
    const h = this.canvas.clientHeight || 1;
    const hw = w / 2 / this.view.scale;
    const hh = h / 2 / this.view.scale;
    Object.assign(this.camera, { left: this.view.cx - hw, right: this.view.cx + hw, top: this.view.cy + hh, bottom: this.view.cy - hh });
    this.camera.updateProjectionMatrix();
  }

  /** Screen (client) coordinates to map-frame metres. */
  toWorld(clientX: number, clientY: number): [number, number] {
    const rect = this.canvas.getBoundingClientRect();
    const x = this.view.cx + (clientX - rect.left - rect.width / 2) / this.view.scale;
    const y = this.view.cy - (clientY - rect.top - rect.height / 2) / this.view.scale;
    return [x, y];
  }

  /** Map-frame metres to the grid cell (row, col), or null off the map. */
  cellAt(x: number, y: number): [number, number] | null {
    if (!this.world) return null;
    const { width: W, height: H, resolution: r, origin } = this.world;
    const col = Math.floor((x - origin[0]) / r);
    const up = Math.floor((y - origin[1]) / r);
    if (col < 0 || up < 0 || col >= W || up >= H) return null;
    return [H - 1 - up, col];
  }

  showPick(cell: [number, number] | null) {
    if (!this.pickBox || !this.world) return;
    this.pickBox.visible = cell !== null;
    if (cell) {
      const { height: H, resolution: r, origin } = this.world;
      this.pickBox.position.set(origin[0] + (cell[1] + 0.5) * r, origin[1] + (H - 1 - cell[0] + 0.5) * r, Z.marker);
    }
  }

  private attachInput() {
    const pts = new Map<number, [number, number]>();
    let pinch0 = 0;
    let scale0 = 1;
    const c = this.canvas;
    c.style.touchAction = 'none';
    c.addEventListener('pointerdown', (e) => { pts.set(e.pointerId, [e.clientX, e.clientY]); c.setPointerCapture(e.pointerId);
      if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch0 = Math.hypot(a[0] - b[0], a[1] - b[1]); scale0 = this.view.scale; } });
    c.addEventListener('pointermove', (e) => {
      const prev = pts.get(e.pointerId);
      if (!prev) return;
      pts.set(e.pointerId, [e.clientX, e.clientY]);
      if (pts.size === 1) {
        this.view.cx -= (e.clientX - prev[0]) / this.view.scale;
        this.view.cy += (e.clientY - prev[1]) / this.view.scale;
      } else if (pts.size === 2 && pinch0 > 0) {
        const [a, b] = [...pts.values()];
        this.view.scale = Math.max(2, Math.min(2000, scale0 * (Math.hypot(a[0] - b[0], a[1] - b[1]) / pinch0)));
      }
      this.applyView();
    });
    const up = (e: PointerEvent) => { pts.delete(e.pointerId); if (pts.size < 2) pinch0 = 0; };
    c.addEventListener('pointerup', up);
    c.addEventListener('pointercancel', up);
    c.addEventListener('wheel', (e) => {
      e.preventDefault();
      const before = this.toWorld(e.clientX, e.clientY);
      this.view.scale = Math.max(2, Math.min(2000, this.view.scale * Math.exp(-e.deltaY * 0.0015)));
      this.applyView();
      const after = this.toWorld(e.clientX, e.clientY);
      this.view.cx += before[0] - after[0];
      this.view.cy += before[1] - after[1];
      this.applyView();
    }, { passive: false });
  }

  // -- the loop -------------------------------------------------------------

  resize() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (this.canvas.width !== Math.round(w * this.renderer.getPixelRatio()) || this.canvas.height !== Math.round(h * this.renderer.getPixelRatio())) {
      this.renderer.setSize(w, h, false);
      this.applyView();
    }
  }

  start() {
    const loop = () => {
      this.resize();
      this.onFrame?.();
      this.syncPlan();
      this.renderer.render(this.scene, this.camera);
      this.onAfterRender?.();
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }

  /** The performance criterion's load: n instanced points, m line segments. */
  addStress(points: number, segments: number) {
    if (!this.world) return;
    const { width: W, height: H, resolution: r, origin } = this.world;
    const rand = (k: number) => { const x = Math.sin(k * 12.9898) * 43758.5453; return x - Math.floor(x); };
    const pm = new THREE.InstancedMesh(new THREE.PlaneGeometry(r * 0.6, r * 0.6), new THREE.MeshBasicMaterial({ color: this.palette.frontier }), points);
    const m = new THREE.Matrix4();
    for (let i = 0; i < points; i += 1) {
      m.makeTranslation(origin[0] + rand(i) * W * r, origin[1] + rand(i + 7e5) * H * r, Z.frontier);
      pm.setMatrixAt(i, m);
    }
    pm.frustumCulled = false;
    const seg = new Float32Array(segments * 6);
    for (let i = 0; i < segments; i += 1) {
      const x = origin[0] + rand(i + 3e5) * W * r;
      const y = origin[1] + rand(i + 4e5) * H * r;
      seg.set([x, y, Z.lidar, x + (rand(i + 5e5) - 0.5), y + (rand(i + 6e5) - 0.5), Z.lidar], i * 6);
    }
    const sg = new THREE.BufferGeometry();
    sg.setAttribute('position', new THREE.BufferAttribute(seg, 3));
    const sl = new THREE.LineSegments(sg, new THREE.LineBasicMaterial({ color: this.palette.lidar, transparent: true, opacity: 0.35 }));
    sl.frustumCulled = false;
    this.scene.add(pm, sl);
    this.stress.push(pm, sl);
  }

  dispose() {
    cancelAnimationFrame(this.raf);
    this.renderer.dispose();
  }
}

export { CLOSED, PATH };
