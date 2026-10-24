// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.2: SIM view -- the same moment drawn the way RViz draws a ROS 2 robot, over the world
 * drawn flat and see-through the way Gazebo's transparent view does.
 *
 * Every display draws something the browser model computed (MODEL; the ROS-shaped messages of
 * src/ros/shapes.ts, built from what coco_lab.ros_shapes computed in the worker): the frames of
 * /tf and /tf_static, /scan, /map, the model's costmap, /plan, the command, the footprint, the
 * goal. Nothing here is RViz or ROS 2. Presentation only (README §3 invariant 11): it is handed
 * the model's state and never writes any. Built once with the world, its materials compiled
 * behind the loading screen with everything else, so switching views costs no shader compile.
 */

import * as THREE from 'three';
import type { Displays } from '../../ros/displays';
import { framePose, type RosInfo, type TFMessage } from '../../ros/shapes';
import type { WorldLook } from '../world/describe';
import { CostLayers, mapPlane } from './rviz_costmap';

/** RViz's default background (48, 48, 48) */
export const SIM_BACKGROUND = 0x303030;
const AXIS = [0xff2020, 0x20ff20, 0x2060ff];

/** A flat ribbon along a polyline, just above the floor (a line a phone can see at any zoom). */
export function ribbon(mesh: THREE.Mesh, pts: [number, number][], width: number, z: number) {
  mesh.geometry.dispose();
  if (pts.length < 2) { mesh.geometry = new THREE.BufferGeometry(); return; }
  const pos: number[] = [];
  for (let k = 0; k + 1 < pts.length; k++) {
    const [a, b] = [pts[k], pts[k + 1]];
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1, nx = (-dy / l) * width / 2, ny = (dx / l) * width / 2;
    pos.push(a[0] + nx, a[1] + ny, z, a[0] - nx, a[1] - ny, z, b[0] + nx, b[1] + ny, z, b[0] + nx, b[1] + ny, z, a[0] - nx, a[1] - ny, z, b[0] - nx, b[1] - ny, z);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  mesh.geometry = g;
}

/** RGB axes (x red, y green, z blue) of length 1, scaled by the caller: one draw call. */
export function axesMesh(width = 0.04): THREE.Mesh {
  const pos: number[] = [], col: number[] = [];
  const box = (ax: number) => {
    const g = ax === 0 ? new THREE.BoxGeometry(1, width, width).translate(0.5, 0, 0)
      : ax === 1 ? new THREE.BoxGeometry(width, 1, width).translate(0, 0.5, 0) : new THREE.BoxGeometry(width, width, 1).translate(0, 0, 0.5);
    const p = g.toNonIndexed().getAttribute('position');
    const c = new THREE.Color(AXIS[ax]);
    for (let k = 0; k < p.count; k++) { pos.push(p.getX(k), p.getY(k), p.getZ(k)); col.push(c.r, c.g, c.b); }
    g.dispose();
  };
  box(0); box(1); box(2);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  return new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, toneMapped: false, depthTest: false, transparent: true }));
}

/** A frame's name, drawn at a constant size on screen (as RViz's TF display labels frames). */
function label(text: string, colour = '#ffffff'): THREE.Sprite {
  const c = document.createElement('canvas');
  const px = 28, g = c.getContext('2d')!;
  g.font = `600 ${px}px ui-monospace, monospace`;
  c.width = Math.ceil(g.measureText(text).width) + 12; c.height = px + 12;
  g.font = `600 ${px}px ui-monospace, monospace`;
  g.fillStyle = 'rgba(0,0,0,0.45)'; g.fillRect(0, 0, c.width, c.height);
  g.fillStyle = colour; g.textBaseline = 'middle'; g.fillText(text, 6, c.height / 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, sizeAttenuation: false, depthTest: false, transparent: true, toneMapped: false }));
  const h = 0.026;
  s.scale.set(h * c.width / c.height, h, 1);
  s.center.set(0, 0);
  s.renderOrder = 20;
  return s;
}

