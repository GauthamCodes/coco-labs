// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** G1: the high tier's post-processing (G2.7: ambient occlusion, then bloom on emissives, then ACES output); loaded on demand. */
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';

export function bloomComposer(r: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.Camera): EffectComposer {
  const c = new EffectComposer(r);
  c.addPass(new RenderPass(scene, camera));
  // G2.7: screen-space ambient occlusion (GTAO), the high tier only: contact shadows where racks,
  // pallets and COCO meet the floor
  const ao = new GTAOPass(scene, camera, 512, 512);
  ao.updateGtaoMaterial({ radius: 0.6, distanceExponent: 1.5, thickness: 1, scale: 1 });
  ao.blendIntensity = 0.85;
  // only solids cast ambient occlusion: lights drawn as see-through surfaces (the headlight's pool,
  // LiDAR rays, routes) are hidden while GTAO draws its depth and normals, then shown again
  const render = ao.render.bind(ao);
  ao.render = (...args: Parameters<GTAOPass['render']>) => {
    const hidden: THREE.Object3D[] = [];
    scene.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
      if (o.visible && m && (Array.isArray(m) ? m.some((x) => x.transparent) : m.transparent)) { o.visible = false; hidden.push(o); }
    });
    try { render(...args); } finally { for (const o of hidden) o.visible = true; }
  };
  c.addPass(ao);
  // G1.12: gentler and only on what is really bright (the LEDs, the markers), never the headlight's pool
  c.addPass(new UnrealBloomPass(new THREE.Vector2(256, 256), 0.35, 0.3, 0.97));
  c.addPass(new OutputPass());
  return c;
}
