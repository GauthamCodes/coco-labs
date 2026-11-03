// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1: the Workbench's charts, plain SVG. Every number drawn comes from the
 * experiment's summary (coco_lab.exp_stats); nothing is computed here but scales.
 * Identity is never colour alone: each algorithm has a fixed colour slot AND a
 * shape, a legend, and every chart has a table beside it (Results.tsx). Colours are
 * the validated categorical palette (dataviz reference; dark and light steps).
 */
import type { ReactNode } from 'react';

export const SHAPES = ['circle', 'square', 'triangle', 'diamond', 'cross', 'ring', 'down', 'bar'] as const;
export type Shape = typeof SHAPES[number];
export interface Series { id: string; label: string; slot: number }

export const seriesColour = (slot: number) => `var(--wb-s${(slot % 8) + 1})`;
export const seriesShape = (slot: number): Shape => SHAPES[slot % SHAPES.length];

export function Mark({ shape, x, y, r = 5, fill, title, onClick }: { shape: Shape; x: number; y: number; r?: number; fill: string; title?: string; onClick?: () => void }) {
  const common = { fill, stroke: 'var(--wb-surface)', strokeWidth: 1.5, onClick, style: onClick ? { cursor: 'pointer' } : undefined, tabIndex: onClick ? 0 : undefined,
    onKeyDown: onClick ? (e: { key: string }) => { if (e.key === 'Enter') onClick(); } : undefined };
  const t = title ? <title>{title}</title> : null;
  switch (shape) {
    case 'square': return <rect x={x - r} y={y - r} width={2 * r} height={2 * r} rx={1} {...common}>{t}</rect>;
    case 'triangle': return <polygon points={`${x},${y - r * 1.2} ${x + r * 1.1},${y + r * 0.8} ${x - r * 1.1},${y + r * 0.8}`} {...common}>{t}</polygon>;
    case 'down': return <polygon points={`${x},${y + r * 1.2} ${x + r * 1.1},${y - r * 0.8} ${x - r * 1.1},${y - r * 0.8}`} {...common}>{t}</polygon>;
    case 'diamond': return <polygon points={`${x},${y - r * 1.3} ${x + r * 1.1},${y} ${x},${y + r * 1.3} ${x - r * 1.1},${y}`} {...common}>{t}</polygon>;
    case 'cross': return <path d={`M${x - r} ${y - r}L${x + r} ${y + r}M${x + r} ${y - r}L${x - r} ${y + r}`} stroke={fill} strokeWidth={2.5} fill="none" onClick={onClick}>{t}</path>;
    case 'ring': return <circle cx={x} cy={y} r={r} fill="none" stroke={fill} strokeWidth={2.5} onClick={onClick}>{t}</circle>;
    case 'bar': return <rect x={x - r} y={y - r / 2.5} width={2 * r} height={(2 * r) / 2.5} {...common}>{t}</rect>;
    default: return <circle cx={x} cy={y} r={r} {...common}>{t}</circle>;
  }
}

export function Legend({ series }: { series: Series[] }) {
  return <ul className="wb-legend" aria-label="Algorithms">
    {series.map((s) => <li key={s.id}><svg width="16" height="16" aria-hidden="true"><Mark shape={seriesShape(s.slot)} x={8} y={8} r={5} fill={seriesColour(s.slot)} /></svg>{s.label}</li>)}
  </ul>;
}

/** Round, readable ticks covering [lo, hi]. */
export function ticks(lo: number, hi: number, n = 5): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [];
  if (hi === lo) { hi = lo + 1; }
  const step0 = (hi - lo) / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) ?? 10 * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12));
  return out;
}

export const fmt = (v: number | null | undefined, digits = 3): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  if (Number.isInteger(v) && Math.abs(v) < 1e15) return v.toLocaleString('en-GB');
  const a = Math.abs(v);
  return a !== 0 && (a < 1e-3 || a >= 1e6) ? v.toExponential(2) : (+v.toPrecision(digits + 1)).toString();
};

function Frame({ width, height, title, children }: { width: number; height: number; title: string; children: ReactNode }) {
  return <svg className="wb-chart" viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label={title} style={{ maxWidth: width }}>{children}</svg>;
}

export interface BoxStats { n: number; median: number | null; q1: number | null; q3: number | null; min: number | null; max: number | null }

