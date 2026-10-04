// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from 'react';

import type { LocalisePart } from '../../loc/catalog';

interface Historical { claim: string; label: string; cite: string; caveat?: string; log?: string[] }
interface Exhibits {
  recovery_alpha: { title: string; historical: Historical; ab: LocalisePart['kidnap_ab']; sketch: string };
  aliasing: { title: string; historical: Historical; sketch: string };
  covariance: { title: string; historical: Historical;
    series: { t: number[]; err_xy: number[]; sigma_xy: number[]; scan_map_d: Array<number | null>; injection_t: number } };
  run15: { title: string; historical: Historical; ekf: LocalisePart['ekf_drift'];
    amcl?: NonNullable<LocalisePart['amcl_odom']>; note: string };
}

function Label({ text }: { text: string }) {
  return <p className="label-note"><strong>{text}</strong></p>;
}

function Cite({ text }: { text: string }) {
  return <p className="cite">Evidence: {text}</p>;
}

/** COCO's four documented localisation failures, each with its evidence. */
export function LocExhibits({ part, dataUrl }: { part: LocalisePart; dataUrl: (p: string) => string }) {
  const [ex, setEx] = useState<Exhibits | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    fetch(dataUrl(part.exhibits), { credentials: 'omit', cache: 'no-cache' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setEx).catch((e: Error) => setErr(e.message));
  }, [part, dataUrl]);
  if (err) return <p className="error">Cannot load the exhibits: {err}</p>;
  if (!ex) return <p className="loading">Loading the evidence…</p>;
  const sketchLink = (id: string, text: string) => (
    <a href={`?view=localise&scene=${id}`}>{text}</a>
  );
  return (
    <article className="exhibit" data-testid="loc-exhibits">
      <h2>Not a textbook: four times COCO's real localisation failed</h2>
      <p className="lede">Each one happened on the real ROS 2 stack and is in the record with its evidence.
        Nothing here is re-enacted on the robot; where you can try the idea yourself, the Sketch version is
        linked and labelled.</p>

      <section data-testid="exhibit-recovery-alpha">
        <h3>1. {ex.recovery_alpha.title}</h3>
        <p>{ex.recovery_alpha.historical.claim}</p>
        <Label text={ex.recovery_alpha.historical.label} />
        <Cite text={ex.recovery_alpha.historical.cite} />
        <ABResult ab={ex.recovery_alpha.ab} />
        <p>Try it: {sketchLink(ex.recovery_alpha.sketch, 'the kidnapped robot, in Sketch')} — turn injection off and on.</p>
      </section>

      <section data-testid="exhibit-aliasing">
        <h3>2. {ex.aliasing.title}</h3>
        <p>{ex.aliasing.historical.claim}</p>
        <pre className="log">{(ex.aliasing.historical.log ?? []).join('\n')}</pre>
        <Label text={ex.aliasing.historical.label} />
        <Cite text={ex.aliasing.historical.cite} />
        <p>Try it: {sketchLink(ex.aliasing.sketch, 'the twins room, in Sketch')} — a room that is the same room
          turned around. (A simulated analogue of the idea, not a replay of the event.)</p>
      </section>

      <section data-testid="exhibit-covariance">
        <h3>3. {ex.covariance.title}</h3>
        <p>{ex.covariance.historical.claim}</p>
        <CovPlot s={ex.covariance.series} />
        <p className="honest">{ex.covariance.historical.caveat}</p>
        <Label text={ex.covariance.historical.label} />
        <Cite text={ex.covariance.historical.cite} />
      </section>

      <section data-testid="exhibit-run15">
        <h3>4. {ex.run15.title}</h3>
        <p>{ex.run15.historical.claim}</p>
        <Label text={ex.run15.historical.label} />
        <Cite text={ex.run15.historical.cite} />
        <EkfResult ekf={ex.run15.ekf} />
        {ex.run15.amcl && <AmclResult amcl={ex.run15.amcl} />}
        <p className="note">{ex.run15.note}</p>
      </section>
    </article>
  );
}

