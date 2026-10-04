// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import { makeLayer, putRGBA } from '../../render/draw';
import { buildMapRGBA } from '../../render/layers';
import type { DecodedLocBundle } from '../../loc/decode';
import {
  ellipse, estimateAt, kidnapUpdate, runStyle, scanEndpoints, truthAtUpdate, TRUTH_COLOR,
} from '../../loc/view';

export interface LocCanvasProps {
  bundle: DecodedLocBundle;
  k: number;
  /** runs whose estimate (trail, pose, ellipse) is drawn */
  runs: string[];
  /** the run whose particles and scan are drawn */
  focus: string | null;
  showTruth: boolean;
  showParticles: boolean;
  scanFrom: 'belief' | 'truth' | 'none';
  /** set: a click on the map reports a map-frame point (the kidnap tool) */
  onPick?: (x: number, y: number) => void;
  pick?: [number, number, number] | null;
  label?: string;
}

/** One Sketch run on the map. Only display: every pose comes from the bundle. */
export function LocCanvas(p: LocCanvasProps) {
  const { bundle: b, k } = p;
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [cssWidth, setCssWidth] = useState(0);
  const { width, height, geo } = b.map;
  const layer = useMemo(() => {
    const l = makeLayer(width, height);
    putRGBA(l, buildMapRGBA(b.map), width, height);
    return l;
  }, [b, width, height]);

  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setCssWidth(el.clientWidth));
    ro.observe(el);
    setCssWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvas.current;
    if (!c || cssWidth === 0 || !geo) return;
    const dpr = window.devicePixelRatio || 1;
    const scale = (cssWidth * dpr) / width; // device px per cell
    c.width = Math.round(width * scale);
    c.height = Math.round(height * scale);
    c.style.width = `${cssWidth}px`;
    c.style.height = `${(cssWidth * height) / width}px`;
    const ctx = c.getContext('2d')!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(layer, 0, 0, c.width, c.height);
    const res = geo.resolution;
    const [ox, oy] = geo.origin;
    const X = (x: number) => ((x - ox) / res) * scale;
    const Y = (y: number) => (height - (y - oy) / res) * scale;
    const px = Math.max(1, dpr);
    const u = b.world.updates;
    const row = u[Math.min(k, u.length - 1)];

    // the route the driver was given
    const sc = b.scenario;
    ctx.setLineDash([3 * px, 4 * px]);
    ctx.strokeStyle = 'rgba(90, 90, 85, 0.6)';
    ctx.lineWidth = px;
    ctx.beginPath();
    ctx.moveTo(X(sc.start[0]), Y(sc.start[1]));
    for (const [x, y] of sc.route) ctx.lineTo(X(x), Y(y));
    ctx.stroke();
    ctx.setLineDash([]);

    // the kidnap: where the robot was taken from and to
    const ku = kidnapUpdate(b);
    if (b.world.kidnapRow !== null && sc.kidnap) {
      const from = b.world.kidnapRow - 1;
      const fx = X(b.world.gtX[from]);
      const fy = Y(b.world.gtY[from]);
      const tx = X(sc.kidnap.to[0]);
      const ty = Y(sc.kidnap.to[1]);
      const done = ku !== null && k >= ku;
      ctx.strokeStyle = done ? '#D55E00' : 'rgba(213, 94, 0, 0.45)';
      ctx.lineWidth = 2 * px;
      ctx.setLineDash([6 * px, 4 * px]);
      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.lineTo(tx, ty);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#D55E00';
      ctx.font = `${12 * px}px system-ui, sans-serif`;
      ctx.fillText('kidnap', (fx + tx) / 2 + 4 * px, (fy + ty) / 2 - 4 * px);
    }
    if (p.pick) {
      ctx.strokeStyle = '#D55E00';
      ctx.lineWidth = 2 * px;
      ctx.beginPath();
      ctx.arc(X(p.pick[0]), Y(p.pick[1]), 7 * px, 0, 2 * Math.PI);
      ctx.stroke();
    }

    // the focused run's particles, by weight
    const focus = p.focus ? b.runs.find((r) => r.id === p.focus) : undefined;
    if (p.showParticles && focus?.particles && k < focus.n) {
      const pt = focus.particles;
      const lo = pt.offset[k];
      const hi = pt.offset[k + 1];
      let wmax = 0;
      for (let i = lo; i < hi; i++) wmax = Math.max(wmax, pt.w[i]);
      ctx.fillStyle = runStyle(focus.id).color;
      const r0 = 1.6 * px;
      for (let i = lo; i < hi; i++) {
        const a = wmax > 0 ? 0.15 + 0.85 * (pt.w[i] / wmax) : 0.5;
        ctx.globalAlpha = a;
        const x = X(pt.x[i]);
        const y = Y(pt.y[i]);
        ctx.fillRect(x - r0, y - r0, 2 * r0, 2 * r0);
      }
      ctx.globalAlpha = 1;
    }

    // the scan, placed at the belief (or the truth)
    if (p.scanFrom !== 'none' && k < u.length) {
      const pose = p.scanFrom === 'truth' || !focus ? truthAtUpdate(b, k) : estimateAt(focus, k);
      ctx.fillStyle = p.scanFrom === 'truth' ? TRUTH_COLOR : '#D55E00';
      for (const [x, y] of scanEndpoints(b, k, pose)) ctx.fillRect(X(x) - 1.5 * px, Y(y) - 1.5 * px, 3 * px, 3 * px);
    }

    // the truth: trail and pose
    const pose = (x: number, y: number, th: number, color: string, size: number) => {
      ctx.fillStyle = color;
      ctx.strokeStyle = '#000';
      ctx.lineWidth = px;
      ctx.beginPath();
      const s = size * px;
      ctx.moveTo(X(x) + s * Math.cos(th), Y(y) - s * Math.sin(th));
      ctx.lineTo(X(x) + s * 0.6 * Math.cos(th + 2.5), Y(y) - s * 0.6 * Math.sin(th + 2.5));
      ctx.lineTo(X(x) + s * 0.6 * Math.cos(th - 2.5), Y(y) - s * 0.6 * Math.sin(th - 2.5));
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    };
    if (p.showTruth) {
      ctx.strokeStyle = TRUTH_COLOR;
      ctx.lineWidth = 2 * px;
      ctx.beginPath();
      const kr = b.world.kidnapRow;
      for (let i = 0; i <= row; i++) {
        if (i === 0 || i === kr) ctx.moveTo(X(b.world.gtX[i]), Y(b.world.gtY[i]));
        else ctx.lineTo(X(b.world.gtX[i]), Y(b.world.gtY[i]));
      }
      ctx.stroke();
      pose(b.world.gtX[row], b.world.gtY[row], b.world.gtYaw[row], TRUTH_COLOR, 11);
    }

    // each run's belief: trail, ellipse, pose
    for (const id of p.runs) {
      const r = b.runs.find((x) => x.id === id);
      if (!r || k >= r.n) continue;
      const color = runStyle(id).color;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2 * px;
      ctx.beginPath();
      for (let i = 0; i <= k; i++) {
        const x = X(r.cols.est_x[i]);
        const y = Y(r.cols.est_y[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      const e = ellipse(r.cols.cov_xx[k], r.cols.cov_xy[k], r.cols.cov_yy[k]);
      ctx.beginPath();
      ctx.ellipse(X(r.cols.est_x[k]), Y(r.cols.est_y[k]), Math.max(px, (e.rx / res) * scale),
        Math.max(px, (e.ry / res) * scale), -e.angle, 0, 2 * Math.PI);
      ctx.stroke();
      pose(r.cols.est_x[k], r.cols.est_y[k], r.cols.est_yaw[k], color, 10);
    }
  }, [b, k, p.runs, p.focus, p.showTruth, p.showParticles, p.scanFrom, p.pick, cssWidth, layer, width, height, geo]);

  const onClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!p.onPick || !geo) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const fx = (e.clientX - rect.left) / rect.width;
    const fy = (e.clientY - rect.top) / rect.height;
    const x = geo.origin[0] + fx * width * geo.resolution;
    const y = geo.origin[1] + (1 - fy) * height * geo.resolution;
    p.onPick(x, y);
  };

  return (
    <figure className="loc-figure">
      {p.label && <figcaption>{p.label}</figcaption>}
      <div className="map-wrap" ref={wrap}>
        <canvas ref={canvas} className={p.onPick ? 'map-canvas editable' : 'map-canvas'} onClick={onClick}
          role="img" aria-label={`Sketch map at update ${k + 1} of ${b.world.updates.length}`} data-testid="loc-canvas" />
      </div>
    </figure>
  );
}
