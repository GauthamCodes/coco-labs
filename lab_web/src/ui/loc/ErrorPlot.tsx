// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import type { DecodedLocBundle } from '../../loc/decode';
import { runStyle } from '../../loc/view';

const W = 640;
const H = 200;
const L = 44;
const R = 10;
const T = 10;
const B = 30;

/**
 * Each filter's position error against the truth, over sim time, from the
 * trace's own `err_xy` column (coco_lab scored it; the page only plots).
 */
export function ErrorPlot({ bundle: b, runs, k, onSeek }: {
  bundle: DecodedLocBundle; runs: string[]; k: number; onSeek: (k: number) => void;
}) {
  const shown = b.runs.filter((r) => runs.includes(r.id));
  const t = b.runs[0].cols.t as Float64Array;
  const t0 = t[0];
  const t1 = Math.max(t[t.length - 1], t0 + 1);
  let ymax = 1;
  for (const r of shown) for (const v of r.cols.err_xy) ymax = Math.max(ymax, v);
  ymax = Math.ceil(ymax);
  const sx = (v: number) => L + ((v - t0) / (t1 - t0)) * (W - L - R);
  const sy = (v: number) => T + (1 - v / ymax) * (H - T - B);
  const ok = b.runs[0].summary.ok_xy;
  const ticks = Array.from({ length: 5 }, (_, i) => (ymax * i) / 4);
  const kr = b.world.kidnapRow;
  const tk = kr === null ? null : b.world.t[kr];
  const onPointer = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const tv = t0 + (((e.clientX - rect.left) / rect.width) * W - L) / (W - L - R) * (t1 - t0);
    let best = 0;
    for (let i = 0; i < t.length; i++) if (Math.abs(t[i] - tv) < Math.abs(t[best] - tv)) best = i;
    onSeek(best);
  };
  return (
    <div className="loc-plot">
      <svg className="plot" viewBox={`0 0 ${W} ${H}`} role="img" data-testid="loc-error-plot"
        aria-label="Position error of each filter against the truth, over time" onPointerDown={onPointer}>
        {ticks.map((v) => (
          <g key={v}>
            <line className="grid" x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} />
            <text className="tick" x={L - 6} y={sy(v) + 4} textAnchor="end">{v.toFixed(ymax > 4 ? 0 : 1)}</text>
          </g>
        ))}
        <text className="axis-label" x={8} y={T + 10}>m</text>
        <text className="axis-label" x={W - R} y={H - 6} textAnchor="end">sim time (s)</text>
        <text className="tick" x={L} y={H - 6}>{t0.toFixed(0)}</text>
        <line className="ref" x1={L} x2={W - R} y1={sy(ok)} y2={sy(ok)} strokeDasharray="4 3" />
        <text className="ref-label" x={W - R - 4} y={sy(ok) - 4} textAnchor="end">{ok} m: localised</text>
        {tk !== null && (
          <g>
            <line x1={sx(tk)} x2={sx(tk)} y1={T} y2={H - B} stroke="#D55E00" strokeWidth={2} strokeDasharray="6 4" />
            <text x={sx(tk) + 4} y={T + 12} fill="#D55E00" fontSize={12}>kidnap</text>
          </g>
        )}
        {shown.map((r) => (
          <polyline key={r.id} fill="none" stroke={runStyle(r.id).color} strokeWidth={2.2} strokeLinejoin="round"
            points={Array.from(r.cols.err_xy, (v, i) => `${sx(t[i]).toFixed(1)},${sy(v).toFixed(1)}`).join(' ')} />
        ))}
        <line x1={sx(t[Math.min(k, t.length - 1)])} x2={sx(t[Math.min(k, t.length - 1)])} y1={T} y2={H - B}
          stroke="currentColor" strokeWidth={1} />
      </svg>
      <ul className="legend" aria-label="Plot legend">
        {shown.map((r) => (
          <li key={r.id}><i className="sw" style={{ background: runStyle(r.id).color, height: 4, border: 0 }} />
            {runStyle(r.id).label}: {r.cols.err_xy[Math.min(k, r.n - 1)].toFixed(2)} m now</li>
        ))}
      </ul>
    </div>
  );
}
