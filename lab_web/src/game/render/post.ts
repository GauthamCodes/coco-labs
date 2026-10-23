// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** G1: the high tier's post-processing (bloom on emissives, then ACES output); loaded on demand. */
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

export function bloomComposer(r: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.Camera): EffectComposer {
  const c = new EffectComposer(r);
  c.addPass(new RenderPass(scene, camera));
  // G1.12: gentler and only on what is really bright (the LEDs, the markers), never the headlight's pool
  c.addPass(new UnrealBloomPass(new THREE.Vector2(256, 256), 0.35, 0.3, 0.97));
  c.addPass(new OutputPass());
  return c;
}
