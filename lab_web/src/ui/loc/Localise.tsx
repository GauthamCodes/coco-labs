// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { BundleError } from '../../bundle/errors';
import { arraysFileName, type Catalog } from '../../bundle/load';
import type { LocEntry, LocalisePart } from '../../loc/catalog';
import { loadLocBytes, parseLocManifest, type DecodedLocBundle } from '../../loc/decode';
import { outcome, outcomeText, questions, runStyle, TRUTH_COLOR, type Answer } from '../../loc/view';
import { modeLabel } from '../../model/mode';
import { requestRecompute, workerStarted } from '../../worker/client';
import type { LocSpec } from '../../worker/protocol';
import { ErrorPlot } from './ErrorPlot';
import { LocCanvas } from './LocCanvas';
import { LocExhibits } from './LocExhibits';

const BASE = import.meta.env.BASE_URL;
const DATA = `${BASE}generated/`;

interface LocCurrent {
  bundle: DecodedLocBundle;
  entry: LocEntry;
  files: { manifest: Uint8Array; arraysName: string; arraysFile: Uint8Array };
  by: 'catalog' | 'pyodide';
  detail: string;
}

type Status =
  | { state: 'idle' }
  | { state: 'busy'; message: string }
  | { state: 'done'; message: string }
  | { state: 'error'; message: string };

