// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { BundleError } from '../../bundle/errors';
import { arraysFileName, type Catalog } from '../../bundle/load';
import { modeLabel } from '../../model/mode';
import type { SearchEntry, SearchPart } from '../../search/catalog';
import {
  loadSearchBytes, parseSearchManifest, type DecodedSearchBundle, type Problem, type SearchRun,
} from '../../search/decode';
import {
  beliefAt, bookkeepingAt, candidatesAt, fmt, kindAt, narrate, outcomeWords, pathAt, pct, positionAt, styleOf,
} from '../../search/view';
import { requestRecompute, workerStarted } from '../../worker/client';
import type { SearchSpec } from '../../worker/protocol';

const BASE = import.meta.env.BASE_URL;
const DATA = `${BASE}generated/`;

interface Current {
  bundle: DecodedSearchBundle;
  entry: SearchEntry;
  files: { manifest: Uint8Array; arraysName: string; arraysFile: Uint8Array };
  by: 'catalog' | 'pyodide';
  detail: string;
}

type Status = { state: 'idle' } | { state: 'busy' | 'done' | 'error'; message: string };
type Sub = 'try' | 'replay' | 'evidence';
type Plan = { order: string[]; expected_cost: number; p_find: number };

async function fetchBytes(url: string): Promise<Uint8Array> {
  const r = await fetch(url, { credentials: 'omit', cache: 'no-cache' });
  if (!r.ok) throw new Error(`cannot fetch ${url}: HTTP ${r.status}`);
  return new Uint8Array(await r.arrayBuffer());
}

async function loadEntry(entry: SearchEntry): Promise<Current> {
  const dir = `${DATA}${entry.path}`;
  const manifest = await fetchBytes(`${dir}manifest.json`);
  const name = arraysFileName(parseSearchManifest(manifest).compression);
  const arraysFile = await fetchBytes(`${dir}${name}`);
  const bundle = await loadSearchBytes(manifest, arraysFile);
  if (bundle.contentHash !== entry.content_hash) {
    throw new BundleError('catalog_mismatch', `${entry.id}: content hash is not the catalog's`);
  }
  return { bundle, entry, files: { manifest, arraysName: name, arraysFile }, by: 'catalog',
    detail: `${entry.validated.by}; ${entry.validated.replay}` };
}

const planOf = (run: SearchRun) => (run.summary as unknown as { plan: Plan }).plan;

/** Lab 4: Search. Every belief, cost and choice on it comes from coco_lab or the evidence. */
export function SearchLab({ catalog, reducedMotion }: { catalog: Catalog; reducedMotion: boolean }) {
  const part = (catalog as Catalog & { search?: SearchPart }).search;
  const [sub, setSub] = useState<Sub>(() => {
    const v = new URLSearchParams(window.location.search).get('search');
    return v === 'replay' || v === 'evidence' ? v : 'try';
  });
  if (!part) return <p className="error">This site was built without Lab 4.</p>;
  const tabs: Array<[Sub, string]> = [['try', 'Find it (Sketch)'], ['replay', 'The full ROS 2 stack (simulated) — Replay'],
    ['evidence', 'What is proven']];
  return (
    <div className="loc search-lab">
      <p className="lede"><strong>Where should the robot look next, given what it knows?</strong> COCO is told one
        word — a colour. It is not told which bay. It knows its map, the four bays, what it costs to drive to each
        and climb its ramp, and how often its camera finds a target that is there.</p>
      <nav className="seg" aria-label="Lab 4 sections">
        {tabs.map(([id, label]) => (
          <button key={id} type="button" className={sub === id ? 'seg-btn active' : 'seg-btn'} aria-pressed={sub === id}
            onClick={() => setSub(id)} data-testid={`search-sub-${id}`}>{label}</button>
        ))}
      </nav>
      {sub === 'try' && <TryLab catalog={catalog} part={part} reducedMotion={reducedMotion} />}
      {sub === 'replay' && <ReplayLab part={part} reducedMotion={reducedMotion} />}
      {sub === 'evidence' && <Evidence part={part} />}
    </div>
  );
}

// -- the arena drawing ---------------------------------------------------------------

const VIEW = { x0: -3.2, x1: 7.4, y0: -8.2, y1: 8.2 };

