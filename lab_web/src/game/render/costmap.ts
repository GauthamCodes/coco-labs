// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.7: Robot vision's costmap, drawn as a hologram on the floor. The costs are
 * the model's own (coco_lab.costmap, Nav2's convention: LETHAL 254, INSCRIBED 253,
 * inflation 1..252, free 0), emitted on `coco.costmap.layers.cells.v1`; this only
 * draws them. Pattern carries the meaning as well as colour (colour-blind safe):
 * lethal = red cross-hatch, inscribed = yellow diagonal stripes, inflation = a cyan
 * wash fading with cost, free = nothing. A faint scanline sweeps it (presentation).
 */

import * as THREE from 'three';

export const LETHAL = 254;
export const INSCRIBED = 253;

export class CostmapHologram {
  readonly mesh: THREE.Mesh;
  private readonly data: Uint8Array;
  private readonly tex: THREE.DataTexture;
  private readonly uniforms: { uCost: { value: THREE.DataTexture }; uTime: { value: number }; uOrigin: { value: THREE.Vector2 }; uSize: { value: THREE.Vector2 } };

  constructor(readonly width: number, readonly height: number, readonly resolution: number, origin: [number, number]) {
    this.data = new Uint8Array(width * height);
    this.tex = new THREE.DataTexture(this.data, width, height, THREE.RedFormat, THREE.UnsignedByteType);
    this.tex.magFilter = THREE.NearestFilter; this.tex.minFilter = THREE.NearestFilter;
    this.tex.unpackAlignment = 1; // one byte per cell; rows are not 4-byte aligned (490 wide)
    this.tex.needsUpdate = true;
    const W = width * resolution, H = height * resolution;
    this.uniforms = { uCost: { value: this.tex }, uTime: { value: 0 }, uOrigin: { value: new THREE.Vector2(origin[0], origin[1]) }, uSize: { value: new THREE.Vector2(W, H) } };
    const mat = new THREE.ShaderMaterial({
      uniforms: this.uniforms, transparent: true, depthWrite: false, blending: THREE.NormalBlending,
      vertexShader: `varying vec2 vW; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xy; gl_Position = projectionMatrix * viewMatrix * w; }`,
      fragmentShader: `uniform sampler2D uCost; uniform float uTime; uniform vec2 uOrigin; uniform vec2 uSize; varying vec2 vW;
        void main() {
          vec2 uv = (vW - uOrigin) / uSize;
          if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) discard;
          float c = texture2D(uCost, vec2(uv.x, 1.0 - uv.y)).r * 255.0;   // row 0 is the map's top
          if (c < 0.5 || c > 254.5) discard;                                  // free, or unknown
          float d1 = fract((vW.x + vW.y) * 8.0), d2 = fract((vW.x - vW.y) * 8.0);
          float scan = 0.85 + 0.15 * smoothstep(0.0, 0.08, fract(vW.y * 0.25 - uTime * 0.35));
          vec4 col;
          if (c > 253.5) { float h = step(0.55, d1) + step(0.55, d2); col = vec4(0.94, 0.27, 0.27, (0.25 + 0.5 * min(h, 1.0)) * scan); }
          else if (c > 252.5) { col = vec4(0.98, 0.80, 0.08, (0.18 + 0.45 * step(0.5, d1)) * scan); }
          else { float k = c / 252.0; col = vec4(0.13, 0.83, 0.93, (0.04 + 0.42 * k) * scan); }
          gl_FragColor = col;
        }`,
    });
    this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(W, H), mat);
    this.mesh.position.set(origin[0] + W / 2, origin[1] + H / 2, 0.008);
    this.mesh.renderOrder = 2;
    this.mesh.name = 'vision:costmap';
  }

  /** One batch of the model's cells (rows, cols, combined costs). */
  apply(rows: ArrayLike<number>, cols: ArrayLike<number>, costs: ArrayLike<number>) {
    for (let k = 0; k < rows.length; k++) this.data[Number(rows[k]) * this.width + Number(cols[k])] = Number(costs[k]);
    this.tex.needsUpdate = true;
  }

  tick(t: number) { this.uniforms.uTime.value = t; }

  dispose() { this.tex.dispose(); this.mesh.geometry.dispose(); (this.mesh.material as THREE.Material).dispose(); }
}
