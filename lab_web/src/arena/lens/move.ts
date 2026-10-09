// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Move lens's drawing (M2.5): what the local controller considered
 * this cycle -- every candidate trajectory it scored (valid ones shaded by
 * cost, rejected ones in their own colour), the one it chose, RPP's
 * lookahead point, the 3 x 3 m local window around the robot's BELIEVED
 * pose -- plus the path it was given whole (a Lab 5 scenario's frozen
 * path) and the actors' bodies. All read from coco_lab.move_arena's
 * batches and the tick; MODEL throughout.
 */

import { registerDrawer, registerHover, type DrawContext } from './draw';

type Num = ArrayLike<number>;
/** The model's local window (coco_lab.control.WindowParams). */
const WINDOW = 3.0;
const RES = 0.05;

function trajSegments(cols: Record<string, unknown>, rows: number[]): number[] {
  const off = cols.traj_offset as Num; const len = cols.traj_len as Num;
  const tx = cols.traj_x as Num; const ty = cols.traj_y as Num;
  const out: number[] = [];
  for (const k of rows) {
    for (let j = 1; j < len[k]; j += 1) {
      const a = off[k] + j - 1;
      out.push(tx[a], ty[a], tx[a + 1], ty[a + 1]);
    }
  }
  return out;
}

/** The latest candidate batch at or before the tick that `keep` accepts (a recorded drive interleaves two kinds). */
function latestWhere(c: DrawContext, keep: (controller: string) => boolean) {
  const all = c.session.families.before('coco.control.local.candidates.v1', c.tick);
  for (let i = all.length - 1; i >= 0; i -= 1) if (keep(String(all[i].scalars.controller_id ?? ''))) return all[i];
  return null;
}

function drawMove(c: DrawContext) {
  const L = c.layers;
  const rec = c.session.recordAt(c.tick) ?? c.session.shownTick;
  // a STACK drive (M2.7) sends Nav2's sampled candidates and, as "<run>/chosen", the trajectory it chose each cycle
  const cand = latestWhere(c, (id) => !id.endsWith('/chosen'));
  const stackChosen = latestWhere(c, (id) => id.endsWith('/chosen'));
  const cmd = c.session.families.latest('coco.control.local.command.v1', c.tick);
  if (cand) {
    const cols = cand.columns; const valid = cols.valid as ArrayLike<boolean | number>; const cost = cols.cost as Num;
    const chosen = cmd ? (cmd.columns.chosen as Num)[0] : -1;
    const ok: number[] = []; const bad: number[] = [];
    let lo = Infinity; let hi = -Infinity;
    for (let k = 0; k < valid.length; k += 1) {
      if (k === chosen) continue;
      if (valid[k]) { ok.push(k); lo = Math.min(lo, cost[k]); hi = Math.max(hi, cost[k]); } else bad.push(k);
    }
    // shade by cost: the cheapest darkest, so the eye finds what the critics preferred
    const shade: number[] = [];
    for (const k of ok) {
      const s = hi > lo ? (cost[k] - lo) / (hi - lo) : 0;
      const n = Math.max(0, (cols.traj_len as Num)[k] - 1);
      for (let j = 0; j < n; j += 1) shade.push(s);
    }
    if (ok.length) L.segments('candidates', trajSegments(cols, ok), 'candidate', L.alpha('candidateAlpha'), shade); else L.remove('candidates');
    if (bad.length) L.segments('rejected', trajSegments(cols, bad), 'rejected', L.alpha('rejectedAlpha')); else L.remove('rejected');
    if (chosen >= 0 && chosen < valid.length && !stackChosen) L.segments('chosen', trajSegments(cols, [chosen]), 'chosen', 1);
    else if (!stackChosen) L.remove('chosen');
  } else { L.remove('candidates'); L.remove('rejected'); if (!stackChosen) L.remove('chosen'); }
  if (stackChosen) L.segments('chosen', trajSegments(stackChosen.columns, [0]), 'chosen', 1);
  if (cmd) {
    const lx = (cmd.columns.lookahead_x as Num)[0]; const ly = (cmd.columns.lookahead_y as Num)[0];
    if (Number.isFinite(lx)) L.points('lookahead', [lx], [ly], 'lookahead', 1, 0.06); else L.remove('lookahead');
  } else L.remove('lookahead');
  if (rec && c.session.headers.get('coco.control.local.header.v1')) {
    const [bx, by] = rec.pose;
    const ox = Math.floor((bx - WINDOW / 2) / RES) * RES; const oy = Math.floor((by - WINDOW / 2) / RES) * RES;
    const x1 = ox + WINDOW; const y1 = oy + WINDOW;
    L.segments('local_window', [ox, oy, x1, oy, x1, oy, x1, y1, x1, y1, ox, y1, ox, y1, ox, oy], 'localWindow', 0.8);
  } else L.remove('local_window');
  const actors = rec?.actors ?? [];
  if (actors.length) {
    L.points('actors', actors.map((a) => a[0]), actors.map((a) => a[1]), 'actor', 0.85, 0.15, actors.map((a) => a[2]));
  } else L.remove('actors');
  const given = c.session.givenPaths.filter((p) => p.tick <= c.tick).at(-1);
  if (given) {
    const xy = given.xy; const seg: number[] = [];
    for (let i = 2; i < xy.length; i += 2) seg.push(xy[i - 2], xy[i - 1], xy[i], xy[i + 1]);
    L.segments('given_path', seg, 'path', 0.9);
  } else L.remove('given_path');
  for (const id of ['candidates', 'rejected', 'chosen', 'lookahead', 'local_window', 'actors', 'given_path']) L.setVisible(id, c.on(id));
}

