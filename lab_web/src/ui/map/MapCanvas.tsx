// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import { makeLayer, putRGBA } from '../../render/draw';
import { snapshotAt, type DecodedSlamBundle } from '../../map/decode';
import {
  diffRGBA, edgesUpTo, ellipse, estimateAt, externalAt, finalAt, landmarksAt, observationsAt,
  occupancyRGBA, particlesAt, runStyle, scanEndpoints, truthAtUpdate, truthRGBA, TRUTH_COLOR, type Pose,
} from '../../map/view';

export interface MapShow {
  truth: boolean;      // the truth: trail, pose, true landmarks
  map: boolean;        // the run's occupancy map at this moment
  diff: boolean;       // coco_lab's final map-vs-truth classes
  rays: boolean;       // the scan, placed at the run's belief
  particles: boolean;
  landmarks: boolean;
  graph: boolean;
  final: boolean;      // the trajectory as finally believed (dashed)
}

export interface MapCanvasProps {
  bundle: DecodedSlamBundle;
  k: number;
  /** the coco_lab run (or external run, Replay) whose map and belief are drawn */
  focus: string;
  show: MapShow;
  /** the learner's waypoints, and the drive coco_lab planned through them */
  clicks?: Array<[number, number]>;
  route?: Array<[number, number]> | null;
  onPick?: (x: number, y: number) => void;
  label?: string;
}

