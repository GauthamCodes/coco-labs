// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Decide lens's drawing (M2.6): COCO's four bays, each filled by the
 * robot's belief that the target is there (fill = probability), the bay
 * it chose outlined, and every look it made -- found or missed -- at the
 * place it BELIEVED it looked from. All read from coco_lab.mission_arena's
 * batches and the search header's geometry; MODEL throughout.
 */

import { registerDrawer, registerHover, type DrawContext } from './draw';

type Num = ArrayLike<number>;

interface Bay { id: string; label: string; rect: [number, number, number, number]; approach: [number, number] }

export function bays(c: DrawContext): Bay[] {
  const head = c.session.headers.get('coco.decide.search.header.v1');
  if (!head) return [];
  const params = (head.params ?? {}) as Record<string, unknown>;
  return ((head.region_ids as string[] | undefined) ?? []).map((id) => {
    const r = String(params[`${id}.platform`] ?? '0,0,0,0').split(',').map(Number) as [number, number, number, number];
    const a = String(params[`${id}.approach`] ?? '0,0').split(',').map(Number) as [number, number];
    return { id, label: String(params[`${id}.label`] ?? id), rect: r, approach: a };
  });
}

const square = ([x0, x1, y0, y1]: [number, number, number, number]): [number, number][] => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];

function outline(rects: [number, number, number, number][]): number[] {
  const out: number[] = [];
  for (const r of rects) {
    const p = square(r);
    for (let i = 0; i < 4; i += 1) out.push(p[i][0], p[i][1], p[(i + 1) % 4][0], p[(i + 1) % 4][1]);
  }
  return out;
}

function drawDecide(c: DrawContext) {
  const L = c.layers;
  const bs = bays(c);
  if (!bs.length) { for (const id of ['bays', 'belief', 'chosen_bay', 'detection']) L.remove(id); return; }
  L.segments('bays', outline(bs.map((b) => b.rect)), 'bay', 0.9);
  const bel = c.session.families.latest('coco.decide.search.belief.v1', c.tick);
  if (bel) {
    const p = bel.columns.probability as Num;
    L.polygons('belief', bs.map((b) => square(b.rect)), 'belief', bs.map((_, i) => Math.max(0.03, p[i] * L.alpha('beliefAlpha') * 1.6)));
  } else L.remove('belief');
  const act = c.session.families.latest('coco.decide.search.action.v1', c.tick);
  if (act) {
    const i = (act.columns.region as Num)[0];
    L.segments('chosen_bay', outline([bs[i].rect]), 'chosen', 1);
  } else L.remove('chosen_bay');
  const looks = c.session.families.before('coco.decide.search.observation.v1', c.tick);
  if (looks.length) {
    const xs: number[] = []; const ys: number[] = []; const r: number[] = [];
    for (const o of looks) {
      const i = (o.columns.region as Num)[0];
      xs.push(bs[i].approach[0]); ys.push(bs[i].approach[1]);
      r.push((o.columns.found as ArrayLike<boolean | number>)[0] ? 0.22 : 0.1);
    }
    L.points('detection', xs, ys, 'detection', 0.9, 0.1, r);
  } else L.remove('detection');
  L.setVisible('bays', c.on('bays'));
  L.setVisible('belief', c.on('belief'));
  L.setVisible('chosen_bay', c.on('belief'));
  L.setVisible('detection', c.on('detection'));
}

function hoverDecide(c: DrawContext, x: number, y: number): string | null {
  const bs = bays(c);
  const bel = c.session.families.latest('coco.decide.search.belief.v1', c.tick);
  const head = c.session.headers.get('coco.decide.search.header.v1');
  for (let i = 0; i < bs.length; i += 1) {
    const [x0, x1, y0, y1] = bs[i].rect;
    if (x >= x0 && x <= x1 && y >= y0 && y <= y1) {
      const p = bel ? (bel.columns.probability as Num)[i] : NaN;
      const looked = c.session.families.before('coco.decide.search.observation.v1', c.tick)
        .filter((o) => (o.columns.region as Num)[0] === i).length;
      return `${bs[i].label}: P(target here) ${(100 * p).toFixed(1)} %, looked ${looked}× — a miss is evidence, not proof (d = ${head?.detection} is an ${head?.detection_label})`;
    }
  }
  return null;
}

registerDrawer('decide', drawDecide);
registerHover('decide', hoverDecide);