/** World (x forward, y left) to SVG: y up the page, x across it. */
function sx(y: number) { return (VIEW.y1 - y) * 40; }
function sy(x: number) { return (VIEW.x1 - x) * 40; }

export function Arena({ problem, run, e, truth, showTruth, colour }: {
  problem: Problem; run: SearchRun | null; e: number; truth: number | null; showTruth: boolean; colour: string;
}) {
  const n = problem.regions.length;
  const belief = run ? beliefAt(run, n, e) : problem.prior;
  const book = run ? bookkeepingAt(run, e) : { searched: [], current: null, discovered: null, order: [], surveys: 0 };
  const pos = run ? positionAt(problem, run, e) : problem.start_xy;
  const path = run ? pathAt(problem, run, e) : [problem.start_xy];
  const kind = run ? kindAt(run, Math.min(e, run.n - 1)) : null;
  const looking = run && (kind === 'survey' || kind === 'discover') ? run.region[e] : null;
  const W = (VIEW.y1 - VIEW.y0) * 40;
  const H = (VIEW.x1 - VIEW.x0) * 40;
  return (
    <svg className="arena-svg" viewBox={`0 0 ${W} ${H}`} role="img" data-testid="search-arena"
      aria-label={`The four bays. Belief: ${problem.regions.map((r, i) => `${r.label} ${pct(belief[i])}`).join(', ')}.`}>
      <rect x={0} y={0} width={W} height={H} className="arena-floor" />
      {problem.regions.map((r, i) => {
        const [xa, xb, ya, yb] = r.platform;
        const searched = book.searched.includes(i);
        const current = book.current === i;
        const found = book.discovered === i;
        return (
          <g key={r.id} data-testid={`search-bay-${r.id}`} className={`bay${searched ? ' searched' : ''}${current ? ' current' : ''}${found ? ' found' : ''}`}>
            <rect className="ramp" x={sx(yb)} y={sy(xa)} width={sx(ya) - sx(yb)} height={sy(1.0) - sy(xa)} />
            <rect className="ramp" x={sx(yb)} y={sy(6.2)} width={sx(ya) - sx(yb)} height={sy(xb) - sy(6.2)} />
            <rect className="platform" x={sx(yb)} y={sy(xb)} width={sx(ya) - sx(yb)} height={sy(xa) - sy(xb)} />
            <text className="bay-label" x={sx((ya + yb) / 2)} y={sy(6.6)} textAnchor="middle">{r.label}</text>
            {/* belief bar on the flat in front of the bay */}
            <rect className="belief-bg" x={sx((ya + yb) / 2) - 18} y={sy(-0.4)} width={36} height={80} />
            <rect className="belief-bar" x={sx((ya + yb) / 2) - 18} y={sy(-0.4) + 80 * (1 - belief[i])} width={36}
              height={80 * belief[i]} />
            <text className="belief-text" x={sx((ya + yb) / 2)} y={sy(-0.4) + 98} textAnchor="middle">{pct(belief[i])}</text>
            {searched && <text className="searched-mark" x={sx((ya + yb) / 2)} y={sy((xa + xb) / 2) + 8}
              textAnchor="middle">searched</text>}
            {showTruth && truth === i && (
              <g data-testid="search-truth"><circle className="truth" cx={sx(r.survey_pose[1])} cy={sy(4.05)} r={9}
                style={{ fill: colour }} /><text className="truth-label" x={sx(r.survey_pose[1]) + 14} y={sy(4.05) + 5}>
                truth</text></g>
            )}
            {found && <text className="found-mark" x={sx(r.survey_pose[1])} y={sy(4.05) - 14} textAnchor="middle">found</text>}
          </g>
        );
      })}
      {looking !== null && looking >= 0 && (() => {
        const sp = problem.regions[looking].survey_pose;
        const half = 0.625; // coco_config CAMERA_HFOV / 2
        const L = 1.6;
        const a = [sp[0] + L * Math.cos(sp[2] + half), sp[1] + L * Math.sin(sp[2] + half)];
        const b = [sp[0] + L * Math.cos(sp[2] - half), sp[1] + L * Math.sin(sp[2] - half)];
        return <polygon className="fov" data-testid="search-fov"
          points={`${sx(sp[1])},${sy(sp[0])} ${sx(a[1])},${sy(a[0])} ${sx(b[1])},${sy(b[0])}`} />;
      })()}
      <polyline className="search-path" points={path.map(([x, y]) => `${sx(y)},${sy(x)}`).join(' ')} />
      <circle className="home" cx={sx(problem.start_xy[1])} cy={sy(problem.start_xy[0])} r={7} />
      <text className="home-label" x={sx(problem.start_xy[1]) + 10} y={sy(problem.start_xy[0]) + 18}>home</text>
      <circle className="robot" cx={sx(pos[1])} cy={sy(pos[0])} r={8} data-testid="search-robot" />
    </svg>
  );
}