function ABResult({ ab }: { ab: LocalisePart['kidnap_ab'] }) {
  if (ab.status !== 'measured') {
    return <p className="honest">The Phase 3 real-stack A/B (recovery_alpha on vs off): not yet measured.</p>;
  }
  return (
    <div className="honest" data-testid="exhibit-ab">
      <p><strong>Phase 3 asked the real stack directly (measured).</strong> {ab.definition}</p>
      <table className="rows-table">
        <thead><tr><th>arm</th><th>α slow / fast</th><th>recovered</th><th>times (s)</th></tr></thead>
        <tbody>
          {Object.entries(ab.arms).map(([arm, a]) => (
            <tr key={arm}><td>{arm}</td><td>{a.alpha_slow} / {a.alpha_fast}</td>
              <td>{a.recovered} of {a.n}{a.void ? ` (+${a.void} void)` : ''}</td>
              <td>{a.recovery_s.length ? a.recovery_s.map((v) => v.toFixed(1)).join(', ') : '—'}</td></tr>
          ))}
        </tbody>
      </table>
      {ab.fisher_one_sided_p !== undefined && (
        <p className="honest" data-testid="exhibit-ab-p">Is injection better here? Not shown: if the arm made no
          difference, a split at least this lopsided would happen with probability {ab.fisher_one_sided_p.toFixed(3)}
          (one-sided Fisher exact test, derived).</p>
      )}
      <TrialPlot trials={ab.trials} />
      <p className="note">Fresh simulator per trial; counts this small are not rates.</p>
      <Cite text={ab.cite} />
    </div>
  );
}

function TrialPlot({ trials }: { trials: Extract<LocalisePart['kidnap_ab'], { status: 'measured' }>['trials'] }) {
  const W = 640;
  const H = 180;
  const L = 40;
  const T = 8;
  const B = 24;
  const tmax = Math.max(1, ...trials.flatMap((t) => t.t));
  const ymax = Math.ceil(Math.max(1, ...trials.flatMap((t) => t.err_xy)));
  const sx = (v: number) => L + (v / tmax) * (W - L - 8);
  const sy = (v: number) => T + (1 - Math.min(v, ymax) / ymax) * (H - T - B);
  return (
    <svg className="plot" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="AMCL error after each kidnap, per trial">
      <line className="ref" x1={L} x2={W - 8} y1={sy(0.5)} y2={sy(0.5)} strokeDasharray="4 3" />
      <text className="tick" x={L - 4} y={sy(0.5) + 4} textAnchor="end">0.5</text>
      <text className="tick" x={L - 4} y={sy(ymax) + 8} textAnchor="end">{ymax}</text>
      <text className="axis-label" x={W - 8} y={H - 6} textAnchor="end">s after the kidnap</text>
      {trials.map((tr, i) => (
        <polyline key={i} fill="none" strokeWidth={1.8}
          stroke={tr.arm === 'recovery' ? '#E69F00' : '#CC79A7'}
          points={tr.t.map((t, j) => `${sx(t).toFixed(1)},${sy(tr.err_xy[j]).toFixed(1)}`).join(' ')} />
      ))}
      <text x={L + 6} y={T + 12} fill="#E69F00" fontSize={12}>injection on</text>
      <text x={L + 100} y={T + 12} fill="#CC79A7" fontSize={12}>injection off (as shipped)</text>
    </svg>
  );
}

function EkfResult({ ekf }: { ekf: LocalisePart['ekf_drift'] }) {
  if (ekf.status !== 'measured') {
    return <p className="honest">robot_localization (wheel odometry + IMU) on Phase 3 drives: not yet measured.</p>;
  }
  return (
    <div className="honest" data-testid="exhibit-ekf">
      <p><strong>What an EKF fusing the IMU does to the odometry AMCL leans on (measured, Phase 3).</strong> {ekf.config}</p>
      <table className="rows-table">
        <thead><tr><th>drive</th><th>driven</th><th>wheel odometry: final / max error</th><th>EKF (odometry + IMU): final / max error</th></tr></thead>
        <tbody>
          {ekf.drives.map((d) => (
            <tr key={`${d.session}/${d.drive}`}><td>{d.drive} ({d.session})</td>
              <td>{d.distance_m.toFixed(1)} m, {d.rotation_rad.toFixed(1)} rad</td>
              <td>{d.wheel_odom.final_pos_err_m.toFixed(2)} / {d.wheel_odom.max_pos_err_m.toFixed(2)} m</td>
              <td>{d.ekf.final_pos_err_m.toFixed(2)} / {d.ekf.max_pos_err_m.toFixed(2)} m</td></tr>
          ))}
        </tbody>
      </table>
      <Cite text={ekf.cite} />
    </div>
  );
}