async function fetchBytes(url: string): Promise<Uint8Array> {
  const r = await fetch(url, { credentials: 'omit', cache: 'no-cache' });
  if (!r.ok) throw new Error(`cannot fetch ${url}: HTTP ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

/** Lab 2: Localise. Sketch only; every number on it comes from coco_lab or the evidence. */
export function Localise({ catalog, reducedMotion }: { catalog: Catalog; reducedMotion: boolean }) {
  const part = (catalog as Catalog & { localise?: LocalisePart }).localise;
  const [sub, setSub] = useState<'lab' | 'exhibits'>(
    () => (new URLSearchParams(window.location.search).get('loc') === 'exhibits' ? 'exhibits' : 'lab'));
  if (!part) return <p className="error">This site was built without Lab 2.</p>;
  return (
    <div className="loc">
      <nav className="seg" aria-label="Lab 2 sections">
        <button type="button" className={sub === 'lab' ? 'seg-btn active' : 'seg-btn'} aria-pressed={sub === 'lab'}
          onClick={() => setSub('lab')} data-testid="loc-sub-lab">Try it (Sketch)</button>
        <button type="button" className={sub === 'exhibits' ? 'seg-btn active' : 'seg-btn'}
          aria-pressed={sub === 'exhibits'} onClick={() => setSub('exhibits')} data-testid="loc-sub-exhibits">
          COCO's real localisation failures</button>
      </nav>
      {sub === 'lab'
        ? <LocLab catalog={catalog} part={part} reducedMotion={reducedMotion} />
        : <LocExhibits part={part} dataUrl={(p) => `${DATA}${p}`} />}
    </div>
  );
}

function LocLab({ catalog, part, reducedMotion }: { catalog: Catalog; part: LocalisePart; reducedMotion: boolean }) {
  const [entryId, setEntryId] = useState(() => {
    const want = new URLSearchParams(window.location.search).get('scene');
    return part.bundles.find((e) => e.id === want)?.id ?? 'loc_kidnap';
  });
  const entry = part.bundles.find((e) => e.id === entryId) ?? part.bundles[0];
  const [cur, setCur] = useState<LocCurrent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [k, setK] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(4);
  const [showTruth, setShowTruth] = useState(true);
  const [showParticles, setShowParticles] = useState(true);
  const [scanFrom, setScanFrom] = useState<'belief' | 'truth' | 'none'>('belief');
  const [focus, setFocus] = useState('mcl');
  const [race, setRace] = useState(false);
  const [spec, setSpec] = useState<LocSpec>(entry.spec);
  const [picking, setPicking] = useState(false);
  const [status, setStatus] = useState<Status>({ state: 'idle' });
  const [preds, setPreds] = useState<Record<string, Answer>>({});
  const [revealed, setRevealed] = useState(false);
  const busy = useRef(false);

  // load the catalog bundle; the page draws it only if its hash is the catalog's
  useEffect(() => {
    let alive = true;
    setError(null);
    (async () => {
      const dir = `${DATA}${entry.path}`;
      const manifest = await fetchBytes(`${dir}manifest.json`);
      const name = arraysFileName(parseLocManifest(manifest).compression);
      const arraysFile = await fetchBytes(`${dir}${name}`);
      const bundle = await loadLocBytes(manifest, arraysFile);
      if (bundle.contentHash !== entry.content_hash) {
        throw new BundleError('catalog_mismatch', `${entry.id}: content hash is not the catalog's`);
      }
      if (!alive) return;
      setCur({ bundle, entry, files: { manifest, arraysName: name, arraysFile }, by: 'catalog',
        detail: `${entry.validated.by}; ${entry.validated.replay}` });
      setSpec(entry.spec);
      setK(0);
      setPlaying(false);
      setPreds({});
      setRevealed(false);
      setFocus('mcl');
    })().catch((exc: Error) => alive && setError(exc.message));
    return () => { alive = false; };
  }, [entry]);

  const b = cur?.bundle ?? null;
  const n = b ? b.world.updates.length : 0;

  // play in sim time: `rate` simulated seconds per wall second
  useEffect(() => {
    if (!playing || !b) return;
    const t = b.runs[0].cols.t;
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
  }, [playing, b, rate, n, reducedMotion]);

  const runIds = useMemo(() => (b ? b.runs.map((r) => r.id) : []), [b]);
  const qs = useMemo(() => (b ? questions(b) : []), [b]);

  const runCoco = useCallback(async () => {
    if (!cur || busy.current || !catalog.wheel) return;
    busy.current = true;
    setPicking(false);
    setStatus({ state: 'busy', message: workerStarted()
      ? 'coco_lab is simulating the world and running the filters in your browser…'
      : `Loading Python (Pyodide ${__PYODIDE_VERSION__}) and coco_lab — the first run takes a while…` });
    try {
      const wheelUrl = new URL(`${DATA}${catalog.wheel.path}`, window.location.href).href;
      const t0 = performance.now();
      const r = await requestRecompute({ manifest: cur.files.manifest, arraysName: cur.files.arraysName,
        arraysFile: cur.files.arraysFile, spec, wheelUrl, wheelSha256: catalog.wheel.sha256 }, 'localise');
      if (!r.ok) {
        setStatus({ state: 'error', message: r.refused ? `Not run: ${r.error}` : `coco_lab could not run this: ${r.error}` });
        return;
      }
      const w = r.bundles[0];
      const bundle = await loadLocBytes(w.manifest, w.arraysFile);
      if (bundle.contentHash !== w.contentHash) {
        throw new BundleError('hash', 'the worker\'s bundle hash is not what the decoder computed');
      }
      setCur({ bundle, entry: cur.entry, files: { manifest: w.manifest, arraysName: w.arraysName, arraysFile: w.arraysFile },
        by: 'pyodide', detail: `coco_lab ${r.cocoLabVersion} on Python ${r.pythonVersion} (Pyodide ${r.pyodideVersion})` });
      setK(0);
      setRevealed(false);
      setStatus({ state: 'done', message: `Done in ${((performance.now() - t0) / 1000).toFixed(1)} s ` +
        `(coco_lab: ${(r.timings.search_ms / 1000).toFixed(1)} s for the world and ${r.timings.runs} filters).` });
      setPlaying(!reducedMotion);
    } catch (exc) {
      setStatus({ state: 'error', message: exc instanceof Error ? exc.message : String(exc) });
    } finally {
      busy.current = false;
    }
  }, [cur, spec, catalog, reducedMotion]);

  const onPick = useCallback((x: number, y: number) => {
    setSpec((s) => ({ ...s, kidnap: { t: s.kidnap?.t ?? defaultKidnapT(cur), to: [round2(x), round2(y), 0] } }));
    setPicking(false);
  }, [cur]);

  const rates = part.sketch_rates.status === 'measured' ? part.sketch_rates : null;
  const fid = part.fidelity;
  const ml = b ? modeLabel(b.provenance) : null;

  return (
    <>
      <div className="loc-head">
        <label className="picker-inline">
          <span>Scene</span>
          <select value={entry.id} onChange={(e) => setEntryId(e.target.value)} data-testid="loc-picker">
            {part.bundles.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select>
        </label>
        {ml && <span className="mode-badge mode-sketch" data-testid="loc-mode">{ml.text}</span>}
      </div>
      <FidelityNote fid={fid} />
      {error && <div className="error" role="alert">Refused: {error}</div>}
      {!b && !error && <p className="loading">Loading and checking the Sketch bundle…</p>}
      {b && cur && (
        <main className="stage">
          <div className="canvas-col">
            <p className="lede">{entry.lesson}</p>
            {race ? (
              <div className="race-grid" data-testid="loc-race">
                {b.runs.map((r) => (
                  <LocCanvas key={r.id} bundle={b} k={k} runs={[r.id]} focus={r.id} showTruth={showTruth}
                    showParticles={showParticles} scanFrom={scanFrom} label={runStyle(r.id).label} />
                ))}
              </div>
            ) : (
              <LocCanvas bundle={b} k={k} runs={runIds} focus={focus} showTruth={showTruth}
                showParticles={showParticles} scanFrom={scanFrom}
                onPick={picking ? onPick : undefined} pick={picking ? null : spec.kidnap ? spec.kidnap.to : null} />
            )}
            {picking && <p className="note" role="status">Click the map where the robot should be carried to.</p>}
            <LocPlayer n={n} k={k} t={b.runs[0].cols.t as Float64Array} playing={playing} rate={rate}
              onSeek={(v) => { setPlaying(false); setK(v); }} onPlaying={setPlaying} onRate={setRate} />
            <ErrorPlot bundle={b} runs={runIds} k={k} onSeek={(v) => { setPlaying(false); setK(v); }} />
            <RaceTable bundle={b} k={k} />
          </div>
          <aside className="side">
            <section>
              <h2>Show</h2>
              <label className="choice"><input type="checkbox" checked={showTruth} data-testid="loc-truth"
                onChange={(e) => setShowTruth(e.target.checked)} />the truth <i className="sw" style={{ background: TRUTH_COLOR, height: 4, border: 0 }} /></label>
              <p className="note">Off: you see only what the robot believes. Only a simulator knows the truth.</p>
              <label className="choice"><input type="checkbox" checked={showParticles}
                onChange={(e) => setShowParticles(e.target.checked)} />particles</label>
              <label className="choice"><input type="checkbox" checked={race} data-testid="loc-race-toggle"
                onChange={(e) => setRace(e.target.checked)} />race: one map per filter</label>
              <div className="field"><span>Particles of</span>
                <select value={focus} onChange={(e) => setFocus(e.target.value)} aria-label="Whose particles and scan">
                  {b.runs.map((r) => <option key={r.id} value={r.id}>{runStyle(r.id).label}</option>)}
                </select></div>
              <div className="field"><span>Scan placed at</span>
                <select value={scanFrom} onChange={(e) => setScanFrom(e.target.value as typeof scanFrom)} aria-label="Where to draw the scan">
                  <option value="belief">the belief (endpoints off the walls = lost)</option>
                  <option value="truth">the truth</option>
                  <option value="none">nowhere</option>
                </select></div>
            </section>
            <Predict bundle={b} qs={qs} preds={preds} setPreds={setPreds} revealed={revealed}
              onReveal={() => setRevealed(true)} rates={rates} sceneId={entry.id} />
            <Controls spec={spec} setSpec={setSpec} part={part} picking={picking} setPicking={setPicking}
              onRun={runCoco} busy={status.state === 'busy'} canRun={!!catalog.wheel}
              defaultTo={b.scenario.kidnap?.to ?? cur.entry.spec.kidnap?.to ?? b.scenario.start} />
            {status.state !== 'idle' && (
              <p className={`edit-status ${status.state}`} role="status" data-testid="loc-status">{status.message}</p>
            )}
            <section>
              <h2>Where this run came from</h2>
              <dl className="rows">
                <div className="row"><dt>made by</dt><dd>{cur.by === 'catalog' ? 'coco_lab at site build' : 'coco_lab in your browser'}</dd></div>
                <div className="row"><dt>checked by</dt><dd>{cur.detail}</dd></div>
                <div className="row"><dt>content</dt><dd><code>{b.contentHash.slice(0, 19)}…</code></dd></div>
                <div className="row"><dt>world seed</dt><dd>{b.scenario.seed}</dd></div>
                <div className="row"><dt>map</dt><dd>{b.map.id}</dd></div>
                <div className="row"><dt>LiDAR</dt><dd>{b.world.nBeams} of COCO's 480 beams, {b.scenario.lidar.range_min}–{b.scenario.lidar.range_max} m</dd></div>
                <div className="row"><dt>inputs</dt><dd>every filter here read the same world: one odometry, one set of scans (identical inputs)</dd></div>
              </dl>
              <p className="cite">Tests: {entry.cites.join('; ')}</p>
            </section>
          </aside>
        </main>
      )}
    </>
  );
}

