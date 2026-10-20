// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.3: the minimap (a 112 px circle, north-up or heading-up) and the full
 * tactical map it opens (pinch and drag, tap to set a goal). Both draw the
 * model's own planning occupancy (the World message's grid), the robot, its
 * plan in magenta and the order's targets as icons. They compute nothing.
 */

import { useEffect, useRef, useState } from 'react';
import type { World } from '../../arena/protocol';

export interface MapMarks {
  pose: [number, number, number] | null;
  plan: [number, number][];
  target: [number, number] | null;
  drop: { min: [number, number]; max: [number, number] } | null;
  goal: [number, number] | null;
  actors: [number, number][];
}

/** The occupancy as an image, once per world (row 0 is the map's top, +y). */
function occupancyImage(world: World, occ: Uint8Array): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = world.width; c.height = world.height;
  const g = c.getContext('2d')!, img = g.createImageData(world.width, world.height);
  for (let k = 0; k < occ.length; k++) {
    const v = occ[k];
    const rgb = v === 0 ? [24, 31, 44] : v === 1 ? [150, 166, 190] : [8, 10, 14]; // coco_lab.maps: FREE 0, OCCUPIED 1, UNKNOWN 2
    img.data.set([...rgb, 255], k * 4);
  }
  g.putImageData(img, 0, 0);
  return c;
}

const toPx = (world: World, x: number, y: number): [number, number] =>
  [(x - world.origin[0]) / world.resolution, world.height - (y - world.origin[1]) / world.resolution];

function drawMarks(g: CanvasRenderingContext2D, world: World, m: MapMarks, ppc: number) {
  const P = (x: number, y: number) => toPx(world, x, y);
  if (m.drop) {
    const [x0, y0] = P(m.drop.min[0], m.drop.max[1]), [x1, y1] = P(m.drop.max[0], m.drop.min[1]);
    g.fillStyle = 'rgba(52,211,153,0.35)'; g.fillRect(x0, y0, x1 - x0, y1 - y0);
    g.strokeStyle = '#34D399'; g.lineWidth = 2 / ppc; g.strokeRect(x0, y0, x1 - x0, y1 - y0);
  }
  if (m.plan.length > 1) {
    g.strokeStyle = '#F43F8E'; g.lineWidth = 3 / ppc; g.lineJoin = 'round'; g.beginPath();
    m.plan.forEach(([x, y], k) => { const [px, py] = P(x, y); if (k) g.lineTo(px, py); else g.moveTo(px, py); });
    g.stroke();
  }
  for (const [x, y] of m.actors) { const [px, py] = P(x, y); g.fillStyle = '#FACC15'; g.fillRect(px - 4 / ppc, py - 4 / ppc, 8 / ppc, 8 / ppc); }
  if (m.target) {
    const [px, py] = P(m.target[0], m.target[1]);
    g.fillStyle = '#34D399'; g.beginPath(); g.moveTo(px, py + 5 / ppc); g.lineTo(px - 5 / ppc, py - 4 / ppc); g.lineTo(px + 5 / ppc, py - 4 / ppc); g.fill();
  }
  if (m.goal) { const [px, py] = P(m.goal[0], m.goal[1]); g.strokeStyle = '#F43F8E'; g.lineWidth = 2 / ppc; g.beginPath(); g.arc(px, py, 5 / ppc, 0, Math.PI * 2); g.stroke(); }
  if (m.pose) {
    const [px, py] = P(m.pose[0], m.pose[1]), th = m.pose[2], r = 7 / ppc;
    g.save(); g.translate(px, py); g.rotate(-th);
    g.fillStyle = '#FF7A1A'; g.strokeStyle = '#fff'; g.lineWidth = 1.2 / ppc;
    g.beginPath(); g.moveTo(r, 0); g.lineTo(-r * 0.7, r * 0.65); g.lineTo(-r * 0.35, 0); g.lineTo(-r * 0.7, -r * 0.65); g.closePath(); g.fill(); g.stroke();
    g.restore();
  }
}

