// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useRef, useState } from 'react';

import { BundleError } from '../../bundle/errors';
import { arraysFileName, type Catalog } from '../../bundle/load';
import type { MapEntry, MapPart } from '../../map/catalog';
import { loadSlamBytes, parseSlamManifest, type DecodedSlamBundle } from '../../map/decode';
import { challengeScore, DIFF_COLORS, fmt, pct, runStyle } from '../../map/view';
import { modeLabel } from '../../model/mode';
import { requestRecompute, workerStarted } from '../../worker/client';
import type { MapSpec } from '../../worker/protocol';
import { MapCanvas, type MapShow } from './MapCanvas';

const BASE = import.meta.env.BASE_URL;
const DATA = `${BASE}generated/`;

interface Current {
  bundle: DecodedSlamBundle;
  entry: MapEntry;
  files: { manifest: Uint8Array; arraysName: string; arraysFile: Uint8Array };
  by: 'catalog' | 'pyodide';
  detail: string;
}

type Status = { state: 'idle' } | { state: 'busy' | 'done' | 'error'; message: string };
type Sub = 'sketch' | 'challenge' | 'replay';

async function fetchBytes(url: string): Promise<Uint8Array> {
  const r = await fetch(url, { credentials: 'omit', cache: 'no-cache' });
  if (!r.ok) throw new Error(`cannot fetch ${url}: HTTP ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

async function loadEntry(entry: MapEntry): Promise<Current> {
  const dir = `${DATA}${entry.path}`;
  const manifest = await fetchBytes(`${dir}manifest.json`);
  const name = arraysFileName(parseSlamManifest(manifest).compression);
  const arraysFile = await fetchBytes(`${dir}${name}`);
  const bundle = await loadSlamBytes(manifest, arraysFile);
  if (bundle.contentHash !== entry.content_hash) {
    throw new BundleError('catalog_mismatch', `${entry.id}: content hash is not the catalog's`);
  }
  return { bundle, entry, files: { manifest, arraysName: name, arraysFile }, by: 'catalog',
    detail: `${entry.validated.by}; ${entry.validated.replay}` };
}

const DEFAULT_SHOW: MapShow = {
  truth: true, map: true, diff: false, rays: true, particles: true, landmarks: true, graph: true, final: true,
};

/** Lab 3: Map. Every number on it comes from coco_lab or the evidence. */
export function MapLab({ catalog, reducedMotion }: { catalog: Catalog; reducedMotion: boolean }) {
  const part = (catalog as Catalog & { map?: MapPart }).map;
  const [sub, setSub] = useState<Sub>(() => {
    const v = new URLSearchParams(window.location.search).get('map');
    return v === 'challenge' || v === 'replay' ? v : 'sketch';
  });
  if (!part) return <p className="error">This site was built without Lab 3.</p>;
  const tabs: Array<[Sub, string]> = [['sketch', 'Try it (Sketch)'], ['challenge', 'Map the arena (challenge)'],
    ['replay', "COCO's real tour (Replay)"]];
  return (
    <div className="loc">
      <nav className="seg" aria-label="Lab 3 sections">
        {tabs.map(([id, label]) => (
          <button key={id} type="button" className={sub === id ? 'seg-btn active' : 'seg-btn'} aria-pressed={sub === id}
            onClick={() => setSub(id)} data-testid={`map-sub-${id}`}>{label}</button>
        ))}
      </nav>
      {sub === 'sketch' && <SketchLab catalog={catalog} part={part} reducedMotion={reducedMotion} />}
      {sub === 'challenge' && <ChallengeLab catalog={catalog} part={part} reducedMotion={reducedMotion} />}
      {sub === 'replay' && <ReplayLab part={part} reducedMotion={reducedMotion} />}
    </div>
  );
}

// -- shared pieces ------------------------------------------------------------------

