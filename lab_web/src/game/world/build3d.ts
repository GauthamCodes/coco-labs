// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.5: draw a WorldLook with three.js. Presentation only (invariant 11).
 *
 * Every (shape, material) pair is ONE instanced draw, so the Depot's ~800
 * parts cost ~25 draw calls. Textured materials map in world metres (a
 * shader patch), so an instanced unit box gets the same panel pitch at any
 * size. Contact shadow at the base of every vertical face is the baked
 * "AO" for solids; the floor's AO and light pools are the baked light map.
 */

import * as THREE from 'three';
import type { ActorLook, Mat, Part, Shape, WorldLook } from './describe';
import { concreteRoughness, floorTexture, surface } from './textures';

export type Tier = 'low' | 'medium' | 'high';

interface MatSpec { color: number; rough: number; metal?: number; tex?: Parameters<typeof surface>[0]; scale?: number; emissive?: number; ei?: number; tint?: boolean; transparent?: number }
/** The palette of the Night Shift Depot and the test lab (ART_DIRECTION.md). */
export const MATS: Record<Mat, MatSpec> = {
  panel: { color: 0xffffff, rough: 0.8, tex: 'panel', scale: 0.25 },
  office: { color: 0xffffff, rough: 0.9, tex: 'office', scale: 0.5 },
  fence: { color: 0xffffff, rough: 0.6, metal: 0.3, tex: 'fence', scale: 1 },
  trim: { color: 0x3b4a63, rough: 0.5, metal: 0.4 },
  column: { color: 0x2c3646, rough: 0.5, metal: 0.6 },
  rollup: { color: 0xffffff, rough: 0.6, metal: 0.4, tex: 'rollup', scale: 0.5 },
  exit: { color: 0xffffff, rough: 0.4, tex: 'exit', scale: 1.6, emissive: 0x2bd27f, ei: 1.6 },
  fixture: { color: 0xfff1d6, rough: 0.3, emissive: 0xffd59a, ei: 3.2 },
  ceiling: { color: 0x090c12, rough: 1 },
  upright: { color: 0x2f5a9a, rough: 0.5, metal: 0.5 },
  beam: { color: 0xe2742a, rough: 0.45, metal: 0.4 },
  deck: { color: 0x59626f, rough: 0.6, metal: 0.5 },
  carton: { color: 0xffffff, rough: 0.9, tex: 'carton', scale: 1.5, tint: true },
  crate: { color: 0xffffff, rough: 0.85, tex: 'crate', scale: 1.4 },
  wrap: { color: 0xffffff, rough: 0.25, metal: 0.05, tex: 'wrap', scale: 1 },
  wood: { color: 0xffffff, rough: 0.9, tex: 'wood', scale: 1 },
  cabinet: { color: 0x3a4456, rough: 0.6, metal: 0.3 },
  benchtop: { color: 0x8b6a45, rough: 0.7 },
  railing: { color: 0xf2b705, rough: 0.5, metal: 0.4 },
  mesh: { color: 0xffffff, rough: 0.6, metal: 0.4, tex: 'mesh', scale: 1 },
  ramp: { color: 0xffffff, rough: 0.7, tex: 'ramp', scale: 0.5 },
  mezz: { color: 0xffffff, rough: 0.7, tex: 'deck', scale: 1 },
  hazard: { color: 0xfacc15, rough: 0.6 },
  labpanel: { color: 0xffffff, rough: 0.8, tex: 'labpanel', scale: 0.5 },
  labblock: { color: 0x9aa6b6, rough: 0.7 },
  landmark: { color: 0xffffff, rough: 0.4, tint: true, emissive: 0xffffff, ei: 0.08 },
  labtrim: { color: 0xff7a1a, rough: 0.5 },
  body: { color: 0xf2b705, rough: 0.5, metal: 0.2 },
  counter: { color: 0x2b2f36, rough: 0.6 },
  mast: { color: 0x3a3f48, rough: 0.5, metal: 0.6 },
  fork: { color: 0x8a9099, rough: 0.4, metal: 0.8 },
  beacon: { color: 0xffb020, rough: 0.3, emissive: 0xffa000, ei: 2.5 },
  glass: { color: 0x9fb4c8, rough: 0.1, transparent: 0.4 },
  vest: { color: 0xc8ff2e, rough: 0.6, emissive: 0x6a8a00, ei: 0.25 },
  skin: { color: 0xc99a74, rough: 0.8 },
  dark: { color: 0x1d2027, rough: 0.7 },
};

