// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.7: the results screen's "what the planner computed" inset (MODEL). It replays, over the
 * level's map, the A* route the model's planner computed for each of the round's orders (the
 * planner ghost, precomputed with the round: coco_lab.games, rules 4) and, beside it, the path
 * COCO actually drove in this run (the model's poses). Drawn once, then the planner's routes
 * are traced out over 2 s; a still image under reduced motion.
 */

import { useEffect, useRef } from 'react';

export interface InsetData {
  map: { width: number; height: number; resolution: number; origin: [number, number] };
  occupancy: Uint8Array;
  planned: [number, number][][];
  driven: [number, number][];
}

/** Metres along a polyline. */
export function pathLength(p: [number, number][]): number {
  let m = 0;
  for (let k = 1; k < p.length; k++) m += Math.hypot(p[k][0] - p[k - 1][0], p[k][1] - p[k - 1][1]);
  return m;
}

/** G2.9 (Gautham's review): the legend lists only lines that are drawn; a drive under this is a speck, not a line. */
export const MIN_DRIVE_M = 0.5;

export function PlannerInset({ d, still }: { d: InsetData; still: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const hasPlan = d.planned.some((p) => p.length >= 2), drove = pathLength(d.driven), hasDrive = drove >= MIN_DRIVE_M;
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const pts = [...d.planned.flat(), ...d.driven];
    if (!pts.length) return;
    const pad = 2;
    const x0 = Math.min(...pts.map((p) => p[0])) - pad, x1 = Math.max(...pts.map((p) => p[0])) + pad;
    const y0 = Math.min(...pts.map((p) => p[1])) - pad, y1 = Math.max(...pts.map((p) => p[1])) + pad;
    const W = c.clientWidth || 320, H = c.clientHeight || 200, dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
    const g = c.getContext('2d')!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const k = Math.min(W / (x1 - x0), H / (y1 - y0));
    const ox = (W - k * (x1 - x0)) / 2, oy = (H - k * (y1 - y0)) / 2;
    const px = (x: number) => ox + (x - x0) * k, py = (y: number) => H - oy - (y - y0) * k;
    // the map (a LabMap: row 0 at the top), occupied cells only
    const { width: mw, height: mh, resolution: r, origin: [mx, my] } = d.map;
    g.fillStyle = '#0b0f16'; g.fillRect(0, 0, W, H);
    g.fillStyle = '#475569';
    const c0 = Math.max(0, Math.floor((x0 - mx) / r)), c1 = Math.min(mw - 1, Math.ceil((x1 - mx) / r));
    const r0 = Math.max(0, Math.floor((my + mh * r - y1) / r)), r1 = Math.min(mh - 1, Math.ceil((my + mh * r - y0) / r));
    for (let row = r0; row <= r1; row++) for (let col = c0; col <= c1; col++) {
      if (d.occupancy[row * mw + col] !== 1) continue;
      const x = mx + col * r, y = my + (mh - 1 - row) * r;
      g.fillRect(px(x), py(y + r), Math.max(1, r * k), Math.max(1, r * k));
    }
    const line = (p: [number, number][], colour: string, width: number, upTo = Infinity) => {
      g.strokeStyle = colour; g.lineWidth = width; g.lineJoin = 'round'; g.beginPath();
      p.slice(0, Math.max(2, upTo)).forEach(([x, y], i) => (i ? g.lineTo(px(x), py(y)) : g.moveTo(px(x), py(y))));
      g.stroke();
    };
    const total = d.planned.reduce((s, p) => s + p.length, 0);
    let raf = 0;
    const t0 = performance.now();
    const draw = () => {
      const f = still ? 1 : Math.min(1, (performance.now() - t0) / 2000);
      let left = Math.ceil(f * total);
      for (const p of d.planned) { if (left <= 0) break; line(p, '#22d3ee', 2.5, left); left -= p.length; }
      // the drive on top, thinner, so it shows where it runs along the planned route
      if (hasDrive) line(d.driven, 'rgba(255,122,26,.95)', 1.75);
      if (f < 1) raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [d, still, hasDrive]);
  return <figure className="g2-inset g1-glass" data-testid="g2-planner-inset">
    <canvas ref={ref} aria-label={`The planner's routes for this round${hasPlan ? ' (cyan)' : ''}${hasDrive ? ' and the path COCO drove (orange)' : ''}, on the map`} />
    <figcaption data-testid="g2-inset-legend"><b>MODEL</b> What the planner computed{hasPlan && <>: its A* route for each order <i className="k cy" /></>}
      {hasDrive ? <> · your drive <i className="k or" /></> : <> · COCO drove {drove.toFixed(1)} m (too short to draw)</>}</figcaption>
  </figure>;
}