function usePlayer(n: number, t: Float64Array | null, reducedMotion: boolean) {
  const [k, setK] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(8);
  useEffect(() => {
    if (!playing || !t) return;
    let last = performance.now();
    let sim = t[Math.min(k, n - 1)];
    let raf = 0;
    const tick = (now: number) => {
      sim += ((now - last) / 1000) * (reducedMotion ? rate * 4 : rate);
      last = now;
      let next = k;
      while (next < n - 1 && t[next + 1] <= sim) next++;
      setK(next);
      if (next >= n - 1) setPlaying(false);
      else raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // k is read once at start; the loop owns it while playing
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, t, rate, n, reducedMotion]);
  return { k, setK, playing, setPlaying, rate, setRate };
}

function Player({ n, k, t, playing, rate, onSeek, onPlaying, onRate }: {
  n: number; k: number; t: Float64Array; playing: boolean; rate: number;
  onSeek: (k: number) => void; onPlaying: (p: boolean) => void; onRate: (r: number) => void;
}) {
  return (
    <div className="player" role="group" aria-label="Run player">
      <div className="player-buttons">
        <button type="button" onClick={() => onSeek(Math.max(0, k - 1))} aria-label="Back one update">‹</button>
        <button type="button" className="play" data-testid="map-play"
          onClick={() => { if (!playing && k >= n - 1) onSeek(0); onPlaying(!playing); }}>{playing ? 'Pause' : 'Play'}</button>
        <button type="button" onClick={() => onSeek(Math.min(n - 1, k + 1))} aria-label="Forward one update">›</button>
        <button type="button" onClick={() => { onPlaying(false); onSeek(n - 1); }} data-testid="map-end">End</button>
        <label className="speed"><span>speed</span>
          <select value={rate} onChange={(e) => onRate(Number(e.target.value))} aria-label="Playback speed">
            {[2, 4, 8, 16, 32].map((r) => <option key={r} value={r}>{r}× sim time</option>)}
          </select></label>
      </div>
      <input className="scrub" type="range" min={0} max={Math.max(0, n - 1)} value={k} aria-label="Scrub"
        data-testid="map-scrub" onChange={(e) => onSeek(Number(e.target.value))} />
      <div className="player-pos">update {k + 1} of {n} · t = {t[Math.min(k, n - 1)].toFixed(1)} s</div>
    </div>
  );
}

function ShowPanel({ show, setShow, run }: { show: MapShow; setShow: (s: MapShow) => void; run: string }) {
  const box = (key: keyof MapShow, label: string, note?: string) => (
    <label className="choice" title={note}><input type="checkbox" checked={show[key]}
      onChange={(e) => setShow({ ...show, [key]: e.target.checked })} data-testid={`map-show-${key}`} />{label}</label>
  );
  return (
    <section>
      <h2>Show</h2>
      {box('truth', 'the truth (only a simulator knows it)')}
      {box('map', "the run's map as it was at this moment")}
      {box('diff', 'its final map against the truth')}
      {show.diff && (
        <p className="note">
          <i className="sw" style={{ background: `rgb(${DIFF_COLORS[1].join(',')})` }} /> wall the map got right ·{' '}
          <i className="sw" style={{ background: `rgb(${DIFF_COLORS[2].join(',')})` }} /> wall that is not there ·{' '}
          <i className="sw" style={{ background: `rgb(${DIFF_COLORS[3].join(',')})` }} /> visible wall it missed
          (coco_lab's scoring, 0.10 m tolerance)</p>
      )}
      {box('rays', 'the LiDAR, placed at the belief')}
      {run === 'fastslam' && box('particles', 'particles (by weight)')}
      {run === 'ekf_slam' && box('landmarks', 'landmarks and their 2σ ellipses')}
      {run.startsWith('pose_graph') && box('graph', 'the pose graph (thick: loop closures)')}
      {box('final', 'the trajectory as finally believed (dashed)')}
    </section>
  );
}

function ScoreTable({ bundle: b, k, focus, onFocus }: {
  bundle: DecodedSlamBundle; k: number; focus: string; onFocus: (id: string) => void;
}) {
  const rows = [
    ...b.runs.map((r) => ({
      id: r.id, s: r.summary, final: r.summary.ate_final.rmse,
      errNow: (r.arrays['score.err_online'] as Float64Array)[Math.min(k, r.n - 1)],
      extra: r.algorithm === 'pose_graph' ? `${r.arrays['loops.k'].length} loop closures`
        : r.algorithm === 'fastslam' ? `resampled ${Array.from(r.cols.resampled as Int32Array).reduce((a, v) => a + v, 0)}×`
          : r.algorithm === 'ekf_slam' ? `${(r.cols.n_landmarks as Int32Array)[r.n - 1]} landmarks` : '',
    })),
    ...b.external.map((e) => ({
      id: e.id, s: { ate_online: e.summary.ate_online, map: e.summary.map }, final: null as number | null,
      errNow: e.errOnline[Math.min(k, e.errOnline.length - 1)], extra: `${e.backend} (${e.arm})`,
    })),
  ];
  return (
    <div className="scroll-x"><table className="race-table" data-testid="map-score-table">
      <caption className="note">Same world, same odometry, same scans: only the algorithm differs.
        {b.scoring.align ? ' Trajectories are scored after one rigid 2D alignment (no SLAM here was given the map frame).'
          : ' Every run was told the start, so they share the map frame.'}</caption>
      <thead><tr><th>run</th><th>error now</th><th>trajectory error (RMSE)</th><th>map score F1</th>
        <th>precision</th><th>recall</th><th>coverage</th><th /></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className={r.id === focus ? 'focus' : ''} onClick={() => onFocus(r.id)}>
            <td><i className="sw" style={{ background: runStyle(r.id).color, height: 4, border: 0 }} /> {runStyle(r.id).label}</td>
            <td>{fmt(r.errNow)} m</td>
            <td>{r.final === null ? `${fmt(r.s.ate_online.rmse)} m (online)`
              : r.final !== r.s.ate_online.rmse ? `${fmt(r.s.ate_online.rmse)} → ${fmt(r.final)} m` : `${fmt(r.final)} m`}</td>
            <td><strong>{fmt(r.s.map.f1)}</strong></td>
            <td>{fmt(r.s.map.precision)}</td><td>{fmt(r.s.map.recall)}</td><td>{pct(r.s.map.coverage)}</td>
            <td className="note">{r.extra}</td>
          </tr>
        ))}
      </tbody>
    </table></div>
  );
}