function Legend() {
  return (
    <ul className="legend">
      <li><i className="sw belief" /> the robot's belief that the target is in that bay</li>
      <li><i className="sw platform" /> platform (the camera only sees it from the top of the ramp)</li>
      <li><i className="sw fov" /> the camera's field of view while it looks (1.25 rad, coco_config)</li>
      <li><i className="sw truth" /> truth — only the simulator, or you, know it</li>
    </ul>
  );
}

// -- a run, step by step -----------------------------------------------------------------

function useStepper(n: number, reducedMotion: boolean) {
  const [e, setE] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => { setE(0); setPlaying(false); }, [n]);
  useEffect(() => {
    if (!playing) return undefined;
    if (e >= n - 1) { setPlaying(false); return undefined; }
    const id = window.setTimeout(() => setE((k) => Math.min(n - 1, k + 1)), reducedMotion ? 150 : 900);
    return () => window.clearTimeout(id);
  }, [playing, e, n, reducedMotion]);
  return { e, setE, playing, setPlaying };
}

function Stepper({ n, e, setE, playing, setPlaying, prefix }: {
  n: number; e: number; setE: (k: number) => void; playing: boolean; setPlaying: (p: boolean) => void; prefix: string;
}) {
  return (
    <div className="player" role="group" aria-label="Search player">
      <div className="player-buttons">
        <button type="button" onClick={() => setE(Math.max(0, e - 1))} aria-label="Back one step">‹</button>
        <button type="button" className="play" data-testid={`${prefix}-play`}
          onClick={() => { if (!playing && e >= n - 1) setE(0); setPlaying(!playing); }}>{playing ? 'Pause' : 'Play'}</button>
        <button type="button" onClick={() => setE(Math.min(n - 1, e + 1))} aria-label="Forward one step"
          data-testid={`${prefix}-step`}>›</button>
        <button type="button" onClick={() => { setPlaying(false); setE(n - 1); }} data-testid={`${prefix}-end`}>End</button>
      </div>
      <input className="scrub" type="range" min={0} max={Math.max(0, n - 1)} value={e} aria-label="Scrub"
        onChange={(ev) => { setPlaying(false); setE(Number(ev.target.value)); }} />
      <div className="player-pos">step {e + 1} of {n}</div>
    </div>
  );
}

function BeliefTable({ problem, run, e }: { problem: Problem; run: SearchRun; e: number }) {
  const n = problem.regions.length;
  const b = beliefAt(run, n, e);
  const c = candidatesAt(run, n, e);
  const book = bookkeepingAt(run, e);
  return (
    <div className="scroll-x"><table className="race-table" data-testid="search-belief-table">
      <caption className="note">After step {e + 1}. Belief and costs are coco_lab's (Bayes' rule; every remaining
        order costed exactly).</caption>
      <thead><tr><th>bay</th><th>belief</th><th>state</th><th>expected cost if chosen next</th></tr></thead>
      <tbody>{problem.regions.map((r, i) => (
        <tr key={r.id} className={book.current === i ? 'focus' : ''}>
          <td>{r.label}</td><td>{pct(b[i])}</td>
          <td>{book.discovered === i ? 'found' : book.searched.includes(i) ? 'searched' : book.current === i ? 'looking' : 'unsearched'}</td>
          <td>{c[i] === null ? '—' : `${fmt(c[i], 1)} m`}</td>
        </tr>))}</tbody>
    </table></div>
  );
}

// -- Try it ------------------------------------------------------------------------------

