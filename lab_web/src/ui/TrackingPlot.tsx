// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useMemo, useState } from 'react';

import type { CatalogEntry } from '../bundle/load';
import type { DecodedBundle } from '../bundle/model';

/** tracking/<id>.json, written by tools/build_catalog.py (tracking_series). */
export interface TrackingSeries {
  definition: string;
  by: string;
  cite: string;
  window_sim: [number, number];
  t: number[]; // sim seconds since FollowPath acceptance
  e: number[]; // metres
  stats: { n: number; mean: number; p95: number; max: number };
}

const W = 640;
const H = 200;
const M = { l: 44, r: 92, t: 12, b: 30 };

/** Nice axis steps: 1, 2 or 5 x 10^k. */
function step(span: number, target: number): number {
  const raw = span / target;
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * p).find((s) => s >= raw) ?? raw;
}

/** The index of the sample nearest `t` (t is sorted). */
function nearest(ts: number[], t: number): number {
  let lo = 0;
  let hi = ts.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (ts[mid] < t) lo = mid;
    else hi = mid;
  }
  return Math.abs(ts[lo] - t) <= Math.abs(ts[hi] - t) ? lo : hi;
}

/**
 * The tracking error of a recorded real run over its FollowPath window.
 * The series is 1C's definition, recomputed at site build by 1C's own code
 * and checked there against the recorded statistics; this component also
 * refuses to draw it unless its n / mean / p95 / max equal the bundle's.
 */