function Explain({ focus }: { focus: string }) {
  return (
    <p className="note" data-testid="map-explain"><strong>{runStyle(focus).label}:</strong> {runStyle(focus).what}.
      {focus === 'ekf_slam' && <> <strong>The landmark sensor is IDEALISED</strong> — it reports every visible box
        corner with its identity, no false detections. COCO has no such sensor: it has a LiDAR, and a real feature
        extractor would miss corners and confuse them.</>}
      {focus === 'fastslam' && ' The estimate is the heaviest particle; the dashed line is the history that survived.'}
      {focus.startsWith('pose_graph') && ' The arrow is the estimate as it ran; the dashed line is the optimised graph at the end.'}</p>
  );
}

function Provenance({ cur }: { cur: Current }) {
  const b = cur.bundle;
  const p = b.provenance as Record<string, unknown>;
  const bag = p.rosbag as { sha256: string; sim_time_start: number; sim_time_end: number } | null;
  return (
    <section>
      <h2>Where this came from</h2>
      <dl className="rows">
        <div className="row"><dt>made by</dt><dd>{cur.by === 'catalog' ? 'coco_lab at site build' : 'coco_lab in your browser'}</dd></div>
        <div className="row"><dt>checked by</dt><dd>{cur.detail}</dd></div>
        <div className="row"><dt>content</dt><dd><code>{b.contentHash.slice(0, 19)}…</code></dd></div>
        <div className="row"><dt>map</dt><dd>{b.map.id} ({b.map.width} × {b.map.height} at {b.map.geo?.resolution} m)</dd></div>
        <div className="row"><dt>LiDAR</dt><dd>{b.world.nBeams} of COCO's 480 beams, {fmt(b.world.lidar.range_min)}–{fmt(b.world.lidar.range_max, 0)} m</dd></div>
        <div className="row"><dt>updates</dt><dd>{b.world.updates.length} (every 0.25 m or 0.2 rad of odometry)</dd></div>
        {bag && <div className="row"><dt>recording</dt><dd>rosbag2 <code>{bag.sha256.slice(0, 12)}…</code>, sim time
          {' '}{bag.sim_time_start.toFixed(1)}–{bag.sim_time_end.toFixed(1)} s</dd></div>}
        {b.world.source === 'sketch' && <div className="row"><dt>world seed</dt><dd>{String(p.seed)}</dd></div>}
      </dl>
      <p className="cite">Evidence: {cur.entry.cites.join('; ')}</p>
    </section>
  );
}

function FocusPicker({ b, focus, setFocus }: { b: DecodedSlamBundle; focus: string; setFocus: (f: string) => void }) {
  return (
    <div className="field"><span>Look at</span>
      <select value={focus} onChange={(e) => setFocus(e.target.value)} aria-label="Whose map and belief" data-testid="map-focus">
        {b.runs.map((r) => <option key={r.id} value={r.id}>{runStyle(r.id).label}</option>)}
        {b.external.map((e) => <option key={e.id} value={e.id}>{runStyle(e.id).label}</option>)}
      </select></div>
  );
}

