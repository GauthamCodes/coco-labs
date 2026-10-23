// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * A level's grid on a canvas (M3.5): blocked cells, the cost layer shaded,
 * S and G, and whatever the challenge overlays. It draws what coco_lab.play
 * handed it and reports clicks as cells; it computes nothing.
 */

import { useEffect, useRef, useState } from 'react';
import {TOKENS} from '../ui/tokens';
import {activeTheme} from '../ui/theme';
import {PREFERENCES_CHANGED} from '../shell/settings_events';

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
  const [theme,setTheme]=useState(activeTheme);
  const [keyboardCell,setKeyboardCell]=useState<Cell>(grid.marks.S??[0,0]);
  const [keyboardFocus,setKeyboardFocus]=useState(false);
  useEffect(()=>{const update=()=>setTheme(activeTheme());window.addEventListener(PREFERENCES_CHANGED,update);return()=>window.removeEventListener(PREFERENCES_CHANGED,update);},[]);
  const ref = useRef<HTMLCanvasElement | null>(null);
  const wrap = useRef<HTMLDivElement | null>(null);
  const [px, setPx] = useState(28);
  useEffect(() => {
    const fit = () => {
      const w = wrap.current?.clientWidth ?? 448;
      const h=wrap.current?.clientHeight??0;
      setPx(Math.max(6,Math.min(36,Math.floor(w/grid.width),h>0?Math.floor(h/grid.height):36)));
    };
    fit();
    const observer=new ResizeObserver(fit);if(wrap.current)observer.observe(wrap.current);
    window.addEventListener('resize', fit);
    return () => {observer.disconnect();window.removeEventListener('resize', fit);};
  }, [grid.width,grid.height]);
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
    const p=TOKENS.computation[theme];
    const free=p.free,wall=p.occupied,ink=p.text,accent=p.path;
    for (let r = 0; r < grid.height; r += 1) {
      for (let c = 0; c < grid.width; c += 1) {
        const i = r * grid.width + c;
        if (grid.blocked[i]) g.fillStyle = wall;
        else if (grid.cost[i] > 0) g.fillStyle = TOKENS.viridis[Math.min(4,Math.floor(grid.cost[i]/COST_MAX*4))];
        else g.fillStyle = free;
        g.fillRect(c * px, r * px, px, px);
      }
    }
    // faint cell lines: a path is drawn one cell at a time
    g.strokeStyle = TOKENS.colours[theme].line; g.lineWidth = 1;
    g.beginPath();
    for (let c = 1; c < grid.width; c += 1) { g.moveTo(c * px + 0.5, 0); g.lineTo(c * px + 0.5, grid.height * px); }
    for (let r = 1; r < grid.height; r += 1) { g.moveTo(0, r * px + 0.5); g.lineTo(grid.width * px, r * px + 0.5); }
    g.stroke();
    const box = (cells: Cell[] | undefined, fill: string | null, stroke: string | null, inset = 1) => {
      for (const [r, c] of cells ?? []) {
        if (fill) { g.fillStyle = fill; g.fillRect(c * px + inset, r * px + inset, px - 2 * inset, px - 2 * inset); }
        if (stroke) { g.strokeStyle = stroke; g.lineWidth = 2; g.strokeRect(c * px + inset + 1, r * px + inset + 1, px - 2 * inset - 2, px - 2 * inset - 2); }
      }
    };
    box(overlay.closed, p.closed+'73', null);
    box(overlay.open, null, p.frontier, 2);
    box(overlay.tied, null, p.truth, 3);
    const line = (cells: Cell[] | undefined, color: string, width: number, dash: number[] = []) => {
      if (!cells || cells.length < 2) return;
      g.strokeStyle = color; g.lineWidth = width; g.setLineDash(dash);
      g.beginPath();
      cells.forEach(([r, c], k) => (k ? g.lineTo : g.moveTo).call(g, c * px + px / 2, r * px + px / 2));
      g.stroke();
      g.setLineDash([]);
    };
    line(overlay.ghost, p.truth, 3, [6, 4]);
    line(overlay.path, accent, 4);
    for (const [r, c] of overlay.path ?? []) { g.fillStyle = accent; g.beginPath(); g.arc(c * px + px / 2, r * px + px / 2, 3, 0, 7); g.fill(); }
    box(overlay.truth ? [overlay.truth] : [], null, p.truth, 0);
    box(overlay.mark ? [overlay.mark] : [], null, p.path, 4);
    g.font = `bold ${Math.max(14,Math.round(px * 0.6))}px ${TOKENS.type.ui}`;
    g.textAlign = 'center'; g.textBaseline = 'middle';
    for (const [k, [r, c]] of Object.entries(grid.marks)) { g.strokeStyle=free;g.lineWidth=4;g.strokeText(k,c*px+px/2,r*px+px/2);g.fillStyle = ink; g.fillText(k, c * px + px / 2, r * px + px / 2); }
    if(keyboardFocus&&onCell){const [r,c]=keyboardCell;g.strokeStyle=accent;g.lineWidth=3;g.strokeRect(c*px+2,r*px+2,px-4,px-4);}
  }, [grid, overlay, px,theme,keyboardCell,keyboardFocus]);
  const cellAt = (e: React.PointerEvent<HTMLCanvasElement>): Cell | null => {
    const b = (e.target as HTMLCanvasElement).getBoundingClientRect();
    const c = Math.floor((e.clientX - b.left) / px); const r = Math.floor((e.clientY - b.top) / px);
    return r >= 0 && c >= 0 && r < grid.height && c < grid.width ? [r, c] : null;
  };
  return (
    <div className="grid-board" ref={wrap}>
      <canvas ref={ref} role={onCell?"application":"img"} tabIndex={onCell?0:undefined} aria-label={onCell?label+"; arrow keys choose a cell, Enter selects":label} data-testid="grid-board" data-px={px}
        onFocus={()=>setKeyboardFocus(true)} onBlur={()=>{setKeyboardFocus(false);onHover?.(null);}}
        onKeyDown={event=>{
          if(!onCell)return;
          const [r,c]=keyboardCell,delta:Record<string,Cell>={ArrowUp:[-1,0],ArrowDown:[1,0],ArrowLeft:[0,-1],ArrowRight:[0,1]};
          if(delta[event.key]){event.preventDefault();const [dr,dc]=delta[event.key],cell:Cell=[Math.max(0,Math.min(grid.height-1,r+dr)),Math.max(0,Math.min(grid.width-1,c+dc))];setKeyboardCell(cell);onHover?.(cell);}
          else if(event.key==='Enter'||event.key===' '){event.preventDefault();onCell(keyboardCell);}
        }}
        onPointerDown={(e) => { const c = cellAt(e); if (c&&onCell) { setKeyboardCell(c); onCell(c); } }}
        onPointerMove={(e) => onHover?.(cellAt(e))} onPointerLeave={() => onHover?.(null)} />
      {onCell&&<span className="sr-only" role="status">{keyboardFocus?`Cell ${keyboardCell.join(', ')}; ${grid.blocked[keyboardCell[0]*grid.width+keyboardCell[1]]?'wall':'free'}; cost ${grid.cost[keyboardCell[0]*grid.width+keyboardCell[1]]??0}`:''}</span>}
    </div>
  );
}