/** Patch a standard material: world-metre UVs for its map, and a contact darkening near the floor. */
function patch(m: THREE.MeshStandardMaterial, scale: number, contact: boolean) {
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uWScale = { value: scale };
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vW; varying vec3 vWN;')
      .replace('#include <worldpos_vertex>', `#include <worldpos_vertex>
  vec4 wpos = vec4(transformed, 1.0);
  #ifdef USE_INSTANCING
  wpos = instanceMatrix * wpos;
  #endif
  vW = (modelMatrix * wpos).xyz;
  mat3 nm = mat3(modelMatrix);
  #ifdef USE_INSTANCING
  nm = nm * mat3(instanceMatrix);
  #endif
  vWN = normalize(nm * objectNormal);`);
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vW; varying vec3 vWN; uniform float uWScale;')
      .replace('#include <map_fragment>', `#ifdef USE_MAP
  vec3 an = abs(vWN);
  vec2 wuv = an.z > 0.5 ? vW.xy : (an.x > 0.5 ? vec2(vW.y, vW.z) : vec2(vW.x, vW.z));
  vec4 sampledDiffuseColor = texture2D(map, wuv * uWScale);
  diffuseColor *= sampledDiffuseColor;
#endif
${contact ? 'diffuseColor.rgb *= mix(0.45, 1.0, smoothstep(0.0, 0.7, vW.z)) * mix(1.0, 0.82, step(0.5, 1.0 - abs(vWN.z)) * (1.0 - smoothstep(0.0, 1.6, vW.z)));' : ''}`);
  };
  m.customProgramCacheKey = () => `g1w${contact ? 1 : 0}${m.type}`;
}

const textures = new Map<string, THREE.Texture>();
/**
 * Physically based shading on the high tier; below it, Lambert (no specular term): the same
 * colours, textures, light map and fog for a fraction of the per-pixel cost (G1.3: touch-to-motion
 * on a frame-bound device).
 */
function material(mat: Mat, tier: Tier): THREE.MeshStandardMaterial {
  const s = MATS[mat];
  const m = (tier === 'high' ? new THREE.MeshStandardMaterial({ color: s.color, roughness: s.rough, metalness: s.metal ?? 0 })
    : new THREE.MeshLambertMaterial({ color: s.color })) as THREE.MeshStandardMaterial;
  if (s.tex) {
    const key = s.tex;
    if (!textures.has(key)) textures.set(key, surface(s.tex, key.length * 31));
    m.map = textures.get(key)!;
  }
  if (s.emissive !== undefined) { m.emissive.set(s.emissive); m.emissiveIntensity = (s.ei ?? 1) * (tier === 'high' ? 1 : 0.8); if (s.tex === 'exit') m.emissiveMap = m.map; }
  if (s.transparent !== undefined) { m.transparent = true; m.opacity = s.transparent; m.depthWrite = false; }
  patch(m, s.scale ?? 1, !['fixture', 'ceiling', 'exit', 'beacon'].includes(mat));
  m.name = mat;
  return m;
}

/** A unit wedge: x 0..1 rising from z 0 to z 1, y -0.5..0.5 (centred in x for the instance matrix). */
function unitWedge(): THREE.BufferGeometry {
  const v = [
    [-0.5, -0.5, 0], [0.5, -0.5, 0], [0.5, -0.5, 1], [-0.5, 0.5, 0], [0.5, 0.5, 0], [0.5, 0.5, 1],
  ];
  const tri = [[0, 2, 1], [3, 4, 5], [0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4], [0, 3, 5], [0, 5, 2]];
  const pos: number[] = [];
  for (const t of tri) for (const k of t) pos.push(...v[k]);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(new Array((pos.length / 3) * 2).fill(0), 2));
  g.computeVertexNormals();
  return g;
}
const GEOMETRY: Record<Shape, () => THREE.BufferGeometry> = {
  box: () => new THREE.BoxGeometry(1, 1, 1).translate(0, 0, 0.5),
  cyl: () => new THREE.CylinderGeometry(0.5, 0.5, 1, 16).rotateX(Math.PI / 2).translate(0, 0, 0.5),
  wedge: () => unitWedge(),
};

