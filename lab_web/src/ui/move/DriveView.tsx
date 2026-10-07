// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useMemo, useState } from 'react';

import { modeLabel } from '../../model/mode';
import type { ControllerInfo, ControllerResult, DriveEntry, MovePart } from '../../move/catalog';
import type { DecodedDriveBundle, DriveRun } from '../../move/decode';
import {
  candidatesAt, chosenAt, evalAt, fmt, footprint, monitorAt, rowAt, trackAt, valuesAt,
} from '../../move/view';
import { Clock, frameOf, MapSvg, pts, useClock, useDrive, Walls, X, Y, type Frame } from './shared';

const OUTCOME_WORDS: Record<string, string> = {
  succeeded: 'reached the goal', follow_failed: 'gave up', failed: 'did not start', error: 'error',
};
const ERROR_WORDS: Record<number, string> = {
  104: 'patience exceeded', 105: 'failed to make progress (stuck 10 s)', 106: 'no valid control', 107: 'timed out',
};

export function outcomeText(run: { outcome: string; record?: Record<string, unknown> }): string {
  const code = Number(run.record?.error_code ?? 0);
  return OUTCOME_WORDS[run.outcome] + (code && ERROR_WORDS[code] ? `: ${ERROR_WORDS[code]}` : code ? ` (code ${code})` : '');
}

function pathXY(b: DecodedDriveBundle): Array<[number, number]> {
  const p = b.scenario.path;
  const out: Array<[number, number]> = [];
  for (let i = 0; i < p.length; i += 3) out.push([p[i], p[i + 1]]);
  return out;
}

function trajXY(run: DriveRun, until = Infinity, step = 5): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (let i = 0; i < run.gt.length; i += 4 * step) {
    if (run.gt[i] > until) break;
    out.push([run.gt[i + 1], run.gt[i + 2]]);
  }
  return out;
}

/** The scenario's frame: the path and every run, padded. */
function frameFor(b: DecodedDriveBundle): Frame {
  const xs: number[] = [];
  const ys: number[] = [];
  for (const [x, y] of pathXY(b)) { xs.push(x); ys.push(y); }
  for (const r of b.runs) for (const [x, y] of trajXY(r, Infinity, 25)) { xs.push(x); ys.push(y); }
  return frameOf(xs, ys, 1.2, 60);
}

export function DriveView({ part, reducedMotion, scenarioIds, intro }: {
  part: MovePart; reducedMotion: boolean; scenarioIds: string[]; intro?: string;
}) {
  const entries = part.drive.bundles.filter((e) => scenarioIds.includes(e.id));
  const [sid, setSid] = useState(entries[0]?.id);
  const entry = entries.find((e) => e.id === sid) ?? entries[0];
  if (!entry) {
    return <p className="note" data-testid="move-drive-none">No recorded controller runs for {scenarioIds.join(', ')}
      {' '}are in this build yet (not yet measured).</p>;
  }
  return (
    <>
      {entries.length > 1 && (
        <nav className="seg" aria-label="Scenario">
          {entries.map((e) => (
            <button key={e.id} type="button" className={e.id === entry.id ? 'seg-btn active' : 'seg-btn'}
              aria-pressed={e.id === entry.id} onClick={() => setSid(e.id)} data-testid={`move-scenario-${e.id}`}>
              {e.title}</button>))}
        </nav>
      )}
      {intro && <p className="lede">{intro}</p>}
      <Scenario key={entry.id} part={part} entry={entry} reducedMotion={reducedMotion} />
    </>
  );
}

