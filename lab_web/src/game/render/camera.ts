// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.4: Play's cameras. Presentation only (invariant 11): they read the pose
 * the model produced and never write anything back.
 *
 * - chase (default): behind and above COCO, spring-damped, looking a little
 *   ahead along the direction of travel, pulled in when a wall would block
 *   the view (a ray-cast against the world's render meshes);
 * - tactical: top-down, for planning (the minimap's big brother);
 * - orbit: free, two-finger orbit and pinch zoom, mouse drag and wheel.
 *
 * No shake, no bob (README §5.6). Mode changes blend over BLEND_S seconds
 * (a straight cut under reduced motion).
 */

import * as THREE from 'three';

export type CamMode = 'chase' | 'tactical' | 'orbit';
export const CAM_MODES: CamMode[] = ['chase', 'tactical', 'orbit'];
export const BLEND_S = 0.4;
/** Chase framing: distance back, height, look-ahead (m) and the spring rate (1/s). */
export const CHASE = { back: 1.55, up: 0.85, ahead: 0.7, lookUp: 0.12, k: 6, kYaw: 4.5, minBack: 0.35, nearPad: 0.12 };

const approach = (dt: number, k: number) => 1 - Math.exp(-k * dt);
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));

export class GameCamera {
  readonly camera = new THREE.PerspectiveCamera(58, 1, 0.05, 200);
  mode: CamMode = 'chase';
  reducedMotion = false;
  /** the chase rig's sprung state */
  private rig = { x: 0, y: 0, z: 0, yaw: 0, back: CHASE.back, init: false };
  /** orbit: yaw, pitch, distance about the target */
  readonly orbit = { yaw: -Math.PI / 2, pitch: 0.55, dist: 3.2 };
  /** tactical: a top-down view centred where the person dragged it (or on COCO) */
  readonly tactical = { x: 0, y: 0, h: 14, follow: true };
  private blend: { pos: THREE.Vector3; quat: THREE.Quaternion; t: number } | null = null;
  private readonly ray = new THREE.Raycaster();
  /** what the chase camera may not see through (the world's tall render meshes) */
  colliders: THREE.Object3D[] = [];
  /** the last chase pull-in distance (m), for tests */
  lastPull = 0;

  constructor() { this.camera.up.set(0, 0, 1); }

  setAspect(w: number, h: number) { this.camera.aspect = w / Math.max(1, h); this.camera.updateProjectionMatrix(); }

  setMode(mode: CamMode) {
    if (mode === this.mode) return;
    if (!this.reducedMotion) this.blend = { pos: this.camera.position.clone(), quat: this.camera.quaternion.clone(), t: 0 };
    this.mode = mode;
    if (mode === 'tactical') this.tactical.follow = true;
  }

  next(): CamMode { const m = CAM_MODES[(CAM_MODES.indexOf(this.mode) + 1) % CAM_MODES.length]; this.setMode(m); return m; }

  /** Pan the tactical view by a screen drag (m), or orbit by (dyaw, dpitch). */
  drag(dx: number, dy: number) {
    if (this.mode === 'tactical') { this.tactical.follow = false; this.tactical.x -= dx * this.tactical.h / 600; this.tactical.y += dy * this.tactical.h / 600; }
    else { this.orbit.yaw -= dx * 0.006; this.orbit.pitch = Math.min(1.45, Math.max(0.12, this.orbit.pitch + dy * 0.005)); if (this.mode === 'chase') this.setMode('orbit'); }
  }

  zoom(factor: number) {
    if (this.mode === 'tactical') this.tactical.h = Math.min(60, Math.max(4, this.tactical.h * factor));
    else { this.orbit.dist = Math.min(30, Math.max(0.8, this.orbit.dist * factor)); if (this.mode === 'chase') this.setMode('orbit'); }
  }

  /**
   * Place the camera for this frame. `pose` is where COCO is drawn (map frame), `z` its height,
   * `v` its signed speed (for the look-ahead).
   */
  update(dt: number, pose: [number, number, number], z: number, v: number) {
    const [x, y, th] = pose;
    const cam = this.camera;
    const target = new THREE.Vector3();
    if (this.mode === 'chase') {
      const r = this.rig;
      if (!r.init) { r.x = x; r.y = y; r.z = z; r.yaw = th; r.init = true; }
      // look ahead along the direction of travel (backwards when reversing)
      const dir = v < -0.02 ? th + Math.PI : th;
      const k = this.reducedMotion ? 1 : approach(dt, CHASE.k);
      r.x += (x - r.x) * k; r.y += (y - r.y) * k; r.z += (z - r.z) * k;
      r.yaw += wrap(th - r.yaw) * (this.reducedMotion ? 1 : approach(dt, CHASE.kYaw));
      target.set(r.x + CHASE.ahead * Math.cos(dir) * Math.min(1, Math.abs(v) / 0.3 + 0.35), r.y + CHASE.ahead * Math.sin(dir) * Math.min(1, Math.abs(v) / 0.3 + 0.35), r.z + CHASE.lookUp);
      const want = new THREE.Vector3(r.x - CHASE.back * Math.cos(r.yaw), r.y - CHASE.back * Math.sin(r.yaw), r.z + CHASE.up);
      // pull in: the camera may not sit behind a wall it would see COCO through
      const head = new THREE.Vector3(x, y, z + 0.25);
      const to = want.clone().sub(head);
      const len = to.length();
      let back = len;
      if (this.colliders.length) {
        this.ray.set(head, to.normalize());
        this.ray.far = len;
        const hit = this.ray.intersectObjects(this.colliders, false)[0];
        if (hit) back = Math.max(CHASE.minBack, hit.distance - CHASE.nearPad);
      }
      r.back += (back - r.back) * (back < r.back ? 1 : (this.reducedMotion ? 1 : approach(dt, 3)));
      this.lastPull = len - r.back;
      cam.position.copy(head).addScaledVector(want.clone().sub(head).normalize(), r.back);
      cam.lookAt(target);
    } else if (this.mode === 'orbit') {
      const o = this.orbit;
      target.set(x, y, z + 0.2);
      cam.position.set(x + o.dist * Math.cos(o.pitch) * Math.cos(o.yaw), y + o.dist * Math.cos(o.pitch) * Math.sin(o.yaw), z + 0.2 + o.dist * Math.sin(o.pitch));
      cam.lookAt(target);
    } else {
      const t = this.tactical;
      if (t.follow) { t.x = x; t.y = y; }
      cam.position.set(t.x, t.y - 0.001, t.h);
      cam.lookAt(t.x, t.y, 0);
    }
    if (this.blend) {
      this.blend.t += dt;
      const f = Math.min(1, this.blend.t / BLEND_S), e = f * f * (3 - 2 * f);
      const endPos = cam.position.clone(), endQ = cam.quaternion.clone();
      cam.position.lerpVectors(this.blend.pos, endPos, e);
      cam.quaternion.slerpQuaternions(this.blend.quat, endQ, e);
      if (f >= 1) this.blend = null;
    }
  }
}