function hoverMove(c: DrawContext, x: number, y: number): string | null {
  const rec = c.session.recordAt(c.tick);
  for (const a of rec?.actors ?? []) {
    if (Math.hypot(a[0] - x, a[1] - y) < a[2] + 0.05) return `actor at (${a[0].toFixed(2)}, ${a[1].toFixed(2)}), body radius ${a[2].toFixed(2)} m — solid in the Arena (Lab 5's Gazebo actors had no collision body)`;
  }
  const cand = c.session.families.latest('coco.control.local.candidates.v1', c.tick);
  if (!cand || !(c.on('candidates') || c.on('rejected'))) return null;
  const cols = cand.columns; const off = cols.traj_offset as Num; const len = cols.traj_len as Num;
  const tx = cols.traj_x as Num; const ty = cols.traj_y as Num;
  let best = 0.12; let bk = -1;
  for (let k = 0; k < len.length; k += 1) {
    if (!len[k]) continue;
    const e = off[k] + len[k] - 1;
    const d = Math.hypot(tx[e] - x, ty[e] - y);
    if (d < best) { best = d; bk = k; }
  }
  if (bk < 0) return null;
  const head = c.session.headers.get('coco.control.local.header.v1');
  const critics = (head?.critics as string[] | undefined) ?? [];
  const sc = cols.critic_scores as Num; const stride = critics.length;
  const v = (cols.v as Num)[bk]; const w = (cols.w as Num)[bk];
  const rej = (cols.rejection as string[])[bk];
  if (rej) return `candidate ${bk}: v ${v.toFixed(2)} m/s, w ${w.toFixed(2)} rad/s — rejected: ${rej.replace('_', ' ')}`;
  const parts = critics.map((n, i) => `${n} ${Number(sc[bk * stride + i]).toFixed(1)}`).join(', ');
  return `candidate ${bk}: v ${v.toFixed(2)} m/s, w ${w.toFixed(2)} rad/s, cost ${(cols.cost as Num)[bk].toFixed(1)}${parts ? ` (${parts})` : ''}`;
}

registerDrawer('move', drawMove);
registerHover('move', hoverMove);
