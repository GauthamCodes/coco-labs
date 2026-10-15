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
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

import { TIER_SETTINGS, type Tier } from './quality';
import { TOKENS } from '../../ui/tokens';
import { activeTheme } from '../../ui/theme';

/**
 * M4.4: the 3D world draws on its own layer, in a first pass with tone mapping, the sun's shadow and
 * the environment; the computation layers (layer 0) draw after it, unlit and un-tone-mapped, against
 * its depth (README §5.3: "computation layers draw unlit in an overlay pass").
 */
export const WORLD_LAYER = 1;
/** Put an object and everything under it on the 3D world's layer. */
export const onWorldLayer = (o: THREE.Object3D) => o.traverse((c) => c.layers.set(WORLD_LAYER));
/** Half the side of the square the sun's shadow covers, centred on the robot (m). */
const SHADOW_HALF = 3;
/**
 * M4.4: the arena's tall kinds (convert_world.py's node names), which cutaway and low walls may open.
 * Ramps, platforms and the ground are never cut: they are what the robot stands on.
 */
const CUTTABLE = new Set(['walls', 'obstacles', 'landmarks', 'bay_guards', 'bay_columns', 'bay_approaches']);
/** Low walls stop here (m); the cutaway opens this far around the camera-to-robot line (m). */
export const LOW_WALL_Z = 0.35;
const CUT_RADIUS = 0.7;

export type CameraMode = 'topdown' | 'follow' | 'orbit' | 'robot_eye';
export const CAMERA_MODES: CameraMode[] = ['follow', 'orbit', 'robot_eye', 'topdown'];

/** COCO's camera (URDF camera_link) in base_footprint, and its vertical field of view (hfov 1.25 rad at 4:3). */
const CAMERA_LINK: [number, number, number] = [0.125, 0, 0.0135 + 0.055];
const CAMERA_VFOV_DEG = (2 * Math.atan(Math.tan(1.25 / 2) * 0.75) * 180) / Math.PI;
/** The arena's centre in the WORLD frame and its half-extent (convert_world.py's footprints: x -8..16, y -9..9). */
const ARENA_CENTRE_WORLD: [number, number] = [4, 0];

export interface Scene3DAssets {
  arena: string; robot: string;
  /** M4.7: the same files already being fetched (the page starts them at once, beside the recording) */
  buffers?: { arena: Promise<ArrayBuffer>; robot: Promise<ArrayBuffer> };
}

/** The targets' colours as drawn (coco_config's names; the hues are the page's, not the SDF's). */
const TARGET_COLOURS: Record<string, number> = { red: 0xd03a2f, green: 0x2f9e44, blue: 0x2f6fd0, yellow: 0xe0b020 };

interface Joint { q: THREE.Object3D; axis: THREE.Vector3 }