function useRunner(catalog: Catalog) {
  const busy = useRef(false);
  const [status, setStatus] = useState<Status>({ state: 'idle' });
  const run = useCallback(async (cur: Current, spec: SearchSpec): Promise<Current | null> => {
    if (busy.current || !catalog.wheel) return null;
    busy.current = true;
    setStatus({ state: 'busy', message: workerStarted()
      ? 'coco_lab is costing every order and running the searches in your browser…'
      : `Loading Python (Pyodide ${__PYODIDE_VERSION__}) and coco_lab — the first run takes a while…` });
    try {
      const wheelUrl = new URL(`${DATA}${catalog.wheel.path}`, window.location.href).href;
      const t0 = performance.now();
      const r = await requestRecompute({ manifest: cur.files.manifest, arraysName: cur.files.arraysName,
        arraysFile: cur.files.arraysFile, spec, wheelUrl, wheelSha256: catalog.wheel.sha256 }, 'search');
      if (!r.ok) {
        setStatus({ state: 'error', message: r.refused ? `Not run: ${r.error}` : `coco_lab could not run this: ${r.error}` });
        return null;
      }
      const w = r.bundles[0];
      const bundle = await loadSearchBytes(w.manifest, w.arraysFile);
      if (bundle.contentHash !== w.contentHash) {
        throw new BundleError('hash', 'the worker\'s bundle hash is not what the decoder computed');
      }
      setStatus({ state: 'done', message: `Done in ${((performance.now() - t0) / 1000).toFixed(1)} s ` +
        `(coco_lab: ${r.timings.search_ms.toFixed(0)} ms for ${r.timings.runs} searches).` });
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

const COLOUR_SWATCH = '#d62728';

function TryLab({ catalog, part, reducedMotion }: { catalog: Catalog; part: SearchPart; reducedMotion: boolean }) {
  const entry = part.bundles.find((b) => b.kind === 'sketch')!;
  const [base, setBase] = useState<Current | null>(null);
  const [cur, setCur] = useState<Current | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<number[]>([]);
  const [pred, setPred] = useState<'mine' | 'robot' | null>(null);
  const [truth, setTruth] = useState<number | null>(null);
  const [prior, setPrior] = useState<number[] | null>(null);
  const [detection, setDetection] = useState<number | null>(null);
  const [trueDet, setTrueDet] = useState<number | null>(null);
  const [seed, setSeed] = useState(0);
  const [watch, setWatch] = useState('robot');
  const { run, status } = useRunner(catalog);

  useEffect(() => {
    let alive = true;
    loadEntry(entry).then((c) => { if (alive) { setBase(c); setCur(c); } })
      .catch((exc) => alive && setError(exc instanceof Error ? exc.message : String(exc)));
    return () => { alive = false; };
  }, [entry]);

  const p = (cur ?? base)?.bundle.problem ?? null;
  const pr = prior ?? (p ? p.prior.map(() => 1) : [1, 1, 1, 1]);
  const d = detection ?? p?.detection[0] ?? 0.9;
  const td = trueDet ?? d;
  const computed = cur && cur.by === 'pyodide';
  const runs = cur?.bundle.runs ?? [];
  const robot = computed ? runs.find((r) => r.id === 'robot') : null;
  const mine = computed ? runs.find((r) => r.id === 'mine') : null;
  const shown = computed ? runs.find((r) => r.id === watch) ?? robot : null;
  const stepper = useStepper(shown?.n ?? 1, reducedMotion);
  const revealed = !!(computed && pred);

  const onRun = useCallback(async () => {
    if (!base) return;
    const out = await run(base, { prior: pr, detection: d, true_detection: td, truth, order, seed });
    if (out) setCur(out);
  }, [base, run, pr, d, td, truth, order, seed]);

  const toggleBay = (i: number) => {
    setCur(base);
    setPred(null);
    setOrder((o) => (o.includes(i) ? o.filter((k) => k !== i) : [...o, i]));
  };
  const ml = cur ? modeLabel(cur.bundle.provenance) : null;
  const defaultRobot = base?.bundle.runs.find((r) => r.id.startsWith('robot_'));

  return (
    <>
      <div className="loc-head">
        <h2 className="inline">Find it</h2>
        {ml && <span className="mode-badge mode-sketch" data-testid="search-mode">{ml.text}</span>}
      </div>
      {error && <div className="error" role="alert">Refused: {error}</div>}
      {!p && !error && <p className="loading">Loading and checking the search bundle…</p>}
      {p && (
        <main className="stage">
          <div className="canvas-col">
            <p className="lede">{entry.lesson}</p>
            <Arena problem={p} run={shown ?? null} e={stepper.e} truth={truth} showTruth={revealed} colour={COLOUR_SWATCH} />
            <Legend />
            {shown && (
              <>
                <Stepper n={shown.n} {...stepper} prefix="search" />
                <p className="narrate" data-testid="search-narrate" role="status">
                  <strong>{styleOf(String(shown.header.policy)).label}:</strong> {narrate(p, shown, stepper.e, 'the red target')}</p>
                <BeliefTable problem={p} run={shown} e={stepper.e} />
              </>
            )}
            {computed && <Outcomes problem={p} runs={runs} truth={truth} />}
          </div>
          <aside className="side">
            <section>
              <h2>1 · Your order</h2>
              <p className="note">Click the bays in the order you would search them. You may stop early — but the
                challenge is to find it.</p>
              <div className="bay-buttons" role="group" aria-label="Your search order">
                {p.regions.map((r, i) => (
                  <button key={r.id} type="button" className={order.includes(i) ? 'seg-btn active' : 'seg-btn'}
                    aria-pressed={order.includes(i)} onClick={() => toggleBay(i)} data-testid={`search-order-${r.id}`}>
                    {r.label}{order.includes(i) ? ` (${order.indexOf(i) + 1})` : ''}</button>
                ))}
              </div>
              <p className="note" data-testid="search-my-order">Your order: {order.length
                ? order.map((i) => p.regions[i].label).join(' → ') : 'none yet'}</p>
            </section>
            <section>
              <h2>2 · Predict</h2>
              <fieldset className="predict"><legend>Before you reveal it</legend>
                <div className="field"><span>Whose order has the lower expected search cost?</span>
                  {([['mine', 'mine'], ['robot', "the robot's"]] as const).map(([v, label]) => (
                    <label key={v} className="choice"><input type="radio" name="search-pred" checked={pred === v}
                      disabled={!order.length} onChange={() => setPred(v)} data-testid={`search-pred-${v}`} />{label}</label>
                  ))}</div>
              </fieldset>
            </section>
            <section>
              <h2>3 · Place the target, then reveal</h2>
              <div className="field"><span>The red target stands in</span>
                <select value={truth ?? ''} aria-label="Where the target stands" data-testid="search-truth-pick"
                  onChange={(ev) => { setTruth(ev.target.value === '' ? null : Number(ev.target.value)); setCur(base); }}>
                  <option value="">no bay (it is not there)</option>
                  {p.regions.map((r, i) => <option key={r.id} value={i}>{r.label}</option>)}
                </select></div>
              <p className="note">Hidden from every policy: it only decides what a look sees. The robot and your order
                search the SAME placement with the SAME seed.</p>
              <button type="button" className="run" disabled={!order.length || !pred || status.state === 'busy' || !catalog.wheel}
                onClick={onRun} data-testid="search-run">{status.state === 'busy' ? 'Running…' : 'Reveal: run both with coco_lab'}</button>
              {status.state !== 'idle' && <p className={`edit-status ${status.state}`} role="status" data-testid="search-status">
                {status.message}</p>}
              {revealed && robot && mine && <Reveal robot={robot} mine={mine} pred={pred!} problem={p} />}
              {computed && (
                <div className="field"><span>Watch</span>
                  <select value={watch} onChange={(ev) => setWatch(ev.target.value)} aria-label="Whose search" data-testid="search-watch">
                    {runs.map((r) => <option key={r.id} value={r.id}>{styleOf(String(r.header.policy)).label}</option>)}
                  </select></div>
              )}
            </section>
            <section>
              <h2>What the robot assumes</h2>
              <div className="field"><span>Prior weights (what it believes before looking)</span>
                {p.regions.map((r, i) => (
                  <label key={r.id} className="slider-row"><span>{r.label}: {pr[i]}</span>
                    <input type="range" min={0} max={4} step={1} value={pr[i]} aria-label={`Prior weight for ${r.label}`}
                      onChange={(ev) => { const v = [...pr]; v[i] = Number(ev.target.value); setPrior(v); setCur(base); }} />
                  </label>))}
              </div>
              <p className="note">The real mission uses equal weights: a prior built from "red is usually in bay 1"
                would be telling it the answer by another name.</p>
              <div className="field"><span>Detection d = P(seen | there): {d.toFixed(2)}</span>
                <input type="range" min={part.limits.detection[0]} max={part.limits.detection[1]} step={0.05} value={d}
                  aria-label="Detection probability" data-testid="search-detection"
                  onChange={(ev) => { setDetection(Number(ev.target.value)); setCur(base); }} /></div>
              <p className="note">0.90 is the mission's ASSUMPTION, not a measurement. Try 1.00: the robot's order
                becomes nearest-first.</p>
              <div className="field"><span>How often the camera really finds it: {td.toFixed(2)}</span>
                <input type="range" min={0} max={1} step={0.05} value={td} aria-label="True detection"
                  onChange={(ev) => { setTrueDet(Number(ev.target.value)); setCur(base); }} /></div>
              <div className="field"><span>Seed</span>
                <button type="button" className="seg-btn" onClick={() => { setSeed(seed + 1); setCur(base); }}>
                  new seed ({seed})</button></div>
            </section>
            {defaultRobot && !computed && (
              <section>
                <h2>The robot's plan (no target placed yet)</h2>
                <p className="note" data-testid="search-default-plan">{planOf(defaultRobot).order.map((id) =>
                  p.regions.find((r) => r.id === id)?.label).join(' → ')}: expected {fmt(planOf(defaultRobot).expected_cost, 1)} m
                  {' '}(found with probability {pct(planOf(defaultRobot).p_find)}). Reveal it against yours above.</p>
              </section>
            )}
            {cur && <Provenance cur={cur} />}
          </aside>
        </main>
      )}
    </>
  );
}

function Reveal({ robot, mine, pred, problem }: { robot: SearchRun; mine: SearchRun; pred: 'mine' | 'robot'; problem: Problem }) {
  const r = planOf(robot);
  const m = planOf(mine);
  const winner = m.expected_cost < r.expected_cost - 1e-9 ? 'mine' : 'robot';
  const lbl = (ids: string[]) => ids.map((id) => problem.regions.find((x) => x.id === id)?.label).join(' → ');
  return (
    <p className={`reveal ${winner === pred ? 'right' : 'wrong'}`} data-testid="search-revealed">
      The robot's order: {lbl(r.order)}, expected {fmt(r.expected_cost, 1)} m. Yours: {lbl(m.order)}, expected
      {' '}{fmt(m.expected_cost, 1)} m{m.p_find < r.p_find - 1e-12 ? ` — and it finds the target only ${pct(m.p_find)} of the time` : ''}.
      {' '}{winner === 'robot' ? 'The robot\'s is cheaper' : 'Yours is cheaper'} on average; you said {pred === 'mine' ? 'yours' : 'the robot\'s'}.
      (Expected cost: averaged over where the target might be and whether the camera sees it, under the robot's
      belief. One placement can go either way.)</p>
  );
}

function Outcomes({ problem, runs, truth }: { problem: Problem; runs: SearchRun[]; truth: number | null }) {
  return (
    <div className="scroll-x"><table className="race-table" data-testid="search-outcomes">
      <caption className="note">One placement ({truth === null ? 'no target anywhere' : `the target in ${problem.regions[truth].label}`}),
        one seed, every policy: only the order differs (rule 6).</caption>
      <thead><tr><th>search</th><th>order looked</th><th>found</th><th>metres driven</th><th>expected (plan)</th><th>challenge</th></tr></thead>
      <tbody>{runs.map((r) => (
        <tr key={r.id}>
          <td><i className="sw" style={{ background: styleOf(String(r.header.policy)).color, height: 4, border: 0 }} />
            {' '}{styleOf(String(r.header.policy)).label}</td>
          <td>{r.summary.order.map((id) => problem.regions.find((x) => x.id === id)?.label).join(' → ') || '—'}</td>
          <td>{r.summary.discovered ? `${problem.regions.find((x) => x.id === r.summary.discovered)?.label} (look ${r.summary.discovered_at})` : 'no'}</td>
          <td>{fmt(r.summary.cost, 1)} m</td>
          <td>{fmt(planOf(r).expected_cost, 1)} m</td>
          <td>{r.summary.status === 'discovered' ? 'pass' : 'fail'}</td>
        </tr>))}</tbody>
    </table></div>
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
        <div className="row"><dt>travel costs</dt><dd>coco_lab's A* on the robot's own map ({String(b.problem.meta.map ?? '?')}), metres</dd></div>
        <div className="row"><dt>detection</dt><dd>{b.problem.detection[0].toFixed(2)} ({String(b.problem.meta.detection_is ?? 'set here')})</dd></div>
        {bag && <div className="row"><dt>recording</dt><dd>rosbag2 <code>{bag.sha256.slice(0, 12)}…</code>, sim time
          {' '}{bag.sim_time_start.toFixed(1)}–{bag.sim_time_end.toFixed(1)} s</dd></div>}
      </dl>
      <p className="cite">Evidence: {cur.entry.cites.join('; ')}</p>
    </section>
  );
}

// -- Replay ------------------------------------------------------------------------------

function ReplayLab({ part, reducedMotion }: { part: SearchPart; reducedMotion: boolean }) {
  const recs = part.bundles.filter((b) => b.kind === 'replay');
  const [entryId, setEntryId] = useState(recs[0]?.id);
  const entry = recs.find((e) => e.id === entryId) ?? recs[0];
  const [cur, setCur] = useState<Current | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [showTruth, setShowTruth] = useState(false);
  useEffect(() => {
    if (!entry) return undefined;
    let alive = true;
    setCur(null);
    loadEntry(entry).then((c) => { if (alive) { setCur(c); setRunId(c.bundle.runs[0].id); } })
      .catch((exc) => alive && setError(exc instanceof Error ? exc.message : String(exc)));
    return () => { alive = false; };
  }, [entry]);
  const b = cur?.bundle ?? null;
  const run = b?.runs.find((r) => r.id === runId) ?? b?.runs[0] ?? null;
  const stepper = useStepper(run?.n ?? 1, reducedMotion);
  const truthIdx = useMemo(() => {
    const t = run?.evaluator?.truth_region;
    return b && typeof t === 'string' ? b.problem.regions.findIndex((r) => r.id === t) : null;
  }, [b, run]);
  if (!recs.length) {
    return <p className="note" data-testid="search-no-replay">No Gazebo search is recorded in this build yet
      (not yet measured).</p>;
  }
  const rec = (run?.record ?? {}) as Record<string, unknown>;
  return (
    <>
      <div className="loc-head">
        <label className="picker-inline"><span>Recording</span>
          <select value={entry.id} onChange={(ev) => setEntryId(ev.target.value)} data-testid="search-replay-picker">
            {recs.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
          </select></label>
        {b && <span className="mode-badge mode-recorded" data-testid="search-replay-mode">{modeLabel(b.provenance).text}</span>}
      </div>
      {error && <div className="error" role="alert">Refused: {error}</div>}
      {b && run && (
        <main className="stage">
          <div className="canvas-col">
            <p className="lede">{entry.lesson}</p>
            <Arena problem={b.problem} run={run} e={stepper.e} truth={truthIdx} showTruth={showTruth}
              colour={String(rec.colour ?? 'red')} />
            <Legend />
            <Stepper n={run.n} {...stepper} prefix="search-replay" />
            <p className="narrate" role="status" data-testid="search-replay-narrate">
              {run.t && Number.isFinite(run.t[stepper.e]) && <>t = {run.t[stepper.e].toFixed(1)} s (sim) · </>}
              {narrate(b.problem, run, stepper.e, `the ${String(rec.colour ?? '')} target`)}</p>
            <BeliefTable problem={b.problem} run={run} e={stepper.e} />
            <Timeline run={run} e={stepper.e} />
          </div>
          <aside className="side">
            <section>
              <div className="field"><span>Run</span>
                <select value={run.id} onChange={(ev) => setRunId(ev.target.value)} aria-label="Which run" data-testid="search-replay-run">
                  {b.runs.map((r) => <option key={r.id} value={r.id}>{r.id}</option>)}
                </select></div>
              <label className="choice"><input type="checkbox" checked={showTruth} data-testid="search-replay-truth"
                onChange={(ev) => setShowTruth(ev.target.checked)} />show the truth (from the episode manifest —
                the evaluator's side; the robot never had it)</label>
              <dl className="rows">
                <div className="row"><dt>told</dt><dd>"{String(rec.colour ?? '?')}" — and nothing else</dd></div>
                <div className="row"><dt>episode</dt><dd>{String(rec.level ?? '?')} seed {String(rec.seed ?? '?')}</dd></div>
                <div className="row"><dt>order given</dt><dd>{String(rec.order_arg ?? 'the robot\'s policy')}</dd></div>
                <div className="row"><dt>mission</dt><dd>{String(rec.outcome ?? '?')}{rec.reason ? ` (${String(rec.reason)})` : ''}</dd></div>
                <div className="row"><dt>looks</dt><dd>{(rec.observations as Array<{ region: string; found: boolean; seen: string[] }> | undefined)
                  ?.map((o) => `${o.region}: ${o.found ? 'found' : `no (saw ${o.seen.join(', ') || 'nothing'})`}`).join('; ') ?? '—'}</dd></div>
                {showTruth && <div className="row"><dt>truth</dt><dd data-testid="search-replay-truth-value">
                  {String(run.evaluator?.truth_region ?? '?')}</dd></div>}
              </dl>
            </section>
            {cur && <Provenance cur={cur} />}
          </aside>
        </main>
      )}
    </>
  );
}

function Timeline({ run, e }: { run: SearchRun; e: number }) {
  if (!run.timeline.length) return null;
  const now = run.t ? run.t[Math.min(e, run.n - 1)] : Infinity;
  return (
    <details className="honest" open>
      <summary>The mission's state machine, as it ran (sim time)</summary>
      <ol className="timeline" data-testid="search-timeline">
        {run.timeline.map(([t, state, reason], i) => (
          <li key={i} className={t <= now ? 'past' : 'future'}>
            <code>{t.toFixed(1)} s</code> {state}{reason ? ` [${reason}]` : ''}</li>
        ))}
      </ol>
    </details>
  );
}

// -- What is proven ------------------------------------------------------------------------


function Evidence({ part }: { part: SearchPart }) {
  const m = part.matrix;
  return (
    <section className="evidence" data-testid="search-evidence">
      <h2>What is proven, and where</h2>
      <ul className="claims">
        {part.claims.map((c) => (
          <li key={c.id}><p>{c.text}</p><p className="cite">Tested: {c.cites.join('; ')}</p></li>
        ))}
      </ul>
      <h2>The real mission in Gazebo</h2>
      {m.status !== 'measured' ? <p className="note" data-testid="search-matrix-none">Not yet measured.</p> : (
        <>
          <p className="note">{m.label} <span className="cite">{m.command}</span></p>
          <div className="scroll-x"><table className="race-table" data-testid="search-matrix">
            <thead><tr><th>run</th><th>asked</th><th>truth (manifest)</th><th>order searched</th><th>found</th>
              <th>mission</th><th>lift</th><th>home error</th><th>relocalise</th><th>recoveries</th></tr></thead>
            <tbody>{m.rows.map((r) => (
              <tr key={r.run}><td>{r.run}</td><td>{r.colour}</td><td>{r.truth_region}</td>
                <td>{r.order.join(' → ') || '—'}{r.order_arg !== 'policy' ? ' (given)' : ''}</td>
                <td>{r.discovered ?? 'no'}</td><td>{outcomeWords(r.outcome, r.reason)}</td>
                <td>{r.lifted === null ? '—' : r.lifted ? 'yes' : 'no'}</td><td>{r.home_error_m === null ? '—' : `${fmt(r.home_error_m)} m`}</td>
                <td>{r.relocalisations}</td><td>{r.recoveries}</td></tr>))}</tbody>
          </table></div>
          <ul className="note">{m.notes.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </>
      )}
      <p className="cite">{part.challenge.score} — {part.challenge.cites.join('; ')}</p>
    </section>
  );
}