export interface SimFrame {
  pose: [number, number, number]; z: number; v: number; w: number;
  ranges: Float32Array | null; tf: TFMessage | null; plan: [number, number][]; goal: [number, number] | null;
}

export class SimView {
  readonly group = new THREE.Group();
  private readonly world = new THREE.Group();
  private readonly gridMinor: THREE.LineSegments;
  private readonly gridMajor: THREE.LineSegments;
  private readonly origin: THREE.Mesh;
  private map: THREE.Mesh | null = null;
  costs: CostLayers | null = null;
  private readonly scan: THREE.Points;
  private readonly scanPos: Float32Array;
  private readonly scanCol: Float32Array;
  private readonly plan: THREE.Mesh;
  private readonly local: THREE.Mesh;
  private readonly footprint: THREE.LineLoop;
  private readonly goal: THREE.Group;
  private readonly frames = new Map<string, { axes: THREE.Mesh; text: THREE.Sprite }>();
  private info: RosInfo | null = null;
  private displays: Displays | null = null;
  /** the arm's URDF link frames in COCO's drawn model (link:<name> nodes), posed by its joint states */
  arm: { name: string; node: THREE.Object3D }[] = [];
  private disposables: { dispose(): void }[] = [];

  constructor(look: WorldLook, readonly radius: number) {
    this.group.name = 'g2-sim';
    this.group.visible = false;
    // the world, flat and see-through (Gazebo's transparent view): every solid but the roof
    const byShape = new Map<string, WorldLook['parts']>();
    for (const p of look.parts) {
      if (p.mat === 'ceiling' || p.mat === 'fixture' || p.cls === 'light') continue;
      if (!byShape.has(p.shape)) byShape.set(p.shape, []);
      byShape.get(p.shape)!.push(p);
    }
    const geom: Record<string, () => THREE.BufferGeometry> = {
      box: () => new THREE.BoxGeometry(1, 1, 1).translate(0, 0, 0.5),
      cyl: () => new THREE.CylinderGeometry(0.5, 0.5, 1, 12).rotateX(Math.PI / 2).translate(0, 0, 0.5),
      wedge: () => new THREE.BoxGeometry(1, 1, 1).translate(0, 0, 0.5),
    };
    const mat = new THREE.MeshLambertMaterial({ color: 0xb8bec8, transparent: true, opacity: 0.32, flatShading: true, depthWrite: false });
    this.disposables.push(mat);
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), pv = new THREE.Vector3(), sv = new THREE.Vector3(), zAx = new THREE.Vector3(0, 0, 1);
    for (const [shape, parts] of byShape) {
      const g = (geom[shape] ?? geom.box)();
      const mesh = new THREE.InstancedMesh(g, mat, parts.length);
      parts.forEach((p, k) => {
        pv.set((p.min[0] + p.max[0]) / 2, (p.min[1] + p.max[1]) / 2, p.min[2]);
        sv.set(p.max[0] - p.min[0], p.max[1] - p.min[1], Math.max(1e-4, p.max[2] - p.min[2]));
        q.setFromAxisAngle(zAx, p.shape === 'wedge' ? p.yaw ?? 0 : 0);
        mesh.setMatrixAt(k, m4.compose(pv, q, sv));
      });
      mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingSphere();
      mesh.renderOrder = 1;
      this.world.add(mesh);
      this.disposables.push(g);
    }
    this.group.add(this.world);
    // the Grid display: 1 m major and 0.1 m minor lines over the floor, map frame
    const f = look.floor;
    const lines = (step: number) => {
      const pos: number[] = [];
      const x0 = Math.floor(f.minX / step) * step, x1 = Math.ceil(f.maxX / step) * step;
      const y0 = Math.floor(f.minY / step) * step, y1 = Math.ceil(f.maxY / step) * step;
      for (let x = x0; x <= x1 + 1e-9; x += step) pos.push(x, y0, 0.001, x, y1, 0.001);
      for (let y = y0; y <= y1 + 1e-9; y += step) pos.push(x0, y, 0.001, x1, y, 0.001);
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      this.disposables.push(g);
      return g;
    };
    this.gridMinor = new THREE.LineSegments(lines(0.1), new THREE.LineBasicMaterial({ color: 0xa0a0a4, transparent: true, opacity: 0.12, depthWrite: false, toneMapped: false }));
    this.gridMajor = new THREE.LineSegments(lines(1), new THREE.LineBasicMaterial({ color: 0xa0a0a4, transparent: true, opacity: 0.5, depthWrite: false, toneMapped: false }));
    this.origin = axesMesh(0.03);
    this.origin.scale.setScalar(1);
    this.group.add(this.gridMinor, this.gridMajor, this.origin);
    // the LaserScan display: points coloured by range
    this.scanPos = new Float32Array(1024 * 3);
    this.scanCol = new Float32Array(1024 * 3);
    const sg = new THREE.BufferGeometry();
    sg.setAttribute('position', new THREE.BufferAttribute(this.scanPos, 3));
    sg.setAttribute('color', new THREE.BufferAttribute(this.scanCol, 3));
    sg.setDrawRange(0, 0);
    this.scan = new THREE.Points(sg, new THREE.PointsMaterial({ size: 0.05, vertexColors: true, sizeAttenuation: true, transparent: true, toneMapped: false, depthWrite: false }));
    this.scan.frustumCulled = false;
    this.scan.renderOrder = 6;
    // Path displays, footprint, goal arrow
    this.plan = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: 0x19ff00, toneMapped: false, transparent: true, depthWrite: false }));
    this.local = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: 0xff4040, toneMapped: false, transparent: true, depthWrite: false }));
    for (const m of [this.plan, this.local]) { m.renderOrder = 7; m.frustumCulled = false; }
    const circle: number[] = [];
    for (let k = 0; k < 48; k++) { const a = (k / 48) * Math.PI * 2; circle.push(radius * Math.cos(a), radius * Math.sin(a), 0.015); }
    const fg = new THREE.BufferGeometry(); fg.setAttribute('position', new THREE.Float32BufferAttribute(circle, 3));
    this.footprint = new THREE.LineLoop(fg, new THREE.LineBasicMaterial({ color: 0x00ff00, toneMapped: false }));
    this.goal = new THREE.Group();
    const arrowMat = new THREE.MeshBasicMaterial({ color: 0xff1900, toneMapped: false });
    const shaft = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.06, 0.06).translate(0.3, 0, 0.05), arrowMat);
    const head = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.25, 12).rotateZ(-Math.PI / 2).translate(0.72, 0, 0.05), arrowMat);
    this.goal.add(shaft, head);
    this.goal.visible = false;
    this.group.add(this.scan, this.plan, this.local, this.footprint, this.goal);
  }

  /** The ROS-shaped model's constants (frames, scan) and the world's map (the Map display). */
  setInfo(info: RosInfo, map: { width: number; height: number; resolution: number; origin: [number, number] }, occupancy: ArrayLike<number>) {
    this.info = info;
    if (!this.map) { this.map = mapPlane(map, occupancy); this.group.add(this.map); }
    if (!this.costs) { this.costs = new CostLayers(map.width, map.height, map.resolution, map.origin); this.group.add(this.costs.global, this.costs.local); }
    for (const f of [...info.frames]) this.frame(f, '#ffffff');
    for (const a of this.arm) this.frame(a.name, '#ffd27a');
    if (this.displays) this.apply(this.displays);
  }

  /** The arm's link frames were found in COCO's model: give them their TF axes and labels. */
  armReady() {
    if (!this.info) return;   // setInfo adds them
    for (const a of this.arm) this.frame(a.name, '#ffd27a');
    if (this.displays) this.apply(this.displays);
  }

  private frame(name: string, colour: string) {
    if (this.frames.has(name)) return;
    const axes = axesMesh(0.035);
    axes.renderOrder = 19;
    const text = label(name, colour);
    this.frames.set(name, { axes, text });
    this.group.add(axes, text);
  }

  /** Displays on and off, and their options (src/ros/displays.ts). */
  apply(d: Displays) {
    this.displays = d;
    this.gridMinor.visible = this.gridMajor.visible = this.origin.visible = d.grid.on;
    for (const g of [this.gridMinor, this.gridMajor]) (g.material as THREE.LineBasicMaterial).color.set(d.grid.color ?? '#a0a0a4');
    (this.gridMajor.material as THREE.LineBasicMaterial).opacity = d.grid.alpha ?? 0.5;
    (this.gridMinor.material as THREE.LineBasicMaterial).opacity = (d.grid.alpha ?? 0.5) * 0.24;
    this.scan.visible = d.scan.on;
    const sm = this.scan.material as THREE.PointsMaterial;
    sm.size = d.scan.size ?? 0.05; sm.opacity = d.scan.alpha ?? 1;
    if (this.map) { this.map.visible = d.map.on; (this.map.material as THREE.MeshBasicMaterial).opacity = d.map.alpha ?? 0.7; }
    if (this.costs) { this.costs.global.visible = d.global_costmap.on; this.costs.local.visible = d.local_costmap.on; this.costs.alpha(d.global_costmap.alpha ?? 0.5, d.local_costmap.alpha ?? 0.8); }
    this.plan.visible = d.global_plan.on; (this.plan.material as THREE.MeshBasicMaterial).color.set(d.global_plan.color ?? '#19ff00');
    this.local.visible = d.local_plan.on; (this.local.material as THREE.MeshBasicMaterial).color.set(d.local_plan.color ?? '#ff4040');
    this.footprint.visible = d.footprint.on; (this.footprint.material as THREE.LineBasicMaterial).color.set(d.footprint.color ?? '#00ff00');
    for (const m of this.goal.children) ((m as THREE.Mesh).material as THREE.MeshBasicMaterial).color.set(d.goal.color ?? '#ff1900');
    for (const { axes, text } of this.frames.values()) { axes.visible = text.visible = d.tf.on; axes.scale.setScalar(d.tf.size ?? 0.3); }
  }

  /** The model's scan, plan, frames, command and goal at this tick. */
  update(s: SimFrame) {
    const d = this.displays, info = this.info;
    // LaserScan: each beam's end in the map frame, from lidar_link's pose (/tf + /tf_static)
    if (s.ranges && info && s.tf && (!d || d.scan.on)) {
      const lp = framePose(info.scan.frame_id, s.tf, info.tf_static);
      if (lp) {
        const [lx, ly, lth] = lp;
        const lz = (info.tf_static.transforms.reduce((z, t) => z + t.transform.translation.z, 0)) + s.z;
        const n = Math.min(s.ranges.length, 1024), inc = n > 1 ? (info.scan.angle_max - info.scan.angle_min) / (n - 1) : 0;
        let k = 0;
        const c = new THREE.Color();
        for (let i = 0; i < n; i++) {
          const r = s.ranges[i];
          if (!(r >= info.scan.range_min && r <= info.scan.range_max)) continue;   // RViz drops out-of-range beams
          const a = lth + info.scan.angle_min + i * inc;
          this.scanPos[k * 3] = lx + r * Math.cos(a); this.scanPos[k * 3 + 1] = ly + r * Math.sin(a); this.scanPos[k * 3 + 2] = lz;
          c.setHSL(0.72 * Math.min(1, r / Math.min(info.scan.range_max, 8)), 1, 0.5);   // near red, far blue
          this.scanCol[k * 3] = c.r; this.scanCol[k * 3 + 1] = c.g; this.scanCol[k * 3 + 2] = c.b;
          k++;
        }
        const g = this.scan.geometry;
        g.setDrawRange(0, k);
        (g.getAttribute('position') as THREE.BufferAttribute).needsUpdate = true;
        (g.getAttribute('color') as THREE.BufferAttribute).needsUpdate = true;
      }
    }
    // Path (global): the plan from where COCO is; Path (local): the command held for 1 s
    ribbon(this.plan, s.plan.length ? [[s.pose[0], s.pose[1]], ...s.plan] : [], 0.035, 0.02);
    const arc: [number, number][] = [];
    if (Math.abs(s.v) > 1e-3 || Math.abs(s.w) > 1e-3) {
      let [x, y, th] = s.pose;
      arc.push([x, y]);
      for (let k = 0; k < 10; k++) { x += s.v * 0.1 * Math.cos(th + s.w * 0.05); y += s.v * 0.1 * Math.sin(th + s.w * 0.05); th += s.w * 0.1; arc.push([x, y]); }
    }
    ribbon(this.local, arc, 0.035, 0.024);
    this.goal.visible = !!s.goal && (!d || d.goal.on);
    if (s.goal) {
      const last = s.plan.length >= 2 ? s.plan.slice(-2) : null;
      this.goal.position.set(s.goal[0], s.goal[1], 0);
      this.goal.rotation.z = last ? Math.atan2(last[1][1] - last[0][1], last[1][0] - last[0][0]) : 0;
    }
    // TF: the frames above the robot (map, odom) from this tick's /tf; base_footprint and the
    // frames on it are placed every drawn frame (follow), on COCO as drawn
    if (info && s.tf) {
      for (const name of ['map', 'odom']) {
        const f = this.frames.get(name), p = framePose(name, s.tf, info.tf_static);
        if (!f || !p) continue;
        f.axes.position.set(p[0], p[1], 0); f.axes.rotation.set(0, 0, p[2]);
        f.text.position.set(p[0], p[1], 0.02);
      }
    }
  }

  /**
   * Every drawn frame: base_footprint is COCO as drawn (between two ticks it moves smoothly,
   * as the robot does on screen), base_link and lidar_link on it by /tf_static; the arm's link
   * frames from COCO's model; the footprint and the local costmap's window follow it too.
   */
  follow(pose: [number, number, number], z: number) {
    this.footprint.position.set(pose[0], pose[1], z);
    this.costs?.follow(pose[0], pose[1]);
    if (this.info) {
      let [x, y, th] = pose, h = z, at = 'base_footprint', row = 0;
      // the frames on COCO sit within 0.2 m of each other: their names are stacked above them
      const put = (name: string) => {
        const f = this.frames.get(name);
        if (!f) return;
        f.axes.position.set(x, y, h); f.axes.rotation.set(0, 0, th);
        f.text.position.set(pose[0], pose[1], z + 0.45 + 0.17 * row++);
      };
      put(at);
      for (;;) {
        const t = this.info.tf_static.transforms.find((q) => q.header.frame_id === at);
        if (!t) break;
        const p = t.transform.translation, c = Math.cos(th), sn = Math.sin(th);
        x += c * p.x - sn * p.y; y += sn * p.x + c * p.y; h += p.z;
        th += 2 * Math.atan2(t.transform.rotation.z, t.transform.rotation.w);
        at = t.child_frame_id;
        put(at);
      }
    }
    const v = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
    for (const a of this.arm) {
      const f = this.frames.get(a.name);
      if (!f) continue;
      a.node.matrixWorld.decompose(v, q, s);
      f.axes.position.copy(v); f.axes.quaternion.copy(q);
      f.text.position.copy(v);
    }
  }

  dispose() {
    this.costs?.dispose();
    for (const d of this.disposables) d.dispose();
    this.group.traverse((o) => { const m = o as THREE.Mesh; if (m.geometry) m.geometry.dispose(); const mt = m.material as THREE.Material | undefined; if (mt?.dispose) mt.dispose(); });
  }
}
