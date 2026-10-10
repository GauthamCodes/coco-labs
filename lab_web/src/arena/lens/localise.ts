// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Localise lens's drawing (M2.3): MCL's particles (translucent discs,
 * size by weight), each estimator's pose with its 95 % covariance ellipse
 * (MCL's and the EKF's, translucent), and dead reckoning's pose -- all read
 * from the batches coco_lab.loc_arena emitted at the shown tick. Truth is
 * the M1 renderer's dashed outline; nothing here draws it.
 */

import { registerDrawer, registerHover, type DrawContext } from './draw';
import type { FamilyBatch } from './store';

type Num = ArrayLike<number>;

/** The latest estimate batch of one estimator at or before `tick`. */
export function latestEstimate(c: DrawContext, estimator: string): FamilyBatch | null {
  for (let t = c.tick, guard = 0; guard < 4000; guard += 1) {
    const b = c.session.families.latest('coco.estimate.pose.v1', t);
    if (!b) return null;
    const same = c.session.families.at('coco.estimate.pose.v1', b.tick).filter((x) => x.scalars.estimator === estimator);
    if (same.length) return same.at(-1)!;
    t = b.tick - 1;
    if (t < 0) return null;
  }
  return null;
}

function drawLocalise(c: DrawContext) {
  const L = c.layers;
  const ps = c.session.families.latest('coco.localise.particles.set.v1', c.tick);
  if (ps) {
    const x = ps.columns.x as Num; const y = ps.columns.y as Num; const w = ps.columns.weight as Num;
    const n = x.length;
    const r = new Float32Array(n);
    for (let i = 0; i < n; i += 1) r[i] = 0.018 + 0.05 * Math.min(1, Math.sqrt(w[i] * n));
    L.points('particles', x, y, 'particles', paletteAlpha(c, 'particlesAlpha'), 0.03, r);
  } else L.remove('particles');
  const poses: [number, number, number][] = [];
  const ells: { x: number; y: number; cxx: number; cxy: number; cyy: number }[] = [];
  for (const who of ['mcl', 'ekf']) {
    const b = latestEstimate(c, who);
    if (!b) continue;
    const g = (k: string) => (b.columns[k] as Num)[0];
    poses.push([g('x'), g('y'), g('theta')]);
    ells.push({ x: g('x'), y: g('y'), cxx: g('cov_xx'), cxy: g('cov_xy'), cyy: g('cov_yy') });
  }
  if (poses.length) L.poses('estimate', poses, 'estimate', 0.3); else L.remove('estimate');
  if (ells.length) L.ellipses('covariance', ells, 'covariance', paletteAlpha(c, 'covarianceAlpha')); else L.remove('covariance');
  const od = latestEstimate(c, 'odometry');
  if (od) {
    const g = (k: string) => (od.columns[k] as Num)[0];
    L.poses('odometry', [[g('x'), g('y'), g('theta')]], 'odometry', 0.25);
  } else L.remove('odometry');
  for (const id of ['particles', 'estimate', 'covariance', 'odometry']) L.setVisible(id, c.on(id));
}

function paletteAlpha(c: DrawContext, key: 'particlesAlpha' | 'covarianceAlpha'): number {
  return c.layers.alpha(key);
}

function hoverLocalise(c: DrawContext, x: number, y: number): string | null {
  for (const who of ['mcl', 'ekf', 'odometry']) {
    const b = latestEstimate(c, who);
    if (!b) continue;
    const g = (k: string) => (b.columns[k] as Num)[0];
    if (Math.hypot(g('x') - x, g('y') - y) < 0.2) {
      const sd = (k: string) => Math.sqrt(Math.max(0, g(k)));
      return `${who === 'odometry' ? 'dead reckoning' : who.toUpperCase()} estimate (${g('x').toFixed(2)}, ${g('y').toFixed(2)}) m, θ ${g('theta').toFixed(2)}`
        + (who !== 'odometry' ? ` · σx ${sd('cov_xx').toFixed(2)} σy ${sd('cov_yy').toFixed(2)} m` : '');
    }
  }
  const ps = c.session.families.latest('coco.localise.particles.set.v1', c.tick);
  if (ps && c.on('particles')) {
    const px = ps.columns.x as Num; const py = ps.columns.y as Num; const w = ps.columns.weight as Num;
    let best = -1; let bd = 0.12;
    for (let i = 0; i < px.length; i += 1) {
      const d = Math.hypot(px[i] - x, py[i] - y);
      if (d < bd) { bd = d; best = i; }
    }
    if (best >= 0) return `particle ${best} of ${px.length}: weight ${(w[best] * px.length).toFixed(2)}× average (update ${ps.scalars.update})`;
  }
  return null;
}

registerDrawer('localise', drawLocalise);
registerHover('localise', hoverLocalise);