function round2(v: number) {
  return Math.round(v * 100) / 100;
}

function defaultKidnapT(cur: LocCurrent | null): number {
  if (!cur) return 20;
  const t = cur.bundle.world.t;
  return Math.round(t[t.length - 1] * 0.4);
}

function FidelityNote({ fid }: { fid: LocalisePart['fidelity'] }) {
  if (fid.status !== 'measured') {
    return <p className="honest" data-testid="loc-fidelity">Sketch's fidelity against Gazebo: not yet measured.</p>;
  }
  const e = fid.abs_error_m;
  const pct = (v: number) => `${(100 * v).toFixed(1)} %`;
  return (
    <details className="honest" data-testid="loc-fidelity">
      <summary>
        <strong>How close is Sketch to the real stack?</strong> At {fid.scans_used} identical poses in Gazebo,
        Sketch's LiDAR is within 5 cm of Gazebo's on {pct(fid.frac_abs_below['0.05'])} of {fid.beams_both.toLocaleString('en')} beams
        (median |error| {(1000 * (e.median ?? 0)).toFixed(1)} mm). Its wheels never slip: Gazebo's don't either
        on a straight line, but on turns they do (measured).
      </summary>
      <table className="rows-table">
        <caption>Range error, Gazebo − Sketch, where both returned (m)</caption>
        <tbody>
          {(['p05', 'p25', 'median', 'p75', 'p95', 'p99'] as const).map((q) => (
            <tr key={q}><th>{q}</th><td>{(fid.error_m[q] ?? 0).toFixed(4)}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="scroll-x"><table className="rows-table">
        <caption>Odometry drift on the same commands</caption>
        <thead><tr><th>drive</th><th>driven</th><th>Gazebo odometry, final error</th><th>Sketch (default noise), median [p05–p95]</th></tr></thead>
        <tbody>
          {fid.drives.map((d) => (
            <tr key={`${d.session}/${d.drive}`}>
              <td>{d.drive} ({d.session})</td>
              <td>{d.distance_m.toFixed(1)} m, {d.rotation_rad.toFixed(1)} rad</td>
              <td>{d.gazebo.final_pos_err_m.toFixed(2)} m, {d.gazebo.final_yaw_err_rad.toFixed(3)} rad</td>
              <td>{(d.sketch_default_noise.final_pos_err_m.median ?? 0).toFixed(2)} m
                [{(d.sketch_default_noise.final_pos_err_m.p05 ?? 0).toFixed(2)}–{(d.sketch_default_noise.final_pos_err_m.p95 ?? 0).toFixed(2)}]</td>
            </tr>
          ))}
        </tbody>
      </table></div>
      <p className="cite">(measured) {fid.cite}. Command: <code>{fid.command}</code></p>
    </details>
  );
}

function LocPlayer({ n, k, t, playing, rate, onSeek, onPlaying, onRate }: {
  n: number; k: number; t: Float64Array; playing: boolean; rate: number;
  onSeek: (k: number) => void; onPlaying: (p: boolean) => void; onRate: (r: number) => void;
}) {
  return (
    <div className="player" role="group" aria-label="Run player">
      <div className="player-buttons">
        <button type="button" onClick={() => onSeek(Math.max(0, k - 1))} aria-label="Back one update">‹</button>
        <button type="button" className="play" data-testid="loc-play"
          onClick={() => { if (!playing && k >= n - 1) onSeek(0); onPlaying(!playing); }}>{playing ? 'Pause' : 'Play'}</button>
        <button type="button" onClick={() => onSeek(Math.min(n - 1, k + 1))} aria-label="Forward one update">›</button>
        <label className="speed"><span>speed</span>
          <select value={rate} onChange={(e) => onRate(Number(e.target.value))} aria-label="Playback speed">
            {[1, 2, 4, 8, 16].map((r) => <option key={r} value={r}>{r}× sim time</option>)}
          </select></label>
      </div>
      <input className="scrub" type="range" min={0} max={Math.max(0, n - 1)} value={k} aria-label="Scrub" data-testid="loc-scrub"
        onChange={(e) => onSeek(Number(e.target.value))} />
      <div className="player-pos">filter update {k + 1} of {n} · t = {t[Math.min(k, n - 1)].toFixed(1)} s</div>
    </div>
  );
}

function RaceTable({ bundle: b, k }: { bundle: DecodedLocBundle; k: number }) {
  const f = (v: number | null, d = 2) => (v === null ? '—' : v.toFixed(d));
  return (
    <div className="scroll-x"><table className="race-table" data-testid="loc-race-table">
      <caption className="note">Same world, same odometry, same scans: only the filter differs.</caption>
      <thead><tr><th>filter</th><th>error now</th><th>mean error</th><th>converged at</th>
        {b.world.kidnapRow !== null && <th>after the kidnap</th>}</tr></thead>
      <tbody>
        {b.runs.map((r) => (
          <tr key={r.id}>
            <td><i className="sw" style={{ background: runStyle(r.id).color, height: 4, border: 0 }} /> {runStyle(r.id).label}</td>
            <td>{f(r.cols.err_xy[Math.min(k, r.n - 1)])} m</td>
            <td>{f(r.summary.mean_err_xy)} m</td>
            <td>{r.summary.converged_s === null ? 'never' : `${f(r.summary.converged_s, 1)} s`}</td>
            {b.world.kidnapRow !== null && (
              <td>{r.summary.recovered ? `recovered in ${f(r.summary.recovery_s, 1)} s` : 'not recovered'}</td>
            )}
          </tr>
        ))}
      </tbody>
    </table></div>
  );
}

const RATE_KEYS: Record<string, Record<string, string>> = {
  loc_kidnap: { mcl: 'mcl_augmented', mcl_coco: 'mcl_off', ekf: 'ekf' },
  loc_global: { mcl: 'mcl_1000', ekf: 'ekf' },
  loc_twins: { mcl: 'mcl_1000', ekf: 'ekf' },
  loc_tracking: { mcl: 'mcl_300', ekf: 'ekf' },
  loc_arena_kidnap: { mcl: 'mcl_augmented_500', mcl_coco: 'mcl_off_500', ekf: 'ekf' },
};
const RATE_EXP: Record<string, string> = {
  loc_kidnap: 'kidnap', loc_global: 'global', loc_twins: 'twins', loc_tracking: 'tracking',
  loc_arena_kidnap: 'arena_kidnap',
};

function Predict({ bundle: b, qs, preds, setPreds, revealed, onReveal, rates, sceneId }: {
  bundle: DecodedLocBundle; qs: ReturnType<typeof questions>; preds: Record<string, Answer>;
  setPreds: (p: Record<string, Answer>) => void; revealed: boolean; onReveal: () => void;
  rates: Extract<LocalisePart['sketch_rates'], { status: 'measured' }> | null; sceneId: string;
}) {
  const ready = qs.every((q) => preds[q.runId]);
  return (
    <section>
      <h2>Predict, then reveal</h2>
      <fieldset className="predict">
        <legend>Before you play it</legend>
        {qs.map((q) => (
          <div key={q.runId} className="field">
            <span>{q.text}</span>
            {(['yes', 'no'] as const).map((a) => (
              <label key={a} className="choice">
                <input type="radio" name={`p-${q.runId}`} checked={preds[q.runId] === a} disabled={revealed}
                  onChange={() => setPreds({ ...preds, [q.runId]: a })} />{a}</label>
            ))}
          </div>
        ))}
        <button type="button" className="run" disabled={!ready || revealed} onClick={onReveal} data-testid="loc-reveal">
          Reveal</button>
      </fieldset>
      {revealed && (
        <div data-testid="loc-revealed">
          {b.runs.map((r) => {
            const got = outcome(b, r);
            const right = preds[r.id] === got;
            const key = RATE_KEYS[sceneId]?.[r.id];
            const rr = key && rates ? rates.experiments[RATE_EXP[sceneId]]?.runs[key] : undefined;
            const kidnap = b.world.kidnapRow !== null;
            return (
              <p key={r.id} className={`reveal ${right ? 'right' : 'wrong'}`}>
                <strong>{runStyle(r.id).label}:</strong> {outcomeText(b, r)} — you said {preds[r.id]},
                {right ? ' right.' : ' not this time.'}
                {rr && (
                  <span className="note"> One run is not a rate: on this scene's catalog world, over {rr.n} filter
                    seed{rr.n === 1 ? '' : 's'}, it {kidnap ? `recovered in ${rr.recovered}` : `converged in ${rr.converged}`} of {rr.n}
                    {rr.deterministic ? ' (the EKF draws nothing random, so one run is all runs)' : ''} — Sketch, {rates?.cite}.</span>
                )}
              </p>
            );
          })}
        </div>
      )}
    </section>
  );
}

function Controls({ spec, setSpec, part, picking, setPicking, onRun, busy, canRun, defaultTo }: {
  spec: LocSpec; setSpec: (f: (s: LocSpec) => LocSpec) => void; part: LocalisePart; picking: boolean;
  setPicking: (p: boolean) => void; onRun: () => void; busy: boolean; canRun: boolean;
  /** a free pose to carry the robot to until the learner picks one */
  defaultTo: [number, number, number];
}) {
  const set = <K extends keyof LocSpec>(key: K, v: LocSpec[K]) => setSpec((s) => ({ ...s, [key]: v }));
  const lim = part.limits;
  return (
    <section>
      <h2>Change the world, change the filter</h2>
      <p className="note">coco_lab reruns everything in your browser: one new Sketch world, then every filter on it.</p>
      <div className="field">
        <span>Particles: {spec.particles}</span>
        <input type="range" min={50} max={lim.particles[1]} step={50} value={spec.particles} aria-label="Particles"
          onChange={(e) => set('particles', Number(e.target.value))} data-testid="loc-particles" />
      </div>
      <p className="note">More guesses cover more of the map, so a lost robot is likelier to have one near the truth — and every update costs more.</p>
      <div className="field">
        <span>Motion noise: ×{spec.motion_noise}</span>
        <input type="range" min={0} max={4} step={0.25} value={spec.motion_noise} aria-label="Motion noise"
          onChange={(e) => set('motion_noise', Number(e.target.value))} />
      </div>
      <p className="note">How much the wheel odometry lies (×1 = alphas of 0.02). Both the world and the filters' motion model change: a noisier robot, and filters that trust its wheels less.</p>
      <div className="field">
        <span>Sensor noise: {(spec.sensor_sigma * 100).toFixed(0)} cm</span>
        <input type="range" min={0} max={0.3} step={0.01} value={spec.sensor_sigma} aria-label="Sensor noise"
          onChange={(e) => set('sensor_sigma', Number(e.target.value))} />
      </div>
      <p className="note">Gaussian noise on every LiDAR range. The filters are told it, but never assume less than COCO's AMCL does (σ 0.2 m).</p>
      <div className="field">
        <span>Injection</span>
        <select value={spec.injection} onChange={(e) => set('injection', e.target.value as LocSpec['injection'])}
          aria-label="Particle injection" data-testid="loc-injection">
          <option value="none">off (as COCO ships AMCL: recovery_alpha 0, 0)</option>
          <option value="augmented">augmented MCL (AMCL's recovery_alpha)</option>
          <option value="fixed">a fixed share every update</option>
        </select>
      </div>
      {spec.injection === 'augmented' && (
        <div className="field">
          <span>α slow / fast</span>
          <input type="number" min={0} max={1} step={0.001} value={spec.alpha_slow} aria-label="alpha slow"
            onChange={(e) => set('alpha_slow', Number(e.target.value))} />
          <input type="number" min={0} max={1} step={0.01} value={spec.alpha_fast} aria-label="alpha fast"
            onChange={(e) => set('alpha_fast', Number(e.target.value))} />
        </div>
      )}
      {spec.injection === 'fixed' && (
        <div className="field">
          <span>{Math.round(spec.inject_fraction * 100)} % random</span>
          <input type="range" min={0} max={lim.inject_fraction[1]} step={0.01} value={spec.inject_fraction}
            aria-label="Injected share" onChange={(e) => set('inject_fraction', Number(e.target.value))} />
        </div>
      )}
      <p className="note">Injection throws a few particles somewhere random. Augmented MCL does it when the scans suddenly fit worse than they used to (w_fast falls below w_slow); 0.001 / 0.1 are Nav2's suggested values.</p>
      <div className="field">
        <span>Start</span>
        <label className="choice"><input type="radio" checked={spec.init === 'tracking'} onChange={() => set('init', 'tracking')} />known</label>
        <label className="choice"><input type="radio" checked={spec.init === 'global'} onChange={() => set('init', 'global')} />unknown</label>
      </div>
      <div className="field">
        <label className="choice"><input type="checkbox" checked={spec.kidnap !== null} data-testid="loc-kidnap"
          onChange={(e) => set('kidnap', e.target.checked ? { t: spec.kidnap?.t ?? 20, to: spec.kidnap?.to ?? defaultTo } : null)} />
          kidnap the robot</label>
        {spec.kidnap && (
          <>
            <span>at t = {spec.kidnap.t} s</span>
            <input type="range" min={1} max={300} step={1} value={spec.kidnap.t} aria-label="Kidnap time"
              onChange={(e) => set('kidnap', { ...spec.kidnap!, t: Number(e.target.value) })} />
            <button type="button" className="seg-btn" aria-pressed={picking} onClick={() => setPicking(!picking)}>
              {picking ? 'click the map…' : `to (${spec.kidnap.to[0].toFixed(1)}, ${spec.kidnap.to[1].toFixed(1)})`}</button>
          </>
        )}
      </div>
      <p className="note">A kidnap carries the robot somewhere else. Odometry is not told: it is exactly the moment a filter's belief and the truth part ways.</p>
      <div className="field">
        <span>Seeds</span>
        <button type="button" className="seg-btn" onClick={() => set('seed', spec.seed + 1)}>new world ({spec.seed})</button>
        <button type="button" className="seg-btn" onClick={() => set('filter_seed', spec.filter_seed + 1)}>
          re-roll the filter ({spec.filter_seed})</button>
      </div>
      <button type="button" className="run" onClick={onRun} disabled={busy || !canRun} data-testid="loc-run">
        {busy ? 'Running…' : 'Run it with coco_lab'}</button>
    </section>
  );
}