function Scenario({ part, entry, reducedMotion }: { part: MovePart; entry: DriveEntry; reducedMotion: boolean }) {
  const { b, error } = useDrive(entry);
  const ctrls = part.controllers;
  const [shown, setShown] = useState<string[]>(ctrls.map((c) => c.id));
  const [focusId, setFocusId] = useState<string | null>(null);
  const focus = b?.runs.find((r) => r.id === focusId) ?? b?.runs.find((r) => r.rollouts) ?? b?.runs[0] ?? null;
  const clock = useClock(focus?.window[0] ?? 0, focus?.window[1] ?? 1, reducedMotion);
  const f = useMemo(() => (b ? frameFor(b) : null), [b]);
  if (error) return <div className="error" role="alert">Refused: {error}</div>;
  if (!b || !f || !focus) return <p className="loading">Loading and checking the recording…</p>;
  const colour = (c: string) => ctrls.find((x) => x.id === c)?.colour ?? '#888';
  return (
    <main className="stage">
      <div className="canvas-col">
        <div className="loc-head">
          <span className="mode-badge mode-recorded" data-testid="move-mode">{modeLabel(b.provenance).text}</span>
        </div>
        <p className="lede">{entry.lesson}</p>
        <DriveMap b={b} f={f} focus={focus} t={clock.t} shown={shown} colour={colour} />
        <Legend />
        <Clock {...clock} t0={focus.window[0]} t1={focus.window[1]} prefix="move-drive" />
        <Readout run={focus} t={clock.t} info={ctrls.find((c) => c.id === focus.controller)!} />
      </div>
      <aside className="side">
        <section>
          <h2>Controllers</h2>
          <div className="bay-buttons" role="group" aria-label="Show controllers">
            {ctrls.map((c) => (
              <button key={c.id} type="button" className={shown.includes(c.id) ? 'seg-btn active' : 'seg-btn'}
                aria-pressed={shown.includes(c.id)} data-testid={`move-show-${c.id}`}
                onClick={() => setShown((s) => (s.includes(c.id) ? s.filter((x) => x !== c.id) : [...s, c.id]))}>
                <i className="sw" style={{ background: c.colour, height: 4, border: 0 }} /> {c.id}</button>))}
          </div>
          <div className="field"><span>Watch one run closely</span>
            <select value={focus.id} onChange={(ev) => setFocusId(ev.target.value)} aria-label="Focus run"
              data-testid="move-focus">
              {b.runs.map((r) => <option key={r.id} value={r.id}>{r.id.replace('_', ' run ')} — {outcomeText(r)}
                {r.rollouts ? ' (candidates shown)' : ''}</option>)}
            </select></div>
          <p className="note">Every run of a controller drives the same frozen path file (sha256
            {' '}<code>{String(b.scenario.path_sha256).slice(0, 12)}…</code>) from the same start. Candidates are
            kept for the first run of each controller only (bundle size).</p>
        </section>
        <Compare part={part} entry={entry} />
        <Provenance b={b} entry={entry} />
      </aside>
    </main>
  );
}

function DriveMap({ b, f, focus, t, shown, colour }: {
  b: DecodedDriveBundle; f: Frame; focus: DriveRun; t: number; shown: string[]; colour: (c: string) => string;
}) {
  const path = pathXY(b);
  const pose = valuesAt(focus.gt, 4, t);
  const belief = valuesAt(focus.amcl, 4, t);
  const cand = candidatesAt(focus.rollouts, t);
  const chosen = chosenAt(focus, t);
  const clr = focus.metrics.clearance;
  const goal = b.scenario.goal as number[];
  return (
    <MapSvg f={f} testid="move-map" label={`${b.scenario.title}: the frozen global path and the robot's drive, ` +
      `${focus.controller} ${focus.id}, at t = ${(t - focus.window[0]).toFixed(1)} s`}>
      <Walls f={f} boxes={b.scenario.boxes} />
      <polyline className="mv-path" points={pts(f, path)} />
      <circle className="mv-goal" cx={X(f, goal[0])} cy={Y(f, goal[1])} r={0.12 * f.s} />
      {b.runs.filter((r) => shown.includes(r.controller) && r !== focus).map((r) => (
        <polyline key={r.id} className="mv-traj" points={pts(f, trajXY(r))} style={{ stroke: colour(r.controller) }} />))}
      <polyline className="mv-traj focus" points={pts(f, trajXY(focus, t, 2))} style={{ stroke: colour(focus.controller) }} />
      {cand?.cands.map((c, i) => (
        <polyline key={i} points={pts(f, c.pts)}
          className={c.valid === null ? 'mv-cand sampled' : c.valid ? (c.best ? 'mv-cand best' : 'mv-cand ok') : 'mv-cand bad'} />))}
      {chosen && chosen.length > 1 && <polyline className="mv-chosen" points={pts(f, chosen)} />}
      {Object.entries(focus.actors).map(([aid, tr]) => {
        const p = trackAt(tr, t);
        return (
          <g key={aid}>
            <polyline className="mv-actor-track" points={pts(f, Array.from({ length: tr.length / 4 }, (_, i) => [tr[4 * i + 1], tr[4 * i + 2]]))} />
            {p && <circle className="mv-actor" cx={X(f, p[0])} cy={Y(f, p[1])} r={b.scenario.actor_radius * f.s}
              data-testid="move-actor" />}
          </g>);
      })}
      {belief && <polygon className="mv-belief" points={pts(f, footprint(belief[0], belief[1], belief[2]))} />}
      {pose && <polygon className="mv-robot" points={pts(f, footprint(pose[0], pose[1], pose[2]))}
        style={{ fill: colour(focus.controller) }} />}
      {[clr.static, clr.actor].filter((c) => c.t !== null).map((c, i) => {
        const at = rowAt(focus.gt, 4, c.t!);
        if (at < 0) return null;
        const [x, y, yaw] = Array.from(focus.gt.subarray(at * 4 + 1, at * 4 + 4));
        return <polygon key={i} className="mv-closest" points={pts(f, footprint(x, y, yaw))} />;
      })}
    </MapSvg>
  );
}