const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), pv = new THREE.Vector3(), sv = new THREE.Vector3(), zAxis = new THREE.Vector3(0, 0, 1);
/** A part's instance matrix (geometry base at z 0, centred in x and y). */
function partMatrix(p: Part): THREE.Matrix4 {
  pv.set((p.min[0] + p.max[0]) / 2, (p.min[1] + p.max[1]) / 2, p.min[2]);
  sv.set(p.max[0] - p.min[0], p.max[1] - p.min[1], Math.max(1e-4, p.max[2] - p.min[2]));
  q.setFromAxisAngle(zAxis, p.shape === 'wedge' ? p.yaw ?? 0 : 0);
  return m4.compose(pv, q, sv);
}

/** Whether a part blocks the chase camera's boom (solids and wall fixtures taller than its lowest swing). */
export const blocksView = (p: Part) => (p.cls === 'solid' || p.cls === 'wall') && p.max[2] > 0.3;

/**
 * The chase camera's ray-cast set without drawing anything: the same unit geometry and instance
 * matrices buildWorld draws, for the tall parts (tests use this; the renderer uses buildWorld's).
 */
export function colliderMeshes(look: WorldLook): THREE.InstancedMesh[] {
  const byShape = new Map<Shape, Part[]>();
  for (const p of look.parts.filter(blocksView)) { if (!byShape.has(p.shape)) byShape.set(p.shape, []); byShape.get(p.shape)!.push(p); }
  return [...byShape].map(([shape, parts]) => {
    const mesh = new THREE.InstancedMesh(GEOMETRY[shape](), new THREE.MeshBasicMaterial(), parts.length);
    parts.forEach((p, k) => mesh.setMatrixAt(k, partMatrix(p)));
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    mesh.updateMatrixWorld(true);
    return mesh;
  });
}

export interface BuiltWorld {
  group: THREE.Group;
  /** what the chase camera's pull-in ray-casts against (render meshes of tall solids) */
  colliders: THREE.Object3D[];
  dropZones: Map<string, THREE.Mesh>;
  triangles: number;
  draws: number;
  dispose(): void;
}