export function Minimap({ world, occupancy, marks, headingUp, onOpen }: { world: World; occupancy: Uint8Array; marks: MapMarks; headingUp: boolean; onOpen: () => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const img = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => { img.current = occupancyImage(world, occupancy); }, [world, occupancy]);
  useEffect(() => {
    const c = ref.current, im = img.current;
    if (!c || !im) return;
    const g = c.getContext('2d')!, S = c.width, metres = 18, ppc = S / (metres / world.resolution);
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.fillStyle = '#0b0f15'; g.fillRect(0, 0, S, S);
    const pose = marks.pose ?? [world.start[0], world.start[1], world.start[2]];
    const [px, py] = toPx(world, pose[0], pose[1]);
    g.translate(S / 2, S / 2);
    if (headingUp) g.rotate(pose[2] - Math.PI / 2);
    g.scale(ppc, ppc);
    g.translate(-px, -py);
    g.imageSmoothingEnabled = false;
    g.drawImage(im, 0, 0);
    drawMarks(g, world, marks, ppc);
  });
  return <button className="g1-minimap" data-testid="minimap" aria-label="Map: tap to open the tactical map" onClick={onOpen}>
    <canvas ref={ref} width={224} height={224} />
    <span className="g1-minimap-n" style={headingUp && marks.pose ? { transform: `rotate(${(marks.pose[2] - Math.PI / 2) * -180 / Math.PI}deg)` } : undefined}>N</span>
  </button>;
}

/** The full tactical map: drag to pan, pinch or wheel to zoom, tap to send COCO there. */
export function TacticalMap({ world, occupancy, marks, onGoal, onClose }: { world: World; occupancy: Uint8Array; marks: MapMarks; onGoal: (x: number, y: number) => void; onClose: () => void }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const img = useRef<HTMLCanvasElement | null>(null);
  const [view, setView] = useState(() => ({ cx: marks.pose?.[0] ?? world.start[0], cy: marks.pose?.[1] ?? world.start[1], mpp: 0.06 }));
  const pointers = useRef(new Map<number, { x: number; y: number; x0: number; y0: number }>());
  const pinch = useRef<{ d: number; mpp: number } | null>(null);
  useEffect(() => { img.current = occupancyImage(world, occupancy); }, [world, occupancy]);
  useEffect(() => {
    const c = ref.current, im = img.current;
    if (!c || !im) return;
    const r = c.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(r.width * dpr); c.height = Math.round(r.height * dpr);
    const g = c.getContext('2d')!;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.fillStyle = '#0b0f15'; g.fillRect(0, 0, c.width, c.height);
    const ppc = (world.resolution / view.mpp) * dpr;
    const [px, py] = toPx(world, view.cx, view.cy);
    g.translate(c.width / 2, c.height / 2); g.scale(ppc, ppc); g.translate(-px, -py);
    g.imageSmoothingEnabled = false;
    g.drawImage(im, 0, 0);
    drawMarks(g, world, marks, ppc / dpr);
  });
  const toWorld = (clientX: number, clientY: number): [number, number] => {
    const r = ref.current!.getBoundingClientRect();
    return [view.cx + (clientX - r.left - r.width / 2) * view.mpp, view.cy - (clientY - r.top - r.height / 2) * view.mpp];
  };
  const down = (e: React.PointerEvent) => { ref.current!.setPointerCapture(e.pointerId); pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY }); if (pointers.current.size === 2) { const [a, b] = [...pointers.current.values()]; pinch.current = { d: Math.hypot(a.x - b.x, a.y - b.y), mpp: view.mpp }; } };
  const move = (e: React.PointerEvent) => {
    const p = pointers.current.get(e.pointerId);
    if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    if (pointers.current.size === 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      setView((v) => ({ ...v, mpp: Math.min(0.3, Math.max(0.01, pinch.current!.mpp * pinch.current!.d / Math.max(10, d))) }));
    } else if (pointers.current.size === 1) setView((v) => ({ ...v, cx: v.cx - dx * v.mpp, cy: v.cy + dy * v.mpp }));
  };
  const up = (e: React.PointerEvent) => {
    const p = pointers.current.get(e.pointerId);
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (p && Math.hypot(e.clientX - p.x0, e.clientY - p.y0) < 8 && pointers.current.size === 0) { const [x, y] = toWorld(e.clientX, e.clientY); onGoal(x, y); }
  };
  return <section className="g1-tactical" data-testid="tactical-map" role="dialog" aria-label="Tactical map">
    <canvas ref={ref} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}
      onWheel={(e) => setView((v) => ({ ...v, mpp: Math.min(0.3, Math.max(0.01, v.mpp * (e.deltaY > 0 ? 1.15 : 1 / 1.15))) }))} aria-label="Tap to send COCO there; drag to pan; pinch to zoom" />
    <p className="g1-tactical-hint">Tap to send COCO · drag to pan · pinch to zoom</p>
    <button className="g1-tactical-close" onClick={onClose} aria-label="Close the map">✕</button>
  </section>;
}
