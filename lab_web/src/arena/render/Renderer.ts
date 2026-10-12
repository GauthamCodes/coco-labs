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

import type { Tick, World } from '../protocol';

/** coco_lab.arm's names for the arm's joints, and the URDF's (coco_robo2.urdf). */
const ARM_JOINTS: [string, string][] = [['joint1', 'm_link1_Revolute-6'], ['joint2', 'm_link2_Revolute-7'],
  ['finger_left', 'm_link3_Revolute-8'], ['finger_right', 'm_link3_Revolute-9']];

/**
 * Give a line new points. `geometry.setFromPoints` on a geometry that
 * already has positions only overwrites them in place (three r186): a
 * longer path was cut to the old length and a shorter one kept the old
 * tail, so every replanned path after the first was drawn wrong (found in
 * M2.4). A new geometry each time is always right.
 */
export function setLinePoints(line: THREE.Line, pts: THREE.Vector3[]) {
  line.geometry.dispose();
  line.geometry = new THREE.BufferGeometry().setFromPoints(pts);
}
import { PALETTES, VIRIDIS, type Palette, type Theme } from './palette';
import { CLOSED, FRONTIER, PATH, type PlanStore } from './planStore';
import { Scene3D, WORLD_LAYER, type CameraMode, type Scene3DAssets } from './scene3d';
import { drapedPlane, surfaces, type Elevation, type Quad } from './drape';
import { QualityController, TIER_SETTINGS, type QualityEvent, type Tier, type TierChoice } from './quality';

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
uniform float uPlanDim, uWorldDim;
uniform vec3 uBg;
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
  c = mix(uBg, c, uWorldDim);  // Focus (M2.2): the world, dimmed outside the lens
  vec3 base = c;
  vec4 st = texture2D(uState, vUv) * 255.0;
  float s = st.r;
  float order = st.g * 65536.0 + st.b * 256.0 + st.a;
  bool expanded = s > 1.5;
  if (uHeat && expanded) c = viridis(uMaxOrder > 0.0 ? order / uMaxOrder : 0.0);
  else if (uShowClosed && s > 1.5 && s < 2.5) c = mix(c, uClosed, uClosedAlpha);
  if (uShowPath && s > 2.5) c = mix(c, uPath, uHeat ? 0.0 : 0.25);
  c = mix(base, c, uPlanDim);  // Focus: the Plan lens's layers, dimmed outside it
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
  /** M2.3: while the page drags something (the robot, to kidnap it), a drag does not pan. */
  panSuspended = false;
  private raf = 0;
  /** M4.1: the 3D scene (perspective camera, glTF arena and robot), once enabled. */
  three: Scene3D | null = null;
  cameraMode: CameraMode = 'topdown';
  private lastFrame = 0;
  private lastPose: [number, number, number] = [0, 0, 0];
  private lastTilt: [number, number, number] | undefined;
  /** M4.4: the 3D view's quality tier, chosen from measured frame time (render/quality.ts). */
  quality: QualityController | null = null;
  /** M4.4: a tier change or the fallback to top-down, for the page to say (a notice, the perf overlay). */
  onQuality?: (e: QualityEvent) => void;
  /** M4.4: the walkable quads decals drape over (World Spec v2), and the decals themselves. */
  private terrain: Quad[] = [];
  private readonly decals = new Set<THREE.Mesh>();
  private readonly draped = new Map<string, THREE.BufferGeometry>();
  /** M4.4: the walkable surface (floor, ramps, platform tops) that pointer rays pick on in 3D; never drawn */
  private pickSurface: THREE.Mesh | null = null;
  private readonly picker = new THREE.Raycaster();
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
        uPlanDim: { value: 1 }, uWorldDim: { value: 1 }, uBg: { value: col(p.background) },
      },
    });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(W * r, H * r), this.gridMat);
    plane.position.set(origin[0] + (W * r) / 2, origin[1] + (H * r) / 2, Z.grid);
    this.scene.add(plane);
    this.registerDecal(plane);

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
    // its vertices are rewritten every tick and the bounding sphere is computed once: never cull it
    // (in 3D the camera follows the robot away from where the first scan was drawn; M4.3)
    this.lidar.frustumCulled = false;
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
  setPose(pose: [number, number, number], truth: [number, number, number] = pose, tilt?: [number, number, number]) {
    this.lastPose = pose;
    this.lastTilt = tilt;
    this.three?.setPose(pose, tilt);
    this.robot.position.set(pose[0], pose[1], Z.robot);
    this.robot.rotation.z = pose[2];
    // M4.3: in 3D the marks that belong to the robot stand on its surface (a platform's top, not
    // the floor beneath it); top-down keeps the layer order. The scan is horizontal, as the model's is.
    const lift = this.is3D ? tilt?.[0] ?? 0 : 0;
    this.footprint?.position.set(pose[0], pose[1], Z.footprint + lift);
    if (this.lidar) this.lidar.position.z = Z.lidar + lift;
    if (this.truth) {
      this.truth.position.set(truth[0], truth[1], Z.truth + lift);
      this.truth.rotation.z = truth[2];
    }
  }

  /** The LiDAR, once it is known: a Case File's scans load after its first frame (D6). */
  setLidar(lidar: World['lidar']) {
    if (!this.lidar || !this.world) return;
    this.world = { ...this.world, lidar };
    const old = this.lidar.geometry;
    const lg = new THREE.BufferGeometry();
    lg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(lidar.samples * 6), 3).setUsage(THREE.DynamicDrawUsage));
    this.lidar.geometry = lg;
    old.dispose();
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
      if (this.pathLine) setLinePoints(this.pathLine, []);
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
    if (this.pathLine) setLinePoints(this.pathLine, pts);
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
    this.robot.visible = L.robot && !this.is3D;
    if (this.three) this.three.robotHolder.visible = L.robot && this.cameraMode !== 'robot_eye';
    if (this.footprint) this.footprint.visible = L.footprint;
    if (this.truth) this.truth.visible = L.truth;
  }

  /**
   * Focus (M2.2): dim the Plan lens's layers (closed set, heatmap, path,
   * frontier) and the world (occupancy, LiDAR, footprint) by these factors
   * (1 = as drawn). The robot and the truth outline are never dimmed.
   */
  setFocusDim(plan: number, world: number) {
    if (this.gridMat) { this.gridMat.uniforms.uPlanDim.value = plan; this.gridMat.uniforms.uWorldDim.value = 0.35 + 0.65 * world; }
    const fade = (o: THREE.Object3D | null, f: number, base: number) => {
      const m = (o as THREE.Mesh | null)?.material as THREE.Material | undefined;
      if (!m) return;
      m.transparent = true;
      m.opacity = base * f;
    };
    fade(this.frontier, plan, 1);
    fade(this.pathLine, plan, 1);
    fade(this.lidar, world, this.palette.lidarAlpha);
    fade(this.footprint, world, 1);
  }

  // -- camera and input -----------------------------------------------------

  /** M4.1: load the 3D arena and robot; the perspective cameras become available. */
  async enable3D(assets: Scene3DAssets, worldToMap: [number, number], targets: World['targets'] = [],
    elevation: Elevation[] = [], tier: TierChoice = 'auto') {
    if (this.three) return;
    const s = new Scene3D(this.scene, worldToMap);
    this.three = s;
    await s.load(assets);
    s.setTargets(targets ?? []);
    this.terrain = surfaces(elevation, worldToMap);
    // a phone starts a tier down; the measurement moves it from there
    const coarse = window.matchMedia?.('(pointer: coarse)').matches ?? false;
    this.quality = new QualityController(performance.now(), tier, coarse ? 'medium' : 'high');
    this.applyTier(this.quality.tier);
    // the 3D view may already be the camera (is3D turned true with `ready`): drape what exists
    this.redrape();
    if (this.world && this.terrain.length) {
      const { width: W, height: H, resolution: r, origin } = this.world;
      const cx = origin[0] + (W * r) / 2, cy = origin[1] + (H * r) / 2;
      this.pickSurface = new THREE.Mesh(drapedPlane(W * r, H * r, cx, cy, this.terrain), new THREE.MeshBasicMaterial({ side: THREE.DoubleSide }));
      this.pickSurface.position.set(cx, cy, 0);
      this.pickSurface.updateMatrixWorld(true);
    }
    s.setPose(this.lastPose, this.lastTilt);
    this.setCameraMode(this.cameraMode);
  }

  /** M4.3: the wheels' speeds (rad/s, left and right): the 3D robot's wheels turn at them. */
  setWheels(w: [number, number]) {
    this.three?.setWheelSpeeds(w);
  }

  /** M4.3: the targets where the model has them (a tick's grasp state); the carried one rides. */
  setGrasp(g: Tick['grasp']) {
    if (g?.targets) this.three?.moveTargets(g.targets, g.phase === 'carry' || g.phase === 'release' ? g.target ?? null : null);
    // the pick's joints (coco_lab.arm: URDF joint angles) on the URDF's joints
    const a = (g?.arm ?? {}) as Record<string, unknown>;
    for (const [k, joint] of ARM_JOINTS) if (typeof a[k] === 'number') this.three?.setJoint(joint, a[k] as number);
  }

  /** Top-down (orthographic, the analytic view) or a perspective camera; 3D only once loaded. */
  /**
   * Change camera. `dur` (s) is the transition (M4.5; 0 cuts: reduced motion, the fallback). 3D to 3D
   * blends; 3D to top-down blends to the overhead pose above the top-down view, then cuts to the
   * orthographic camera, where the two coincide; top-down to 3D starts from that pose.
   */
  setCameraMode(mode: CameraMode, dur = 0) {
    this.pendingTopdown = 0;
    const t = this.three;
    if (t?.ready && dur > 0) {
      const h = (this.canvas.clientHeight || 1) / this.view.scale;
      t.setOverhead(this.view.cx, this.view.cy, h);
      if (mode === 'topdown' && this.is3D) {
        t.setMode('overhead', dur);
        this.pendingTopdown = performance.now() + dur * 1000;   // the loop cuts to top-down then
        return;
      }
      if (mode !== 'topdown' && !this.is3D) t.startFromOverhead(mode, dur);
      else if (mode !== 'topdown') t.setMode(mode, dur);
    } else if (t && mode !== 'topdown') t.setMode(mode, 0);
    this.applyCamera(mode);
  }

  /** Top-down's own camera, when a transition to it is over. */
  private pendingTopdown = 0;

  private applyCamera(mode: CameraMode) {
    const was = this.is3D;
    this.cameraMode = mode;
    const on = this.is3D;
    // a person choosing 3D again after the fallback: measure afresh, from the low tier
    if (on && !was && this.quality?.fellBack) {
      this.quality = new QualityController(performance.now(), this.quality.choice, 'low');
      this.applyTier('low');
    }
    this.three?.setVisible(on);
    if (on !== was) {
      this.redrape();
      // top-down keeps M1's pixel ratio; 3D takes its tier's
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, on && this.quality ? TIER_SETTINGS[this.quality.tier].pixelRatioCap : 2));
      if (on) this.quality?.restart(performance.now());
    }
    // in 3D the glTF robot stands for the flat outline; the footprint and truth stay as floor marks
    this.robot.visible = this.layers.robot && !on;
    if (this.three) this.three.robotHolder.visible = this.layers.robot && mode !== 'robot_eye';
  }

  /** M4.4: a person's tier choice in settings ('auto' measures). */
  setTier(choice: TierChoice) {
    const e = this.quality?.setChoice(choice, performance.now());
    if (e?.kind === 'tier') { this.applyTier(e.tier); this.onQuality?.(e); }
  }

  private applyTier(tier: Tier) {
    if (!this.three) return;
    this.three.applyTier(tier, this.renderer, this.scene);
    if (this.is3D) this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, TIER_SETTINGS[tier].pixelRatioCap));
  }

  /**
   * M4.4: a computation layer drawn as a texture over the map (a PlaneGeometry centred on its mesh).
   * In 3D on a terrain it gets the draped twin of its plane (render/drape.ts): the same material and
   * texture over the floor, the ramps and the platform tops. Top-down, its own plane.
   */
  registerDecal(m: THREE.Mesh) {
    if (!(m.geometry instanceof THREE.PlaneGeometry)) return;
    m.userData.flat = m.geometry;
    this.decals.add(m);
    this.drapeOne(m);
  }

  private drapeOne(m: THREE.Mesh) {
    const flat = m.userData.flat as THREE.PlaneGeometry;
    if (!this.is3D || !this.terrain.length) { m.geometry = flat; return; }
    const { width, height } = flat.parameters;
    const key = `${width}|${height}|${m.position.x}|${m.position.y}`;
    let g = this.draped.get(key);
    if (!g) { g = drapedPlane(width, height, m.position.x, m.position.y, this.terrain); this.draped.set(key, g); }
    m.geometry = g;
  }

  private redrape() {
    for (const m of [...this.decals]) {
      let o: THREE.Object3D | null = m;
      while (o && o !== this.scene) o = o.parent;
      if (!o) { this.decals.delete(m); continue; }   // removed with its layer
      this.drapeOne(m);
    }
  }

  get is3D(): boolean {
    return this.cameraMode !== 'topdown' && !!this.three?.ready;
  }

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
    if (this.is3D) {
      // the floor point under the pointer (README §5.3: picking uses a floor ray for grids); on a terrain
      // the ray stops at the walkable surface first, so a click on a platform is a point on the platform
      const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
      if (this.pickSurface) {
        this.picker.setFromCamera(ndc, this.three!.camera);
        const hit = this.picker.intersectObject(this.pickSurface, false)[0];
        if (hit) return [hit.point.x, hit.point.y];
      }
      const hit = this.three!.toFloor(ndc.x, ndc.y);
      return hit ?? [this.lastPose[0], this.lastPose[1]];
    }
    const x = this.view.cx + (clientX - rect.left - rect.width / 2) / this.view.scale;
    const y = this.view.cy - (clientY - rect.top - rect.height / 2) / this.view.scale;
    return [x, y];
  }

  /** Map-frame metres on the floor to client (screen) pixels: the inverse of toWorld, in either camera (harnesses use it). */
  screenOf(x: number, y: number): [number, number] {
    const rect = this.canvas.getBoundingClientRect();
    const cam = this.is3D ? this.three!.camera : this.camera;
    const v = new THREE.Vector3(x, y, this.is3D ? this.surfaceZ(x, y) : 0).project(cam);
    return [rect.left + ((v.x + 1) / 2) * rect.width, rect.top + ((1 - v.y) / 2) * rect.height];
  }

  /** M4.4: the walkable surface's height under (x, y): a vertical ray onto the drawn surface; 0 off it. */
  surfaceZ(x: number, y: number): number {
    if (!this.pickSurface) return 0;
    this.picker.set(new THREE.Vector3(x, y, 50), new THREE.Vector3(0, 0, -1));
    const hit = this.picker.intersectObject(this.pickSurface, false)[0];
    return hit ? hit.point.z : 0;
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
      if (this.is3D) {
        // 3D (README §5.5): the mouse orbits with one button held; on a touch screen one finger is a tap
        // (a goal), and two fingers orbit (their midpoint moving: half each finger's share) and pinch to zoom
        if (pts.size === 1 && !this.panSuspended && e.pointerType !== 'touch') this.three!.orbitBy(e.clientX - prev[0], e.clientY - prev[1]);
        else if (pts.size === 2 && pinch0 > 0) {
          const [a, b] = [...pts.values()];
          const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
          this.three!.zoomBy(pinch0 / Math.max(1, d));
          this.three!.orbitBy((e.clientX - prev[0]) / 2, (e.clientY - prev[1]) / 2);
          pinch0 = d;
        }
        return;
      }
      if (pts.size === 1 && !this.panSuspended) {
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
      if (this.is3D) { this.three!.zoomBy(Math.exp(e.deltaY * 0.0015)); return; }
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
    const loop = (now: number) => {
      this.resize();
      this.onFrame?.();
      this.syncPlan();
      const dt = this.lastFrame ? (now - this.lastFrame) / 1000 : 1 / 60;
      this.lastFrame = now;
      if (this.pendingTopdown && now >= this.pendingTopdown) { this.pendingTopdown = 0; this.applyCamera('topdown'); }
      if (this.is3D) {
        const q = this.quality?.frame(now, dt * 1000) ?? null;
        if (q?.kind === 'tier') this.applyTier(q.tier);
        if (q) this.onQuality?.(q);
        if (q?.kind === 'fallback') this.setCameraMode('topdown');
      }
      if (this.is3D) {
        const cam = this.three!.camera;
        this.three!.update(dt, (this.canvas.clientWidth || 1) / (this.canvas.clientHeight || 1));
        // pass 1: the 3D world, tone-mapped and shadowed; pass 2: the computation layers over it,
        // unlit and exact, against its depth (README §5.3)
        this.renderer.autoClear = false;
        this.renderer.clear();
        cam.layers.set(WORLD_LAYER);
        this.renderer.toneMapping = THREE.NeutralToneMapping;
        this.renderer.render(this.scene, cam);
        // a colour background forces a clear on every render: the overlay pass must not have one
        const bg = this.scene.background;
        this.scene.background = null;
        cam.layers.set(0);
        this.renderer.toneMapping = THREE.NoToneMapping;
        this.renderer.render(this.scene, cam);
        this.scene.background = bg;
        this.renderer.autoClear = true;
      } else this.renderer.render(this.scene, this.camera);
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
