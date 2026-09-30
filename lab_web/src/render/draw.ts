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

export interface Scene {
  bundle: DecodedBundle;
  mapLayer: HTMLCanvasElement | OffscreenCanvas;
  traceLayer: HTMLCanvasElement | OffscreenCanvas;
  path: Array<[number, number]>; // [row, col] cells, in order
  overlays: Overlay[];
  hover: [number, number] | null;
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

function strokePoints(ctx: CanvasRenderingContext2D, pts: Array<[number, number]>): void {
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.stroke();
}
