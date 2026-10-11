// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The 3D Arena (M4.1, feasibility; README §5.3): COCO's Gazebo arena and the
 * robot as glTF, a perspective camera, and a follow rig.
 *
 * Presentation only (README §3 invariant 11): it reads poses the model or a
 * recording produced and never writes anything back; nothing here is in the
 * per-tick state hash. Frames: the scene is the renderer's map frame, z up.
 * The arena asset is in Gazebo's world frame (lab_web/tools/assets/
 * convert_world.py), so it is placed at the World Spec's `world_to_map`. Both
 * assets are glTF y-up with one root rotation from ROS z-up; that root is
 * turned back here.
 *
 * The computation layers keep drawing where they always did, on the floor
 * plane (z = 0) with their unlit materials: in 3D they are floor decals.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

export type CameraMode = 'topdown' | 'follow' | 'orbit' | 'robot_eye';
export const CAMERA_MODES: CameraMode[] = ['follow', 'orbit', 'robot_eye', 'topdown'];

/** COCO's camera (URDF camera_link) in base_footprint, and its vertical field of view (hfov 1.25 rad at 4:3). */
const CAMERA_LINK: [number, number, number] = [0.125, 0, 0.0135 + 0.055];
const CAMERA_VFOV_DEG = (2 * Math.atan(Math.tan(1.25 / 2) * 0.75) * 180) / Math.PI;
/** The arena's centre in the WORLD frame and its half-extent (convert_world.py's footprints: x -8..16, y -9..9). */
const ARENA_CENTRE_WORLD: [number, number] = [4, 0];

export interface Scene3DAssets { arena: string; robot: string }

interface Joint { q: THREE.Object3D; axis: THREE.Vector3 }

/** Exponential approach: the fraction of the remaining distance covered in dt at rate k (1/s). */
const approach = (dt: number, k: number) => 1 - Math.exp(-k * dt);

export class Scene3D {
  readonly camera = new THREE.PerspectiveCamera(50, 1, 0.05, 300);
  readonly root = new THREE.Group();
  readonly robotHolder = new THREE.Group();
  readonly joints = new Map<string, Joint>();
  ready = false;
  /** Triangles of the loaded assets (what the frame rate is measured against). */
  triangles = 0;
  private pose: [number, number, number] = [0, 0, 0];
  /** The camera rig's own state: sprung toward the robot (feel, not physics). */
  private rig = { x: 0, y: 0, yaw: 0, init: false };
  private orbit = { yaw: 0, pitch: 0.38, dist: 2.6 };
  private wide = { yaw: -2.2, pitch: 0.72, dist: 24 };
  mode: Exclude<CameraMode, 'topdown'> = 'follow';
  private readonly floor = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  private readonly ray = new THREE.Raycaster();
  private readonly sun: THREE.DirectionalLight;

  constructor(scene: THREE.Scene, readonly worldToMap: [number, number]) {
    this.camera.up.set(0, 0, 1);
    this.root.visible = false;
    scene.add(this.root);
    const hemi = new THREE.HemisphereLight(0xf2f4f7, 0x8a8478, 1.6);
    hemi.position.set(0, 0, 1);
    this.sun = new THREE.DirectionalLight(0xffffff, 1.4);
    this.sun.position.set(-4, -6, 10);
    this.root.add(hemi, this.sun, this.sun.target, this.robotHolder);
  }