function Legend() {
  return (
    <ul className="legend" aria-label="Legend">
      <li><i className="sw mv-k-path" />global path (frozen)</li>
      <li><i className="sw mv-k-ok" />candidate kept</li>
      <li><i className="sw mv-k-bad" />candidate rejected</li>
      <li><i className="sw mv-k-sampled" />MPPI sample</li>
      <li><i className="sw mv-k-chosen" />chosen / checked arc</li>
      <li><i className="sw mv-k-belief" />where it thinks it is</li>
      <li><i className="sw mv-k-actor" />person</li>
      <li><i className="sw mv-k-closest" />closest approach</li>
    </ul>
  );
}

function Readout({ run, t, info }: { run: DriveRun; t: number; info: ControllerInfo }) {
  const cmd = valuesAt(run.cmd, 3, t);
  const wheel = valuesAt(run.wheel, 3, t);
  const ev = evalAt(run, t);
  const pose = valuesAt(run.gt, 4, t);
  const bel = valuesAt(run.amcl, 4, t);
  const gap = pose && bel ? Math.hypot(pose[0] - bel[0], pose[1] - bel[1]) : null;
  return (
    <div className="narrate" role="status" data-testid="move-readout">
      <p><strong>{info.name}.</strong> {info.how}</p>
      <dl className="rows">
        <div className="row"><dt>controller asked</dt><dd>{cmd ? `v ${fmt(cmd[0])} m/s, ω ${fmt(cmd[1])} rad/s` : '—'}</dd></div>
        <div className="row"><dt>wheels got</dt><dd>{wheel ? `v ${fmt(wheel[0])} m/s, ω ${fmt(wheel[1])} rad/s` : '—'}
          {' '}(after the velocity smoother and the collision monitor)</dd></div>
        <div className="row"><dt>collision monitor</dt><dd>{monitorAt(run, t)}</dd></div>
        {ev && <div className="row"><dt>DWB this cycle</dt><dd data-testid="move-eval">{ev[1]} of {ev[0]} candidates valid</dd></div>}
        <div className="row"><dt>belief vs truth</dt><dd>{gap === null ? '—' : `${fmt(gap)} m apart (AMCL vs Gazebo)`}</dd></div>
        <div className="row"><dt>outcome</dt><dd>{outcomeText(run)}</dd></div>
      </dl>
      <p className="note">Shown: {info.shows}.</p>
    </div>
  );
}

const PRED = [['tracking', 'stays closest to the path'], ['clearance', 'keeps the most room'],
  ['smooth', 'turns most smoothly']] as const;

