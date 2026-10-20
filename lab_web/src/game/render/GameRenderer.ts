// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1: the game's renderer. One WebGL context, one scene: the level's look
 * (world/build3d.ts), COCO's real model, the actors on their collision
 * bodies, the catalog objects where Grasp Assist says they are, and the
 * Robot vision overlay. Presentation only (README §3 invariant 11): it is
 * handed poses and never computes or writes model state.
 *
 * Tiers: low (no shadows, blob shadow, 1x pixels), medium (1.25x pixels, roughness detail),
 * high (real shadow, a spot-light headlight, bloom on emissives, 2x). ACES tone mapping always.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import type { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import type { WorldLook } from '../world/describe';
import { buildActor, buildWorld, type BuiltWorld, type Tier } from '../world/build3d';
import { GameCamera } from './camera';

export const TIER_PIXELS: Record<Tier, number> = { low: 1, medium: 1.25, high: 2 };
export type Led = 'manual' | 'auto' | 'stop' | 'idle';
const LED_COLOUR: Record<Led, number> = { manual: 0x34d399, auto: 0x22d3ee, stop: 0xef4444, idle: 0x8f9bb0 };

/** Catalog colours as drawn (a page palette, not physics). */
const OBJECT_COLOURS: Record<string, number> = {
  red: 0xd03a2f, green: 0x2f9e44, blue: 0x2f6fd0, yellow: 0xe0b020, silver: 0xb8c0cc, white: 0xe8eef2, orange: 0xf08a24, brown: 0x8a5a32,
};

interface Joint { q: THREE.Object3D; axis: THREE.Vector3 }
export interface ObjectView { id: string; shape: 'cylinder' | 'box'; diameter?: number; height: number; size?: number[]; colour: string }
export interface VisionFrame { ranges: Float32Array | null; angles: { min: number; max: number; samples: number }; mount: [number, number, number]; beamZ: number; plan: [number, number][]; local: [number, number][] }

export class GameRenderer {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly cam = new GameCamera();
  tier: Tier;
  world: BuiltWorld | null = null;
  private composer: EffectComposer | null = null;
  private readonly robot = new THREE.Group();
  private readonly led: THREE.MeshStandardMaterial;
  private readonly head: THREE.SpotLight;
  private readonly cone: THREE.Mesh;
  private readonly blob: THREE.Mesh;
  private readonly key: THREE.DirectionalLight;
  private readonly hemi: THREE.HemisphereLight;
  private joints = new Map<string, Joint>();
  private wheels: { name: string; side: 0 | 1; sign: number }[] = [];
  private wheelAngle: [number, number] = [0, 0];
  private actors = new Map<string, THREE.Group>();
  private objects = new Map<string, THREE.Mesh>();
  private readonly marker: THREE.Mesh;
  private readonly ring: THREE.Mesh;
  private readonly ringFill: THREE.Mesh;
  private readonly beam: THREE.Mesh;
  private readonly vision = new THREE.Group();
  private readonly fan: THREE.Mesh;
  private readonly hits: THREE.Points;
  private readonly planLine: THREE.Mesh;
  private readonly ghostLine: THREE.Mesh;
  private readonly goalPin: THREE.Group;
  private clock = 0;
  pose: [number, number, number] = [0, 0, 0];
  z = 0;
  tilt: [number, number] = [0, 0];
  speed = 0;
  wheelSpeed: [number, number] = [0, 0];
  readonly stats = { triangles: 0, draws: 0 };
  private lostContext = false;
  private ceiling = 99;
  private overheadMeshes: THREE.Object3D[] = [];
  private fogDensity = 0.02;

  constructor(readonly canvas: HTMLCanvasElement, tier: Tier) {
    this.tier = tier;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: tier === 'high', powerPreference: 'high-performance', preserveDrawingBuffer: false });
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.35;
    this.renderer.info.autoReset = false;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); this.lostContext = true; });
    this.scene.background = new THREE.Color(0x0e1116);
    this.hemi = new THREE.HemisphereLight(0x9aa8c8, 0x20262f, 1.1);
    this.hemi.position.set(0, 0, 1);
    this.key = new THREE.DirectionalLight(0xffe2bd, 1.6);
    this.key.position.set(-5, -8, 14);
    this.scene.add(this.hemi, this.key, this.key.target);
    // COCO: its model loads into `robot`; the LED strip, headlight and shadow are ours
    this.led = new THREE.MeshStandardMaterial({ color: 0x111111, emissive: LED_COLOUR.idle, emissiveIntensity: 2.2 });
    const ledStrip = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.16, 0.012), this.led);
    ledStrip.position.set(-0.15, 0, 0.115);
    this.robot.add(ledStrip);
    this.head = new THREE.SpotLight(0xfff1d6, 6, 7, 0.5, 0.6, 1.4);
    this.head.position.set(0.16, 0, 0.12);
    this.head.target.position.set(1.6, 0, -0.1);
    this.robot.add(this.head, this.head.target);
    // the headlight's pool on the floor: a flat, translucent fan (a light, never a solid)
    const poolTex = (() => { const c = document.createElement('canvas'); c.width = 64; c.height = 128; const g = c.getContext('2d')!; const gr = g.createLinearGradient(0, 128, 0, 0); gr.addColorStop(0, 'rgba(255,241,214,0.55)'); gr.addColorStop(1, 'rgba(255,241,214,0)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 128); return new THREE.CanvasTexture(c); })();
    const fan = new THREE.BufferGeometry();
    fan.setAttribute('position', new THREE.Float32BufferAttribute([0.16, 0, 0.004, 2.4, -0.9, 0.004, 2.4, 0.9, 0.004], 3));
    fan.setAttribute('uv', new THREE.Float32BufferAttribute([0.5, 0, 0, 1, 1, 1], 2));
    this.cone = new THREE.Mesh(fan, new THREE.MeshBasicMaterial({ map: poolTex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0.5 }));
    this.robot.add(this.cone);
    const blobTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 64; const g = c.getContext('2d')!; const gr = g.createRadialGradient(32, 32, 4, 32, 32, 32); gr.addColorStop(0, 'rgba(0,0,0,0.65)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c); })();
    this.blob = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 0.55), new THREE.MeshBasicMaterial({ map: blobTex, transparent: true, depthWrite: false }));
    this.blob.position.z = 0.003;
    this.robot.add(this.blob);
    this.scene.add(this.robot);
    // the target: a ▼ marker above it, a ring around it, a ring that fills while COCO approaches
    this.marker = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.14, 4).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x34d399 }));
    this.ring = new THREE.Mesh(new THREE.RingGeometry(0.16, 0.2, 40), new THREE.MeshBasicMaterial({ color: 0x34d399, transparent: true, opacity: 0.85, depthWrite: false }));
    this.ringFill = new THREE.Mesh(new THREE.RingGeometry(0.21, 0.25, 40, 1, 0, 0.001), new THREE.MeshBasicMaterial({ color: 0xff7a1a, depthWrite: false }));
    // a light column over the target, so the order can be found from across the hall (a light, never a solid)
    this.beam = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.12, 3, 16, 1, true).rotateX(Math.PI / 2).translate(0, 0, 1.5),
      new THREE.MeshBasicMaterial({ color: 0x34d399, transparent: true, opacity: 0.22, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
    for (const m of [this.marker, this.ring, this.ringFill, this.beam]) { m.visible = false; this.scene.add(m); }
    // Robot vision: a holographic scanner (the scan area, its hits), the plan, the planner ghost
    this.fan = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: 0x22d3ee, transparent: true, opacity: 0.13, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }));
    this.hits = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({ color: 0x7df3ff, size: 0.05, sizeAttenuation: true, transparent: true, opacity: 0.95, depthWrite: false }));
    this.planLine = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: 0xf43f8e, transparent: true, opacity: 0.9, depthWrite: false }));
    this.ghostLine = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({ color: 0xf9a8d4, transparent: true, opacity: 0.45, depthWrite: false }));
    this.goalPin = new THREE.Group();
    const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.7, 8).rotateX(Math.PI / 2).translate(0, 0, 0.35), new THREE.MeshBasicMaterial({ color: 0xf43f8e }));
    const flag = new THREE.Mesh(new THREE.PlaneGeometry(0.28, 0.18).rotateX(Math.PI / 2).translate(0.14, 0, 0.6), new THREE.MeshBasicMaterial({ color: 0xf43f8e, side: THREE.DoubleSide }));
    this.goalPin.add(pin, flag);
    this.goalPin.visible = false;
    this.vision.add(this.fan, this.hits);
    this.vision.visible = false;
    this.scene.add(this.vision, this.planLine, this.ghostLine, this.goalPin);
    this.applyTier(tier);
  }

  get contextLost() { return this.lostContext; }

  applyTier(tier: Tier) {
    this.tier = tier;
    const r = this.renderer;
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, TIER_PIXELS[tier]));
    r.shadowMap.enabled = tier === 'high';
    r.shadowMap.type = THREE.PCFShadowMap;
    this.key.castShadow = tier === 'high';
    if (tier === 'high') {
      const sc = this.key.shadow.camera;
      sc.left = -5; sc.right = 5; sc.top = 5; sc.bottom = -5; sc.near = 1; sc.far = 40;
      this.key.shadow.mapSize.set(1024, 1024);
      this.key.shadow.bias = -0.0005;
    }
    this.head.visible = tier === 'high'; // a per-pixel spot light: high only; below it the floor pool is the headlight
    this.blob.visible = tier !== 'high';
    this.robot.traverse((o) => { if ((o as THREE.Mesh).isMesh && o !== this.blob && o !== this.cone) o.castShadow = tier === 'high'; });
    this.composer?.dispose();
    this.composer = null;
    if (tier === 'high') {
      // bloom on emissives, high tier only; its code loads only when that tier is used
      void import('./post').then(({ bloomComposer }) => {
        if (this.tier !== 'high' || this.composer) return;
        this.composer = bloomComposer(r, this.scene, this.cam.camera);
        this.resize();
      });
    }
    this.resize();
  }

  resize() {
    const w = this.canvas.clientWidth || 1, h = this.canvas.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.composer?.setSize(w, h);
    this.cam.setAspect(w, h);
  }

  /** Build the level's look; `lightUrl` is its baked floor light map. */
  async loadWorld(look: WorldLook, lightUrl: string | null) {
    const light = lightUrl ? await new THREE.TextureLoader().loadAsync(lightUrl).catch(() => null) : null;
    if (light) { light.colorSpace = THREE.NoColorSpace; light.flipY = true; }
    this.world?.dispose();
    if (this.world) this.scene.remove(this.world.group);
    this.world = buildWorld(look, this.tier, light);
    this.scene.add(this.world.group);
    this.cam.colliders = this.world.colliders;
    this.fogDensity = look.theme === 'lab' ? 0.01 : 0.022;
    this.scene.fog = new THREE.FogExp2(look.theme === 'lab' ? 0x1a2230 : 0x0b1018, this.fogDensity);
    this.ceiling = look.ceiling;
    this.overheadMeshes = ['box:ceiling', 'box:fixture'].map((n) => this.world!.group.getObjectByName(n)).filter((m): m is THREE.Object3D => !!m);
    this.hemi.intensity = look.theme === 'lab' ? 1.5 : 1.15;
    (this.cone.material as THREE.MeshBasicMaterial).opacity = look.theme === 'lab' ? 0.18 : 0.5;
    for (const a of look.actors) {
      const g = buildActor(a);
      this.actors.set(a.id, g);
      this.scene.add(g);
    }
  }

  async loadRobot(url: string) {
    const g = await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync(url);
    const up = new THREE.Group();
    up.rotation.x = Math.PI / 2;
    up.add(g.scene);
    this.robot.add(up);
    g.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = this.tier === 'high';
        // orange accents on the robot's own light-coloured shells (presentation)
        const mat = m.material as THREE.MeshStandardMaterial;
        if (mat?.color) {
          const hsl = { h: 0, s: 0, l: 0 };
          mat.color.getHSL(hsl);
          if (hsl.l > 0.62 && hsl.s < 0.2) { const c = mat.clone(); c.color.set(0xff7a1a); m.material = c; }
        }
      }
      const ex = o.userData as { joint?: string; axis?: number[] };
      if (ex.joint && ex.axis) this.joints.set(ex.joint, { q: o, axis: new THREE.Vector3(...ex.axis).normalize() });
    });
    g.scene.updateMatrixWorld(true);
    const inv = new THREE.Matrix4().copy(g.scene.matrixWorld).invert();
    for (const [name, j] of this.joints) {
      if ((j.q.userData as { type?: string }).type !== 'continuous') continue;
      const p = new THREE.Vector3().setFromMatrixPosition(j.q.matrixWorld).applyMatrix4(inv);
      const ax = j.axis.clone().transformDirection(new THREE.Matrix4().extractRotation(j.q.matrixWorld)).applyMatrix4(new THREE.Matrix4().extractRotation(inv));
      this.wheels.push({ name, side: p.z < 0 ? 0 : 1, sign: ax.z < 0 ? 1 : -1 });
    }
    this.countStats();
  }

  private countStats() {
    let tri = 0;
    this.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh || !m.geometry) return;
      const n = (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position?.count ?? 0) / 3;
      tri += n * ((m as THREE.InstancedMesh).isInstancedMesh ? (m as THREE.InstancedMesh).count : 1);
    });
    this.stats.triangles = Math.round(tri);
  }

  setLed(led: Led) { this.led.emissive.set(LED_COLOUR[led]); }

  /** The catalog objects (placed or carried) where Grasp Assist says they are. */
  setObjects(catalog: Map<string, ObjectView>, rows: [string, number, number, number, string][]) {
    for (const [id, x, y, z, status] of rows) {
      let m = this.objects.get(id);
      const it = catalog.get(id);
      if (!it) continue;
      if (!m) {
        const g = it.shape === 'cylinder' ? new THREE.CylinderGeometry(it.diameter! / 2, it.diameter! / 2, it.height, 18).rotateX(Math.PI / 2).translate(0, 0, it.height / 2)
          : new THREE.BoxGeometry(it.size![0], it.size![1], it.size![2]).translate(0, 0, it.size![2] / 2);
        m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: OBJECT_COLOURS[it.colour] ?? 0xcccccc, roughness: 0.35, metalness: it.colour === 'silver' ? 0.8 : 0.3 }));
        m.castShadow = this.tier === 'high';
        m.name = `object:${id}`;
        this.objects.set(id, m);
        this.scene.add(m);
      }
      // a carried object is drawn under the gripper (the model carries it in x, y; presentation height)
      m.position.set(x, y, status === 'carried' ? z + 0.04 : z);
    }
  }

  /** Highlight the object GRAB would take, and how far along the approach is (0..1; null hides the ring). */
  setTarget(id: string | null, progress: number | null) {
    const m = id ? this.objects.get(id) : undefined;
    for (const x of [this.marker, this.ring, this.ringFill, this.beam]) x.visible = !!m;
    if (!m) return;
    const p = m.position;
    this.beam.position.set(p.x, p.y, p.z);
    const top = (m.geometry.boundingBox ?? (m.geometry.computeBoundingBox(), m.geometry.boundingBox!)).max.z;
    const bob = Math.sin(this.clock * 3) * 0.03;
    this.marker.position.set(p.x, p.y, p.z + top + 0.18 + bob);
    this.ring.position.set(p.x, p.y, p.z + 0.004);
    this.ringFill.position.set(p.x, p.y, p.z + 0.005);
    (this.ring.material as THREE.MeshBasicMaterial).opacity = 0.55 + 0.35 * Math.sin(this.clock * 4);
    if (progress !== null) {
      this.ringFill.visible = true;
      this.ringFill.geometry.dispose();
      this.ringFill.geometry = new THREE.RingGeometry(0.21, 0.25, 40, 1, Math.PI / 2, Math.max(0.001, progress * Math.PI * 2));
    } else this.ringFill.visible = false;
  }

  private dropStrong = false;
  /** The drop zone that is the target glows (stronger, pulsing, while COCO carries the object). */
  setDropZone(id: string | null, strong = false) {
    this.dropStrong = strong;
    for (const [zid, m] of this.world?.dropZones ?? []) m.visible = zid === id;
  }

  setActors(rows: [string, number, number, number][]) {
    for (const [id, x, y, yaw] of rows) {
      const g = this.actors.get(id);
      if (!g) continue;
      g.position.set(x, y, 0);
      g.rotation.set(0, 0, yaw);
      const b = g.getObjectByName('beacon') as THREE.Mesh | undefined;
      if (b) (b.material as THREE.MeshStandardMaterial).emissiveIntensity = Math.sin(this.clock * 9 + x) > 0 ? 3 : 0.3;
    }
  }

  /** A flat ribbon along a polyline, just above the floor. */
  private ribbon(mesh: THREE.Mesh, pts: [number, number][], width: number, z: number) {
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

  setPlan(pts: [number, number][]) { this.ribbon(this.planLine, pts, 0.08, 0.012); }
  setGhost(pts: [number, number][] | null) { this.ghostLine.visible = !!pts; if (pts) this.ribbon(this.ghostLine, pts, 0.05, 0.01); }
  setGoal(xy: [number, number] | null) { this.goalPin.visible = !!xy; if (xy) this.goalPin.position.set(xy[0], xy[1], 0); }

  setVision(on: boolean) { this.vision.visible = on; }

  /** The LiDAR as a holographic fan: what COCO can see, at its beam height, and the bright hit points. */
  setScan(ranges: Float32Array, angles: { min: number; max: number; samples: number }, mount: [number, number, number], rangeMax: number) {
    if (!this.vision.visible) return;
    const [x, y, th] = this.pose;
    const ox = x + mount[0] * Math.cos(th) - mount[1] * Math.sin(th), oy = y + mount[0] * Math.sin(th) + mount[1] * Math.cos(th);
    const z = this.z + 0.02;
    const n = ranges.length, step = (angles.max - angles.min) / Math.max(1, angles.samples - 1);
    const fan: number[] = [], hits: number[] = [];
    let prev: [number, number] | null = null;
    for (let k = 0; k < n; k += 2) {
      const r = Number.isFinite(ranges[k]) ? Math.min(ranges[k], rangeMax) : rangeMax;
      const a = th + angles.min + k * step;
      const px = ox + r * Math.cos(a), py = oy + r * Math.sin(a);
      if (prev) fan.push(ox, oy, z, prev[0], prev[1], z, px, py, z);
      prev = [px, py];
      if (Number.isFinite(ranges[k]) && ranges[k] < rangeMax) hits.push(px, py, z + 0.01);
    }
    this.fan.geometry.dispose();
    const fg = new THREE.BufferGeometry(); fg.setAttribute('position', new THREE.Float32BufferAttribute(fan, 3)); this.fan.geometry = fg;
    this.hits.geometry.dispose();
    const hg = new THREE.BufferGeometry(); hg.setAttribute('position', new THREE.Float32BufferAttribute(hits, 3)); this.hits.geometry = hg;
  }

  /** Draw one frame; `dt` in seconds. */
  frame(dt: number) {
    this.clock += dt;
    const [x, y, th] = this.pose;
    for (const m of this.world?.dropZones.values() ?? []) if (m.visible) (m.material as THREE.MeshBasicMaterial).opacity = this.dropStrong ? 0.32 + 0.18 * Math.sin(this.clock * 4) : 0.14;
    this.robot.position.set(x, y, this.z);
    this.robot.rotation.set(this.tilt[1], this.tilt[0], th, 'ZYX');
    // wheels turn at the model's own wheel speed
    for (const w of this.wheels) {
      this.wheelAngle[w.side] += this.wheelSpeed[w.side] * dt;
      const j = this.joints.get(w.name);
      if (j) j.q.quaternion.setFromAxisAngle(j.axis, w.sign * this.wheelAngle[w.side]);
    }
    if (this.tier === 'high') { this.key.position.set(x - 5, y - 8, 14); this.key.target.position.set(x, y, 0); }
    this.cam.update(dt, this.pose, this.z, this.speed);
    // a camera above the roof (tactical, a high orbit) sees through it; fog thins with height
    const above = this.cam.camera.position.z > Math.min(this.ceiling, 5.4) - 0.3;
    for (const m of this.overheadMeshes) m.visible = !above;
    if (this.scene.fog instanceof THREE.FogExp2) this.scene.fog.density = this.fogDensity * (above ? 0.25 : 1);
    this.renderer.info.reset();
    if (this.composer) this.composer.render(dt);
    else this.renderer.render(this.scene, this.cam.camera);
    this.stats.draws = this.renderer.info.render.calls;
  }

  /** Floor point under a canvas pixel (for a tap or click goal), or null. */
  pick(px: number, py: number): [number, number] | null {
    const r = this.canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(((px - r.left) / r.width) * 2 - 1, -((py - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, this.cam.camera);
    const hit = new THREE.Vector3();
    return ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), hit) ? [hit.x, hit.y] : null;
  }

  dispose() {
    this.world?.dispose();
    this.composer?.dispose();
    this.renderer.dispose();
  }
}