/** One horizontal box per algorithm: quartile box, median line, whiskers to min and max, N beside it. */
export function BoxPlot({ rows, unit, title }: { rows: { series: Series; stats: BoxStats }[]; unit: string; title: string }) {
  const W = 560, rowH = 34, left = 150, right = 70, top = 8, H = top + rows.length * rowH + 30;
  const vals = rows.flatMap((r) => [r.stats.min, r.stats.max]).filter((v): v is number => v !== null);
  if (!vals.length) return <p className="wb-muted">No defined values to plot.</p>;
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (lo === hi) { lo -= 1; hi += 1; }
  const tk = ticks(lo, hi); lo = Math.min(lo, tk[0]); hi = Math.max(hi, tk[tk.length - 1]);
  const x = (v: number) => left + ((v - lo) / (hi - lo)) * (W - left - right);
  return <Frame width={W} height={H} title={title}>
    {tk.map((t) => <g key={t}><line x1={x(t)} x2={x(t)} y1={top} y2={H - 24} className="wb-grid" /><text x={x(t)} y={H - 8} className="wb-tick" textAnchor="middle">{fmt(t)}</text></g>)}
    {rows.map((r, i) => {
      const y = top + i * rowH + rowH / 2, s = r.stats, c = seriesColour(r.series.slot);
      return <g key={r.series.id}>
        <text x={left - 8} y={y + 4} textAnchor="end" className="wb-label">{r.series.label}</text>
        {s.median !== null && s.q1 !== null && s.q3 !== null && s.min !== null && s.max !== null ? <>
          <line x1={x(s.min)} x2={x(s.max)} y1={y} y2={y} stroke={c} strokeWidth={2} />
          <rect x={x(s.q1)} y={y - 10} width={Math.max(2, x(s.q3) - x(s.q1))} height={20} rx={4} fill={c} fillOpacity={0.35} stroke={c} strokeWidth={2}>
            <title>{`${r.series.label}: median ${fmt(s.median)} ${unit}, IQR ${fmt(s.q1)}–${fmt(s.q3)}, range ${fmt(s.min)}–${fmt(s.max)}, N=${s.n}`}</title>
          </rect>
          <line x1={x(s.median)} x2={x(s.median)} y1={y - 12} y2={y + 12} stroke="var(--fg)" strokeWidth={2.5} />
        </> : <text x={left + 4} y={y + 4} className="wb-muted">no defined values</text>}
        <text x={W - right + 8} y={y + 4} className="wb-tick">N={s.n}</text>
      </g>;
    })}
  </Frame>;
}

/** Success rate per algorithm with its Wilson 95% interval. */
export function SuccessBars({ rows, title }: { rows: { series: Series; k: number; n: number; low: number | null; high: number | null }[]; title: string }) {
  const W = 560, rowH = 34, left = 150, right = 80, top = 8, H = top + rows.length * rowH + 30;
  const x = (v: number) => left + v * (W - left - right);
  return <Frame width={W} height={H} title={title}>
    {[0, 0.25, 0.5, 0.75, 1].map((t) => <g key={t}><line x1={x(t)} x2={x(t)} y1={top} y2={H - 24} className="wb-grid" /><text x={x(t)} y={H - 8} textAnchor="middle" className="wb-tick">{t * 100}%</text></g>)}
    {rows.map((r, i) => {
      const y = top + i * rowH + rowH / 2, c = seriesColour(r.series.slot), rate = r.n ? r.k / r.n : 0;
      return <g key={r.series.id}>
        <text x={left - 8} y={y + 4} textAnchor="end" className="wb-label">{r.series.label}</text>
        <rect x={left} y={y - 9} width={Math.max(0, x(rate) - left)} height={18} rx={4} fill={c}>
          <title>{`${r.series.label}: ${r.k}/${r.n} (${(rate * 100).toFixed(1)}%), Wilson 95% ${r.low === null ? '—' : (r.low * 100).toFixed(1)}–${r.high === null ? '—' : (r.high * 100).toFixed(1)}%`}</title>
        </rect>
        {r.low !== null && r.high !== null && <g stroke="var(--fg)" strokeWidth={2}><line x1={x(r.low)} x2={x(r.high)} y1={y} y2={y} /><line x1={x(r.low)} x2={x(r.low)} y1={y - 6} y2={y + 6} /><line x1={x(r.high)} x2={x(r.high)} y1={y - 6} y2={y + 6} /></g>}
        <text x={W - right + 8} y={y + 4} className="wb-tick">{r.k}/{r.n}</text>
      </g>;
    })}
  </Frame>;
}

