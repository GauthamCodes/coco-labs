// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { BundleError } from '../../bundle/errors';
import type { Catalog } from '../../bundle/load';
import { modeLabel } from '../../model/mode';
import type { MovePart, ReplanEntry } from '../../move/catalog';
import { loadReplanBytes, type DecodedReplanBundle } from '../../move/decode';
import { expandedIn, fmt, knownAt, planAt, robotAt, roundAt, steps, truthAt } from '../../move/view';
import { requestRecompute, workerStarted } from '../../worker/client';
import type { ReplanSpec } from '../../worker/protocol';
import { DATA, loadReplanEntry, type Files } from './shared';

interface Current { bundle: DecodedReplanBundle; files: Files; entry: ReplanEntry; by: 'catalog' | 'pyodide'; detail: string }
type Status = { state: 'idle' } | { state: 'busy' | 'done' | 'error'; message: string };

function useStep(n: number, reducedMotion: boolean) {
  const [k, setK] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { setK(0); setPlaying(false); }, [n]);
  useEffect(() => {
    if (!playing) return undefined;
    if (k >= n) { setPlaying(false); return undefined; }
    const id = window.setTimeout(() => setK((x) => Math.min(n, x + 1)), reducedMotion ? 300 : 160);
    return () => window.clearTimeout(id);
  }, [playing, k, n, reducedMotion]);
  return { k, setK, playing, setPlaying };
}

