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
  private rig = { x: 0, y: 0, z: 0, yaw: 0, back: CHASE.back, elev: Math.atan2(CHASE.up - 0.25, CHASE.back), init: false };
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

  /** How far a boom from `from` along `dir` may reach (at most `len`), keeping NEAR_PAD from the face it would hit. */
  private boom(from: THREE.Vector3, dir: THREE.Vector3, len: number): number {
    if (!this.colliders.length) return len;
    this.ray.set(from, dir);
    this.ray.far = len + CHASE.nearPad * 4;
    const hit = this.ray.intersectObjects(this.colliders, false)[0];
    if (!hit) return len;
    const cos = Math.max(0.2, Math.abs(dir.dot(hit.face?.normal ?? new THREE.Vector3(0, 0, 1))));
    return Math.max(0.05, Math.min(len, hit.distance - CHASE.nearPad / cos));
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
      const look = v < -0.02 ? th + Math.PI : th;
      const k = this.reducedMotion ? 1 : approach(dt, CHASE.k);
      r.x += (x - r.x) * k; r.y += (y - r.y) * k; r.z += (z - r.z) * k;
      r.yaw += wrap(th - r.yaw) * (this.reducedMotion ? 1 : approach(dt, CHASE.kYaw));
      target.set(r.x + CHASE.ahead * Math.cos(look) * Math.min(1, Math.abs(v) / 0.3 + 0.35), r.y + CHASE.ahead * Math.sin(look) * Math.min(1, Math.abs(v) / 0.3 + 0.35), r.z + CHASE.lookUp);
      // the boom: from COCO's head, back along its heading and up. If a wall would come between,
      // shorten it (keeping PAD from the wall's face, not only along the ray); if even the
      // shortest boom has no room, swing it up toward a top-down view (never into the wall).
      const head = new THREE.Vector3(x, y, z + 0.25);
      const len = Math.hypot(CHASE.back, CHASE.up - 0.25);
      const base = Math.atan2(CHASE.up - 0.25, CHASE.back);
      let best: { dir: THREE.Vector3; back: number } | null = null;
      for (const elev of [base, 0.85, 1.05, 1.25, 1.45, 1.55]) {
        if (elev < base) continue;
        const dir = new THREE.Vector3(-Math.cos(elev) * Math.cos(r.yaw), -Math.cos(elev) * Math.sin(r.yaw), Math.sin(elev));
        let back = len;
        if (this.colliders.length) {
          this.ray.set(head, dir);
          this.ray.far = len + CHASE.nearPad * 4;
          const hit = this.ray.intersectObjects(this.colliders, false)[0];
          if (hit) {
            const n = hit.face?.normal ?? new THREE.Vector3(0, 0, 1);
            const cos = Math.max(0.2, Math.abs(dir.dot(n)));
            back = Math.min(len, hit.distance - CHASE.nearPad / cos);
          }
        }
        if (!best || back > best.back) best = { dir, back };
        if (back >= CHASE.minBack) { best = { dir, back }; break; }
      }
      // the swing: up at once (to stay clear), back down smoothly; clearance re-checked on the drawn direction
      const want = Math.asin(Math.min(1, best!.dir.z));
      r.elev = want >= r.elev || this.reducedMotion ? want : r.elev + (want - r.elev) * approach(dt, 2.5);
      const dir = new THREE.Vector3(-Math.cos(r.elev) * Math.cos(r.yaw), -Math.cos(r.elev) * Math.sin(r.yaw), Math.sin(r.elev));
      let b = len;
      if (this.colliders.length) {
        this.ray.set(head, dir);
        this.ray.far = len + CHASE.nearPad * 4;
        const hit = this.ray.intersectObjects(this.colliders, false)[0];
        if (hit) b = Math.min(len, hit.distance - CHASE.nearPad / Math.max(0.2, Math.abs(dir.dot(hit.face?.normal ?? new THREE.Vector3(0, 0, 1)))));
      }
      b = Math.max(0.05, b);
      r.back += (b - r.back) * (b < r.back ? 1 : (this.reducedMotion ? 1 : approach(dt, 3)));
      r.back = Math.min(r.back, b);
      this.lastPull = len - r.back;
      cam.position.copy(head).addScaledVector(dir, r.back);
      cam.lookAt(target);
    } else if (this.mode === 'orbit') {
      // the orbit boom has the chase boom's rule: shortened before a wall, never through it
      const o = this.orbit;
      target.set(x, y, z + 0.2);
      const dir = new THREE.Vector3(Math.cos(o.pitch) * Math.cos(o.yaw), Math.cos(o.pitch) * Math.sin(o.yaw), Math.sin(o.pitch));
      cam.position.copy(target).addScaledVector(dir, this.boom(target, dir, o.dist));
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