/** Points per run; click one to open it in Compare. */
export function Scatter({ points, xLabel, yLabel, series, title, onPick }: { points: { x: number; y: number; slot: number; tip: string; run: number }[]; xLabel: string; yLabel: string; series: Series[]; title: string; onPick?: (run: number) => void }) {
  const W = 560, H = 340, left = 64, right = 16, top = 12, bottom = 44;
  if (!points.length) return <p className="wb-muted">No runs with both values defined.</p>;
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const tx = ticks(Math.min(...xs), Math.max(...xs)), ty = ticks(Math.min(...ys), Math.max(...ys));
  const [x0, x1, y0, y1] = [Math.min(tx[0], ...xs), Math.max(tx[tx.length - 1], ...xs), Math.min(ty[0], ...ys), Math.max(ty[ty.length - 1], ...ys)];
  const sx = (v: number) => left + ((v - x0) / (x1 - x0 || 1)) * (W - left - right);
  const sy = (v: number) => H - bottom - ((v - y0) / (y1 - y0 || 1)) * (H - top - bottom);
  return <><Frame width={W} height={H} title={title}>
    {tx.map((t) => <g key={'x' + t}><line x1={sx(t)} x2={sx(t)} y1={top} y2={H - bottom} className="wb-grid" /><text x={sx(t)} y={H - bottom + 16} textAnchor="middle" className="wb-tick">{fmt(t)}</text></g>)}
    {ty.map((t) => <g key={'y' + t}><line x1={left} x2={W - right} y1={sy(t)} y2={sy(t)} className="wb-grid" /><text x={left - 6} y={sy(t) + 4} textAnchor="end" className="wb-tick">{fmt(t)}</text></g>)}
    {points.map((p, i) => <Mark key={i} shape={seriesShape(p.slot)} x={sx(p.x)} y={sy(p.y)} r={4.5} fill={seriesColour(p.slot)} title={p.tip} onClick={onPick ? () => onPick(p.run) : undefined} />)}
    <text x={(left + W - right) / 2} y={H - 6} textAnchor="middle" className="wb-label">{xLabel}</text>
    <text x={14} y={(top + H - bottom) / 2} textAnchor="middle" className="wb-label" transform={`rotate(-90 14 ${(top + H - bottom) / 2})`}>{yLabel}</text>
  </Frame><Legend series={series} /></>;
}

/** A one-parameter sweep: median per point with its IQR band, one line per algorithm. */
export function SweepLine({ lines, xLabel, yLabel, series, title }: { lines: { series: Series; pts: { x: number; median: number | null; q1: number | null; q3: number | null; n: number }[] }[]; xLabel: string; yLabel: string; series: Series[]; title: string }) {
  const W = 560, H = 320, left = 64, right = 16, top = 12, bottom = 44;
  const all = lines.flatMap((l) => l.pts.flatMap((p) => [p.q1, p.q3, p.median])).filter((v): v is number => v !== null);
  const xsAll = lines.flatMap((l) => l.pts.map((p) => p.x));
  if (!all.length || !xsAll.length) return <p className="wb-muted">No defined values to plot.</p>;
  const tx = ticks(Math.min(...xsAll), Math.max(...xsAll)), ty = ticks(Math.min(...all), Math.max(...all));
  const [x0, x1, y0, y1] = [Math.min(tx[0], ...xsAll), Math.max(tx[tx.length - 1], ...xsAll), Math.min(ty[0], ...all), Math.max(ty[ty.length - 1], ...all)];
  const sx = (v: number) => left + ((v - x0) / (x1 - x0 || 1)) * (W - left - right);
  const sy = (v: number) => H - bottom - ((v - y0) / (y1 - y0 || 1)) * (H - top - bottom);
  return <><Frame width={W} height={H} title={title}>
    {tx.map((t) => <g key={'x' + t}><line x1={sx(t)} x2={sx(t)} y1={top} y2={H - bottom} className="wb-grid" /><text x={sx(t)} y={H - bottom + 16} textAnchor="middle" className="wb-tick">{fmt(t)}</text></g>)}
    {ty.map((t) => <g key={'y' + t}><line x1={left} x2={W - right} y1={sy(t)} y2={sy(t)} className="wb-grid" /><text x={left - 6} y={sy(t) + 4} textAnchor="end" className="wb-tick">{fmt(t)}</text></g>)}
    {lines.map((l) => {
      const pts = l.pts.filter((p) => p.median !== null && p.q1 !== null && p.q3 !== null);
      const c = seriesColour(l.series.slot);
      const band = pts.map((p) => `${sx(p.x)},${sy(p.q3!)}`).concat([...pts].reverse().map((p) => `${sx(p.x)},${sy(p.q1!)}`)).join(' ');
      return <g key={l.series.id}>
        {pts.length > 1 && <polygon points={band} fill={c} fillOpacity={0.18} />}
        <polyline points={pts.map((p) => `${sx(p.x)},${sy(p.median!)}`).join(' ')} fill="none" stroke={c} strokeWidth={2} />
        {pts.map((p) => <Mark key={p.x} shape={seriesShape(l.series.slot)} x={sx(p.x)} y={sy(p.median!)} r={4.5} fill={c} title={`${l.series.label} at ${fmt(p.x)}: median ${fmt(p.median)}, IQR ${fmt(p.q1)}–${fmt(p.q3)}, N=${p.n}`} />)}
      </g>;
    })}
    <text x={(left + W - right) / 2} y={H - 6} textAnchor="middle" className="wb-label">{xLabel}</text>
    <text x={14} y={(top + H - bottom) / 2} textAnchor="middle" className="wb-label" transform={`rotate(-90 14 ${(top + H - bottom) / 2})`}>{yLabel}</text>
  </Frame><Legend series={series} /></>;
}