export function ReplanView({ catalog, part, reducedMotion }: { catalog: Catalog; part: MovePart; reducedMotion: boolean }) {
  const entries = part.replan.bundles;
  const [eid, setEid] = useState(entries[0]?.id);
  const entry = entries.find((e) => e.id === eid) ?? entries[0];
  const [cur, setCur] = useState<Current | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [painted, setPainted] = useState<Array<[number, number]>>([]);
  const [sense, setSense] = useState(2.5);
  const [seed, setSeed] = useState<number | null>(null);
  const [status, setStatus] = useState<Status>({ state: 'idle' });
  const busy = useRef(false);
  useEffect(() => {
    if (!entry) return undefined;
    let alive = true;
    setCur(null);
    setPainted([]);
    setSeed(null);
    setStatus({ state: 'idle' });
    loadReplanEntry(entry).then(({ bundle, files }) => alive && setCur({ bundle, files, entry, by: 'catalog',
      detail: `${entry.validated.by}; ${entry.validated.replay}` }))
      .catch((exc) => alive && setError(exc instanceof Error ? exc.message : String(exc)));
    return () => { alive = false; };
  }, [entry]);
  const b = cur?.bundle ?? null;
  const step = useStep(b ? steps(b) : 0, reducedMotion);
  const editable = entry?.kind === 'sketch' && !!catalog.wheel;

  const run = useCallback(async () => {
    if (!cur || busy.current || !catalog.wheel) return;
    busy.current = true;
    setStatus({ state: 'busy', message: workerStarted() ? 'coco_lab is driving the episode in your browser…'
      : `Loading Python (Pyodide ${__PYODIDE_VERSION__}) and coco_lab — the first run takes a while…` });
    try {
      const spec: ReplanSpec = { seed, sense_radius: sense, painted };
      const wheelUrl = new URL(`${DATA}${catalog.wheel.path}`, window.location.href).href;
      const t0 = performance.now();
      const r = await requestRecompute({ manifest: cur.files.manifest, arraysName: cur.files.arraysName,
        arraysFile: cur.files.arraysFile, spec, wheelUrl, wheelSha256: catalog.wheel.sha256 }, 'replan');
      if (!r.ok) {
        setStatus({ state: 'error', message: r.refused ? `Not run: ${r.error}` : `coco_lab could not run this: ${r.error}` });
        return;
      }
      const w = r.bundles[0];
      const bundle = await loadReplanBytes(w.manifest, w.arraysFile);
      if (bundle.contentHash !== w.contentHash) throw new BundleError('hash', 'the worker\'s bundle hash is not the decoder\'s');
      setCur({ bundle, entry: cur.entry, files: { manifest: w.manifest, arraysName: w.arraysName, arraysFile: w.arraysFile },
        by: 'pyodide', detail: `coco_lab ${r.cocoLabVersion} on Python ${r.pythonVersion} (Pyodide ${r.pyodideVersion})` });
      setPainted([]);
      setStatus({ state: 'done', message: `Done in ${((performance.now() - t0) / 1000).toFixed(1)} s (coco_lab: `
        + `${r.timings.search_ms.toFixed(0)} ms for ${r.timings.runs} plans).` });
    } catch (exc) {
      setStatus({ state: 'error', message: exc instanceof Error ? exc.message : String(exc) });
    } finally {
      busy.current = false;
    }
  }, [cur, catalog, seed, sense, painted]);

  if (!entry) return <p className="note">This build has no replanning bundle.</p>;
  const toggle = (r: number, c: number) => {
    if (!b || !editable) return;
    if ((r === b.world.start[0] && c === b.world.start[1]) || (r === b.world.goal[0] && c === b.world.goal[1])) return;
    setPainted((p) => (p.some(([x, y]) => x === r && y === c) ? p.filter(([x, y]) => x !== r || y !== c)
      : p.length < part.replan.limits.max_painted ? [...p, [r, c]] : p));
  };
  return (
    <>
      <div className="loc-head">
        <label className="picker-inline"><span>World</span>
          <select value={entry.id} onChange={(ev) => setEid(ev.target.value)} data-testid="move-replan-picker">
            {entries.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}</select></label>
        {b && <span className={`mode-badge ${modeLabel(b.provenance).kind === 'sketch' ? 'mode-sketch' : 'mode-glass-box'}`}
          data-testid="move-replan-mode">{modeLabel(b.provenance).text}</span>}
      </div>
      {error && <div className="error" role="alert">Refused: {error}</div>}
      {!b && !error && <p className="loading">Loading and checking the episode…</p>}
      {b && cur && (
        <main className="stage">
          <div className="canvas-col">
            <p className="lede">{entry.lesson}</p>
            <Grid b={b} k={step.k} painted={painted} onCell={toggle} editable={editable} />
            <ul className="legend" aria-label="Legend">
              <li><i className="sw mv-k-known" />on the robot's map</li>
              <li><i className="sw mv-k-hidden" />in the world, not on its map (yet)</li>
              <li><i className="sw mv-k-plan" />its plan now</li>
              <li><i className="sw mv-k-touched" />cells this plan's search touched</li>
              <li><i className="sw mv-k-sense" />what it can see</li>
            </ul>
            <div className="player" role="group" aria-label="Steps">
              <div className="player-buttons">
                <button type="button" className="play" data-testid="move-replan-play"
                  onClick={() => { if (!step.playing && step.k >= steps(b)) step.setK(0); step.setPlaying(!step.playing); }}>
                  {step.playing ? 'Pause' : 'Play'}</button>
                <button type="button" onClick={() => { step.setPlaying(false); step.setK(steps(b)); }}
                  data-testid="move-replan-end">End</button>
              </div>
              <input className="scrub" type="range" min={0} max={steps(b)} value={step.k} aria-label="Step"
                onChange={(ev) => { step.setPlaying(false); step.setK(Number(ev.target.value)); }} />
              <div className="player-pos">step {step.k} of {steps(b)}</div>
            </div>
            <Narrate b={b} k={step.k} />
            <Rounds b={b} k={step.k} onPick={(s) => { step.setPlaying(false); step.setK(s); }} />
          </div>
          <aside className="side">
            {editable && (
              <section>
                <h2>Change the world</h2>
                <p className="note">Click cells to add obstacles the robot's map does NOT have ({painted.length} painted).
                  It meets them only when they come within its sight.</p>
                <div className="field"><span>Sight: {sense.toFixed(1)} cells</span>
                  <input type="range" min={part.replan.limits.sense_radius[0]} max={part.replan.limits.sense_radius[1]}
                    step={0.5} value={sense} aria-label="Sensing radius" data-testid="move-replan-sense"
                    onChange={(ev) => setSense(Number(ev.target.value))} /></div>
                <div className="field"><span>World</span>
                  <button type="button" className="seg-btn" data-testid="move-replan-seed"
                    onClick={() => { setSeed((s) => ((s ?? b.provenance.seed ?? 0) + 1) % 10000); setPainted([]); }}>
                    {seed === null ? 'this one' : `new world (seed ${seed})`}</button></div>
                <button type="button" className="run" disabled={status.state === 'busy'} onClick={run}
                  data-testid="move-replan-run">{status.state === 'busy' ? 'Running…' : 'Run D* Lite (coco_lab, in your browser)'}</button>
                {status.state !== 'idle' && <p className={`edit-status ${status.state}`} role="status"
                  data-testid="move-replan-status">{status.message}</p>}
              </section>
            )}
            <section>
              <h2>The episode</h2>
              <dl className="rows" data-testid="move-replan-summary">
                <div className="row"><dt>outcome</dt><dd>{b.summary.status === 'reached' ? 'reached the goal'
                  : b.summary.status === 'no_path' ? 'no path on what it knows' : 'step limit'}</dd></div>
                <div className="row"><dt>replans</dt><dd>{b.summary.replans}</dd></div>
                <div className="row"><dt>first plan</dt><dd>{fmt(b.summary.first_cost, 2)} (cells)</dd></div>
                <div className="row"><dt>walked</dt><dd>{fmt(b.summary.walked_length, 2)} (cells)</dd></div>
                <div className="row"><dt>search work, all plans</dt><dd>D* Lite {b.summary.dstar_expansions} · A* from
                  scratch {b.summary.astar_expansions}</dd></div>
                <div className="row"><dt>same answers?</dt><dd>{b.summary.costs_agree ? 'yes, every plan' : 'NO'}</dd></div>
              </dl>
              <p className="note">Costs are in grid steps: 1 across, 1.414 diagonally{b.cost ? ', times the cost layer' : ''}.</p>
            </section>
            <section>
              <h2>Where this came from</h2>
              <dl className="rows">
                <div className="row"><dt>made by</dt><dd>{cur.by === 'catalog' ? 'coco_lab at site build' : 'coco_lab in your browser'}</dd></div>
                <div className="row"><dt>checked by</dt><dd>{cur.detail}</dd></div>
                <div className="row"><dt>content</dt><dd><code>{b.contentHash.slice(0, 19)}…</code></dd></div>
              </dl>
              <p className="cite">Evidence: {entry.cites.join('; ')}</p>
            </section>
          </aside>
        </main>
      )}
    </>
  );
}

