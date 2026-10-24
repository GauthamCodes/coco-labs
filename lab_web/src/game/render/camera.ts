// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.4: Play's cameras. Presentation only (invariant 11): they read the pose
 * the model produced and never write anything back.
 *
 * - chase (default): behind and above COCO on a boom of fixed length, spring-damped.
 *   G1.12 (Gautham, 2026-10-22): COCO is framed in the upper-middle third of the
 *   screen (its centre at CHASE.screenY, clear of the bottom HUD), the boom never
 *   comes closer than CHASE.minDist nor lower than CHASE.minHeight, and when a wall
 *   would block the view the boom swings UP (the camera tilting down) instead of
 *   moving in -- ray-cast against the world's render meshes; only when no elevation
 *   has room at minDist does it shorten (never through a wall);
 * - tactical: top-down, for planning (the minimap's big brother);
 * - orbit: free, two-finger orbit and pinch zoom, mouse drag and wheel;
 * - rviz (G2.2, SIM view only; not in CAM's cycle): RViz's Orbit view -- a focal point on
 *   base_link (plus a pan), drag to orbit, wheel or pinch to zoom, right-drag, shift-drag or two
 *   fingers to pan; no wall pulls it in (RViz's camera sees through geometry).
 *
 * No shake, no bob (README §5.6). Mode changes blend over BLEND_S seconds
 * (a straight cut under reduced motion).
 */

import * as THREE from 'three';

export type CamMode = 'chase' | 'tactical' | 'orbit' | 'rviz';
export const CAM_MODES: CamMode[] = ['chase', 'tactical', 'orbit'];
export const BLEND_S = 0.4;
/**
 * Chase framing (G1.12): the boom's length and its least length (m), its resting elevation
 * (rad), the elevations it may swing up to, the camera's least height above the floor (m),
 * where COCO's centre sits on screen (NDC y: +1 top, -1 bottom; +0.2 is 40 % down), COCO's
 * centre and head heights (m), its half-width for the side rays (m), the springs (1/s) and the gap
 * kept from a wall's face (m).
 */
export const CHASE = {
  dist: 2.1, minDist: 1.7, elev: 0.55, elevs: [0.55, 0.7, 0.87, 1.05, 1.22, 1.4, 1.53], minHeight: 1.2,
  screenY: 0.2, bodyZ: 0.2, headZ: 0.25, shoulder: 0.2, k: 6, kYaw: 4.5, nearPad: 0.12,
};

const approach = (dt: number, k: number) => 1 - Math.exp(-k * dt);
const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));

export class GameCamera {
  readonly camera = new THREE.PerspectiveCamera(58, 1, 0.05, 200);
  mode: CamMode = 'chase';
  reducedMotion = false;
  /** the chase rig's sprung state */
  private rig = { x: 0, y: 0, z: 0, yaw: 0, back: CHASE.dist, elev: CHASE.elev, init: false };
  /** orbit: yaw, pitch, distance about the target */
  readonly orbit = { yaw: -Math.PI / 2, pitch: 0.55, dist: 3.2 };
  /** tactical: a top-down view centred where the person dragged it (or on COCO) */
  readonly tactical = { x: 0, y: 0, h: 14, follow: true };
  /** G2.2 SIM: RViz's Orbit view about base_link (+ a pan, m), its yaw, pitch and distance */
  readonly rviz = { yaw: -2.2, pitch: 0.75, dist: 7, px: 0, py: 0 };
  private blend: { pos: THREE.Vector3; quat: THREE.Quaternion; t: number } | null = null;
  private readonly ray = new THREE.Raycaster();
  /** what the chase camera may not see through (the world's tall render meshes) */
  colliders: THREE.Object3D[] = [];
  /** the last chase pull-in distance (m) and boom elevation (rad), for tests */
  lastPull = 0;
  lastElev: number = CHASE.elev;

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
    else if (this.mode === 'rviz') { this.rviz.yaw -= dx * 0.006; this.rviz.pitch = Math.min(1.55, Math.max(0.05, this.rviz.pitch + dy * 0.005)); }
    else { this.orbit.yaw -= dx * 0.006; this.orbit.pitch = Math.min(1.45, Math.max(0.12, this.orbit.pitch + dy * 0.005)); if (this.mode === 'chase') this.setMode('orbit'); }
  }

  zoom(factor: number) {
    if (this.mode === 'tactical') this.tactical.h = Math.min(60, Math.max(4, this.tactical.h * factor));
    else if (this.mode === 'rviz') this.rviz.dist = Math.min(80, Math.max(0.4, this.rviz.dist * factor));
    else { this.orbit.dist = Math.min(30, Math.max(0.8, this.orbit.dist * factor)); if (this.mode === 'chase') this.setMode('orbit'); }
  }

  /** G2.2 SIM: drag the scene (px): the focal point moves against the drag, on the floor, scaled with distance. */
  pan(dx: number, dy: number) {
    const r = this.rviz, k = r.dist / 700;
    const rx = -Math.sin(r.yaw), ry = Math.cos(r.yaw);      // the screen's right, on the floor (away x up)
    const fx = -Math.cos(r.yaw), fy = -Math.sin(r.yaw);     // the screen's up, on the floor (away from the camera)
    r.px -= (dx * rx - dy * fx) * k;
    r.py -= (dx * ry - dy * fy) * k;
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

  /** How far a boom from `from` along `dir` reaches before a wall (at most `len`), keeping nearPad from its face. */
  private clear(from: THREE.Vector3, dir: THREE.Vector3, len: number): number {
    if (!this.colliders.length) return len;
    this.ray.set(from, dir);
    this.ray.far = len + CHASE.nearPad * 4;
    const hit = this.ray.intersectObjects(this.colliders, false)[0];
    if (!hit) return len;
    const cos = Math.max(0.2, Math.abs(dir.dot(hit.face?.normal ?? new THREE.Vector3(0, 0, 1))));
    return Math.min(len, hit.distance - CHASE.nearPad / cos);
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
      const k = this.reducedMotion ? 1 : approach(dt, CHASE.k);
      r.x += (x - r.x) * k; r.y += (y - r.y) * k; r.z += (z - r.z) * k;
      r.yaw += wrap(th - r.yaw) * (this.reducedMotion ? 1 : approach(dt, CHASE.kYaw));
      void v;
      // the boom, from COCO's head back along its heading and up: at full length at the lowest
      // elevation with room (rising, never moving in); at minDist if none has full room; shorter
      // only if no elevation has room even for that (never through a wall). The least height
      // above the floor is part of the rule.
      const head = new THREE.Vector3(x, y, z + CHASE.headZ);
      const dirAt = (e: number) => new THREE.Vector3(-Math.cos(e) * Math.cos(r.yaw), -Math.cos(e) * Math.sin(r.yaw), Math.sin(e));
      const lowest = Math.asin(Math.min(1, Math.max(0, (CHASE.minHeight - z - CHASE.headZ) / CHASE.dist)));
      // room for the boom: clear from COCO's centre line AND both shoulders, so a wall edge
      // beside COCO cannot hide half of it (G1.12)
      const side = new THREE.Vector3(-Math.sin(r.yaw), Math.cos(r.yaw), 0).multiplyScalar(CHASE.shoulder);
      const heads = [head, head.clone().add(side), head.clone().sub(side)];
      const room = (e: number) => Math.min(...heads.map((h) => this.clear(h, dirAt(e), CHASE.dist)));
      const elevs = CHASE.elevs.filter((e) => e >= lowest - 1e-9);
      if (!elevs.length || elevs[0] > lowest + 1e-9) elevs.unshift(Math.max(lowest, CHASE.elev));
      let pick: { e: number; len: number } | null = null;
      const rooms = elevs.map((e) => ({ e, len: room(e) }));
      pick = rooms.find((q) => q.len >= CHASE.dist - 1e-6) ?? null;
      if (!pick) { const q = rooms.find((q) => q.len >= CHASE.minDist); if (q) pick = { e: q.e, len: Math.min(CHASE.dist, q.len) }; }
      if (!pick) pick = rooms.reduce((a, b) => (b.len > a.len ? b : a));
      // the swing: up at once (to stay clear), back down smoothly; room re-checked on the drawn direction
      r.elev = pick.e >= r.elev || this.reducedMotion ? pick.e : r.elev + (pick.e - r.elev) * approach(dt, 2.5);
      const dir = dirAt(r.elev);
      const b = Math.max(0.05, Math.min(CHASE.dist, ...heads.map((h) => this.clear(h, dir, CHASE.dist))));
      r.back += (b - r.back) * (b < r.back ? 1 : (this.reducedMotion ? 1 : approach(dt, 3)));
      r.back = Math.min(r.back, b);
      this.lastPull = CHASE.dist - r.back;
      this.lastElev = r.elev;
      cam.position.copy(head).addScaledVector(dir, r.back);
      // aim so COCO's centre lands at screenY: the camera looks down by the angle to COCO
      // plus the angle that puts it that far above the screen's centre
      const body = new THREE.Vector3(r.x, r.y, r.z + CHASE.bodyZ);
      const dx = body.x - cam.position.x, dy = body.y - cam.position.y;
      const below = Math.atan2(cam.position.z - body.z, Math.hypot(dx, dy));
      // (along the rig's heading, and never past straight down: with the boom near vertical
      // COCO then sits a little above the centre rather than the view flipping over)
      const tilt = Math.min(Math.PI / 2 - 0.02, below + Math.atan(CHASE.screenY * Math.tan((cam.fov * Math.PI) / 360)));
      const yaw = Math.hypot(dx, dy) > 0.3 ? Math.atan2(dy, dx) : r.yaw;
      target.set(cam.position.x + Math.cos(tilt) * Math.cos(yaw), cam.position.y + Math.cos(tilt) * Math.sin(yaw), cam.position.z - Math.sin(tilt));
      cam.lookAt(target);
    } else if (this.mode === 'orbit') {
      // the orbit boom has the chase boom's rule: shortened before a wall, never through it
      const o = this.orbit;
      target.set(x, y, z + 0.2);
      const dir = new THREE.Vector3(Math.cos(o.pitch) * Math.cos(o.yaw), Math.cos(o.pitch) * Math.sin(o.yaw), Math.sin(o.pitch));
      cam.position.copy(target).addScaledVector(dir, this.boom(target, dir, o.dist));
      cam.lookAt(target);
    } else if (this.mode === 'rviz') {
      const o = this.rviz;
      target.set(x + o.px, y + o.py, z);
      const dir = new THREE.Vector3(Math.cos(o.pitch) * Math.cos(o.yaw), Math.cos(o.pitch) * Math.sin(o.yaw), Math.sin(o.pitch));
      cam.position.copy(target).addScaledVector(dir, o.dist);
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
