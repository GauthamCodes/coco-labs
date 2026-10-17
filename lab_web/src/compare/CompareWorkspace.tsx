// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { useEffect, useRef, useState } from 'react';
import { ArenaClient } from '../arena/client';
import { PlanStore } from '../arena/render/planStore';
import type { CompareInflation, CompareResult, World, LoopFrame } from '../arena/protocol';
import { WorldStage, type ComparisonData } from '../ui/reference/WorldStage';
import type { CostmapData, CostLayer } from '../ui/reference/comparisonPixels';
import { ModeNav } from '../ui/ModeNav';
import '../ui/reference/reference.css';
import './compare.css';
import { Tours, type TourPreset } from './Tours';
const BASE = import.meta.env.BASE_URL;
const LABELS: Record<string, string> = { bfs: 'BFS', dijkstra: 'Dijkstra', astar: 'A*', greedy: 'Greedy', weighted_astar: 'Weighted A*', dstar_lite: 'D* Lite' };
const FAMILY_NAMES = { global: ['astar', 'dijkstra', 'greedy', 'weighted_astar'], control: ['dwa', 'rpp', 'mppi', 'dwa'], localise: ['mcl', 'mcl_augmented', 'ekf', 'mcl'] };
type Family = keyof typeof FAMILY_NAMES;
Object.assign(LABELS, { dwa: 'DWA-style sampler', rpp: 'Pure pursuit', mppi: 'MPPI', mcl: 'MCL · no injection', mcl_augmented: 'MCL · injection', ekf: 'EKF' });
const KEYS = ['A', 'B', 'C', 'D'] as const;
const fresh = (world: World, occupancy: Uint8Array, count: number): ComparisonData => ({ world, occupancy, stores: Array.from({ length: count }, () => new PlanStore(world.width, world.height)) });
export function CompareWorkspace() {
  const [data, setData] = useState<ComparisonData>();
  const state = useRef<ComparisonData | undefined>(undefined); const client = useRef<ArenaClient | undefined>(undefined);
  const [family, setFamily] = useState<Family>('global');
  const [windowSteps, setWindowSteps] = useState(60);
  const history = useRef<LoopFrame[][]>([]);
  const [loopFrames, setLoopFrames] = useState<LoopFrame[]>();
  const [loopCount, setLoopCount] = useState(0);
  const [names, setNames] = useState(['astar', 'dijkstra']);
  const [params, setParams] = useState<CompareInflation>({ inflation_radius: .5, cost_scaling_factor: 10, robot_radius: .25 });
  const [deviceLabel, setDeviceLabel] = useState('This device · ' + navigator.platform);
  const [goal, setGoal] = useState<[number, number]>([2.5, 2]);
  const [result, setResult] = useState<CompareResult>();
  const [busy, setBusy] = useState(true), [error, setError] = useState('');
  const [perspective, setPerspective] = useState(false), [difference, setDifference] = useState(false);
  const [layer, setLayer] = useState<CostLayer>('combined');
  const cursorRef = useRef(0);
  const [cursor, setCursor] = useState(0), [playing, setPlaying] = useState(false);
  const [hover, setHover] = useState<[number, number] | null>(null);
  const controlsToggle = useRef<HTMLButtonElement>(null);
  const [controls, setControls] = useState(new URLSearchParams(location.search).has('tour'));
  const [tours, setTours] = useState(new URLSearchParams(location.search).has('tour'));
  const [preset, setPreset] = useState<TourPreset>(); const appliedPreset = useRef('');
  const closeControls = () => { setControls(false); requestAnimationFrame(() => controlsToggle.current?.focus()); };
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (controls && event.key === 'Escape' && !document.querySelector('dialog[open]')) { event.preventDefault(); closeControls(); } };
    window.addEventListener('keydown', escape); return () => window.removeEventListener('keydown', escape);
  }, [controls]);
  const config = useRef({ names, params, goal, family }); config.current = { names, params, goal, family };
  const run = (nextNames = names, nextParams = params, nextGoal = goal, nextFamily = family, steps = windowSteps) => {
    const old = state.current, c = client.current; if (!old || !c) return;
    const next = fresh(old.world, old.occupancy, nextNames.length);
    state.current = next; setData(next); setResult(undefined); setBusy(true); setError(''); setPlaying(false); setCursor(0); history.current = []; setLoopCount(0); setLoopFrames(undefined);
    if (nextFamily === 'global') c.compareMany(nextNames, nextGoal[0], nextGoal[1], nextParams);
    else c.compareLoop({ family: nextFamily, names: nextNames, goal: nextGoal, inflation: nextParams, steps });
  };
  const applyLoopCursor = (value: number) => {
    const d = state.current; if (!d) return;
    d.stores.forEach((store, pane) => {
      store.state.fill(0); store.cursor = value;
      for (const frame of history.current.slice(0, value)) {
        const pose = frame[pane].pose, col = Math.floor((pose[0] - d.world.origin[0]) / d.world.resolution), row = d.world.height - 1 - Math.floor((pose[1] - d.world.origin[1]) / d.world.resolution);
        if (row >= 0 && row < d.world.height && col >= 0 && col < d.world.width) store.state[row * d.world.width + col] = 3;
      }
    });
    setLoopFrames(history.current[Math.max(0, value - 1)]); setCursor(value); setData({ ...d });
  };
  useEffect(() => {
    const c = new ArenaClient({
      onWorld(world, occupancy) {
        const next = fresh(world, occupancy, config.current.names.length);
        state.current = next; setData(next);
        const cfg = config.current; c.compareMany(cfg.names, ...cfg.goal, cfg.params);
      },
      onFamily(message) {
        const d = state.current, columns = message.columns;
        if (!d || message.channel !== 'coco.costmap.layers.cells.v1' || !columns) return;
        d.costs ??= Object.fromEntries(['static', 'inflation', 'obstacle', 'combined'].map(key => [key, new Uint8Array(d.world.width * d.world.height)])) as unknown as CostmapData;
        for (let k = 0; k < columns.row.length; k++) {
          const i = Number(columns.row[k]) * d.world.width + Number(columns.col[k]);
          for (const key of ['static', 'inflation', 'obstacle', 'combined'] as const) d.costs[key][i] = Number(columns[key + '_cost'][k]);
        }
      },
      onLoopCompareBatch(frames, done) {
        history.current.push(...frames); setLoopCount(history.current.length); applyLoopCursor(history.current.length);
        if (done) {
          setBusy(false);
          const last = history.current.at(-1)!;
          setResult(Object.fromEntries(last.map((frame, i) => [KEYS[i], { planner: config.current.names[i], status: frame.status, resolution: state.current!.world.resolution, summary: frame.summary }])) as unknown as CompareResult);
        }
      },
      onCompareBatch(meta, columns) {
        const store = state.current?.stores[KEYS.indexOf(meta.compare!)]; if (!store) return;
        if (store.searchId !== meta.search_id) store.begin(meta.search_id, meta.planner);
        store.append(columns, meta.final);
      },
      onCompareDone(done) {
        const d = state.current; if (!d) return;
        d.stores.forEach(store => store.seek(store.received));
        setCursor(Math.max(...d.stores.map(store => store.received))); setData({ ...d }); setResult(done); setBusy(false);
      },
      onError(stage, message) { setError(stage + ': ' + message); setBusy(false); },
    }, { seed: 1, hashVersion: 2 });
    client.current = c; return () => { c.close(); client.current = undefined; };
  }, []);
  cursorRef.current = cursor;
  const end = family === 'global' ? Math.max(0, ...(data?.stores.map(store => store.received) ?? [])) : loopCount;
  const seek = (value: number) => { if (family !== 'global') { applyLoopCursor(value); return; } state.current?.stores.forEach(store => store.seek(Math.min(value, store.received))); setCursor(value); };
  useEffect(() => {
    if (!playing || !end) return;
    const timer = setInterval(() => {
      const next = Math.min(end, cursorRef.current + Math.max(1, Math.ceil(end / 200)));
      cursorRef.current = next;
      if (family !== 'global') applyLoopCursor(next);
      else { state.current?.stores.forEach(store => store.seek(Math.min(next, store.received))); setCursor(next); }
      if (next === end) setPlaying(false);
    }, 50); return () => clearInterval(timer);
  }, [playing, end, family]);
  const shown = data ? { ...data, layer, difference: difference && family === 'global', revision: cursor, loopFrames } : undefined;
  useEffect(() => {
    if (busy || !preset || appliedPreset.current === preset.id) return;
    appliedPreset.current = preset.id;
    const nextParams = { ...params, robot_radius: preset.radius ?? params.robot_radius };
    nextParams.inflation_radius = Math.max(nextParams.inflation_radius, nextParams.robot_radius);
    setFamily(preset.family); setNames(preset.names); setParams(nextParams); run(preset.names, nextParams, goal, preset.family);
  }, [preset, busy]);
  const changeParams = (key: keyof CompareInflation, value: number) => {
    const next = { ...params, [key]: value };
    if (next.inflation_radius < next.robot_radius) next.inflation_radius = next.robot_radius;
    setParams(next); run(names, next);
  };
  const select = (index: number, value: string) => { const next = [...names]; next[index] = value; setNames(next); run(next); };
  return <main className={`compare-workspace ${controls ? 'controls-open' : ''}`} data-testid="compare-workspace" data-ready={!!result}>
    <ModeNav current="compare" evidence="MODEL" />
    <section className="compare-stage" aria-label="Comparison panes">
      <WorldStage kind="compare" data={shown} perspective={perspective} onHover={setHover} onGoal={(x, y) => { if (!busy) { setGoal([x, y]); run(names, params, [x, y]); } }} />
      <div className={`compare-labels panes-${names.length}`}>{names.map((name, i) => <div key={i}><strong>{KEYS[i]} · {LABELS[name] ?? name}</strong><span>MODEL · kinematic</span></div>)}</div>
      <div className="compare-toolbar"><button onClick={() => setPerspective(!perspective)}>{perspective ? 'Top down' : '3D view'}</button><button disabled={family !== 'global'} onClick={() => setDifference(!difference)} aria-pressed={difference}>A/B difference</button><button ref={controlsToggle} className="compare-controls-toggle" onClick={() => setControls(!controls)} aria-expanded={controls}>Controls</button></div>
      <output className={`compare-hover ${hover ? 'has-cell' : 'is-hint'}`}>{hover && data?.costs ? `Cell ${hover.join(', ')} · ${layer} cost ${data.costs[layer][hover[0] * data.world.width + hover[1]]}` : 'Hover a cell for its cost · click for the shared goal'}</output>
    </section>
    <aside className="compare-controls" aria-label="Comparison controls"><button className="compare-close-controls" onClick={closeControls}>Close controls</button><div className="compare-mobile-view"><button onClick={() => setPerspective(!perspective)}>{perspective ? 'Top down' : '3D view'}</button><button disabled={family !== 'global'} onClick={() => setDifference(!difference)} aria-pressed={difference}>A/B difference</button></div>
      <h1>One world.<br />Different decisions.</h1><p>Same map, start, goal and seed.</p>
      {tours && <Tours onPreset={setPreset} />}
      {preset?.lens && ['map', 'decide'].includes(preset.lens) && <p>This lesson continues in the existing {preset.lens === 'map' ? 'mapping' : 'decision'} Inspect view. <a href={`${BASE}?view=arena&lens=${preset.lens}&level=explain&camera=topdown`}>Open this lesson's computation</a></p>}
      <fieldset disabled={busy}><legend>Compare algorithms</legend>
        <label>Family<select aria-label="Family" value={family} onChange={e => { const next = e.target.value as Family, values = FAMILY_NAMES[next].slice(0, names.length); setFamily(next); setNames(values); run(values, params, goal, next); }}><option value="global">Global planning</option><option value="control">Local control</option><option value="localise">Localization</option></select></label>
        <label>Panes<select aria-label="Panes" value={names.length} onChange={e => { const next = Number(e.target.value) === 4 ? [...names.slice(0, 2), ...FAMILY_NAMES[family].slice(2)] : names.slice(0, 2); setNames(next); run(next); }}><option value={2}>2 panes</option><option value={4}>4 panes</option></select></label>
        {names.map((name, index) => <label key={index}>Algorithm {KEYS[index]}<select aria-label={`Algorithm ${KEYS[index]}`} value={name} onChange={e => select(index, e.target.value)}>{Object.entries(LABELS).filter(([key]) => family === 'global' ? ![...FAMILY_NAMES.control, ...FAMILY_NAMES.localise].includes(key) : FAMILY_NAMES[family].includes(key)).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>)}
        <label>Inflation radius · {params.inflation_radius.toFixed(2)} m<input type="range" min={params.robot_radius} max={1.5} step={.05} value={params.inflation_radius} onChange={e => changeParams('inflation_radius', +e.target.value)} /></label>
        <label>Cost scaling · {params.cost_scaling_factor}<input type="range" min={0} max={65} step={1} value={params.cost_scaling_factor} onChange={e => changeParams('cost_scaling_factor', +e.target.value)} /></label>
        <label>Robot radius · {params.robot_radius.toFixed(2)} m<input type="range" min={.1} max={.5} step={.01} value={params.robot_radius} onChange={e => changeParams('robot_radius', +e.target.value)} /></label>
      </fieldset>
      <form onSubmit={event => { event.preventDefault(); if (!busy && goal.every(Number.isFinite)) run(); }}>
        <fieldset disabled={busy}><legend>{family === 'localise' ? 'Shared relocation point' : 'Shared goal'}</legend>
        {(['X', 'Y'] as const).map((axis, index) => <label key={axis}>{axis} (m)<input type="number" required step="any" value={goal[index]} onChange={event => setGoal(values => values.map((v, i) => i === index ? +event.target.value : v) as [number, number])} /></label>)}
        <button type="submit">Apply to all panes</button></fieldset>
      </form>
      <label>Timing device (editable)<input type="text" maxLength={100} value={deviceLabel} onChange={event => setDeviceLabel(event.target.value)} /></label>
      {family !== 'global' && <label>Shared time window<select aria-label="Shared time window" disabled={busy} value={windowSteps} onChange={event => { const steps = +event.target.value; setWindowSteps(steps); run(names, params, goal, family, steps); }}><option value={60}>6 seconds</option><option value={200}>20 seconds</option></select></label>}
      <label>Costmap layer<select aria-label="Costmap layer" value={layer} onChange={e => setLayer(e.target.value as CostLayer)}>{['static', 'inflation', 'obstacle', 'combined'].map(key => <option key={key}>{key}</option>)}</select></label>
      {family !== 'global' && <p>{windowSteps / 10}-second MODEL window, shared 0.1 s ticks. {family === 'localise' ? `Same open-loop commands; shared relocation at ${Math.min(50, Math.max(1, Math.floor(windowSteps / 3))) / 10} s. Shared teaching profile: 60 MCL particles and 12 LiDAR beams for each filter. Purple particles, pink estimated trail, green truth outline. Costmap sliders change the displayed common grid, not the localization sensor model. Success means final position error ≤0.5 m.` : 'Same A* global goal; current LiDAR drives each controller. Amber line is the selected candidate. Success means reached within this window.'} The floor costmap shows the common initial grid.</p>}
      <p>COCO arena · seed 1<br />Goal {goal.map(v => v.toFixed(2)).join(', ')} m</p>
      {names.includes('dstar_lite') && <p>D* Lite searches backwards. This is its first plan; the real-story tour examines repair after a costmap change.</p>}
      <p>White contour: lethal 254. Dashed contour: inscribed 253. Circular model radius; current scan marks have no persistence.</p>
      {difference && family === 'global' && <p>Expanded cells stay blue: A only has rising stripes, B only falling stripes, both solid. Paths stay pink: A solid, B dashed where separate.</p>}
      <button onClick={() => setTours(!tours)} aria-expanded={tours}>{tours ? 'Close tours' : 'Guided tours'}</button><a href={`${BASE}?view=arena&lens=${family === 'control' ? 'move' : family === 'localise' ? 'localise' : 'plan'}&level=inspect&camera=topdown`}>Inspect the full robot loop</a>
      <p role="status">{busy ? family === 'global' ? 'Computing every pane…' : `Computing ${loopCount} / ${windowSteps} shared ticks…` : 'Ready'}</p>{error && <p role="alert">{error}</p>}
    </aside>
    <section className="compare-results" aria-label="Final results">{names.map((name, i) => { const side = result?.[KEYS[i]]; return <div key={i}><strong>{KEYS[i]} · {LABELS[name]}</strong><span>{side?.summary.expansions ?? '—'} expansions</span><span>{side?.summary.path_length_m != null ? Number(side.summary.path_length_m).toFixed(2) : side?.summary.path_length != null ? (Number(side.summary.path_length) * side.resolution).toFixed(2) : '—'} m {family === 'global' ? 'planned path' : 'travelled (truth)'}</span><span>Cost {side?.summary.path_cost != null ? Number(side.summary.path_cost).toFixed(2) : '—'}</span><span>{side?.summary.minimum_clearance_m != null ? Number(side.summary.minimum_clearance_m).toFixed(2) : '—'} m minimum clearance</span><span>{side?.summary.compute_ms != null ? Number(side.summary.compute_ms).toFixed(1) : '—'} ms · {deviceLabel || 'Device not named'} · {family === 'global' ? 'search + trace' : 'model window'}</span><span>{side?.status ?? 'computing'}</span></div>; })}</section>
    <section className="compare-timeline" aria-label="Lockstep timeline"><button disabled={busy || !end} onClick={() => { if (cursor === end) seek(0); setPlaying(!playing); }}>{playing ? 'Pause' : 'Replay'}</button><input aria-label="Shared event cursor" type="range" min={0} max={end || 1} value={cursor} disabled={busy} onChange={e => { setPlaying(false); seek(+e.target.value); }} /><output>{cursor} / {end} {family === 'global' ? 'events' : 'ticks'}</output></section>
  </main>;
}