/** glTF is y up; the scene is z up: one rotation at a group above each asset's root. */
const zUp = (o: THREE.Object3D) => { const g = new THREE.Group(); g.rotation.x = Math.PI / 2; g.add(o); return g; };

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
  private z = 0;
  private wheelSpeed: [number, number] = [0, 0];
  private wheelAngle: [number, number] = [0, 0];
  /** each wheel joint and its side (0 left, 1 right), found from where it sits in the robot */
  private wheels: { name: string; side: 0 | 1; sign: number }[] = [];
  private readonly targets = new Map<string, THREE.Mesh>();
  private env: THREE.Texture | null = null;
  /** M4.4: cutaway and low walls, shared by every tall kind's material (see CUTTABLE) */
  readonly walls = {
    uRobot: { value: new THREE.Vector3() }, uCam: { value: new THREE.Vector3() },
    uCut: { value: 0 }, uLow: { value: 0 }, uLowZ: { value: LOW_WALL_Z }, uCutR: { value: CUT_RADIUS },
  };
  lowWalls = false;
  /** The camera rig's own state: sprung toward the robot (feel, not physics). */
  private rig = { x: 0, y: 0, z: 0, yaw: 0, init: false };
  private orbit = { yaw: 0, pitch: 0.38, dist: 2.6 };
  private wide = { yaw: -2.2, pitch: 0.72, dist: 24 };
  mode: Exclude<CameraMode, 'topdown'> | 'overhead' = 'follow';
  /** M4.5: the top-down view's centre and the height that frames it, for the 'overhead' pose */
  private overheadAt = { x: 0, y: 0, h: 20 };
  /** M4.5: a camera transition in progress: where it started, how far along (s), how long (s) */
  private blend: { pos: THREE.Vector3; quat: THREE.Quaternion; fov: number; t: number; dur: number } | null = null;
  private readonly floor = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  private readonly ray = new THREE.Raycaster();
  private readonly sun: THREE.DirectionalLight;

  constructor(scene: THREE.Scene, readonly worldToMap: [number, number]) {
    this.camera.up.set(0, 0, 1);
    this.root.visible = false;
    scene.add(this.root);
    const lighting = TOKENS.warehouse[activeTheme()];
    const hemi = new THREE.HemisphereLight(lighting.sky, lighting.ground, lighting.ambient);
    hemi.position.set(0, 0, 1);
    this.sun = new THREE.DirectionalLight(lighting.workLight, lighting.key);
    this.sun.position.set(-4, -6, 10);
    // the sun's shadow follows the robot: a small square around it, so the map stays cheap
    const sc = this.sun.shadow.camera;
    sc.left = -SHADOW_HALF; sc.right = SHADOW_HALF; sc.top = SHADOW_HALF; sc.bottom = -SHADOW_HALF;
    sc.near = 0.5; sc.far = 25;
    this.sun.shadow.bias = -0.0004;
    // the shadow map draws what its own camera's layers see: the 3D world's
    this.sun.shadow.camera.layers.set(WORLD_LAYER);
    this.sun.shadow.normalBias = 0.02;
    this.root.add(hemi, this.sun, this.sun.target, this.robotHolder);
    onWorldLayer(this.root);
  }

  /**
   * Apply a quality tier (M4.4): the sun's shadow (and its map's size) and the small environment map.
   * The environment is a procedural room (three's RoomEnvironment through PMREM): nothing is downloaded.
   */
  applyTier(tier: Tier, renderer: THREE.WebGLRenderer, scene: THREE.Scene) {
    const t = TIER_SETTINGS[tier];
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.sun.castShadow = t.shadowMapSize > 0;
    if (t.shadowMapSize > 0 && this.sun.shadow.mapSize.x !== t.shadowMapSize) {
      this.sun.shadow.mapSize.set(t.shadowMapSize, t.shadowMapSize);
      this.sun.shadow.map?.dispose();
      this.sun.shadow.map = null;
    }
    if (t.envMap && !this.env) {
      const pm = new THREE.PMREMGenerator(renderer);
      this.env = pm.fromScene(new RoomEnvironment(), 0.04).texture;
      pm.dispose();
    }
    scene.environment = t.envMap ? this.env : null;
    scene.environmentIntensity = 0.35;
  }

  async load(urls: Scene3DAssets) {
    // the assets are meshopt-compressed (EXT_meshopt_compression; ADR 0006)
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    // M4.7: the arena first (28 KB) with a placeholder body, the robot when its file lands: on 4G a Case File's
    // first 3D frame then waits for the recording and the arena only (the robot follows in a few hundred ms)
    const robotP = urls.buffers ? urls.buffers.robot.then((b) => loader.parseAsync(b, '')) : loader.loadAsync(urls.robot);
    const arena = urls.buffers ? await urls.buffers.arena.then((b) => loader.parseAsync(b, '')) : await loader.loadAsync(urls.arena);
    const a = zUp(arena.scene);
    a.position.set(this.worldToMap[0], this.worldToMap[1], 0);
    this.root.add(a);
    const placeholder = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.26, 0.12), new THREE.MeshStandardMaterial({ color: 0x8a8d91, roughness: 0.8 }));
    placeholder.position.z = 0.0135 + 0.06;   // its belly at COCO's ground clearance
    placeholder.castShadow = true;
    placeholder.name = 'placeholder';
    this.robotHolder.add(placeholder);
    arena.scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.castShadow = true; mesh.receiveShadow = true;
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const tuned = materials.map((original) => {
        const material = (original as THREE.MeshStandardMaterial).clone();
        const finish = TOKENS.warehouse[activeTheme()];
        material.color.set(original.name === 'ground' ? finish.floor : finish.structure);
        material.roughness = .92; material.metalness = .02;
        return material;
      });
      mesh.material = Array.isArray(mesh.material) ? tuned : tuned[0];
    });
    // the tall kinds learn to open (cutaway) and to stop low (low walls)
    for (const node of arena.scene.children.flatMap((c) => [c, ...c.children])) {
      if (!CUTTABLE.has(node.name)) continue;
      node.traverse((o) => {
        const m = o as THREE.Mesh;
        if (!m.isMesh) return;
        const mat = (m.material as THREE.MeshStandardMaterial).clone();
        mat.side = THREE.DoubleSide;   // an opened wall shows its inside, not a hole into nothing
        mat.onBeforeCompile = (sh) => {
          Object.assign(sh.uniforms, this.walls);
          sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vCocoWorld;')
            .replace('#include <begin_vertex>', '#include <begin_vertex>\nvCocoWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;');
          sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>
varying vec3 vCocoWorld;
uniform vec3 uRobot; uniform vec3 uCam; uniform float uCut; uniform float uLow; uniform float uLowZ; uniform float uCutR;`)
            .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
if (uLow > 0.5 && vCocoWorld.z > uLowZ) discard;
if (uCut > 0.5) {
  vec3 d = uRobot - uCam;
  float t = clamp(dot(vCocoWorld - uCam, d) / max(dot(d, d), 1e-6), 0.0, 1.0);
  if (t < 0.95 && distance(vCocoWorld, uCam + t * d) < uCutR && vCocoWorld.z > uRobot.z - 0.2) discard;
}`);
        };
        mat.customProgramCacheKey = () => 'coco-walls';
        m.material = mat;
      });
    }
    onWorldLayer(this.root);
    arena.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) this.triangles += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3;
    });
    this.robotReady = robotP.then((robot) => {
      this.robotHolder.remove(placeholder);
      placeholder.geometry.dispose();
      this.addRobot(robot.scene);
    });
    await this.robotReady;
    this.ready = true;
  }

  /** M4.7: the robot's file has been added (the placeholder is gone). */
  robotReady: Promise<void> = Promise.resolve();

  /**
   * M4.9: replace the robot with another level of detail (the landing starts light; the person's
   * takeover brings the high one). Its joints and wheels are wired afresh; the pose is unchanged.
   */
  async swapRobot(url: string) {
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    const g = await loader.loadAsync(url);
    await this.robotReady;
    for (const c of [...this.robotHolder.children]) this.robotHolder.remove(c);
    this.joints.clear();
    this.wheels = [];
    this.triangles -= this.robotTriangles;
    this.addRobot(g.scene);
  }

  private robotTriangles = 0;

  private addRobot(scene: THREE.Group) {
    this.robotHolder.add(zUp(scene));
    const robot = { scene };
    robot.scene.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.castShadow = true; });
    onWorldLayer(this.robotHolder);
    robot.scene.traverse((o) => {
      const ex = o.userData as { joint?: string; axis?: number[]; type?: string };
      if (ex.joint && ex.axis) this.joints.set(ex.joint, { q: o, axis: new THREE.Vector3(...ex.axis).normalize() });
    });
    // the wheels: continuous joints; their side from where each sits (robot frame: +y is left), and
    // the sign that makes a positive wheel speed roll the robot forward (its axis, in the robot frame)
    robot.scene.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(robot.scene.matrixWorld).invert();
    for (const [name, j] of this.joints) {
      if ((j.q.userData as { type?: string }).type !== 'continuous') continue;
      const p = new THREE.Vector3().setFromMatrixPosition(j.q.matrixWorld).applyMatrix4(inv);
      // glTF y-up: the robot's left (+y in ROS) is -z here
      const left = p.z < 0;
      const ax = j.axis.clone().transformDirection(new THREE.Matrix4().extractRotation(j.q.matrixWorld)).applyMatrix4(
        new THREE.Matrix4().extractRotation(inv));
      // forward roll is a rotation about the robot's +y (ROS) = -z here
      this.wheels.push({ name, side: left ? 0 : 1, sign: ax.z < 0 ? 1 : -1 });
    }
    let tri = 0;
    robot.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) tri += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3;
    });
    this.robotTriangles = tri;
    this.triangles += tri;
  }

  setVisible(v: boolean) {
    this.root.visible = v && this.ready;
  }

  /**
   * The robot where the model (or the recording) says it is. On the terrain (M4.3) it stands at the
   * surface's height with its wheel base's pitch and roll (ROS signs: pitch positive nose down, roll
   * positive left up; applied yaw, then pitch, then roll); on a flat world, on the floor.
   */
  setPose(pose: [number, number, number], tilt?: [number, number, number]) {
    this.pose = pose;
    const [z, pitch, roll] = tilt ?? [0, 0, 0];
    this.z = z;
    this.robotHolder.position.set(pose[0], pose[1], z);
    this.robotHolder.rotation.set(roll, pitch, pose[2], 'ZYX');
  }

  /**
   * M4.3: the fetch targets, drawn as their cylinders where the model says they stand. A carried
   * target is drawn under the gripper (presentation: the model carries it in x, y only).
   */
  setTargets(targets: { colour: string; x: number; y: number; z: number; diameter: number; height: number }[]) {
    for (const t of targets) {
      const m = new THREE.Mesh(new THREE.CylinderGeometry(t.diameter / 2, t.diameter / 2, t.height, 24),
        new THREE.MeshStandardMaterial({ color: TARGET_COLOURS[t.colour] ?? 0x888888, roughness: 0.55 }));
      m.rotation.x = Math.PI / 2;   // three's cylinder axis is y; the scene is z up
      m.position.set(t.x, t.y, t.z + t.height / 2);
      m.userData = { height: t.height, z: t.z };
      m.castShadow = true;
      m.layers.set(WORLD_LAYER);
      this.targets.set(t.colour, m);
      this.root.add(m);
    }
  }

  /** Move the targets to the model's positions (each tick's grasp state); `carried` rides the robot. */
  moveTargets(positions: Record<string, [number, number]>, carried: string | null) {
    for (const [c, [x, y]] of Object.entries(positions)) {
      const m = this.targets.get(c);
      if (!m) continue;
      const { height, z } = m.userData as { height: number; z: number };
      m.position.set(x, y, (c === carried ? this.z + 0.06 : z) + height / 2);
    }
  }

  /** M4.8: the race's ghost: a translucent body at `pose` (null hides it); z is the surface under it. */
  setGhost(pose: [number, number, number] | null, z = 0) {
    if (!this.ghostBody) {
      this.ghostBody = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.26, 0.14),
        new THREE.MeshStandardMaterial({ color: 0x5aa0e6, transparent: true, opacity: 0.35, depthWrite: false }));
      this.ghostBody.layers.set(WORLD_LAYER);
      this.root.add(this.ghostBody);
    }
    this.ghostBody.visible = !!pose;
    if (pose) {
      this.ghostBody.position.set(pose[0], pose[1], z + 0.0135 + 0.07);
      this.ghostBody.rotation.set(0, 0, pose[2]);
    }
  }

  private ghostBody: THREE.Mesh | null = null;

  /** The wheels' speeds (rad/s); the wheels turn at them in the render loop (presentation only). */
  setWheelSpeeds(w: [number, number]) {
    this.wheelSpeed = w;
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

  /**
   * Change camera (M4.5; README §5.3: transitions take about 0.4 s). The camera moves from where it is
   * to the new mode's pose over `dur` seconds, eased; 0 cuts (reduced motion).
   */
  /** Presentation-only framing for the design references; the model is untouched. */
  setFollowFraming(distance: number, pitch: number) {
    this.orbit.dist = Math.max(1, Math.min(12, distance));
    this.orbit.pitch = Math.max(.15, Math.min(1.4, pitch));
  }

  setMode(mode: Exclude<CameraMode, 'topdown'> | 'overhead', dur: number) {
    if (mode === this.mode && !this.blend) return;
    this.mode = mode;
    this.blend = dur > 0 ? { pos: this.camera.position.clone(), quat: this.camera.quaternion.clone(), fov: this.camera.fov, t: 0, dur } : null;
  }

  /** Where the top-down view looks: the 'overhead' pose stands above it, framing the same ground. */
  setOverhead(x: number, y: number, viewHeight: number) {
    this.overheadAt = { x, y, h: viewHeight / 2 / Math.tan(((50 * Math.PI) / 180) / 2) };
  }

  /** Start from the overhead pose (coming from top-down): the camera is put there, then blends to `mode`. */
  startFromOverhead(mode: Exclude<CameraMode, 'topdown'>, dur: number) {
    this.mode = 'overhead';
    this.aim(0);
    this.setMode(mode, dur);
  }

  get transitioning(): boolean {
    return this.blend !== null;
  }

  /** The camera for this frame: the mode's pose, blended from the last pose while a transition runs. dt in seconds. */
  update(dt: number, aspect: number) {
    const [x, y] = this.pose;
    for (const k of [0, 1] as const) this.wheelAngle[k] += this.wheelSpeed[k] * Math.min(dt, 0.1);
    for (const w of this.wheels) this.setJoint(w.name, w.sign * this.wheelAngle[w.side]);
    this.camera.aspect = aspect;
    this.sun.position.set(x - 4, y - 6, this.z + 10);
    this.sun.target.position.set(x, y, this.z);
    this.aim(dt);
    // cutaway: in the follow and orbit cameras the walls between the camera and the robot open
    this.walls.uRobot.value.set(x, y, this.z + 0.15);
    this.walls.uCam.value.copy(this.camera.position);
    this.walls.uCut.value = this.mode === 'follow' || this.mode === 'orbit' ? 1 : 0;
    this.walls.uLow.value = this.lowWalls ? 1 : 0;
    const b = this.blend;
    if (b) {
      b.t += Math.min(dt, 0.1);
      const f = b.t >= b.dur ? 1 : 0.5 - 0.5 * Math.cos((Math.PI * b.t) / b.dur);   // ease in-out
      this.camera.position.lerpVectors(b.pos, this.camera.position, f);
      this.camera.quaternion.slerpQuaternions(b.quat, this.camera.quaternion, f);
      this.camera.fov = b.fov + (this.camera.fov - b.fov) * f;
      this.camera.updateProjectionMatrix();
      if (b.t >= b.dur) this.blend = null;
    }
  }

  /** The current mode's own camera pose (no blending). The follow rig: README §5.3, sprung, with look-ahead. */
  private aim(dt: number) {
    const [x, y, th] = this.pose;
    if (this.mode === 'overhead') {
      const o = this.overheadAt;
      this.camera.fov = 50;
      this.camera.up.set(0, 1, 0);           // map +y up the screen, as top-down draws it
      this.camera.position.set(o.x, o.y, o.h);
      this.camera.lookAt(o.x, o.y, 0);
      this.camera.up.set(0, 0, 1);
      this.camera.updateProjectionMatrix();
      return;
    }
    if (this.mode === 'robot_eye') {
      // rendered presentation from the URDF camera link; perception stays abstract (README §5.3)
      const [cx, cy, cz] = CAMERA_LINK;
      this.camera.fov = CAMERA_VFOV_DEG;
      // on the terrain the camera link tilts with the base: the robot's own camera, transformed
      this.robotHolder.updateMatrixWorld(true);
      const eye = new THREE.Vector3(cx, cy, cz).applyMatrix4(this.robotHolder.matrixWorld);
      const at = new THREE.Vector3(cx + 1, cy, cz).applyMatrix4(this.robotHolder.matrixWorld);
      this.camera.position.copy(eye);
      this.camera.lookAt(at);
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
    if (!r.init) { r.x = x; r.y = y; r.z = this.z; r.yaw = th; r.init = true; }
    const k = approach(Math.min(dt, 0.1), 6);
    r.x += (x - r.x) * k;
    r.y += (y - r.y) * k;
    r.z += (this.z - r.z) * k;
    let dyaw = th - r.yaw;
    dyaw = Math.atan2(Math.sin(dyaw), Math.cos(dyaw));
    r.yaw += dyaw * approach(Math.min(dt, 0.1), 3);
    const yaw = r.yaw + this.orbit.yaw;
    const { pitch, dist } = this.orbit;
    const ahead = 0.6;
    this.camera.position.set(r.x - Math.cos(yaw) * Math.cos(pitch) * dist, r.y - Math.sin(yaw) * Math.cos(pitch) * dist,
      r.z + 0.15 + Math.sin(pitch) * dist);
    this.camera.lookAt(r.x + Math.cos(r.yaw) * ahead, r.y + Math.sin(r.yaw) * ahead, r.z + 0.15);
    this.camera.updateProjectionMatrix();
  }

  /** Release presentation resources; never affects a session or model. */
  dispose() {
    this.root.traverse((object) => {
      const mesh = object as THREE.Mesh;
      if (!mesh.isMesh) return;
      mesh.geometry.dispose();
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const material of materials) material.dispose();
    });
    this.sun.shadow.map?.dispose(); this.env?.dispose();
    this.root.removeFromParent();
  }

  /** The floor point (z = 0) under a canvas pixel, or null if the ray misses the floor. */
  toFloor(ndcX: number, ndcY: number): [number, number] | null {
    this.ray.setFromCamera(new THREE.Vector2(ndcX, ndcY), this.camera);
    const hit = new THREE.Vector3();
    return this.ray.ray.intersectPlane(this.floor, hit) ? [hit.x, hit.y] : null;
  }
}