  async load(urls: Scene3DAssets) {
    // the assets are meshopt-compressed (EXT_meshopt_compression; ADR 0006)
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    const [arena, robot] = await Promise.all([loader.loadAsync(urls.arena), loader.loadAsync(urls.robot)]);
    const zUp = (o: THREE.Object3D) => { const g = new THREE.Group(); g.rotation.x = Math.PI / 2; g.add(o); return g; };
    const a = zUp(arena.scene);
    a.position.set(this.worldToMap[0], this.worldToMap[1], 0);
    this.root.add(a);
    this.robotHolder.add(zUp(robot.scene));
    robot.scene.traverse((o) => {
      const ex = o.userData as { joint?: string; axis?: number[] };
      if (ex.joint && ex.axis) this.joints.set(ex.joint, { q: o, axis: new THREE.Vector3(...ex.axis).normalize() });
    });
    for (const s of [arena.scene, robot.scene]) {
      s.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.isMesh) this.triangles += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3;
      });
    }
    this.ready = true;
  }

  setVisible(v: boolean) {
    this.root.visible = v && this.ready;
  }

  /** The robot where the model (or the recording) says it is: on the flat floor until M4.3's terrain. */
  setPose(pose: [number, number, number]) {
    this.pose = pose;
    this.robotHolder.position.set(pose[0], pose[1], 0);
    this.robotHolder.rotation.set(0, 0, pose[2]);
  }

  /** A joint's angle (rad) about its URDF axis. */
  setJoint(name: string, angle: number) {
    const j = this.joints.get(name);
    if (j) j.q.quaternion.setFromAxisAngle(j.axis, angle);
  }

  orbitBy(dx: number, dy: number) {
    const o = this.mode === 'orbit' ? this.wide : this.orbit;
    o.yaw -= dx * 0.006;
    o.pitch = Math.min(1.45, Math.max(0.08, o.pitch + dy * 0.004));
  }

  zoomBy(factor: number) {
    const o = this.mode === 'orbit' ? this.wide : this.orbit;
    o.dist = Math.min(60, Math.max(0.8, o.dist * factor));
  }

  /** The follow rig (README §5.3: sprung, with look-ahead). dt in seconds. */
  update(dt: number, aspect: number) {
    const [x, y, th] = this.pose;
    this.camera.aspect = aspect;
    this.sun.position.set(x - 4, y - 6, 10);
    this.sun.target.position.set(x, y, 0);
    if (this.mode === 'robot_eye') {
      // rendered presentation from the URDF camera link; perception stays abstract (README §5.3)
      const c = Math.cos(th), s = Math.sin(th);
      const [cx, cy, cz] = CAMERA_LINK;
      this.camera.fov = CAMERA_VFOV_DEG;
      this.camera.position.set(x + c * cx - s * cy, y + s * cx + c * cy, cz);
      this.camera.lookAt(x + c * (cx + 1), y + s * (cx + 1), cz);
      this.camera.updateProjectionMatrix();
      return;
    }
    this.camera.fov = 50;
    if (this.mode === 'orbit') {
      const cxm = ARENA_CENTRE_WORLD[0] + this.worldToMap[0], cym = ARENA_CENTRE_WORLD[1] + this.worldToMap[1];
      const { yaw, pitch, dist } = this.wide;
      this.camera.position.set(cxm + Math.cos(yaw) * Math.cos(pitch) * dist, cym + Math.sin(yaw) * Math.cos(pitch) * dist,
        Math.sin(pitch) * dist);
      this.camera.lookAt(cxm, cym, 0);
      this.camera.updateProjectionMatrix();
      return;
    }
    const r = this.rig;
    if (!r.init) { r.x = x; r.y = y; r.yaw = th; r.init = true; }
    const k = approach(Math.min(dt, 0.1), 6);
    r.x += (x - r.x) * k;
    r.y += (y - r.y) * k;
    let dyaw = th - r.yaw;
    dyaw = Math.atan2(Math.sin(dyaw), Math.cos(dyaw));
    r.yaw += dyaw * approach(Math.min(dt, 0.1), 3);
    const yaw = r.yaw + this.orbit.yaw;
    const { pitch, dist } = this.orbit;
    const ahead = 0.6;
    this.camera.position.set(r.x - Math.cos(yaw) * Math.cos(pitch) * dist, r.y - Math.sin(yaw) * Math.cos(pitch) * dist,
      0.15 + Math.sin(pitch) * dist);
    this.camera.lookAt(r.x + Math.cos(r.yaw) * ahead, r.y + Math.sin(r.yaw) * ahead, 0.15);
    this.camera.updateProjectionMatrix();
  }

  /** The floor point (z = 0) under a canvas pixel, or null if the ray misses the floor. */
  toFloor(ndcX: number, ndcY: number): [number, number] | null {
    this.ray.setFromCamera(new THREE.Vector2(ndcX, ndcY), this.camera);
    const hit = new THREE.Vector3();
    return this.ray.ray.intersectPlane(this.floor, hit) ? [hit.x, hit.y] : null;
  }
}
