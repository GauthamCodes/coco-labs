// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useState } from 'react';

import type { Catalog } from '../../bundle/load';
import type { MovePart } from '../../move/catalog';
import { fmt } from '../../move/view';
import { DriveView } from './DriveView';
import { ReplanView } from './ReplanView';

type Sub = 'drive' | 'people' | 'run15' | 'replan' | 'evidence';
const SUBS: Array<[Sub, string]> = [
  ['drive', 'Same path, three controllers'], ['people', 'People on the apron'],
  ['run15', 'Run 15: "0 of 819"'], ['replan', 'When the map is wrong (D* Lite)'], ['evidence', 'What is proven'],
];

/** Lab 5: Move. Every path, candidate and number on it comes from Nav2 (recorded) or coco_lab. */
export function MoveLab({ catalog, reducedMotion }: { catalog: Catalog; reducedMotion: boolean }) {
  const part = (catalog as Catalog & { move?: MovePart }).move;
  const [sub, setSub] = useState<Sub>(() => {
    const v = new URLSearchParams(window.location.search).get('move');
    return (SUBS.find(([id]) => id === v)?.[0]) ?? 'drive';
  });
  if (!part) return <p className="error">This site was built without Lab 5.</p>;
  return (
    <div className="loc move-lab">
      <p className="lede"><strong>A path is not a motion.</strong> The global planner draws a line on the map once.
        Ten times a second a local controller has to turn that line into a speed and a turn rate — with the robot's
        real limits, from where the robot <em>thinks</em> it is, around whatever is in the way.</p>
      <Layers />
      <nav className="seg" aria-label="Lab 5 sections">
        {SUBS.map(([id, label]) => (
          <button key={id} type="button" className={sub === id ? 'seg-btn active' : 'seg-btn'} aria-pressed={sub === id}
            onClick={() => setSub(id)} data-testid={`move-sub-${id}`}>{label}</button>))}
      </nav>
      {sub === 'drive' && <DriveView part={part} reducedMotion={reducedMotion} scenarioIds={['static_room']} />}
      {sub === 'people' && <DriveView part={part} reducedMotion={reducedMotion} scenarioIds={['crossing', 'oncoming']}
        intro="The person is a moving obstacle the global path knows nothing about. It does not move the path: only the local controller, and the collision monitor below it, can react." />}
      {sub === 'run15' && <Run15 part={part} reducedMotion={reducedMotion} />}
      {sub === 'replan' && <ReplanView catalog={catalog} part={part} reducedMotion={reducedMotion} />}
      {sub === 'evidence' && <Evidence part={part} />}
    </div>
  );
}

/** The command chain, drawn: two layers, and what sits between them and the wheels. */
function Layers() {
  const steps = [
    ['global planner', 'once: the whole path (here SmacPlanner2D, frozen in a file)'],
    ['local controller', '10 Hz: DWB, MPPI or Regulated Pure Pursuit'],
    ['velocity smoother', 'caps acceleration'],
    ['collision monitor', 'slows or stops near what the LiDAR sees'],
    ['cmd_vel_arbiter', 'the only thing that drives the wheels'],
  ];
  return (
    <ol className="chain" aria-label="From path to wheels" data-testid="move-chain">
      {steps.map(([name, what], i) => (
        <li key={name} className={i === 0 ? 'chain-global' : i === 1 ? 'chain-local' : ''}>
          <strong>{name}</strong><span>{what}</span></li>))}
    </ol>
  );
}