function Grid({ b, k, painted, onCell, editable }: {
  b: DecodedReplanBundle; k: number; painted: Array<[number, number]>; onCell: (r: number, c: number) => void; editable: boolean;
}) {
  const { width: W, height: H } = b.world;
  const cs = Math.max(2, Math.min(20, Math.floor(640 / W)));
  const known = useMemo(() => knownAt(b, k), [b, k]);
  const truth = useMemo(() => truthAt(b, k), [b, k]);
  const rnd = roundAt(b, k);
  const touched = useMemo(() => expandedIn(b, rnd), [b, rnd]);
  const plan = planAt(b, k);
  const [rr, rc] = robotAt(b, k);
  const R = b.world.sense_radius;
  const walk: Array<[number, number]> = [];
  for (let i = 0; i <= k && 2 * i < b.walk.length; i++) walk.push([b.walk[2 * i], b.walk[2 * i + 1]]);
  const cx = (c: number) => (c + 0.5) * cs;
  const cy = (r: number) => (r + 0.5) * cs;
  const line = (p: Array<[number, number]>) => p.map(([r, c]) => `${cx(c)},${cy(r)}`).join(' ');
  const cells = [];
  for (let r = 0; r < H; r++) {
    for (let c = 0; c < W; c++) {
      const i = r * W + c;
      if (known[i]) cells.push(<rect key={i} className="rp-known" x={c * cs} y={r * cs} width={cs} height={cs} />);
      else if (truth[i]) cells.push(<rect key={i} className="rp-hidden" x={c * cs} y={r * cs} width={cs} height={cs} />);
      else if (b.cost && b.cost[i] > 0) {
        cells.push(<rect key={i} className="rp-cost" x={c * cs} y={r * cs} width={cs} height={cs}
          style={{ opacity: Math.min(0.6, b.cost[i] / 420) }} />);
      }
    }
  }
  return (
    <svg className="move-svg rp" viewBox={`0 0 ${W * cs} ${H * cs}`} role="img" data-testid="move-replan-grid"
      aria-label={`Step ${k}: the robot at row ${rr}, column ${rc}; plan ${plan.length} cells long.`}
      onClick={(ev) => {
        if (!editable) return;
        const box = (ev.currentTarget as SVGSVGElement).getBoundingClientRect();
        const c = Math.floor(((ev.clientX - box.left) / box.width) * W);
        const r = Math.floor(((ev.clientY - box.top) / box.height) * H);
        if (r >= 0 && r < H && c >= 0 && c < W) onCell(r, c);
      }}>
      <rect x={0} y={0} width={W * cs} height={H * cs} className="mv-floor" />
      {touched.map(([r, c]) => <rect key={`t${r},${c}`} className="rp-touched" x={c * cs} y={r * cs} width={cs} height={cs} />)}
      {cells}
      {painted.map(([r, c]) => <rect key={`p${r},${c}`} className="rp-painted" x={c * cs} y={r * cs} width={cs} height={cs} />)}
      {R !== null && <circle className="rp-sense" cx={cx(rc)} cy={cy(rr)} r={R * cs} />}
      <polyline className="rp-walk" points={line(walk)} />
      {plan.length > 1 && <polyline className="rp-plan" points={line(plan)} data-testid="move-replan-plan" />}
      <circle className="rp-goal" cx={cx(b.world.goal[1])} cy={cy(b.world.goal[0])} r={cs * 0.45} />
      <circle className="rp-robot" cx={cx(rc)} cy={cy(rr)} r={cs * 0.4} />
    </svg>
  );
}