function useRunner(catalog: Catalog) {
  const busy = useRef(false);
  const [status, setStatus] = useState<Status>({ state: 'idle' });
  const run = useCallback(async (cur: Current, spec: MapSpec): Promise<Current | null> => {
    if (busy.current || !catalog.wheel) return null;
    busy.current = true;
    setStatus({ state: 'busy', message: workerStarted()
      ? 'coco_lab is planning the drive, simulating the world and running every algorithm in your browser…'
      : `Loading Python (Pyodide ${__PYODIDE_VERSION__}) and coco_lab — the first run takes a while…` });
    try {
      const wheelUrl = new URL(`${DATA}${catalog.wheel.path}`, window.location.href).href;
      const t0 = performance.now();
      const r = await requestRecompute({ manifest: cur.files.manifest, arraysName: cur.files.arraysName,
        arraysFile: cur.files.arraysFile, spec, wheelUrl, wheelSha256: catalog.wheel.sha256 }, 'mapping');
      if (!r.ok) {
        setStatus({ state: 'error', message: r.refused ? `Not run: ${r.error}` : `coco_lab could not run this: ${r.error}` });
        return null;
      }
      const w = r.bundles[0];
      const bundle = await loadSlamBytes(w.manifest, w.arraysFile);
      if (bundle.contentHash !== w.contentHash) {
        throw new BundleError('hash', 'the worker\'s bundle hash is not what the decoder computed');
      }
      setStatus({ state: 'done', message: `Done in ${((performance.now() - t0) / 1000).toFixed(1)} s ` +
        `(coco_lab: ${(r.timings.search_ms / 1000).toFixed(1)} s for the world and ${r.timings.runs} algorithms).` });
      return { bundle, entry: cur.entry, files: { manifest: w.manifest, arraysName: w.arraysName, arraysFile: w.arraysFile },
        by: 'pyodide', detail: `coco_lab ${r.cocoLabVersion} on Python ${r.pythonVersion} (Pyodide ${r.pyodideVersion})` };
    } catch (exc) {
      setStatus({ state: 'error', message: exc instanceof Error ? exc.message : String(exc) });
      return null;
    } finally {
      busy.current = false;
    }
  }, [catalog]);
  return { run, status };
}

function round1(v: number) {
  return Math.round(v * 10) / 10;
}

function routeOf(b: DecodedSlamBundle): Array<[number, number]> | null {
  const sc = b.world.scenario as { route?: Array<[number, number]> } | null;
  return sc?.route ?? null;
}

function Waypoints({ clicks, setClicks, drawing, setDrawing, reset, max }: {
  clicks: Array<[number, number]>; setClicks: (c: Array<[number, number]>) => void; drawing: boolean;
  setDrawing: (d: boolean) => void; reset: () => void; max: number;
}) {
  return (
    <div className="field">
      <span>Your drive: {clicks.length} waypoint{clicks.length === 1 ? '' : 's'}</span>
      <button type="button" className="seg-btn" aria-pressed={drawing} onClick={() => setDrawing(!drawing)}
        data-testid="map-draw">{drawing ? 'click the map… (done)' : 'add waypoints'}</button>
      <button type="button" className="seg-btn" disabled={!clicks.length} onClick={() => setClicks(clicks.slice(0, -1))}>undo</button>
      <button type="button" className="seg-btn" onClick={() => setClicks([])} data-testid="map-clear">clear</button>
      <button type="button" className="seg-btn" onClick={reset}>the scene's drive</button>
      <p className="note">Click where the robot should go (up to {max}). coco_lab's own A* (Lab 1) plans the way
        there round any wall; the robot drives it, steered by the truth like a teleoperator who can see it.</p>
    </div>
  );
}

// -- Sketch ----------------------------------------------------------------------------