/** One map bundle's world and one run on it. Display only: everything comes from the bundle. */
export function MapCanvas(p: MapCanvasProps) {
  const { bundle: b, k, show } = p;
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [cssWidth, setCssWidth] = useState(0);
  const { width, height, geo } = b.map;
  const run = b.runs.find((r) => r.id === p.focus) ?? null;
  const ext = run ? null : b.external.find((e) => e.id === p.focus) ?? null;

  const truthLayer = useMemo(() => {
    const l = makeLayer(width, height);
    putRGBA(l, truthRGBA(b.map.occupancy), width, height);
    return l;
  }, [b, width, height]);
  const snap = run ? snapshotAt(run, k) : 0;
  const mapLayer = useMemo(() => {
    if (run) {
      const l = makeLayer(run.grid.width, run.grid.height);
      putRGBA(l, occupancyRGBA(run.maps[snap]), run.grid.width, run.grid.height);
      return l;
    }
    if (ext) {
      const l = makeLayer(ext.grid.width, ext.grid.height);
      putRGBA(l, occupancyRGBA(ext.cells), ext.grid.width, ext.grid.height);
      return l;
    }
    return null;
  }, [run, ext, snap]);
  const diffLayer = useMemo(() => {
    const d = run ? run.arrays['score.diff'] as Uint8Array : ext?.diff;
    if (!d) return null;
    const l = makeLayer(width, height);
    putRGBA(l, diffRGBA(d), width, height);
    return l;
  }, [run, ext, width, height]);

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
    const scale = (cssWidth * dpr) / width; // device px per truth cell
    c.width = Math.round(width * scale);
    c.height = Math.round(height * scale);
    c.style.width = `${cssWidth}px`;
    c.style.height = `${(cssWidth * height) / width}px`;
    const ctx = c.getContext('2d')!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.imageSmoothingEnabled = false;
    const res = geo.resolution;
    const [ox, oy] = geo.origin;
    const sp = scale / res; // device px per metre
    const X = (x: number) => (x - ox) * sp;
    const Y = (y: number) => (height * res - (y - oy)) * sp;
    const px = Math.max(1, dpr);
    const u = b.world.updates;
    const kk = Math.min(k, u.length - 1);
    const row = u[kk];

    ctx.drawImage(truthLayer, 0, 0, c.width, c.height);
    // the run's map: drawn in its own grid, placed by its geometry (and, for a
    // ROS backend, by the rigid alignment coco_lab scored it with)
    if (show.map && mapLayer) {
      const g = run ? run.grid : ext!.grid;
      const T: [number, number, number] = ext ? ext.summary.ate_online.alignment : [0, 0, 0];
      const co = Math.cos(T[2]);
      const si = Math.sin(T[2]);
      const er = g.resolution;
      const top = g.origin[1] + g.height * er;
      ctx.save();
      ctx.setTransform(sp * co * er, -sp * si * er, sp * si * er, sp * co * er,
        sp * (T[0] + co * g.origin[0] - si * top - ox),
        sp * (height * res + oy - (T[1] + si * g.origin[0] + co * top)));
      ctx.globalAlpha = 0.92;
      ctx.drawImage(mapLayer, 0, 0);
      ctx.restore();
    }
    if (show.diff && diffLayer) {
      ctx.globalAlpha = 0.9;
      ctx.drawImage(diffLayer, 0, 0, c.width, c.height);
      ctx.globalAlpha = 1;
    }

    // the drive: planned route (dashed) and the learner's waypoints
    if (p.route && p.route.length) {
      ctx.setLineDash([3 * px, 4 * px]);
      ctx.strokeStyle = 'rgba(90, 90, 85, 0.7)';
      ctx.lineWidth = px;
      ctx.beginPath();
      ctx.moveTo(X(b.world.start[0]), Y(b.world.start[1]));
      for (const [x, y] of p.route) ctx.lineTo(X(x), Y(y));
      ctx.stroke();
      ctx.setLineDash([]);
    }
    if (p.clicks) {
      ctx.font = `${11 * px}px system-ui, sans-serif`;
      p.clicks.forEach(([x, y], i) => {
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#333';
        ctx.lineWidth = px;
        ctx.beginPath();
        ctx.arc(X(x), Y(y), 7 * px, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#333';
        ctx.fillText(String(i + 1), X(x) - 3.5 * px, Y(y) + 4 * px);
      });
    }

    // the pose graph: its edges, loop closures thick
    if (show.graph && run && run.algorithm === 'pose_graph') {
      const at = (i: number) => (show.final && kk === u.length - 1 ? finalAt(run, i) : estimateAt(run, i));
      for (const e of edgesUpTo(run, kk)) {
        const a = at(e.i);
        const z = at(e.j);
        ctx.strokeStyle = e.kind === 'loop' ? '#CC79A7' : e.kind === 'icp' ? 'rgba(0, 0, 0, 0.25)' : 'rgba(213, 94, 0, 0.6)';
        ctx.lineWidth = (e.kind === 'loop' ? 2.5 : 1) * px;
        ctx.beginPath();
        ctx.moveTo(X(a[0]), Y(a[1]));
        ctx.lineTo(X(z[0]), Y(z[1]));
        ctx.stroke();
      }
    }
    // FastSLAM's particles, by weight
    if (show.particles && run) {
      const parts = particlesAt(run, kk);
      let wmax = 0;
      for (const q of parts) wmax = Math.max(wmax, q[2]);
      ctx.fillStyle = runStyle(run.id).color;
      for (const [x, y, w] of parts) {
        ctx.globalAlpha = wmax > 0 ? 0.2 + 0.8 * (w / wmax) : 0.5;
        ctx.fillRect(X(x) - 2 * px, Y(y) - 2 * px, 4 * px, 4 * px);
      }
      ctx.globalAlpha = 1;
    }
    // landmarks: the true corners, and EKF-SLAM's estimates with 2-sigma ellipses
    if (show.landmarks) {
      if (show.truth) {
        ctx.strokeStyle = TRUTH_COLOR;
        ctx.lineWidth = px;
        for (const [, x, y] of b.world.landmarks) {
          ctx.beginPath();
          ctx.moveTo(X(x) - 4 * px, Y(y) - 4 * px); ctx.lineTo(X(x) + 4 * px, Y(y) + 4 * px);
          ctx.moveTo(X(x) - 4 * px, Y(y) + 4 * px); ctx.lineTo(X(x) + 4 * px, Y(y) - 4 * px);
          ctx.stroke();
        }
      }
      if (run && run.algorithm === 'ekf_slam') {
        const est = landmarksAt(run, kk);
        const pose = estimateAt(run, kk);
        const seen = new Set(observationsAt(b, kk).map((o) => o[0]));
        for (const [id, x, y, cxx, cxy, cyy] of est) {
          const e = ellipse(cxx, cxy, cyy);
          ctx.strokeStyle = runStyle('ekf_slam').color;
          ctx.lineWidth = 1.5 * px;
          ctx.beginPath();
          ctx.ellipse(X(x), Y(y), Math.max(2 * px, e.rx * sp), Math.max(2 * px, e.ry * sp), -e.angle, 0, 2 * Math.PI);
          ctx.stroke();
          if (seen.has(id)) {
            ctx.strokeStyle = 'rgba(0, 158, 115, 0.5)';
            ctx.beginPath();
            ctx.moveTo(X(pose[0]), Y(pose[1]));
            ctx.lineTo(X(x), Y(y));
            ctx.stroke();
          }
        }
      }
    }
    // the scan, placed at the belief: walls where they land are the map's evidence
    const belief: Pose | null = run ? estimateAt(run, kk) : ext ? externalAt(ext, kk) : null;
    if (show.rays && belief) {
      const ends = scanEndpoints(b, kk, belief);
      const [mx, my] = b.world.lidar.mount;
      const cth = Math.cos(belief[2]);
      const sth = Math.sin(belief[2]);
      const sx = belief[0] + cth * mx - sth * my;
      const sy = belief[1] + sth * mx + cth * my;
      ctx.strokeStyle = 'rgba(213, 94, 0, 0.18)';
      ctx.lineWidth = px;
      ctx.beginPath();
      ends.forEach(([x, y], i) => { if (i % 2 === 0) { ctx.moveTo(X(sx), Y(sy)); ctx.lineTo(X(x), Y(y)); } });
      ctx.stroke();
      ctx.fillStyle = '#D55E00';
      for (const [x, y] of ends) ctx.fillRect(X(x) - 1.5 * px, Y(y) - 1.5 * px, 3 * px, 3 * px);
    }

    const pose = (q: Pose, color: string, size: number) => {
      const [x, y, th] = q;
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
    if (show.truth) {
      ctx.strokeStyle = TRUTH_COLOR;
      ctx.lineWidth = 2 * px;
      ctx.beginPath();
      for (let i = 0; i <= row; i++) {
        if (i === 0) ctx.moveTo(X(b.world.gtX[i]), Y(b.world.gtY[i]));
        else ctx.lineTo(X(b.world.gtX[i]), Y(b.world.gtY[i]));
      }
      ctx.stroke();
      pose(truthAtUpdate(b, kk), TRUTH_COLOR, 11);
    }
    const color = runStyle(p.focus).color;
    const trail = (at: (i: number) => Pose, dash: boolean) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2 * px;
      ctx.setLineDash(dash ? [5 * px, 4 * px] : []);
      ctx.beginPath();
      for (let i = 0; i <= kk; i++) {
        const q = at(i);
        if (i === 0) ctx.moveTo(X(q[0]), Y(q[1]));
        else ctx.lineTo(X(q[0]), Y(q[1]));
      }
      ctx.stroke();
      ctx.setLineDash([]);
    };
    if (run) {
      trail((i) => estimateAt(run, i), false);
      if (show.final && 'final.x' in run.arrays) trail((i) => finalAt(run, i), true);
      pose(estimateAt(run, kk), color, 10);
    } else if (ext) {
      trail((i) => externalAt(ext, i), false);
      pose(externalAt(ext, kk), color, 10);
    }
  }, [b, k, show, run, ext, p.focus, p.clicks, p.route, cssWidth, truthLayer, mapLayer, diffLayer, width, height, geo]);

  const onClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!p.onPick || !geo) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const fx = (e.clientX - rect.left) / rect.width;
    const fy = (e.clientY - rect.top) / rect.height;
    p.onPick(geo.origin[0] + fx * width * geo.resolution, geo.origin[1] + (1 - fy) * height * geo.resolution);
  };

  return (
    <figure className="loc-figure">
      {p.label && <figcaption>{p.label}</figcaption>}
      <div className="map-wrap" ref={wrap}>
        <canvas ref={canvas} className={p.onPick ? 'map-canvas editable' : 'map-canvas'} onClick={onClick}
          role="img" aria-label={`Map at update ${k + 1} of ${b.world.updates.length}`} data-testid="map-canvas" />
      </div>
    </figure>
  );
}
