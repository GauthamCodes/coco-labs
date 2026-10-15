// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Working design references; normal product routes migrate in M5.5. */
import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Camera, Columns2, Hand, Library, Navigation2, Pause, Route, ScanEye, Settings, Square } from 'lucide-react';
import { WorldStage, type ComparisonData } from './WorldStage';
import { ArenaClient } from '../../arena/client';
import { PlanStore } from '../../arena/render/planStore';
import type { CompareSide } from '../../arena/protocol';
import { useArenaScene } from '../../arena/sceneCore';
import { Joystick } from '../../arena/Joystick';
import { Help } from '../../arena/Help';
import { rebind, resetBindings } from '../../arena/controls';
import { TOKENS } from '../tokens';
import { activeTheme, applyMotion } from '../theme';
import './reference.css';

const refLink = (screen: string) => `${import.meta.env.BASE_URL}?view=arena&reference=${screen}&camera=follow`;
function Badge() { return <span className="night-badge">MODEL <span>· kinematic</span></span>; }
function Header({ mode }: { mode: string }) {
  return <header className="night-header"><a className="night-brand" href={refLink('title')}>COCO <span>Lab</span></a><span className="night-mode">{mode}</span><Badge /></header>;
}
function TitleReference() {
  useEffect(() => {
    const play = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || ['Tab', 'Shift', 'Escape', 'Control', 'Alt', 'Meta'].includes(event.key) || event.key.startsWith('Arrow')) return;
      if ((event.target as HTMLElement)?.closest('a,button,input,select,textarea')) return;
      window.location.assign(refLink('play'));
    };
    window.addEventListener('keydown', play); return () => window.removeEventListener('keydown', play);
  }, []);
  const cards = [{ mode: 'Play', copy: 'Drive COCO. Race the planner.', icon: Navigation2, key: 'play' }, { mode: 'Compare', copy: 'One map. Different decisions.', icon: Columns2, key: 'compare' }, { mode: 'Research', copy: 'Explore recorded ROS 2 runs.', icon: Library, key: 'research' }];
  return <main className="night-title" data-testid="reference-title">
    <div className="night-title-world"><WorldStage kind="title" /></div>
    <header className="night-title-header"><span className="night-eyebrow">THE NIGHT SHIFT</span><a href={`${import.meta.env.BASE_URL}?view=about`}>About <ArrowUpRight size={16} /></a></header>
    <div className="night-title-copy"><p className="night-eyebrow">A GLASS-BOX ROBOT LAB</p><h1>COCO <span>Lab</span></h1><p className="night-tagline">See what the robot computes.</p><span className="night-rule" /></div>
    <nav className="night-doors" aria-label="Choose a mode">{cards.map(({ mode, copy, icon: Icon, key }) => <a className="night-door" key={key} href={key === 'research' ? `${import.meta.env.BASE_URL}?view=casefiles` : refLink(key)}><div className="night-door-top"><Icon size={24} strokeWidth={1.5} /><ArrowUpRight size={20} strokeWidth={1.5} /></div><h2>{mode}</h2><p>{copy}</p></a>)}</nav>
    <footer className="night-title-footer"><span>Press any key to play</span><Badge /></footer>
  </main>;
}

function Minimap({ model }: { model: ReturnType<typeof useArenaScene> }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!model.world || !model.occupancy.current || !canvas.current) return;
    const world = model.world, occupancy = model.occupancy.current, p = TOKENS.computation[activeTheme()];
    const ctx = canvas.current.getContext('2d')!; const size = 192;
    ctx.clearRect(0, 0, size, size); ctx.fillStyle = p.free; ctx.fillRect(0, 0, size, size);
    const scale = Math.min(size / world.width, size / world.height);
    const ox = (size - world.width * scale) / 2, oy = (size - world.height * scale) / 2;
    ctx.fillStyle = p.occupied;
    for (let row = 0; row < world.height; row++) for (let col = 0; col < world.width; col++) if (occupancy[row * world.width + col]) ctx.fillRect(ox + col * scale, oy + row * scale, Math.max(1, scale), Math.max(1, scale));
    const pose = model.tick?.pose;
    if (pose) {
      const x = ox + (pose[0] - world.origin[0]) / world.resolution * scale;
      const y = oy + (world.height - (pose[1] - world.origin[1]) / world.resolution) * scale;
      ctx.fillStyle = p.robot; ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = p.path; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(pose[2]) * 9, y - Math.sin(pose[2]) * 9); ctx.stroke();
    }
  }, [model.world, model.tick]);
  return <figure className="night-minimap"><canvas ref={canvas} width={192} height={192} aria-label="COCO's known planning occupancy map" /><figcaption>KNOWN MAP</figcaption></figure>;
}

