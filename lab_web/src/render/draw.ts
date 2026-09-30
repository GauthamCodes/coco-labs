// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Canvas 2D composition. The two 1-px-per-cell layers (map, trace state)
 * live on offscreen canvases and are scaled up with smoothing OFF, so a
 * cell is a crisp square; vectors (path, overlays, markers) are drawn in
 * cell units on top. Only display state is drawn -- nothing is computed.
 */

import type { DecodedBundle } from '../bundle/model';
import type { Overlay } from './overlays';
import { PALETTE } from './palette';

/** A brush stroke being drawn, before coco_lab has applied it. */
export interface Preview {
  value: 'occupied' | 'free';
  cells: Array<[number, number]>;
}

export interface Scene {
  bundle: DecodedBundle;
  mapLayer: HTMLCanvasElement | OffscreenCanvas;
  traceLayer: HTMLCanvasElement | OffscreenCanvas;
  path: Array<[number, number]>; // [row, col] cells, in order
  overlays: Overlay[];
  hover: [number, number] | null;
  /** The robot's footprint along the path, pre-rendered (renderSweepLayer). */
  sweepLayer?: HTMLCanvasElement | null;
  preview?: Preview | null;
}

export function makeLayer(width: number, height: number): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = width;
  c.height = height;
  return c;
}

export function putRGBA(layer: HTMLCanvasElement | OffscreenCanvas, rgba: Uint8ClampedArray,
  width: number, height: number): void {
  const ctx = layer.getContext('2d') as CanvasRenderingContext2D;
  ctx.putImageData(new ImageData(rgba as Uint8ClampedArray<ArrayBuffer>, width, height), 0, 0);
}

const OVERLAY_STYLE: Record<string, { color: string; width: number; dash: number[] }> = {
  gt: { color: PALETTE.groundTruth, width: 2.5, dash: [] },
  amcl: { color: PALETTE.amcl, width: 2.5, dash: [] },
  plan: { color: PALETTE.plan, width: 1.5, dash: [6, 4] },
};

/** Draw `scene` onto `ctx`, which is `scale` device pixels per cell. */
export function drawScene(ctx: CanvasRenderingContext2D, s: Scene, scale: number): void {
  const { width, height } = s.bundle.map;
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(s.mapLayer as CanvasImageSource, 0, 0, width * scale, height * scale);
  ctx.drawImage(s.traceLayer as CanvasImageSource, 0, 0, width * scale, height * scale);
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  const px = 1 / scale; // one device pixel, in cell units

  // the footprint swept along the path, rendered once per bundle and size
  // (renderSweepLayer) -- a frame only blits it
  if (s.sweepLayer && s.sweepLayer.width === ctx.canvas.width && s.sweepLayer.height === ctx.canvas.height) {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(s.sweepLayer, 0, 0);
    ctx.restore();
  }

  // a stroke being painted, before coco_lab has applied it
  if (s.preview) {
    ctx.fillStyle = s.preview.value === 'occupied' ? 'rgba(0, 0, 0, 0.55)' : 'rgba(255, 255, 255, 0.75)';
    for (const [r, c] of s.preview.cells) ctx.fillRect(c, r, 1, 1);
  }

  // the search's path, as stored in the trace
  if (s.path.length > 1) {
    // a black casing so the line reads over its own (vermillion) path cells
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    const pts = s.path.map(([r, c]) => [c + 0.5, r + 0.5] as [number, number]);
    const w = Math.max(2 * px, 0.18);
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = w + 2 * px;
    strokePoints(ctx, pts);
    ctx.strokeStyle = PALETTE.path;
    ctx.lineWidth = w;
    strokePoints(ctx, pts);
  }

  // recorded-run overlays (placed ones only; refusals are reported in text)
  for (const o of s.overlays) {
    if (!o.placed || o.points.length === 0) continue;
    const st = OVERLAY_STYLE[o.group];
    ctx.setLineDash(st.dash.map((d) => d * px));
    if (o.group === 'amcl') {
      // yellow needs an outline to read on white
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = (st.width + 2) * px;
      strokePoints(ctx, o.points);
    }
    ctx.strokeStyle = st.color;
    ctx.lineWidth = st.width * px;
    strokePoints(ctx, o.points);
    ctx.setLineDash([]);
  }

  // start and goal markers
  const marker = (cell: [number, number], color: string, shape: 'circle' | 'diamond') => {
    const [r, c] = cell;
    const rad = Math.max(0.45, 7 * px);
    ctx.fillStyle = color;
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1.5 * px;
    ctx.beginPath();
    if (shape === 'circle') ctx.arc(c + 0.5, r + 0.5, rad, 0, 2 * Math.PI);
    else {
      ctx.moveTo(c + 0.5, r + 0.5 - rad);
      ctx.lineTo(c + 0.5 + rad, r + 0.5);
      ctx.lineTo(c + 0.5, r + 0.5 + rad);
      ctx.lineTo(c + 0.5 - rad, r + 0.5);
      ctx.closePath();
    }
    ctx.fill();
    ctx.stroke();
  };
  marker(s.bundle.run.start, PALETTE.start, 'circle');
  marker(s.bundle.run.goal, PALETTE.goal, 'diamond');

  if (s.hover) {
    const [r, c] = s.hover;
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 2 * px;
    ctx.strokeRect(c, r, 1, 1);
  }
  ctx.restore();
}

/**
 * The swept footprint as one device-sized layer: the UNION of the
 * rectangles, lightened and outlined, so it reads as the area the robot
 * covers. One nonzero fill on a mask (so overlaps are not darker), then an
 * outline made by offsetting the mask a device pixel each way and cutting
 * its interior out -- the union's edge, without the rectangles' inner
 * edges. Built outside the frame loop: it costs tens of ms (measured: done
 * lazily inside a frame, it dropped frames that 1D did not).
 */
export function renderSweepLayer(polys: Array<Array<[number, number]>>, scale: number,
  w: number, h: number): HTMLCanvasElement {
  const sweepMask = document.createElement('canvas');
  const sweepRing = document.createElement('canvas');
  const out = document.createElement('canvas');
  for (const c of [sweepMask, sweepRing, out]) {
    c.width = w;
    c.height = h;
  }
  const m = sweepMask.getContext('2d')!;
  m.setTransform(scale, 0, 0, scale, 0, 0);
  m.beginPath();
  for (const poly of polys) {
    poly.forEach(([x, y], i) => (i ? m.lineTo(x, y) : m.moveTo(x, y)));
    m.closePath();
  }
  m.fillStyle = '#ffffff';
  m.fill('nonzero');

  const r = sweepRing.getContext('2d')!;
  const d = Math.max(1.5, Math.min(3, scale / 3));
  for (const [dx, dy] of [[-d, 0], [d, 0], [0, -d], [0, d]]) r.drawImage(sweepMask, dx, dy);
  r.globalCompositeOperation = 'source-in';
  r.fillStyle = PALETTE.sweepEdge;
  r.fillRect(0, 0, w, h);
  r.globalCompositeOperation = 'destination-out';
  r.drawImage(sweepMask, 0, 0);
  r.globalCompositeOperation = 'source-over';

  const o = out.getContext('2d')!;
  o.globalAlpha = 0.45;
  o.drawImage(sweepMask, 0, 0); // lighten what the robot covers
  o.globalAlpha = 1;
  o.drawImage(sweepRing, 0, 0);
  return out;
}

function strokePoints(ctx: CanvasRenderingContext2D, pts: Array<[number, number]>): void {
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.stroke();
}