function SketchLab({ catalog, part, reducedMotion }: { catalog: Catalog; part: MapPart; reducedMotion: boolean }) {
  const scenes = part.bundles.filter((e) => e.kind === 'sketch');
  const [entryId, setEntryId] = useState(() => {
    const want = new URLSearchParams(window.location.search).get('scene');
    return scenes.find((e) => e.id === want)?.id ?? scenes[0]?.id;
  });
  const entry = scenes.find((e) => e.id === entryId) ?? scenes[0];
  const [cur, setCur] = useState<Current | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [spec, setSpec] = useState<MapSpec>(entry.spec as MapSpec);
  const [drawing, setDrawing] = useState(false);
  const [focus, setFocus] = useState('pose_graph');
  const [show, setShow] = useState<MapShow>(DEFAULT_SHOW);
  const [race, setRace] = useState(false);
  const [pred, setPred] = useState<'yes' | 'no' | null>(null);
  const [revealed, setRevealed] = useState(false);
  const { run, status } = useRunner(catalog);
  const b = cur?.bundle ?? null;
  const n = b ? b.world.updates.length : 0;
  const player = usePlayer(n, b ? b.runs[0].cols.t as Float64Array : null, reducedMotion);

  useEffect(() => {
    let alive = true;
    setError(null);
    loadEntry(entry).then((c) => {
      if (!alive) return;
      setCur(c);
      setSpec(entry.spec as MapSpec);
      player.setK(0);
      player.setPlaying(false);
      setPred(null);
      setRevealed(false);
    }).catch((exc: Error) => alive && setError(exc.message));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry]);

  useEffect(() => {
    if (!cur) return;
    (window as unknown as { __cocoLabMap?: unknown }).__cocoLabMap = {
      by: cur.by, contentHash: cur.bundle.contentHash, scene: cur.entry.id,
      runs: cur.bundle.runs.map((r) => ({ id: r.id, summary: r.summary })),
    };
  }, [cur]);

  const onRun = useCallback(async () => {
    if (!cur) return;
    setDrawing(false);
    const next = await run(cur, spec);
    if (next) {
      setCur(next);
      player.setK(0);
      setRevealed(false);
      player.setPlaying(!reducedMotion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, spec, run, reducedMotion]);

  const onPick = useCallback((x: number, y: number) => {
    setSpec((s) => (s.clicks.length >= part.limits.clicks ? s : { ...s, clicks: [...s.clicks, [round1(x), round1(y)]] }));
  }, [part]);

  const counts = part.sketch_counts.status === 'measured' ? part.sketch_counts : null;
  const sceneCounts = counts?.scenes[entry.id];
  const ml = b ? modeLabel(b.provenance) : null;
  const pg = b?.runs.find((r) => r.id === 'pose_graph');
  const pgOff = b?.runs.find((r) => r.id === 'pose_graph_noloop');
  const helped = pg && pgOff ? pg.summary.ate_final.rmse < pgOff.summary.ate_final.rmse : null;
  const set = <K extends keyof MapSpec>(key: K, v: MapSpec[K]) => setSpec((s) => ({ ...s, [key]: v }));

  return (
    <>
      <div className="loc-head">
        <label className="picker-inline"><span>Scene</span>
          <select value={entry.id} onChange={(e) => setEntryId(e.target.value)} data-testid="map-picker">
            {scenes.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select></label>
        {ml && <span className="mode-badge mode-sketch" data-testid="map-mode">{ml.text}</span>}
      </div>
      <FidelityLine part={part} />
      {error && <div className="error" role="alert">Refused: {error}</div>}
      {!b && !error && <p className="loading">Loading and checking the Sketch bundle…</p>}
      {b && cur && (
        <main className="stage">
          <div className="canvas-col">
            <p className="lede">{entry.lesson}</p>
            {race ? (
              <div className="race-grid" data-testid="map-race">
                {b.runs.map((r) => (
                  <MapCanvas key={r.id} bundle={b} k={player.k} focus={r.id} show={show} label={runStyle(r.id).label} />
                ))}
              </div>
            ) : (
              <MapCanvas bundle={b} k={player.k} focus={focus} show={show} clicks={spec.clicks}
                route={routeOf(b)} onPick={drawing ? onPick : undefined} />
            )}
            {drawing && <p className="note" role="status">Click the map to add waypoints; press "done" when finished.</p>}
            <Player n={n} k={player.k} t={b.runs[0].cols.t as Float64Array} playing={player.playing} rate={player.rate}
              onSeek={(v) => { player.setPlaying(false); player.setK(v); }} onPlaying={player.setPlaying} onRate={player.setRate} />
            <Explain focus={focus} />
            <ScoreTable bundle={b} k={player.k} focus={focus} onFocus={setFocus} />
            {sceneCounts && (
              <p className="note" data-testid="map-counts">One world is not a rate. Over {sceneCounts.seeds.length} worlds
                of this scene (Sketch, {counts!.label}): {Object.entries(sceneCounts.runs).map(([id, c]) =>
                  `${runStyle(id).label} final error median ${fmt(c.final_ate_median)} m, F1 median ${fmt(c.f1_median)}`).join('; ')}
                {sceneCounts.loop_closed !== undefined && `. The pose graph closed a loop in ${sceneCounts.loop_closed} of ${sceneCounts.seeds.length} worlds, and that lowered its error in ${sceneCounts.loop_improved}`}.
                {' '}<span className="cite">{counts!.command}</span></p>
            )}
          </div>
          <aside className="side">
            <section>
              <FocusPicker b={b} focus={focus} setFocus={setFocus} />
              <label className="choice"><input type="checkbox" checked={race} data-testid="map-race-toggle"
                onChange={(e) => setRace(e.target.checked)} />compare: one map per algorithm</label>
            </section>
            <ShowPanel show={show} setShow={setShow} run={focus} />
            {pg && pgOff && (
              <section>
                <h2>Predict, then reveal</h2>
                <fieldset className="predict"><legend>Before you play it</legend>
                  <div className="field"><span>Will loop closure make the pose graph's final trajectory better here?</span>
                    {(['yes', 'no'] as const).map((a) => (
                      <label key={a} className="choice"><input type="radio" name="map-pred" checked={pred === a}
                        disabled={revealed} onChange={() => setPred(a)} />{a}</label>
                    ))}</div>
                  <button type="button" className="run" disabled={!pred || revealed} onClick={() => setRevealed(true)}
                    data-testid="map-reveal">Reveal</button>
                </fieldset>
                {revealed && (
                  <p className={`reveal ${(helped ? 'yes' : 'no') === pred ? 'right' : 'wrong'}`} data-testid="map-revealed">
                    With loop closure: {pg.arrays['loops.k'].length} loop closure{pg.arrays['loops.k'].length === 1 ? '' : 's'},
                    final error {fmt(pg.summary.ate_final.rmse)} m; without: {fmt(pgOff.summary.ate_final.rmse)} m —
                    {helped ? ' it helped' : ' it did not help'}; you said {pred}.</p>
                )}
              </section>
            )}
            <section>
              <h2>Change the drive, change the world</h2>
              <p className="note">coco_lab reruns everything in your browser: it plans your drive, simulates one Sketch
                world, then runs every algorithm on it — identical inputs.</p>
              <Waypoints clicks={spec.clicks} setClicks={(c) => set('clicks', c)} drawing={drawing} setDrawing={setDrawing}
                reset={() => set('clicks', (entry.spec as MapSpec).clicks)} max={part.limits.clicks} />
              <div className="field"><span>Odometry noise: ×{spec.noise_scale}</span>
                <input type="range" min={0} max={part.limits.noise_scale[1]} step={0.5} value={spec.noise_scale}
                  aria-label="Odometry noise" data-testid="map-noise" onChange={(e) => set('noise_scale', Number(e.target.value))} /></div>
              <p className="note">How much the wheels lie (×1 = Sketch's default; the scenes use ×3). Every SLAM is told
                the true noise model: what differs between them is the algorithm.</p>
              <div className="field"><span>FastSLAM particles: {spec.particles}</span>
                <input type="range" min={part.limits.particles[0]} max={part.limits.particles[1]} step={1} value={spec.particles}
                  aria-label="Particles" onChange={(e) => set('particles', Number(e.target.value))} /></div>
              <div className="field"><span>Seeds</span>
                <button type="button" className="seg-btn" onClick={() => set('seed', spec.seed + 1)} data-testid="map-new-world">
                  new world ({spec.seed})</button>
                <button type="button" className="seg-btn" onClick={() => set('fastslam_seed', spec.fastslam_seed + 1)}>
                  re-roll FastSLAM ({spec.fastslam_seed})</button></div>
              <button type="button" className="run" onClick={onRun} disabled={status.state === 'busy' || !catalog.wheel || !spec.clicks.length}
                data-testid="map-run">{status.state === 'busy' ? 'Running…' : 'Run it with coco_lab'}</button>
              {status.state !== 'idle' && <p className={`edit-status ${status.state}`} role="status" data-testid="map-status">{status.message}</p>}
            </section>
            <Provenance cur={cur} />
          </aside>
        </main>
      )}
    </>
  );
}

function FidelityLine({ part }: { part: MapPart }) {
  const f = part.fidelity;
  if (f.status !== 'measured') return <p className="honest">Sketch's fidelity against Gazebo: not yet measured.</p>;
  return (
    <p className="honest" data-testid="map-fidelity"><strong>Sketch is coco_lab's 2D model, not the robot.</strong> At
      {' '}{f.scans_used} identical poses its LiDAR is within 5 cm of Gazebo's on {(100 * f.frac_abs_below['0.05']).toFixed(1)} %
      of beams; its wheels never slip (measured, Lab 2: {f.cite}).</p>
  );
}

// -- Challenge --------------------------------------------------------------------------

interface Attempt { n: number; algorithm: string; score: number; f1: number; best: number; coverage: number | null;
  ate: number; waypoints: number }

function ChallengeLab({ catalog, part, reducedMotion }: { catalog: Catalog; part: MapPart; reducedMotion: boolean }) {
  const entry = part.bundles.find((e) => e.kind === 'challenge')!;
  const ch = part.challenge;
  const [cur, setCur] = useState<Current | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [spec, setSpec] = useState<MapSpec>(entry.spec as MapSpec);
  const [alg, setAlg] = useState(ch.algorithms[0]);
  const [drawing, setDrawing] = useState(true);
  const [show, setShow] = useState<MapShow>({ ...DEFAULT_SHOW, diff: false });
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const { run, status } = useRunner(catalog);
  const b = cur?.bundle ?? null;
  const n = b ? b.world.updates.length : 0;
  const player = usePlayer(n, b ? b.runs[0].cols.t as Float64Array : null, reducedMotion);

  useEffect(() => {
    loadEntry(entry).then((c) => { setCur(c); player.setK(c.bundle.world.updates.length - 1); })
      .catch((exc: Error) => setError(exc.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry]);

  const scored = b?.runs.find((r) => r.id === alg) ?? null;
  const known = b?.runs.find((r) => r.id === 'known') ?? null;
  const onRun = useCallback(async () => {
    if (!cur) return;
    setDrawing(false);
    const next = await run(cur, { ...spec, runs: ['known', 'odometry', alg] });
    if (!next) return;
    setCur(next);
    player.setK(0);
    player.setPlaying(!reducedMotion);
    const r = next.bundle.runs.find((x) => x.id === alg)!;
    const kn = next.bundle.runs.find((x) => x.id === 'known')!;
    setAttempts((a) => [...a, { n: a.length + 1, algorithm: alg, score: challengeScore(r.summary.map.f1), f1: r.summary.map.f1,
      best: challengeScore(kn.summary.map.f1), coverage: r.summary.map.coverage, ate: r.summary.ate_final.rmse,
      waypoints: spec.clicks.length }]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, spec, alg, run, reducedMotion]);
  const onPick = useCallback((x: number, y: number) => {
    setSpec((s) => (s.clicks.length >= part.limits.clicks ? s : { ...s, clicks: [...s.clicks, [round1(x), round1(y)]] }));
  }, [part]);

  return (
    <>
      <div className="loc-head">
        <h2 className="inline">{ch.title}</h2>
        {b && <span className="mode-badge mode-sketch" data-testid="map-mode">{modeLabel(b.provenance).text}</span>}
      </div>
      <p className="lede">{ch.task}</p>
      {error && <div className="error" role="alert">Refused: {error}</div>}
      {b && cur && (
        <main className="stage">
          <div className="canvas-col">
            <MapCanvas bundle={b} k={player.k} focus={scored ? alg : b.runs[0].id} show={show} clicks={spec.clicks}
              route={routeOf(b)} onPick={drawing ? onPick : undefined} />
            <Player n={n} k={player.k} t={b.runs[0].cols.t as Float64Array} playing={player.playing} rate={player.rate}
              onSeek={(v) => { player.setPlaying(false); player.setK(v); }} onPlaying={player.setPlaying} onRate={player.setRate} />
            <ScoreTable bundle={b} k={player.k} focus={alg} onFocus={() => undefined} />
          </div>
          <aside className="side">
            <section className="score" data-testid="map-challenge-score">
              <h2>Score</h2>
              {scored && known ? (
                <>
                  <p className="big"><strong>{challengeScore(scored.summary.map.f1)}</strong> / 100
                    <span className="note"> — {runStyle(alg).label}{cur.by === 'catalog' ? " on the scene's drive" : ' on your drive'}</span></p>
                  <p className="note">The best map this drive allows (known poses): {challengeScore(known.summary.map.f1)}.
                    Coverage {pct(scored.summary.map.coverage)}; trajectory error {fmt(scored.summary.ate_final.rmse)} m.</p>
                </>
              ) : <p className="note">Run a drive to score it.</p>}
              <details><summary>How the score is computed</summary>
                <p className="note">{ch.score}.</p>
                <ul className="note">{Object.entries(ch.definition).map(([k, v]) => <li key={k}><strong>{k}</strong>: {v}</li>)}</ul>
                <p className="cite">Tests: {ch.cites.join('; ')}</p>
              </details>
              <p className="note">Loop closures help — coming back where you have been lets the pose graph pull its map
                straight. Long featureless stretches hurt — there the scans cannot tell how far you went.</p>
            </section>
            <ShowPanel show={show} setShow={setShow} run={alg} />
            <section>
              <h2>Your drive</h2>
              <Waypoints clicks={spec.clicks} setClicks={(c) => setSpec((s) => ({ ...s, clicks: c }))} drawing={drawing}
                setDrawing={setDrawing} reset={() => setSpec(entry.spec as MapSpec)} max={part.limits.clicks} />
              <div className="field"><span>SLAM</span>
                <select value={alg} onChange={(e) => setAlg(e.target.value)} aria-label="Which SLAM maps it" data-testid="map-challenge-alg">
                  {ch.algorithms.map((a) => <option key={a} value={a}>{runStyle(a).label}</option>)}
                </select></div>
              <p className="note">Fixed for everyone: the start, world seed {spec.seed}, odometry noise ×{ch.noise_scale}
                {' '}(Sketch's default) and the LiDAR. The same drive always gives the same score.</p>
              <button type="button" className="run" onClick={onRun} disabled={status.state === 'busy' || !catalog.wheel || !spec.clicks.length}
                data-testid="map-challenge-run">{status.state === 'busy' ? 'Mapping…' : 'Drive it and map it'}</button>
              {status.state !== 'idle' && <p className={`edit-status ${status.state}`} role="status">{status.message}</p>}
            </section>
            {attempts.length > 0 && (
              <section>
                <h2>Your attempts</h2>
                <table className="rows-table" data-testid="map-attempts"><thead><tr><th>#</th><th>SLAM</th><th>score</th>
                  <th>best possible</th><th>waypoints</th></tr></thead>
                  <tbody>{attempts.map((a) => (
                    <tr key={a.n}><td>{a.n}</td><td>{runStyle(a.algorithm).label}</td><td><strong>{a.score}</strong></td>
                      <td>{a.best}</td><td>{a.waypoints}</td></tr>))}</tbody></table>
                <p className="note">Kept in this page only; nothing is sent anywhere.</p>
              </section>
            )}
            <Provenance cur={cur} />
          </aside>
        </main>
      )}
    </>
  );
}

// -- Replay -------------------------------------------------------------------------------

function ReplayLab({ part, reducedMotion }: { part: MapPart; reducedMotion: boolean }) {
  const entry = part.bundles.find((e) => e.kind === 'replay') ?? null;
  const [cur, setCur] = useState<Current | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState('slam_toolbox_loop');
  const [show, setShow] = useState<MapShow>({ ...DEFAULT_SHOW, rays: false });
  const b = cur?.bundle ?? null;
  const n = b ? b.world.updates.length : 0;
  const player = usePlayer(n, b ? b.runs[0].cols.t as Float64Array : null, reducedMotion);
  useEffect(() => {
    if (!entry) return;
    loadEntry(entry).then((c) => { setCur(c); player.setK(c.bundle.world.updates.length - 1); })
      .catch((exc: Error) => setError(exc.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry]);
  const real = part.real.status === 'measured' ? part.real : null;
  if (!entry) return <p className="honest">No recorded drive was built into this site: not yet measured.</p>;
  return (
    <>
      <div className="loc-head">
        <h2 className="inline">{entry.title}</h2>
        {b && <span className="mode-badge mode-recorded" data-testid="map-mode">Replay — a recorded run of the real stack in Gazebo</span>}
      </div>
      <p className="lede">{entry.lesson}</p>
      {error && <div className="error" role="alert">Refused: {error}</div>}
      {b && cur && (
        <main className="stage">
          <div className="canvas-col">
            <MapCanvas bundle={b} k={player.k} focus={focus} show={show} />
            <Player n={n} k={player.k} t={b.runs[0].cols.t as Float64Array} playing={player.playing} rate={player.rate}
              onSeek={(v) => { player.setPlaying(false); player.setK(v); }} onPlaying={player.setPlaying} onRate={player.setRate} />
            <Explain focus={focus} />
            <ScoreTable bundle={b} k={player.k} focus={focus} onFocus={setFocus} />
            {real && <RealTable real={real} />}
          </div>
          <aside className="side">
            <section><FocusPicker b={b} focus={focus} setFocus={setFocus} /></section>
            <ShowPanel show={show} setShow={setShow} run={focus} />
            <Provenance cur={cur} />
          </aside>
        </main>
      )}
    </>
  );
}

function RealTable({ real }: { real: Extract<MapPart['real'], { status: 'measured' }> }) {
  return (
    <section data-testid="map-real">
      <h2>Every run, both recorded drives (measured)</h2>
      <div className="scroll-x"><table className="rows-table">
        <thead><tr><th>drive</th><th>run</th><th>round</th><th>trajectory error</th><th>map F1</th><th>machine load</th></tr></thead>
        <tbody>
          {real.backends.map((r, i) => (
            <tr key={`b${i}`}><td>{r.drive}</td><td>{runStyle(`${r.backend}_${r.arm}`).label}</td><td>{r.round}</td>
              <td>{fmt(r.ate_online_rmse)} m (online)</td><td>{fmt(r.f1)}</td><td>{r.loadavg_end}</td></tr>))}
          {real.coco_lab.map((r, i) => (
            <tr key={`c${i}`}><td>{r.drive}</td><td>coco_lab {runStyle(r.arm).label}{r.seed !== null ? ` (seed ${r.seed})` : ''}</td>
              <td>—</td><td>{fmt(r.ate_final_rmse)} m (final)</td><td>{fmt(r.f1)}</td><td /></tr>))}
        </tbody>
      </table></div>
      <ul className="note">{real.notes.map((t) => <li key={t}>{t}</li>)}</ul>
      <p className="cite">{real.label}. {real.command}</p>
    </section>
  );
}