function PlayReference() {
  const m = useArenaScene();
  const phone = navigator.maxTouchPoints > 0 && matchMedia('(pointer: coarse)').matches;
  const [vision, setVision] = useState(false);
  useEffect(() => {
    m.setLayers((layers) => layers.lidar === vision && !layers.frontier && !layers.closed && !layers.path && !layers.footprint
      ? layers : { ...layers, lidar: vision, frontier: false, closed: false, path: false, footprint: false });
  }, [vision, m.layers]);
  // The asynchronous recording creates its drawable buffers after React's
  // initial layer effect; reapply the reference's display choice at each tick.
  useEffect(() => { m.r.current?.setLayers({ lidar: vision, frontier: false, closed: false, path: false, footprint: false }); }, [vision, m.tick]);
  useEffect(() => { const timer = setInterval(() => { const rig = m.r.current?.three; if (rig?.ready) { rig.setFollowFraming(5.2, 40 * Math.PI / 180); clearInterval(timer); } }, 100); return () => clearInterval(timer); }, [m.world, m.tierNow]);
  const stop = () => { m.takeOver(); m.queue.current.push({ kind: 'stop' }); m.latchedRef.current = true; m.setLatched(true); };
  const release = () => { m.latchedRef.current = false; m.setLatched(false); };
  const grasp = () => { if (!m.latchedRef.current) { m.takeOver(); m.queue.current.push({ kind: 'grasp' }); } };
  const autonomy = () => { if (!m.latchedRef.current) { m.takeOver(); m.queue.current.push({ kind: 'autonomy' }); } };
  const wheels = m.tick?.wheels;
  const source = m.tick?.source === 'planner' ? 'PLANNER' : m.tick?.source === 'mission' ? 'ASSIST' : m.tick?.source === 'teleop' ? 'YOU' : m.tick?.source === 'stop' ? 'STOP' : 'IDLE';
  const elapsed = m.tick?.t_world ?? 0;
  return <main className={`night-play ${phone ? 'night-phone' : ''}`} data-testid="reference-play">
    <div className="night-play-world"><canvas ref={m.canvas} className="arena-canvas night-game-canvas" aria-label="Click the floor for a goal; drive with WASD" /></div>
    <section className="night-objective night-glass"><span className="night-eyebrow">FREE ROAM</span><strong>Make your own path.</strong><span className="night-timer">{Math.floor(elapsed / 60).toString().padStart(2, '0')}:{Math.floor(elapsed % 60).toString().padStart(2, '0')}</span></section>
    <Minimap model={m} />
    <button className="night-settings night-icon-button" aria-label="Settings and key bindings" onClick={() => m.setHelpOpen(true)}><Settings size={20} /></button>
    <button className={`night-vision night-icon-button ${vision ? 'is-active' : ''}`} aria-label="Robot vision" onClick={() => { const next = !vision; setVision(next); m.r.current?.setLayers({ lidar: next }); }}><ScanEye size={20} /><span>Vision</span></button>
    <section className="night-drive-readout night-glass"><strong>{m.tick ? Math.abs(m.tick.v).toFixed(2) : '—'} <span>m/s</span></strong><span className="night-source">{source}</span><div className="night-wheel-bars">{[0, 1].map((side) => <div key={side} className="night-wheel-track"><i style={{ width: `${Math.min(100, Math.abs(wheels?.[side] ?? 0) / m.fullWheel.current * 100)}%` }} /></div>)}</div></section>
    {phone && m.coarse && <div className="night-joystick"><Joystick onChange={m.onJoystick} /></div>}
    <div className="night-actions"><button className={`night-action night-stop ${m.latched ? 'is-latched' : ''}`} onClick={m.latched ? release : stop}><Square size={22} fill="currentColor" /><span>{m.latched ? 'Release' : 'STOP'}</span></button><button className="night-action night-grasp" onClick={grasp} disabled={m.latched}><Hand size={21} /><span>Grasp</span></button><button className="night-action night-auto" onClick={autonomy} disabled={m.latched}><Route size={21} /><span>Auto</span></button><button className="night-action night-camera" onClick={() => m.chooseCamera('next')}><Camera size={21} /><span>Camera</span></button></div>
    <div className="night-play-badge"><Badge /></div>
    {m.mode === 'attract' && <p className="night-toast" role="status">Recorded MODEL demo · tap the floor to take control.</p>}
    {m.error && <p className="night-toast error" role="alert">{m.error}</p>}
    <section className="night-rotate"><div><Navigation2 size={32} /><h2>Rotate your phone</h2><p>COCO has room to move in landscape.</p><Badge /></div></section>
    {m.helpOpen && <Help bindings={m.bindings} settings={m.settings} coarse={m.coarse} onRebind={(action, code) => m.setBindings((bindings) => rebind(bindings, action, code))} onReset={() => m.setBindings(resetBindings())} onSetting={(key, value) => { m.changeSetting(key, value); applyMotion(); }} onClose={() => m.setHelpOpen(false)} />}
  </main>;
}

