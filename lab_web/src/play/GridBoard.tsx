// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * A level's grid on a canvas (M3.5): blocked cells, the cost layer shaded,
 * S and G, and whatever the challenge overlays. It draws what coco_lab.play
 * handed it and reports clicks as cells; it computes nothing.
 */

import { useEffect, useRef, useState } from 'react';

export type Cell = [number, number];
export interface GridView {
  width: number; height: number; blocked: boolean[]; cost: number[]; marks: Record<string, Cell>;
}
export interface Overlay {
  closed?: Cell[];
  open?: Cell[];
  path?: Cell[];
  ghost?: Cell[];            // a second path, drawn faint (the optimum, after scoring)
  mark?: Cell | null;        // the learner's pick
  truth?: Cell | null;       // what A* did
  tied?: Cell[];
}

const COST_MAX = 252;

export function GridBoard({ grid, overlay, onCell, onHover, label }: {
  grid: GridView; overlay: Overlay; onCell?: (c: Cell) => void; onHover?: (c: Cell | null) => void; label: string;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const wrap = useRef<HTMLDivElement | null>(null);
  const [px, setPx] = useState(28);
  useEffect(() => {
    const fit = () => {
      const w = wrap.current?.clientWidth ?? 448;
      setPx(Math.max(14, Math.min(36, Math.floor(w / grid.width))));
    };
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, [grid.width]);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = grid.width * px * dpr;
    cv.height = grid.height * px * dpr;
    cv.style.width = `${grid.width * px}px`;
    cv.style.height = `${grid.height * px}px`;
    const g = cv.getContext('2d');
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const css = getComputedStyle(document.documentElement);
    const v = (n: string, d: string) => css.getPropertyValue(n).trim() || d;
    const free = v('--play-free', '#f7f5ef'); const wall = v('--play-wall', '#1d1d1f');
    const ink = v('--ink', '#222'); const accent = v('--play-path', '#0b6e99');
    for (let r = 0; r < grid.height; r += 1) {
      for (let c = 0; c < grid.width; c += 1) {
        const i = r * grid.width + c;
        if (grid.blocked[i]) g.fillStyle = wall;
        else if (grid.cost[i] > 0) g.fillStyle = `rgba(122, 82, 40, ${0.15 + 0.6 * grid.cost[i] / COST_MAX})`;
        else g.fillStyle = free;
        g.fillRect(c * px, r * px, px, px);
      }
    }
    const box = (cells: Cell[] | undefined, fill: string | null, stroke: string | null, inset = 1) => {
      for (const [r, c] of cells ?? []) {
        if (fill) { g.fillStyle = fill; g.fillRect(c * px + inset, r * px + inset, px - 2 * inset, px - 2 * inset); }
        if (stroke) { g.strokeStyle = stroke; g.lineWidth = 2; g.strokeRect(c * px + inset + 1, r * px + inset + 1, px - 2 * inset - 2, px - 2 * inset - 2); }
      }
    };
    box(overlay.closed, 'rgba(120, 120, 130, 0.45)', null);
    box(overlay.open, null, 'rgba(11, 110, 153, 0.9)', 2);
    box(overlay.tied, 'rgba(46, 160, 67, 0.25)', null, 3);
    const line = (cells: Cell[] | undefined, color: string, width: number, dash: number[] = []) => {
      if (!cells || cells.length < 2) return;
      g.strokeStyle = color; g.lineWidth = width; g.setLineDash(dash);
      g.beginPath();
      cells.forEach(([r, c], k) => (k ? g.lineTo : g.moveTo).call(g, c * px + px / 2, r * px + px / 2));
      g.stroke();
      g.setLineDash([]);
    };
    line(overlay.ghost, 'rgba(46, 160, 67, 0.85)', 3, [6, 4]);
    line(overlay.path, accent, 4);
    for (const [r, c] of overlay.path ?? []) { g.fillStyle = accent; g.beginPath(); g.arc(c * px + px / 2, r * px + px / 2, 3, 0, 7); g.fill(); }
    box(overlay.truth ? [overlay.truth] : [], null, 'rgba(46, 160, 67, 1)', 0);
    box(overlay.mark ? [overlay.mark] : [], null, 'rgba(201, 60, 32, 1)', 4);
    g.font = `bold ${Math.round(px * 0.6)}px system-ui, sans-serif`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (const [k, [r, c]] of Object.entries(grid.marks)) { g.fillStyle = ink; g.fillText(k, c * px + px / 2, r * px + px / 2); }
  }, [grid, overlay, px]);
  const cellAt = (e: React.PointerEvent<HTMLCanvasElement>): Cell | null => {
    const b = (e.target as HTMLCanvasElement).getBoundingClientRect();
    const c = Math.floor((e.clientX - b.left) / px); const r = Math.floor((e.clientY - b.top) / px);
    return r >= 0 && c >= 0 && r < grid.height && c < grid.width ? [r, c] : null;
  };
  return (
    <div className="grid-board" ref={wrap}>
      <canvas ref={ref} role="img" aria-label={label} data-testid="grid-board" data-px={px}
        onPointerDown={(e) => { const c = cellAt(e); if (c) onCell?.(c); }}
        onPointerMove={(e) => onHover?.(cellAt(e))} onPointerLeave={() => onHover?.(null)} />
    </div>
  );
}
