// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.3: one run drawn as it streams in -- the world, the robot (truth and belief), and the
 * algorithm's own thinking from ctx.emit (expansions and pushes; candidate trajectories and the
 * lookahead; the particle cloud), in the GAME look or the RViz-style SIM look. Drawing never
 * changes the run (README §3): every number here came from the sandboxed model.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import type { Frame } from './sandbox';

export interface MapInfo {
  width: number; height: number; resolution: number; origin: [number, number]; occupancy: string; radius: number;
  lidar: { angle_min: number; angle_inc: number; mount: [number, number]; every: number };
}
export interface RunDraw {
  family: 'planning' | 'control' | 'localisation';
  frames: Frame[]; expand: number[]; push: number[]; pathCells: number[][];
  start: number[]; goal: number[]; done: boolean; label: string;
}
export type Look = 'game' | 'sim';

const GAME = { bg: '#0b1118', free: '#131d27', wall: '#3a5068', unknown: '#0e151c', expand: 'rgba(255,181,71,0.55)', push: 'rgba(124,199,255,0.35)',
  path: '#7cc7ff', trail: '#ffb547', robot: '#e8eef5', belief: '#9ad7a0', cand: 'rgba(154,215,160,0.35)', bad: 'rgba(255,110,110,0.30)', part: 'rgba(255,158,122,0.7)', scan: 'rgba(255,110,110,0.7)', text: '#e8eef5' };
const SIM = { bg: '#303030', free: '#cdcdcd', wall: '#000000', unknown: '#707f84', expand: 'rgba(230,120,0,0.6)', push: 'rgba(0,120,255,0.35)',
  path: '#00c000', trail: '#ff00ff', robot: '#00ff00', belief: '#ffff00', cand: 'rgba(0,160,255,0.45)', bad: 'rgba(255,0,0,0.35)', part: '#ff0000', scan: '#ff0000', text: '#ffffff' };

function mapImage(m: MapInfo, look: Look): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = m.width; c.height = m.height;
  const g = c.getContext('2d')!;
  const img = g.createImageData(m.width, m.height);
  const pal = look === 'game' ? GAME : SIM;
  const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const cols = [rgb(pal.free), rgb(pal.wall), rgb(pal.unknown)];
  for (let i = 0; i < m.occupancy.length; i++) {
    const v = cols[m.occupancy.charCodeAt(i) - 48] ?? cols[2];
    img.data[i * 4] = v[0]; img.data[i * 4 + 1] = v[1]; img.data[i * 4 + 2] = v[2]; img.data[i * 4 + 3] = 255;
  }
  g.putImageData(img, 0, 0);   // lab maps are stored top row first: row 0 is the image's top
  return c;
}