function Run15({ part, reducedMotion }: { part: MovePart; reducedMotion: boolean }) {
  const res = part.drive.results;
  const sc = res.status === 'measured' ? res.scenarios[part.run15.reproduced] : null;
  const m = sc && sc.status === 'measured' ? sc : null;
  return (
    <>
      <section className="history" data-testid="move-run15-history">
        <h2>History: run 15, as it was recorded</h2>
        <p className="note">From COCO's 20-run fetch matrix (the v1 wedge world, 2026-07). The robot had picked its
          target and was driving home when AMCL put it 3.4 m from where it really was — in a corridor the map
          deliberately left featureless. The global planner still had a path. The local controller rejected every
          single candidate:</p>
        <pre className="quote">{part.run15.quotes.slice(0, 3).join('\n')}</pre>
        <pre className="quote">{part.run15.quotes.slice(3).join('\n')}</pre>
        <p className="cite">Quoted verbatim (checked at site build): {part.run15.source}</p>
      </section>
      <section>
        <h2>The same mechanism, reproduced here — not run 15</h2>
        <p className="note">That world and that corridor are not this arena, so run 15 itself cannot be re-run. What
          can be: tell AMCL the robot stands 3.4 m from where it is (one operator <code>/initialpose</code>, the
          RViz "2D Pose Estimate" button), then hand each controller the same global path.</p>
        {m ? (
          <ul className="claims" data-testid="move-run15-summary">
            {Object.entries(m.controllers).map(([c, r]) => (
              <li key={c}><strong>{c}:</strong> {Object.entries(r.outcomes).map(([o, n]) => `${n} ${o}`).join(', ')}
                {' '}of {r.runs}{r.zero_valid_cycles ? ` · control cycles with 0 valid candidates per run: ${r.zero_valid_cycles.join(', ')}` : ''}
                {r.min_clearance_static_m.min !== null ? ` · closest to a wall: ${fmt(r.min_clearance_static_m.min, 3)} m` : ''}</li>))}
          </ul>
        ) : <p className="note" data-testid="move-run15-none">Not yet measured.</p>}
      </section>
      <DriveView part={part} reducedMotion={reducedMotion} scenarioIds={[part.run15.reproduced]}
        intro="Solid: where the robot is (Gazebo). Hollow: where it believes it is. The candidates are drawn where the controller thought they were." />
    </>
  );
}

function Evidence({ part }: { part: MovePart }) {
  const res = part.drive.results;
  return (
    <section className="evidence" data-testid="move-evidence">
      <h2>What is proven, and where</h2>
      <ul className="claims">
        {part.claims.map((c) => (
          <li key={c.id}><p>{c.text}</p><p className="cite">Evidence: {c.cites.join('; ')}</p></li>))}
      </ul>
      <h2>The controllers</h2>
      <ul className="claims">
        {part.controllers.map((c) => (
          <li key={c.id}><p><strong>{c.name}.</strong> {c.how}</p><p className="cite">{c.cites.join('; ')}</p></li>))}
      </ul>
      <h2>The measurements</h2>
      {res.status !== 'measured' ? <p className="note" data-testid="move-results-none">Not yet measured.</p> : (
        <>
          {Object.entries(res.scenarios).map(([id, sc]) => (
            <div key={id}>
              <h3>{sc.status === 'measured' ? sc.title : id}</h3>
              {sc.status !== 'measured' ? <p className="note">Not yet measured.</p> : (
                <div className="scroll-x"><table className="race-table" data-testid={`move-results-${id}`}>
                  <thead><tr><th>controller</th><th>runs</th><th>outcomes</th><th>tracking mean (median)</th>
                    <th>time (median, reached)</th><th>RMS v̇ / ω̇ (median)</th><th>min clearance (min over runs)</th><th>contacts</th></tr></thead>
                  <tbody>{Object.entries(sc.controllers).map(([c, r]) => (
                    <tr key={c}><td>{c}</td><td>{r.runs}</td>
                      <td>{Object.entries(r.outcomes).map(([o, n]) => `${n} ${o}`).join(', ')}{r.error_codes.length ? ` (codes ${r.error_codes.join(', ')})` : ''}</td>
                      <td>{fmt(r.tracking_mean_m.median, 3)} m</td><td>{fmt(r.time_s_succeeded.median, 1)} s</td>
                      <td>{fmt(r.rms_linear_accel.median)} / {fmt(r.rms_angular_accel.median)}</td>
                      <td>{fmt(r.min_clearance_m.min, 3)} m</td><td>{r.contacts}</td></tr>))}</tbody>
                </table></div>
              )}
            </div>))}
          {res.void.length > 0 && <p className="note">Void attempts (infrastructure, never in a statistic):
            {' '}{res.void.map((v) => `${v.run} (${v.reason ?? '?'})`).join('; ')}</p>}
          <p className="note">Small samples (a few runs per controller, fresh simulator each): distributions, not rates.
            Every number is recomputed from the recordings at site build. Write-up: docs/labs/LAB5_MOVE.md.</p>
        </>
      )}
    </section>
  );
}