function AmclResult({ amcl }: { amcl: NonNullable<LocalisePart['amcl_odom']> }) {
  if (amcl.status !== 'measured') {
    return <p className="honest">AMCL on each odometry, offline on the same scans: not yet measured.</p>;
  }
  const keyed = new Map(amcl.drives.map((d) => [`${d.session}/${d.drive}/${d.arm}`, d]));
  const rows = [...new Set(amcl.drives.map((d) => `${d.session}/${d.drive}`))];
  return (
    <div className="honest" data-testid="exhibit-amcl">
      <p><strong>And AMCL on top of each (measured, Phase 3).</strong> {amcl.definition}</p>
      <div className="scroll-x"><table className="rows-table">
        <thead><tr><th>drive</th><th>AMCL on wheel odometry: mean / max error</th><th>AMCL on the EKF: mean / max error</th></tr></thead>
        <tbody>
          {rows.map((r) => {
            const w = keyed.get(`${r}/wheel`);
            const e = keyed.get(`${r}/ekf`);
            const f = (d?: { mean_err_xy: number; max_err_xy: number }) =>
              (d ? `${d.mean_err_xy.toFixed(3)} / ${d.max_err_xy.toFixed(3)} m` : '—');
            return <tr key={r}><td>{r}</td><td>{f(w)}</td><td>{f(e)}</td></tr>;
          })}
        </tbody>
      </table></div>
      <Cite text={amcl.cite} />
    </div>
  );
}

function CovPlot({ s }: { s: Exhibits['covariance']['series'] }) {
  const W = 640;
  const H = 200;
  const L = 40;
  const T = 8;
  const B = 24;
  const t0 = s.t[0];
  const t1 = s.t[s.t.length - 1];
  const ymax = Math.ceil(Math.max(...s.err_xy, ...s.sigma_xy));
  const sx = (v: number) => L + ((v - t0) / (t1 - t0)) * (W - L - 8);
  const sy = (v: number) => T + (1 - v / ymax) * (H - T - B);
  const line = (vals: Array<number | null>) =>
    vals.map((v, i) => (v === null ? null : `${sx(s.t[i]).toFixed(1)},${sy(v).toFixed(1)}`)).filter(Boolean).join(' ');
  return (
    <figure>
      <svg className="plot" viewBox={`0 0 ${W} ${H}`} role="img" data-testid="exhibit-cov-plot"
        aria-label="AMCL's true error and its own sigma_xy around the injected divergence">
        {[0, ymax / 2, ymax].map((v) => (
          <g key={v}><line className="grid" x1={L} x2={W - 8} y1={sy(v)} y2={sy(v)} />
            <text className="tick" x={L - 4} y={sy(v) + 4} textAnchor="end">{v.toFixed(1)}</text></g>
        ))}
        <line x1={sx(s.injection_t)} x2={sx(s.injection_t)} y1={T} y2={H - B} stroke="#D55E00" strokeDasharray="6 4" />
        <polyline fill="none" stroke="#0072B2" strokeWidth={2} points={line(s.err_xy)} />
        <polyline fill="none" stroke="#E69F00" strokeWidth={2} points={line(s.sigma_xy)} />
        <polyline fill="none" stroke="#009E73" strokeWidth={1.5} points={line(s.scan_map_d)} />
        <text className="axis-label" x={W - 8} y={H - 6} textAnchor="end">sim time (s)</text>
        <text className="axis-label" x={4} y={T + 10}>m</text>
      </svg>
      <figcaption>
        <ul className="legend">
          <li><i className="sw" style={{ background: '#0072B2', height: 4, border: 0 }} />true error (ground truth, not available to the robot)</li>
          <li><i className="sw" style={{ background: '#E69F00', height: 4, border: 0 }} />AMCL's own σxy = √(cxx + cyy)</li>
          <li><i className="sw" style={{ background: '#009E73', height: 4, border: 0 }} />scan-vs-map mean endpoint distance</li>
          <li><i className="sw" style={{ background: '#D55E00', height: 4, border: 0 }} />the injection</li>
        </ul>
      </figcaption>
    </figure>
  );
}