/** A two-parameter sweep for one algorithm: a single-hue ramp, the value written in each cell. */
export function Heatmap({ xs, ys, cell, xLabel, yLabel, title, better }: { xs: (number | string)[]; ys: (number | string)[]; cell: (xi: number, yi: number) => { v: number | null; n: number }; xLabel: string; yLabel: string; title: string; better: 'lower' | 'higher' }) {
  const cw = 64, ch = 34, left = 90, top = 10, W = left + xs.length * cw + 10, H = top + ys.length * ch + 44;
  const vals: number[] = [];
  xs.forEach((_, i) => ys.forEach((__, j) => { const c = cell(i, j); if (c.v !== null) vals.push(c.v); }));
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const t = (v: number) => (hi === lo ? 0.5 : (v - lo) / (hi - lo));
  return <Frame width={W} height={H} title={title}>
    {ys.map((y, j) => <text key={'y' + j} x={left - 8} y={top + j * ch + ch / 2 + 4} textAnchor="end" className="wb-tick">{String(y)}</text>)}
    {xs.map((x, i) => <text key={'x' + i} x={left + i * cw + cw / 2} y={top + ys.length * ch + 16} textAnchor="middle" className="wb-tick">{String(x)}</text>)}
    {xs.map((x, i) => ys.map((y, j) => {
      const c = cell(i, j); const k = c.v === null ? 0 : t(c.v);
      return <g key={`${i}-${j}`}>
        <rect x={left + i * cw + 1} y={top + j * ch + 1} width={cw - 2} height={ch - 2} rx={3}
          fill={c.v === null ? 'url(#wb-hatch)' : `color-mix(in oklab, var(--wb-seq-hi) ${Math.round(15 + 85 * k)}%, var(--wb-seq-lo))`}>
          <title>{`${xLabel} ${x}, ${yLabel} ${y}: ${c.v === null ? 'no defined value' : fmt(c.v)} (N=${c.n})`}</title>
        </rect>
        <text x={left + i * cw + cw / 2} y={top + j * ch + ch / 2 + 4} textAnchor="middle" className={k > 0.55 ? 'wb-cell-dark' : 'wb-cell'}>{c.v === null ? '—' : fmt(c.v, 2)}</text>
      </g>;
    }))}
    <defs><pattern id="wb-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="var(--line)" strokeWidth="2" /></pattern></defs>
    <text x={left + (xs.length * cw) / 2} y={H - 6} textAnchor="middle" className="wb-label">{xLabel} · darker = higher ({better} is better)</text>
    <text x={12} y={top + (ys.length * ch) / 2} textAnchor="middle" className="wb-label" transform={`rotate(-90 12 ${top + (ys.length * ch) / 2})`}>{yLabel}</text>
  </Frame>;
}