export function TrackingPlot({ entry, bundle, dataUrl }: { entry: CatalogEntry; bundle: DecodedBundle; dataUrl: string }) {
  const [series, setSeries] = useState<TrackingSeries | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [at, setAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSeries(null);
    setProblem(null);
    fetch(dataUrl, { credentials: 'omit' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((s: TrackingSeries) => {
        if (cancelled) return;
        const rec = (bundle.recording?.meta as Record<string, any> | undefined)?.tracking_error_m;
        const same = rec && s.t.length === s.e.length && s.e.length === rec.n && s.stats.n === rec.n &&
          s.stats.mean === rec.mean && s.stats.p95 === rec.p95 && s.stats.max === rec.max;
        if (!same) setProblem('the tracking series does not match this bundle\'s recorded statistics, so it is not drawn');
        else setSeries(s);
      })
      .catch((exc: Error) => !cancelled && setProblem(`cannot load the tracking series: ${exc.message}`));
    return () => {
      cancelled = true;
    };
  }, [dataUrl, bundle]);

  const geom = useMemo(() => {
    if (!series) return null;
    const tMax = series.t[series.t.length - 1] || 1;
    const yStep = step(series.stats.max, 4);
    const yMax = Math.ceil(series.stats.max / yStep) * yStep;
    const x = (t: number) => M.l + (t / tMax) * (W - M.l - M.r);
    const y = (e: number) => H - M.b - (e / yMax) * (H - M.t - M.b);
    let d = '';
    series.t.forEach((t, i) => { d += `${i ? 'L' : 'M'}${x(t).toFixed(1)},${y(series.e[i]).toFixed(1)}`; });
    const xs = step(tMax, 6);
    const xTicks = Array.from({ length: Math.floor(tMax / xs) + 1 }, (_, i) => i * xs);
    const yTicks = Array.from({ length: Math.round(yMax / yStep) + 1 }, (_, i) => i * yStep);
    return { tMax, yMax, x, y, d, xTicks, yTicks };
  }, [series]);

  const p = bundle.provenance;
  const provenance = (
    <p className="run-prov" data-testid="run-provenance">
      <strong>Replay — recorded real run.</strong>{' '}
      Commit <code>{p.git_commit ? p.git_commit.slice(0, 7) : 'not recorded'}</code>
      {p.git_dirty ? ' (dirty)' : ''} · seed {p.seed === null ? 'none (a real run is not seeded)' : <code>{p.seed}</code>}
      {' '}· bundle <code title={bundle.contentHash}>{bundle.contentHash.slice(0, 19)}…</code>
      {p.rosbag && <> · rosbag <code title={p.rosbag.sha256}>{p.rosbag.sha256.slice(0, 12)}…</code></>}
    </p>
  );

  if (problem) return <section className="tracking">{provenance}<p className="note">Not drawn: {problem}.</p></section>;
  if (!series || !geom) return <section className="tracking">{provenance}<p className="note">Loading the tracking error…</p></section>;

  const s = series.stats;
  const i = at === null ? null : at;
  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const xv = ((e.clientX - r.left) / r.width) * W;
    const t = ((xv - M.l) / (W - M.l - M.r)) * geom.tMax;
    setAt(t < 0 || t > geom.tMax ? null : nearest(series.t, t));
  };
  const onKey = (e: React.KeyboardEvent<SVGSVGElement>) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    const d = (e.key === 'ArrowRight' ? 1 : -1) * (e.shiftKey ? 50 : 1);
    setAt((cur) => Math.max(0, Math.min(series.t.length - 1, (cur ?? 0) + d)));
  };

  return (
    <section className="tracking" aria-labelledby="tracking-h" data-testid="tracking">
      {provenance}
      <h3 id="tracking-h">Tracking error: ground truth to the published plan (m)</h3>
      <div className="plot-wrap">
        <div className="plot-tip" data-testid={i !== null ? 'tracking-tip' : undefined} role="status">
          {i !== null
            ? <><strong>{series.e[i].toFixed(3)} m</strong> at {series.t[i].toFixed(2)} s</>
            : <span className="note">Point at the plot, or focus it and use ← →, to read a sample.</span>}
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} className="plot" role="img" tabIndex={0} data-testid="tracking-plot"
          aria-label={`Tracking error over ${series.t.length} ground-truth samples; mean ${s.mean.toFixed(3)} m, p95 ${s.p95.toFixed(3)} m, max ${s.max.toFixed(3)} m. Arrow keys read the samples.`}
          onPointerMove={onMove} onPointerLeave={() => setAt(null)} onKeyDown={onKey}>
          {geom.yTicks.map((v) => (
            <g key={`y${v}`}>
              <line className="grid" x1={M.l} x2={W - M.r} y1={geom.y(v)} y2={geom.y(v)} />
              <text className="tick" x={M.l - 6} y={geom.y(v) + 4} textAnchor="end">{v.toFixed(2)}</text>
            </g>
          ))}
          {geom.xTicks.map((v) => (
            <text key={`x${v}`} className="tick" x={geom.x(v)} y={H - M.b + 16} textAnchor="middle">{v}</text>
          ))}
          <text className="axis-label" x={(M.l + W - M.r) / 2} y={H - 2} textAnchor="middle">
            sim seconds since FollowPath accepted the path
          </text>
          {([['mean', s.mean], ['p95', s.p95]] as Array<[string, number]>).map(([name, v]) => (
            <g key={name}>
              <line className="ref" x1={M.l} x2={W - M.r} y1={geom.y(v)} y2={geom.y(v)} />
              <text className="ref-label" x={W - M.r + 6} y={geom.y(v) + 4}>{name} {v.toFixed(3)}</text>
            </g>
          ))}
          <path className="series" d={geom.d} />
          {i !== null && (
            <g className="crosshair">
              <line x1={geom.x(series.t[i])} x2={geom.x(series.t[i])} y1={M.t} y2={H - M.b} />
              <circle cx={geom.x(series.t[i])} cy={geom.y(series.e[i])} r={4} />
            </g>
          )}
        </svg>
      </div>
      <table className="rows-table" data-testid="tracking-table">
        <caption className="note">The recorded statistics (the table view of the plot)</caption>
        <thead><tr><th>samples</th><th>mean</th><th>p95</th><th>max</th></tr></thead>
        <tbody><tr>
          <td>{s.n}</td><td>{s.mean.toFixed(3)} m</td><td>{s.p95.toFixed(3)} m</td><td>{s.max.toFixed(3)} m</td>
        </tr></tbody>
      </table>
      <p className="cite">
        Definition: {series.definition}. Series: {series.by}. Every sample:{' '}
        <a href={dataUrl}>{entry.id}.json</a>. Evidence: {series.cite}.
      </p>
    </section>
  );
}