function CompareReference() {
  const [data, setData] = useState<ComparisonData>();
  const [result, setResult] = useState<{ A: CompareSide; B: CompareSide } | null>(null);
  const [perspective, setPerspective] = useState(false);
  const [error, setError] = useState('');
  const state = useRef<ComparisonData | undefined>(undefined); const client = useRef<ArenaClient | undefined>(undefined);
  useEffect(() => {
    const c = new ArenaClient({
      onWorld(world, occupancy) {
        const next: ComparisonData = { world, occupancy, stores: [new PlanStore(world.width, world.height), new PlanStore(world.width, world.height)] };
        state.current = next; setData(next); c.compare('astar', 'dijkstra', 2.5, 2);
      },
      onCompareBatch(meta, columns) {
        const store = state.current?.stores[meta.compare === 'B' ? 1 : 0];
        if (!store) return;
        if (store.searchId !== meta.search_id) store.begin(meta.search_id, meta.planner);
        store.append(columns, meta.final); store.advance(store.received);
      },
      onCompareDone(done) {
        setResult(done);
        (window as unknown as { __cocoReference: unknown }).__cocoReference = { seed: 1, goal: [2.5, 2], world: state.current?.world, result: done, contextLayout: 'one scissored WebGL context' };
      },
      onError(stage, message) { setError(stage + ': ' + message); },
    }, { seed: 1, hashVersion: 2 });
    client.current = c;
    return () => { c.close(); client.current = undefined; };
  }, []);
  const select = (side: 'A' | 'B', value: string) => {
    if (!data || !client.current) return;
    const a = side === 'A' ? value : data.stores[0].planner || 'astar';
    const b = side === 'B' ? value : data.stores[1].planner || 'dijkstra';
    const next = { ...data, stores: [new PlanStore(data.world.width, data.world.height), new PlanStore(data.world.width, data.world.height)] as [PlanStore, PlanStore] };
    state.current = next; setData(next); setResult(null); client.current.compare(a, b, 2.5, 2);
  };
  return <main className="night-compare" data-testid="reference-compare" data-ready={!!result}>
    <Header mode="Compare" />
    <div className="night-compare-stage"><WorldStage kind="compare" data={data} perspective={perspective} /><div className="night-pane-labels">{(['A', 'B'] as const).map((side) => <div key={side}><span className="night-eyebrow">{side}</span><strong>{side === 'A' ? result?.A.planner === 'astar' ? 'A*' : result?.A.planner ?? 'A*' : result?.B.planner ?? 'Dijkstra'}</strong><Badge /></div>)}</div><div className="night-view-switch"><button onClick={() => setPerspective(!perspective)}>{perspective ? 'Top down' : '3D view'} <Columns2 size={16} /></button></div></div>
    <aside className="night-compare-controls"><span className="night-eyebrow">GLOBAL PLANNING</span><h1>Different searches.<br />Same goal.</h1><p>Same map, start, goal and seed.</p>{(['A', 'B'] as const).map((side) => <label key={side}>Planner {side}<select value={result?.[side].planner ?? (side === 'A' ? 'astar' : 'dijkstra')} onChange={(event) => select(side, event.target.value)}>{(data?.world.planners ?? ['astar', 'dijkstra']).map((name) => <option value={name} key={name}>{name === 'astar' ? 'A*' : name === 'dijkstra' ? 'Dijkstra' : name}</option>)}</select></label>)}<div className="night-map-spec"><span>COCO arena</span><span>Goal 2.5, 2.0 m</span><span>Seed 1</span></div><h2>What you see</h2><ul className="night-computation-key"><li><i className="frontier" />Frontier</li><li><i className="closed" />Expanded</li><li><i className="path" />Planned path</li></ul><p className="night-small">MODEL · paths and counts from coco_lab.</p>{error && <p role="alert" className="error">{error}</p>}</aside>
    <section className="night-results" aria-label="Planner results">{(['A', 'B'] as const).map((side) => <div key={side}><span className="night-eyebrow">{side} · {result?.[side].planner === 'astar' ? 'A*' : result?.[side].planner ?? (side === 'A' ? 'A*' : 'Dijkstra')}</span><span><strong>{result?.[side].summary.expansions ?? '—'}</strong> expansions</span><span><strong>{result?.[side].summary.path_length != null ? (Number(result[side].summary.path_length) * result[side].resolution).toFixed(2) : '—'}</strong> m planned path</span></div>)}</section>
    <div className="night-reference-timeline"><Pause size={16} /><span>{result ? 'Search complete' : 'Computing…'}</span><span className="night-timeline-track" /></div>
  </main>;
}
export function ReferenceScreens() {
  const screen = new URLSearchParams(window.location.search).get('reference');
  return screen === 'play' ? <PlayReference /> : screen === 'compare' ? <CompareReference /> : <TitleReference />;
}
