// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Drawing the live arena: occupancy grid, world geometry, plans, poses.
 * Map frame is x right, y UP; the canvas is y down. `fit` is the one place
 * that conversion lives, and the click-to-goal path uses its inverse.
 */

import type { Belief, Goal, MapFrame, Pose2D, World } from './protocol';

export interface View { scale: number; ox: number; oy: number }

/** Fit the grid's extent to a canvas, keeping aspect. */
export function fit(m: Pick<MapFrame, 'width' | 'height' | 'resolution' | 'origin'>, cw: number, ch: number): View {
  const wm = m.width * m.resolution;
  const hm = m.height * m.resolution;
  const scale = Math.min(cw / wm, ch / hm);
  const ox = (cw - wm * scale) / 2 - m.origin.x * scale;
  const oy = (ch + hm * scale) / 2 + m.origin.y * scale;
  return { scale, ox, oy };
}

export const toCanvas = (v: View, x: number, y: number): [number, number] => [v.ox + x * v.scale, v.oy - y * v.scale];
export const toMap = (v: View, px: number, py: number): [number, number] => [(px - v.ox) / v.scale, (v.oy - py) / v.scale];

/** Decode the base64 int8 grid into an RGBA image, once per map frame. */
export function gridImage(m: MapFrame, dark: boolean): ImageData {
  const raw = atob(m.data);
  const img = new ImageData(m.width, m.height);
  for (let j = 0; j < m.height; j++) {
    for (let i = 0; i < m.width; i++) {
      const v = raw.charCodeAt(j * m.width + i);
      const occ = v === 255 ? -1 : v; // -1 unknown arrives as byte 255
      const shade = occ < 0 ? (dark ? 40 : 205) : occ >= 50 ? (dark ? 230 : 30) : (dark ? 22 : 250);
      const k = ((m.height - 1 - j) * m.width + i) * 4; // row 0 is the BOTTOM
      img.data[k] = img.data[k + 1] = img.data[k + 2] = shade;
      img.data[k + 3] = 255;
    }
  }
  return img;
}

export interface Scene {
  map: MapFrame | null; grid: ImageBitmap | HTMLCanvasElement | null;
  world: World | null | undefined;
  path: [number, number][]; local: [number, number][];
  pose: Pose2D | null; belief: Belief | null | undefined;
  truth: Pose2D | null | undefined; showTruth: boolean;
  goal: Goal | null | undefined; colours: Record<string, string>;
}

export function draw(ctx: CanvasRenderingContext2D, s: Scene, cw: number, ch: number, ink: string): View | null {
  ctx.clearRect(0, 0, cw, ch);
  if (!s.map) return null;
  const v = fit(s.map, cw, ch);
  const res = s.map.resolution;
  if (s.grid) {
    const [x0, y1] = toCanvas(v, s.map.origin.x, s.map.origin.y + s.map.height * res);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(s.grid, x0, y1, s.map.width * res * v.scale, s.map.height * res * v.scale);
  }
  const rect = (x0: number, x1: number, yc: number, w: number, fill: string) => {
    const [a, b] = toCanvas(v, x0, yc + w / 2);
    ctx.fillStyle = fill;
    ctx.fillRect(a, b, (x1 - x0) * v.scale, w * v.scale);
  };
  const w = s.world;
  if (w) {
    for (const bay of w.bays ?? []) {
      rect(bay.ramp.x0, bay.ramp.x1, bay.y, bay.width, 'rgba(230,159,0,0.22)');
      rect(bay.platform.x0, bay.platform.x1, bay.y, bay.width, 'rgba(230,159,0,0.38)');
      rect(bay.descent.x0, bay.descent.x1, bay.y, bay.width, 'rgba(230,159,0,0.22)');
    }
    for (const t of w.targets) {
      const [px, py] = toCanvas(v, t.x, t.y);
      ctx.fillStyle = s.colours[t.colour] ?? t.colour;
      ctx.beginPath();
      ctx.arc(px, py, Math.max(3, t.diameter * v.scale), 0, 2 * Math.PI);
      ctx.fill();
    }
    const [hx, hy] = toCanvas(v, w.home.x, w.home.y);
    ctx.strokeStyle = ink;
    ctx.strokeRect(hx - 6, hy - 6, 12, 12);
  }
  const line = (pts: [number, number][], colour: string, width: number) => {
    if (pts.length < 2) return;
    ctx.strokeStyle = colour;
    ctx.lineWidth = width;
    ctx.beginPath();
    pts.forEach(([x, y], i) => {
      const [px, py] = toCanvas(v, x, y);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.stroke();
    ctx.lineWidth = 1;
  };
  line(s.path, '#0072b2', 2.5);
  line(s.local, '#d55e00', 3);
  if (s.goal) {
    const [gx, gy] = toCanvas(v, s.goal.x, s.goal.y);
    ctx.strokeStyle = '#cc79a7';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(gx - 7, gy - 7); ctx.lineTo(gx + 7, gy + 7);
    ctx.moveTo(gx + 7, gy - 7); ctx.lineTo(gx - 7, gy + 7);
    ctx.stroke();
    ctx.lineWidth = 1;
  }
  if (s.showTruth && s.truth) robot(ctx, v, s.truth, 'rgba(0,158,115,0.9)', true);
  if (s.belief && s.belief.cov_xx !== null && s.belief.cov_yy !== null) {
    const [bx, by] = toCanvas(v, s.belief.x, s.belief.y);
    ctx.strokeStyle = 'rgba(255,140,42,0.8)';
    ctx.beginPath();
    ctx.ellipse(bx, by, Math.max(2, 2 * Math.sqrt(Math.max(0, s.belief.cov_xx)) * v.scale),
      Math.max(2, 2 * Math.sqrt(Math.max(0, s.belief.cov_yy)) * v.scale), 0, 0, 2 * Math.PI);
    ctx.stroke();
  }
  if (s.pose) robot(ctx, v, s.pose, '#ff8c2a', false);
  return v;
}

function robot(ctx: CanvasRenderingContext2D, v: View, p: Pose2D, colour: string, ghost: boolean) {
  const [px, py] = toCanvas(v, p.x, p.y);
  ctx.save();
  ctx.translate(px, py);
  ctx.rotate(-p.yaw);
  ctx.beginPath();
  ctx.moveTo(11, 0); ctx.lineTo(-7, 7); ctx.lineTo(-7, -7); ctx.closePath();
  if (ghost) {
    ctx.setLineDash([3, 2]);
    ctx.strokeStyle = colour;
    ctx.lineWidth = 2;
    ctx.stroke();
  } else {
    ctx.fillStyle = colour;
    ctx.fill();
  }
  ctx.restore();
}