function Narrate({ b, k }: { b: DecodedReplanBundle; k: number }) {
  const i = roundAt(b, k);
  const r = b.rounds[i];
  const fresh = r.step === k;
  let text: string;
  if (i === 0 && k === 0) text = `First plan, on the map it has: cost ${fmt(r.cost)}. D* Lite searched backwards from the goal and touched ${r.dstar_expansions} cells; A* would have touched ${r.astar_expansions}.`;
  else if (fresh) text = `It saw ${r.changed.length} cell(s) that its map had wrong. D* Lite repaired the plan, touching ${r.dstar_expansions} cell(s) (${r.dstar_reexpansions} it had touched before); A* from scratch would touch ${r.astar_expansions}. New cost ${fmt(r.cost)}${r.astar_cost !== null ? ` — A* finds ${fmt(r.astar_cost)}` : ''}.`;
  else text = `Following plan ${i} (made at step ${r.step}); nothing it can see disagrees with its map.`;
  if (k >= steps(b)) {
    text = b.summary.status === 'reached' ? `Arrived, after ${b.summary.replans} replan(s).`
      : b.summary.status === 'no_path' ? 'Stopped: on what it now knows, no path exists.' : 'Stopped at the step limit.';
  }
  return <p className="narrate" role="status" data-testid="move-replan-narrate">{text}</p>;
}

function Rounds({ b, k, onPick }: { b: DecodedReplanBundle; k: number; onPick: (step: number) => void }) {
  const cur = roundAt(b, k);
  const max = Math.max(1, ...b.rounds.map((r) => Math.max(r.dstar_expansions, r.astar_expansions)));
  return (
    <div className="scroll-x"><table className="race-table" data-testid="move-rounds">
      <caption className="note">Every plan: the same cost from both (coco_lab checks each), different work. Bars: cells touched.</caption>
      <thead><tr><th>plan</th><th>at step</th><th>cells it saw change</th><th>cost</th><th>D* Lite</th><th>A* from scratch</th></tr></thead>
      <tbody>{b.rounds.map((r, i) => (
        <tr key={i} className={i === cur ? 'focus' : ''} onClick={() => onPick(r.step)} style={{ cursor: 'pointer' }}>
          <td>{i === 0 ? 'first' : `replan ${i}`}</td><td>{r.step}</td><td>{r.changed.length}</td>
          <td>{r.found ? fmt(r.cost) : 'no path'}</td>
          <td><Bar v={r.dstar_expansions} max={max} cls="rp-bar-d" /></td>
          <td><Bar v={r.astar_expansions} max={max} cls="rp-bar-a" /></td></tr>))}</tbody>
    </table></div>
  );
}

function Bar({ v, max, cls }: { v: number; max: number; cls: string }) {
  return (
    <span className="bar-cell"><svg width={80} height={10} aria-hidden="true"><rect className={cls} x={0} y={1} height={8}
      width={Math.max(1, (80 * v) / max)} /></svg> {v}</span>
  );
}