export function buildWorld(look: WorldLook, tier: Tier, lightMap: THREE.Texture | null): BuiltWorld {
  const group = new THREE.Group();
  group.name = `g1-world-${look.id}`;
  const colliders: THREE.Object3D[] = [];
  const disposables: { dispose(): void }[] = [];
  let triangles = 0, draws = 0;
  const groups = new Map<string, Part[]>();
  for (const p of look.parts) {
    if (tier === 'low' && (p.mat === 'ceiling' || p.cls === 'light')) continue;
    const key = `${p.shape}:${p.mat}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(p);
  }
  for (const [key, parts] of groups) {
    const [shape, mat] = key.split(':') as [Shape, Mat];
    const geom = GEOMETRY[shape]();
    const m = material(mat, tier);
    const mesh = new THREE.InstancedMesh(geom, m, parts.length);
    mesh.name = key;
    const tint = MATS[mat].tint;
    parts.forEach((p, k) => {
      mesh.setMatrixAt(k, partMatrix(p));
      if (tint) mesh.setColorAt(k, new THREE.Color(p.tint ?? 0xffffff));
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
    mesh.castShadow = tier === 'high' && mat !== 'ceiling' && mat !== 'fixture';
    mesh.receiveShadow = tier !== 'low';
    group.add(mesh);
    disposables.push(geom, m);
    triangles += (geom.index ? geom.index.count : geom.attributes.position.count) / 3 * parts.length;
    draws += 1;
    if (parts.some(blocksView)) colliders.push(mesh);
  }
  // the floor: paint and concrete in one texture, the baked light map, a roughness detail
  const f = look.floor;
  const pxPerM = tier === 'low' ? 14 : tier === 'medium' ? 22 : 32;
  const floorMap = floorTexture(look, pxPerM);
  // G2.7: the Depot's polished floor (high tier: physically based, reflecting the baked environment)
  const fm = (tier === 'high' ? new THREE.MeshStandardMaterial({ map: floorMap, roughness: look.theme === 'lab' ? 0.75 : 0.4, metalness: 0.0, envMapIntensity: 0.8 })
    : new THREE.MeshLambertMaterial({ map: floorMap })) as THREE.MeshStandardMaterial;
  if (lightMap) { fm.lightMap = lightMap; fm.lightMapIntensity = look.theme === 'lab' ? 1.4 : 2.6; }
  if (tier === 'high') {
    const r = concreteRoughness();
    r.repeat.set((f.maxX - f.minX) / 4, (f.maxY - f.minY) / 4);
    fm.roughnessMap = r;
    disposables.push(r);
  }
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(f.maxX - f.minX, f.maxY - f.minY), fm);
  floor.position.set((f.minX + f.maxX) / 2, (f.minY + f.maxY) / 2, 0);
  floor.receiveShadow = tier !== 'low';
  floor.name = 'floor';
  group.add(floor);
  disposables.push(floor.geometry, fm, floorMap);
  triangles += 2; draws += 1;
  // drop zones: a glowing square just above the floor (a decal), shown when it is the target
  const dropZones = new Map<string, THREE.Mesh>();
  for (const z of look.zones.filter((x) => x.role === 'drop')) {
    const m = new THREE.MeshBasicMaterial({ color: 0x34d399, transparent: true, opacity: 0.0, depthWrite: false, blending: THREE.AdditiveBlending });
    const g = new THREE.PlaneGeometry(z.max[0] - z.min[0], z.max[1] - z.min[1]);
    const mesh = new THREE.Mesh(g, m);
    mesh.position.set((z.min[0] + z.max[0]) / 2, (z.min[1] + z.max[1]) / 2, 0.006);
    mesh.visible = false;
    mesh.name = `drop:${z.id}`;
    group.add(mesh);
    dropZones.set(z.id, mesh);
    disposables.push(g, m);
  }
  return {
    group, colliders, dropZones, triangles, draws,
    dispose() { for (const d of disposables) d.dispose(); },
  };
}

/** One actor as one merged mesh (vertex colours) plus its emissive beacon: 2 draws. */
export function buildActor(a: ActorLook): THREE.Group {
  const g = new THREE.Group();
  g.name = `actor:${a.id}`;
  const geoms: THREE.BufferGeometry[] = [];
  const glow: THREE.BufferGeometry[] = [];
  for (const p of a.parts) {
    const geom = GEOMETRY.box().applyMatrix4(partMatrix(p));
    const c = new THREE.Color(MATS[p.mat].color);
    const colors = new Float32Array(geom.attributes.position.count * 3);
    for (let k = 0; k < colors.length; k += 3) { colors[k] = c.r; colors[k + 1] = c.g; colors[k + 2] = c.b; }
    geom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    (MATS[p.mat].emissive !== undefined && p.mat === 'beacon' ? glow : geoms).push(geom);
  }
  const merge = (list: THREE.BufferGeometry[]) => {
    const out = new THREE.BufferGeometry();
    const attrs = ['position', 'normal', 'color'];
    for (const name of attrs) {
      const arrays = list.map((x) => (x.index ? x.toNonIndexed() : x).getAttribute(name).array as Float32Array);
      const total = arrays.reduce((s, x) => s + x.length, 0);
      const merged = new Float32Array(total);
      let o = 0;
      for (const x of arrays) { merged.set(x, o); o += x.length; }
      out.setAttribute(name, new THREE.BufferAttribute(merged, 3));
    }
    return out;
  };
  const body = new THREE.Mesh(merge(geoms), new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.6, metalness: 0.2 }));
  body.castShadow = true;
  g.add(body);
  if (glow.length) {
    const beacon = new THREE.Mesh(merge(glow), new THREE.MeshStandardMaterial({ color: 0xffb020, emissive: 0xffa000, emissiveIntensity: 2.5 }));
    beacon.name = 'beacon';
    g.add(beacon);
  }
  return g;
}