export function StudioView({ map, run, look, onLook, title }: { map: MapInfo | null; run: RunDraw | null; look: Look; onLook: (l: Look) => void; title?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(4);
  const base = useMemo(() => (map ? mapImage(map, look) : null), [map, look]);
  const n = run ? (run.family === 'planning' ? 100 : run.frames.length) : 0;

  useEffect(() => { setFrame(0); setPlaying(true); }, [run?.label, run?.start?.join(',')]);
  useEffect(() => {
    if (!playing || !run) return;
    const id = setInterval(() => setFrame((f) => {
      const last = Math.max(0, n - 1);
      if (f >= last) { if (run.done) setPlaying(false); return last; }
      return Math.min(last, f + (run.family === 'planning' ? 2 : speed));
    }), 50);
    return () => clearInterval(id);
  }, [playing, run, n, speed]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv || !map || !base) return;
    const pal = look === 'game' ? GAME : SIM;
    const W = cv.clientWidth || 640;
    const scale = W / map.width;
    cv.width = Math.round(W * devicePixelRatio);
    cv.height = Math.round(map.height * scale * devicePixelRatio);
    cv.style.height = `${map.height * scale}px`;
    const g = cv.getContext('2d')!;
    g.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    g.fillStyle = pal.bg; g.fillRect(0, 0, W, map.height * scale);
    g.imageSmoothingEnabled = false;
    g.drawImage(base, 0, 0, map.width * scale, map.height * scale);
    const [ox, oy] = map.origin, res = map.resolution;
    const X = (x: number) => ((x - ox) / res) * scale;
    const Y = (y: number) => (map.height - (y - oy) / res) * scale;
    const cell = (r: number, c: number): [number, number] => [ox + (c + 0.5) * res, oy + (map.height - 1 - r + 0.5) * res];
    if (look === 'sim') {   // RViz's grid: 1 m cells
      g.strokeStyle = 'rgba(160,160,164,0.25)'; g.lineWidth = 1;
      for (let x = Math.ceil(ox); x < ox + map.width * res; x++) { g.beginPath(); g.moveTo(X(x), 0); g.lineTo(X(x), map.height * scale); g.stroke(); }
      for (let y = Math.ceil(oy); y < oy + map.height * res; y++) { g.beginPath(); g.moveTo(0, Y(y)); g.lineTo(W, Y(y)); g.stroke(); }
    }
    if (!run) return;
    const dot = (x: number, y: number, r: number, col: string) => { g.fillStyle = col; g.fillRect(X(x) - r / 2, Y(y) - r / 2, r, r); };
    const ps = Math.max(1.5, scale * res * 0.9);
    if (run.family === 'planning') {
      const frac = Math.min(1, (frame + 1) / n);
      const k = Math.floor((run.push.length / 2) * frac);
      for (let i = 0; i < k; i++) dot(run.push[2 * i], run.push[2 * i + 1], ps, pal.push);
      const e = Math.floor((run.expand.length / 2) * frac);
      for (let i = 0; i < e; i++) dot(run.expand[2 * i], run.expand[2 * i + 1], ps, pal.expand);
      if (frac >= 1 && run.pathCells.length) {
        g.strokeStyle = pal.path; g.lineWidth = Math.max(2, scale * res * 1.2); g.lineJoin = 'round';
        if (look === 'game') { g.shadowColor = pal.path; g.shadowBlur = 8; }
        g.beginPath();
        run.pathCells.forEach(([r, c], i) => { const [x, y] = cell(r, c); if (i) g.lineTo(X(x), Y(y)); else g.moveTo(X(x), Y(y)); });
        g.stroke(); g.shadowBlur = 0;
      }
    } else {
      const f = run.frames[Math.min(frame, run.frames.length - 1)];
      let wp: number[][] | null = null;
      for (let i = Math.min(frame, run.frames.length - 1); i >= 0 && !wp; i--) wp = run.frames[i].waypoints;
      if (wp?.length) {
        g.strokeStyle = pal.path; g.lineWidth = 2; g.beginPath();
        wp.forEach(([x, y], i) => (i ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y)))); g.stroke();
      }
      g.strokeStyle = pal.trail; g.lineWidth = 2; g.beginPath();
      run.frames.slice(0, frame + 1).forEach((fr, i) => (i ? g.lineTo(X(fr.truth[0]), Y(fr.truth[1])) : g.moveTo(X(fr.truth[0]), Y(fr.truth[1])))); g.stroke();
      if (f) {
        for (const c of f.candidates) {
          g.strokeStyle = c.valid ? pal.cand : pal.bad; g.lineWidth = 1; g.beginPath();
          c.points.forEach(([x, y], i) => (i ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y)))); g.stroke();
        }
        if (f.particles) for (let i = 0; i < f.particles.x.length; i++) dot(f.particles.x[i], f.particles.y[i], 2.5, pal.part);
        if (f.lookahead) { g.strokeStyle = pal.trail; g.beginPath(); g.arc(X(f.lookahead[0]), Y(f.lookahead[1]), 5, 0, 2 * Math.PI); g.stroke(); }
        const [bx, by, bt] = f.belief;
        if (look === 'sim' && f.scan) {
          const L = map.lidar, c = Math.cos(bt), s = Math.sin(bt);
          const sx = bx + c * L.mount[0] - s * L.mount[1], sy = by + s * L.mount[0] + c * L.mount[1];
          f.scan.forEach((r, i) => { if (r > 0 && r < 11.9) { const a = bt + L.angle_min + i * L.every * L.angle_inc; dot(sx + r * Math.cos(a), sy + r * Math.sin(a), 2, pal.scan); } });
        }
        const [tx, ty, tt] = f.truth;
        const R = map.radius / res * scale;
        g.strokeStyle = pal.belief; g.setLineDash([3, 3]); g.beginPath(); g.arc(X(bx), Y(by), R, 0, 2 * Math.PI); g.stroke(); g.setLineDash([]);
        if (look === 'game') { g.shadowColor = '#7cc7ff'; g.shadowBlur = 12; }
        g.fillStyle = look === 'game' ? 'rgba(232,238,245,0.9)' : 'rgba(0,0,0,0)';
        g.strokeStyle = pal.robot; g.lineWidth = 2;
        g.beginPath(); g.arc(X(tx), Y(ty), R, 0, 2 * Math.PI); g.fill(); g.stroke(); g.shadowBlur = 0;
        if (look === 'sim') {   // base_footprint's TF axes: x red, y green
          g.lineWidth = 2;
          g.strokeStyle = '#ff0000'; g.beginPath(); g.moveTo(X(tx), Y(ty)); g.lineTo(X(tx + 0.4 * Math.cos(tt)), Y(ty + 0.4 * Math.sin(tt))); g.stroke();
          g.strokeStyle = '#00ff00'; g.beginPath(); g.moveTo(X(tx), Y(ty)); g.lineTo(X(tx - 0.4 * Math.sin(tt)), Y(ty + 0.4 * Math.cos(tt))); g.stroke();
        } else {
          g.strokeStyle = '#0b1118'; g.beginPath(); g.moveTo(X(tx), Y(ty)); g.lineTo(X(tx + map.radius * Math.cos(tt)), Y(ty + map.radius * Math.sin(tt))); g.stroke();
        }
      }
    }
    // start (circle) and goal (square)
    g.lineWidth = 2; g.strokeStyle = pal.text;
    if (run.start?.length) { g.beginPath(); g.arc(X(run.start[0]), Y(run.start[1]), 6, 0, 2 * Math.PI); g.stroke(); }
    if (run.goal?.length) g.strokeRect(X(run.goal[0]) - 6, Y(run.goal[1]) - 6, 12, 12);
  }, [map, base, run, frame, look]);

  const t = run && run.family !== 'planning' ? run.frames[Math.min(frame, run.frames.length - 1)] : null;
  return <figure className="studio-view" data-look={look}>
    <div className="studio-view-bar">
      <span className="studio-badge" title="Every view of the model says so (README §3)">MODEL · kinematic</span>
      {title && <span className="studio-pane-title">{title}</span>}
      <span className="studio-seg" role="group" aria-label="View">
        <button aria-pressed={look === 'game'} onClick={() => onLook('game')}>GAME</button>
        <button aria-pressed={look === 'sim'} onClick={() => onLook('sim')}>SIM</button>
      </span>
    </div>
    <canvas ref={canvas} className="studio-canvas" role="img" aria-label={run ? `${run.label}: the run drawn on the map` : 'The map'} />
    {run && <div className="studio-play">
      <button onClick={() => { if (frame >= n - 1) setFrame(0); setPlaying(!playing); }} aria-label={playing ? 'Pause' : 'Play'}>{playing ? '❚❚' : '▶'}</button>
      <input type="range" min={0} max={Math.max(0, n - 1)} value={Math.min(frame, Math.max(0, n - 1))} onChange={(e) => { setPlaying(false); setFrame(Number(e.target.value)); }} aria-label="Time" />
      {run.family !== 'planning' && <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Speed">
        {[1, 4, 16].map((s) => <option key={s} value={s}>×{s}</option>)}</select>}
      <span className="studio-muted">{run.family === 'planning'
        ? `${run.expand.length / 2} expansions${run.done ? '' : ' (running…)'}`
        : t ? `t = ${(t.tick * 0.1).toFixed(1)} s · v ${t.v.toFixed(2)} m/s · ω ${t.w.toFixed(2)} rad/s${t.contact ? ' · CONTACT' : ''}${run.done ? '' : ' (running…)'}` : 'starting…'}</span>
    </div>}
  </figure>;
}