function Compare({ part, entry }: { part: MovePart; entry: DriveEntry }) {
  const [pred, setPred] = useState<string | null>(null);
  const [q, setQ] = useState<(typeof PRED)[number][0]>('tracking');
  const [shown, setShown] = useState(false);
  const res = part.drive.results;
  const sc = res.status === 'measured' ? res.scenarios[entry.id] : null;
  if (!sc || sc.status !== 'measured') return <p className="note">Not yet measured.</p>;
  const ctrl = Object.keys(sc.controllers);
  const pick = (c: ControllerResult) => q === 'tracking' ? c.tracking_mean_m.median
    : q === 'clearance' ? -(c.min_clearance_m.median ?? Infinity) : c.rms_angular_accel.median;
  const winner = ctrl.filter((c) => pick(sc.controllers[c]) !== null)
    .sort((a, z) => (pick(sc.controllers[a]) ?? 0) - (pick(sc.controllers[z]) ?? 0))[0];
  return (
    <section>
      <h2>Compare (measured)</h2>
      {!shown && (
        <fieldset className="predict"><legend>Predict first</legend>
          <div className="field"><span>Which controller…</span>
            <select value={q} onChange={(ev) => setQ(ev.target.value as typeof q)} aria-label="Question">
              {PRED.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
          <div className="field">{ctrl.map((c) => (
            <label key={c} className="choice"><input type="radio" name="move-pred" checked={pred === c}
              onChange={() => setPred(c)} data-testid={`move-pred-${c}`} />{c}</label>))}</div>
          <button type="button" className="run" disabled={!pred} onClick={() => setShown(true)}
            data-testid="move-reveal">Reveal the measurements</button>
        </fieldset>
      )}
      {shown && (
        <>
          <p className={`reveal ${winner === pred ? 'right' : 'wrong'}`} data-testid="move-revealed">
            On the median run, {winner} {PRED.find((p) => p[0] === q)![1]}; you said {pred}.</p>
          <div className="scroll-x"><table className="race-table" data-testid="move-table">
            <caption className="note">Median over runs [min–max]; times only for runs that reached the goal.</caption>
            <thead><tr><th>controller</th><th>reached the goal</th><th>tracking error, mean</th><th>travel time</th>
              <th>RMS ω̇ (rad/s²)</th><th>min clearance</th></tr></thead>
            <tbody>{ctrl.map((c) => {
              const r = sc.controllers[c];
              const d = (x: { median: number | null; min: number | null; max: number | null }, u: string, k = 2) =>
                x.median === null ? '—' : `${fmt(x.median, k)} ${u} [${fmt(x.min, k)}–${fmt(x.max, k)}]`;
              return (
                <tr key={c}><td>{c}</td><td>{r.outcomes.succeeded ?? 0} / {r.runs}</td>
                  <td>{d(r.tracking_mean_m, 'm', 3)}</td><td>{d(r.time_s_succeeded, 's', 1)}</td>
                  <td>{d(r.rms_angular_accel, '', 2)}</td><td>{d(r.min_clearance_m, 'm', 3)}{r.contacts ? ` · ${r.contacts} contact(s)` : ''}</td></tr>);
            })}</tbody>
          </table></div>
          <p className="note">{sc.controllers[ctrl[0]].runs} runs per controller, each on a fresh simulator: a small
            sample, not a rate. Definitions: docs/labs/LAB5_MOVE.md §2.</p>
        </>
      )}
    </section>
  );
}

function Provenance({ b, entry }: { b: DecodedDriveBundle; entry: DriveEntry }) {
  const p = b.provenance;
  return (
    <section>
      <h2>Where this came from</h2>
      <dl className="rows">
        <div className="row"><dt>recorded</dt><dd>Gazebo Harmonic + Nav2 1.3.11, {b.runs.length} runs, fresh simulator each</dd></div>
        <div className="row"><dt>checked by</dt><dd>{entry.validated.by}; {entry.validated.replay}</dd></div>
        <div className="row"><dt>content</dt><dd><code>{b.contentHash.slice(0, 19)}…</code></dd></div>
        {p.rosbag && <div className="row"><dt>recordings</dt><dd>rosbag2 set <code>{p.rosbag.sha256.slice(0, 12)}…</code></dd></div>}
        {p.git_commit && <div className="row"><dt>code</dt><dd><code>{p.git_commit.slice(0, 7)}</code>{p.git_dirty ? ' (dirty)' : ''}</dd></div>}
      </dl>
      <p className="cite">Evidence: {entry.cites.join('; ')}</p>
    </section>
  );
}
