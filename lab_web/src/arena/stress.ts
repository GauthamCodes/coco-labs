// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The M2 laptop stress scene (`?stress=m2`, M2 B.3 "Laptop performance"):
 * on top of whatever the lenses draw, 2,000 particles, 1,000 MPPI-style
 * rollouts of 56 steps and a full occupancy grid over the whole world,
 * REBUILT at the model's 10 Hz as the real layers are (the grid every tenth
 * tick, as the map lens's snapshots arrive), so the measurement includes
 * the cost of re-uploading geometry, not just of drawing it. Synthetic and
 * labelled as such: it measures the renderer, never an algorithm.
 */

import type { World } from './protocol';
import type { LensLayers } from './render/lensLayers';

export const STRESS = { particles: 2000, rollouts: 1000, steps: 56, hz: 10, gridEvery: 10 } as const;

/** Start the scene; returns a function that stops it and removes its layers. */
export function startLensStress(ll: LensLayers, world: World): () => void {
  const { width: W, height: H, resolution: r, origin } = world;
  const x0 = origin[0]; const y0 = origin[1];
  const wx = W * r; const wy = H * r;
  let k = 0;
  const rand = (i: number) => { const v = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return v - Math.floor(v); };
  const grid = new Float32Array(W * H);
  const frame = () => {
    k += 1;
    const cx = x0 + wx * (0.3 + 0.4 * rand(1)); const cy = y0 + wy * (0.3 + 0.4 * rand(2));
    const px = new Float32Array(STRESS.particles); const py = new Float32Array(STRESS.particles);
    for (let i = 0; i < STRESS.particles; i += 1) { px[i] = cx + (rand(3 * i) - 0.5) * 3; py[i] = cy + (rand(3 * i + 1) - 0.5) * 3; }
    ll.points('stress_particles', px, py, 'particles', ll.alpha('particlesAlpha'), 0.03);
    const segs = new Float32Array(STRESS.rollouts * (STRESS.steps - 1) * 4);
    let o = 0;
    for (let j = 0; j < STRESS.rollouts; j += 1) {
      let x = cx; let y = cy; let th = rand(5 * j) * 2 * Math.PI;
      const w = (rand(5 * j + 1) - 0.5) * 1.2;
      for (let s = 1; s < STRESS.steps; s += 1) {
        const nx = x + 0.05 * Math.cos(th); const ny = y + 0.05 * Math.sin(th);
        segs[o++] = x; segs[o++] = y; segs[o++] = nx; segs[o++] = ny;
        x = nx; y = ny; th += w * 0.1;
      }
    }
    ll.segments('stress_rollouts', segs, 'candidate', ll.alpha('candidateAlpha'));
    if (k % STRESS.gridEvery === 1) {
      for (let i = 0; i < grid.length; i += 1) grid[i] = (rand(i) - 0.5) * 8;
      ll.mapTexture('stress_grid', W, H, r, [x0, y0], grid, true, 0);
    }
  };
  frame();
  const timer = setInterval(frame, 1000 / STRESS.hz);
  return () => {
    clearInterval(timer);
    for (const id of ['stress_particles', 'stress_rollouts', 'stress_grid']) ll.remove(id);
  };
}
