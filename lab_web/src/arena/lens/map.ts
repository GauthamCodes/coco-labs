// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Map lens's drawing (M2.4): the map the robot is building (the latest
 * log-odds keyframe), the SLAM's trajectory, EKF-SLAM's landmarks with
 * translucent 95 % ellipses (on the IDEALISED sensor, labelled), FastSLAM's
 * particles, and the pose graph -- its nodes, its edges, loop closures in
 * their own colour, and at a closure the graph BEFORE optimising (faint)
 * beside the graph after. All read from what coco_lab.map_arena emitted.
 */

import { registerDrawer, registerHover, type DrawContext } from './draw';
import type { FamilyBatch } from './store';

type Num = ArrayLike<number>;

/** The mapping estimator's trajectory up to the shown tick, as segments. */
function trajectory(c: DrawContext): number[] {
  const header = c.session.headers.get('coco.map.grid.header.v1');
  const est = header ? String(header.estimator) : '';
  const name = est === 'truth' || est === 'odometry' || est === 'belief' ? `map:${est}` : est;
  const seg: number[] = [];
  if (!name) return seg;
  let px = NaN; let py = NaN;
  // that estimator's own batches (M3.3: indexed, not every estimator's)
  for (const b of c.session.families.beforeWhere('coco.estimate.pose.v1', name, c.tick)) {
    const x = (b.columns.x as Num)[0]; const y = (b.columns.y as Num)[0];
    if (!Number.isNaN(px)) seg.push(px, py, x, y);
    px = x; py = y;
  }
  return seg;
}

// the built map's texture is rebuilt only when a new keyframe is shown
let shownSnap: FamilyBatch | null = null;

function drawMap(c: DrawContext) {
  const L = c.layers;
  const head = c.session.headers.get('coco.map.grid.header.v1');
  const snap = c.session.families.latest('coco.map.grid.snapshot.v1', c.tick);
  if (head && snap) {
    if (snap !== shownSnap || !L.has('built_map')) L.mapTexture('built_map', Number(head.width), Number(head.height), Number(head.resolution),
      [Number(head.origin_x), Number(head.origin_y)], snap.columns.logodds_f32 as Num, true, 0.7);
    shownSnap = snap;
  } else { L.remove('built_map'); shownSnap = null; }
  const seg = trajectory(c);
  if (seg.length) L.segments('slam_pose', seg, 'estimate', 0.9); else L.remove('slam_pose');
  const lm = c.session.families.latest('coco.map.slam.landmarks.v1', c.tick);
  if (lm) {
    const x = lm.columns.x as Num; const y = lm.columns.y as Num;
    const items = Array.from(x, (_, i) => ({ x: x[i], y: y[i], cxx: (lm.columns.cov_xx as Num)[i], cxy: (lm.columns.cov_xy as Num)[i], cyy: (lm.columns.cov_yy as Num)[i] }));
    L.ellipses('landmarks', items, 'landmark', L.alpha('landmarkAlpha'));
  } else L.remove('landmarks');
  const sp = c.session.families.latest('coco.map.slam.particles.v1', c.tick);
  if (sp) L.points('slam_particles', sp.columns.x as Num, sp.columns.y as Num, 'particles', L.alpha('particlesAlpha'), 0.04);
  else L.remove('slam_particles');
  const nodes = c.session.families.latest('coco.map.slam.nodes.v1', c.tick);
  const edges = c.session.families.latest('coco.map.slam.edges.v1', c.tick);
  if (nodes && edges) {
    const nx = nodes.columns.x as Num; const ny = nodes.columns.y as Num;
    const from = edges.columns.from_node as Num; const to = edges.columns.to_node as Num; const kind = edges.columns.kind as string[];
    const seq: number[] = []; const loop: number[] = [];
    for (let i = 0; i < from.length; i += 1) {
      const a = from[i]; const b = to[i];
      if (a >= nx.length || b >= nx.length) continue;
      (kind[i] === 'loop' ? loop : seq).push(nx[a], ny[a], nx[b], ny[b]);
    }
    L.segments('graph', seq, 'graphEdge', 0.8);
    if (loop.length) L.segments('graph_loops', loop, 'graphLoop', 1); else L.remove('graph_loops');
    // the last closure: the graph before it was optimised, faint, until the next closure
    const last = c.session.families.before('coco.map.slam.nodes.v1', c.tick).filter((b) => b.scalars.stage === 'optimised').at(-1);
    const raw = last && c.session.families.at('coco.map.slam.nodes.v1', last.tick).find((b) => b.scalars.stage === 'raw');
    if (raw) {
      const rx = raw.columns.x as Num; const ry = raw.columns.y as Num;
      const rs: number[] = [];
      for (let i = 1; i < rx.length; i += 1) rs.push(rx[i - 1], ry[i - 1], rx[i], ry[i]);
      L.segments('graph_before', rs, 'graphNode', 0.3);
    } else L.remove('graph_before');
  } else for (const id of ['graph', 'graph_loops', 'graph_before']) L.remove(id);
  for (const id of ['built_map', 'slam_pose', 'landmarks', 'slam_particles']) L.setVisible(id, c.on(id));
  for (const id of ['graph', 'graph_loops', 'graph_before']) L.setVisible(id, c.on('graph'));
}

function hoverMap(c: DrawContext, x: number, y: number): string | null {
  const lm = c.session.families.latest('coco.map.slam.landmarks.v1', c.tick);
  if (lm && c.on('landmarks')) {
    const lx = lm.columns.x as Num; const ly = lm.columns.y as Num; const id = lm.columns.landmark_id as Num;
    for (let i = 0; i < lx.length; i += 1) {
      if (Math.hypot(lx[i] - x, ly[i] - y) < 0.2) {
        return `landmark ${id[i]} (IDEALISED sensor): (${lx[i].toFixed(2)}, ${ly[i].toFixed(2)}) m, σx ${Math.sqrt((lm.columns.cov_xx as Num)[i]).toFixed(3)} m`;
      }
    }
  }
  const head = c.session.headers.get('coco.map.grid.header.v1');
  const snap = c.session.families.latest('coco.map.grid.snapshot.v1', c.tick);
  if (head && snap && c.on('built_map')) {
    const r = Number(head.resolution);
    const ix = Math.floor((x - Number(head.origin_x)) / r); const iy = Math.floor((y - Number(head.origin_y)) / r);
    const w = Number(head.width);
    if (ix >= 0 && iy >= 0 && ix < w && iy < Number(head.height)) {
      const l = (snap.columns.logodds_f32 as Num)[iy * w + ix];
      if (l !== 0) return `built map cell (${ix}, ${iy}): log-odds ${l.toFixed(2)}, P(occupied) ${(1 / (1 + Math.exp(-l))).toFixed(2)} (keyframe at update ${snap.scalars.update})`;
      return `built map cell (${ix}, ${iy}): never observed`;
    }
  }
  return null;
}

registerDrawer('map', drawMap);
registerHover('map', hoverMap);
