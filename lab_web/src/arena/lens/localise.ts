// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Localise lens's drawing (M2.3): MCL's particles (translucent discs,
 * size by weight), each estimator's pose with its 95 % covariance ellipse
 * (MCL's and the EKF's, translucent), and dead reckoning's pose -- all read
 * from the batches coco_lab.loc_arena emitted at the shown tick. Truth is
 * the M1 renderer's dashed outline; nothing here draws it.
 *
 * M3.3: a Case File (a recording of the full stack) carries the STACK's own
 * estimators -- AMCL, robot_localization, wheel odometry -- named as
 * recorded, with the frame they are in (`@map`, `@odom`). They are drawn the
 * same way, labelled as theirs; an estimate still in the odom frame is not
 * drawn on the map (it would be in the wrong place).
 */

import { registerDrawer, registerHover, type DrawContext } from './draw';
import type { FamilyBatch } from './store';

type Num = ArrayLike<number>;

const CH = 'coco.estimate.pose.v1';
/** The model's filters (coco_lab.loc_arena) and its dead reckoning. */
const MODEL_FILTERS = ['mcl', 'ekf'];

/** The latest estimate batch of one estimator at or before `tick` (indexed: a binary search). */
export function latestEstimate(c: DrawContext, estimator: string): FamilyBatch | null {
  return c.session.families.latestWhere(CH, estimator, c.tick);
}

/** Pose estimators to draw: the model's filters, and any recorded one in the map frame. */
export function poseEstimators(c: DrawContext): string[] {
  const recorded = c.session.families.scalarValues(CH)
    .filter((e) => !MODEL_FILTERS.includes(e) && e !== 'odometry' && !e.startsWith('wheel_odometry') && !e.endsWith('@odom'));
  return [...MODEL_FILTERS, ...recorded];
}

/** Dead-reckoning estimators: the model's, and a recording's wheel odometry in the map frame. */
export function odometryEstimators(c: DrawContext): string[] {
  return ['odometry', ...c.session.families.scalarValues(CH).filter((e) => e.startsWith('wheel_odometry') && !e.endsWith('@odom'))];
}

function estimatorName(who: string): string {
  if (who === 'odometry') return 'dead reckoning';
  if (MODEL_FILTERS.includes(who)) return who.toUpperCase();
  return `${who.replace(/@map$/, '')} (recorded, STACK)`;
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
  for (const who of poseEstimators(c)) {
    const b = latestEstimate(c, who);
    if (!b) continue;
    const g = (k: string) => (b.columns[k] as Num)[0];
    poses.push([g('x'), g('y'), g('theta')]);
    ells.push({ x: g('x'), y: g('y'), cxx: g('cov_xx'), cxy: g('cov_xy'), cyy: g('cov_yy') });
  }
  if (poses.length) L.poses('estimate', poses, 'estimate', 0.3); else L.remove('estimate');
  if (ells.length) L.ellipses('covariance', ells, 'covariance', paletteAlpha(c, 'covarianceAlpha')); else L.remove('covariance');
  const ods = odometryEstimators(c).map((who) => latestEstimate(c, who)).filter((b): b is FamilyBatch => !!b);
  if (ods.length) {
    L.poses('odometry', ods.map((od) => {
      const g = (k: string) => (od.columns[k] as Num)[0];
      return [g('x'), g('y'), g('theta')] as [number, number, number];
    }), 'odometry', 0.25);
  } else L.remove('odometry');
  for (const id of ['particles', 'estimate', 'covariance', 'odometry']) L.setVisible(id, c.on(id));
}

function paletteAlpha(c: DrawContext, key: 'particlesAlpha' | 'covarianceAlpha'): number {
  return c.layers.alpha(key);
}

function hoverLocalise(c: DrawContext, x: number, y: number): string | null {
  const dead = odometryEstimators(c);
  for (const who of [...poseEstimators(c), ...dead]) {
    const b = latestEstimate(c, who);
    if (!b) continue;
    const g = (k: string) => (b.columns[k] as Num)[0];
    if (Math.hypot(g('x') - x, g('y') - y) < 0.2) {
      const sd = (k: string) => Math.sqrt(Math.max(0, g(k)));
      return `${estimatorName(who)} estimate (${g('x').toFixed(2)}, ${g('y').toFixed(2)}) m, θ ${g('theta').toFixed(2)}`
        + (!dead.includes(who) ? ` · σx ${sd('cov_xx').toFixed(2)} σy ${sd('cov_yy').toFixed(2)} m` : '');
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
