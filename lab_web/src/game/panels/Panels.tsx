// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.4: the panels, docked on the left on a desktop (as RViz or Foxglove dock theirs) and a
 * bottom sheet on a phone that stops short of STOP's column, so STOP is never covered.
 *
 * - Displays: RViz's display tree for SIM view, with each display's options (saved in prefs);
 * - ROS 2 graph (model of COCO's stack): nodes and topics, live rates and last message times;
 *   tap a topic to echo it;
 * - Topic echo: the chosen topic's latest message, as `ros2 topic echo` prints it;
 * - Plot: v, ω, distance to the goal and the nearest LiDAR return over sim time.
 * Every panel is MODEL (the browser model's messages); each has a "?" (learn.ts).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { DISPLAYS, type DisplayId, type Displays } from '../../ros/displays';
import type { Frame, Recorder, TopicStats } from '../../ros/recorder';
import { laserScan, occupancyGrid, odometry, path, twistStamped, type RosGraph, type RosInfo } from '../../ros/shapes';
import { STACK_NODES, STACK_TOPICS } from '../../ros/stack';
import { toYaml } from '../../ros/yaml';
import { LEARN, type PanelId } from './learn';

export interface MapMeta { width: number; height: number; resolution: number; origin: [number, number] }

export interface PanelsProps {
  tab: PanelId; onTab: (t: PanelId) => void; onClose: () => void;
  displays: Displays; onDisplays: (d: Displays) => void;
  info: RosInfo | null; stats: TopicStats; recorder: Recorder; frame: Frame | null;
  map: MapMeta | null; occupancy: Uint8Array | null; goal: [number, number] | null;
  echo: string; onEcho: (topic: string) => void;
}

const TABS: [PanelId, string][] = [['displays', 'Displays'], ['graph', 'ROS 2 graph'], ['echo', 'Topic echo'], ['plot', 'Plot']];

export function Panels(p: PanelsProps) {
  const [learn, setLearn] = useState(false);
  const l = LEARN[p.tab];
  return <aside className="g2-panels g1-glass" data-testid="g2-panels" aria-label="ROS 2 panels (model of COCO's stack)">
    <header>
      <nav role="tablist">{TABS.map(([id, label]) => <button key={id} role="tab" aria-selected={p.tab === id} data-testid={`g2-tab-${id}`} onClick={() => { p.onTab(id); setLearn(false); }}>{label}</button>)}</nav>
      <button className="q" aria-expanded={learn} aria-label={`What is ${l.title}?`} data-testid="g2-learn" onClick={() => setLearn((x) => !x)}>?</button>
      <button className="x" aria-label="Close the panels" onClick={p.onClose}>✕</button>
    </header>
    <p className="g2-panel-tag"><b>MODEL</b> {p.tab === 'graph' ? "ROS 2 graph (model of COCO's stack)" : 'the browser model\'s messages, ROS 2 shapes — not ROS 2'}</p>
    {learn && <p className="g2-learn" data-testid="g2-learn-text"><b>{l.title}.</b> {l.text}</p>}
    <div className="g2-panel-body">
      {p.tab === 'displays' && <DisplaysPanel displays={p.displays} onDisplays={p.onDisplays} />}
      {p.tab === 'graph' && p.info && <GraphPanel graph={p.info.graph} stats={p.stats} onEcho={p.onEcho} />}
      {p.tab === 'echo' && <EchoPanel {...p} />}
      {p.tab === 'plot' && <PlotPanel recorder={p.recorder} frame={p.frame} goal={p.goal} info={p.info} />}
    </div>
  </aside>;
}

function DisplaysPanel({ displays, onDisplays }: { displays: Displays; onDisplays: (d: Displays) => void }) {
  const [open, setOpen] = useState<DisplayId | null>(null);
  const set = (id: DisplayId, patch: Partial<Displays[DisplayId]>) => onDisplays({ ...displays, [id]: { ...displays[id], ...patch } });
  return <ul className="g2-displays" data-testid="g2-displays">
    {DISPLAYS.map((d) => <li key={d.id}>
      <div className="row">
        <button className="tw" aria-expanded={open === d.id} aria-label={`${d.rviz} options`} onClick={() => setOpen(open === d.id ? null : d.id)}>{open === d.id ? '▾' : '▸'}</button>
        <label><input type="checkbox" checked={displays[d.id].on} data-testid={`g2-display-${d.id}`} onChange={(e) => set(d.id, { on: e.target.checked })} /> {d.rviz}</label>
        <span className="src">{d.source}</span>
      </div>
      {open === d.id && <div className="opts">
        <p>{d.what}</p>
        {d.options.includes('color') && <label>Color <input type="color" value={displays[d.id].color} onChange={(e) => set(d.id, { color: e.target.value })} /></label>}
        {d.options.includes('size') && <label>Size (m) <input type="range" min={0.01} max={d.id === 'tf' ? 1 : 0.2} step={0.01} value={displays[d.id].size} onChange={(e) => set(d.id, { size: Number(e.target.value) })} /> {displays[d.id].size?.toFixed(2)}</label>}
        {d.options.includes('alpha') && <label>Alpha <input type="range" min={0} max={1} step={0.05} value={displays[d.id].alpha} onChange={(e) => set(d.id, { alpha: Number(e.target.value) })} /> {displays[d.id].alpha?.toFixed(2)}</label>}
      </div>}
    </li>)}
  </ul>;
}

/** Where each of the model graph's nodes is drawn (left to right, as rqt_graph lays a pipeline out). */
const NODE_POS: Record<string, [number, number]> = {
  lidar: [90, 40], map_server: [90, 115], robot_state_publisher: [90, 190], teleop: [90, 265],
  slam_or_amcl: [290, 70], global_planner: [360, 160], local_controller: [500, 70], cmd_vel_arbiter: [500, 265], diff_drive: [620, 165],
};
const boxW = (n: string) => Math.max(96, n.length * 8.2 + 16);

function GraphPanel({ graph, stats, onEcho }: { graph: RosGraph; stats: TopicStats; onEcho: (t: string) => void }) {
  const now = performance.now();
  const pos = (n: string, k: number): [number, number] => NODE_POS[n] ?? [60 + 120 * (k % 5), 300 + 40 * Math.floor(k / 5)];
  const nodes = graph.nodes.map((n, k) => ({ n, at: pos(n, k) }));
  const where = Object.fromEntries(nodes.map((x) => [x.n, x.at]));
  const [sel, setSel] = useState<string | null>(null);
  return <div className="g2-graph" data-testid="g2-graph">
    <svg viewBox="0 0 700 310" role="img" aria-label="The model's ROS 2 graph: nodes (boxes) and topics (pills)">
      {graph.topics.map((t, k) => {
        const a = where[t.publisher];
        const subs = t.subscribers.map((s) => where[s]).filter(Boolean);
        if (!a || !subs.length) return null;
        const c: [number, number] = [(a[0] + subs.reduce((x, s) => x + s[0], 0) / subs.length) / 2, (a[1] + subs.reduce((x, s) => x + s[1], 0) / subs.length) / 2 + ((k % 3) - 1) * 11];
        const last = stats.last(t.name, now);
        const hot = !!last && last.agoMs < 350;
        return <g key={t.name} className={`edge ${hot ? 'hot' : ''}`}>
          <line x1={a[0]} y1={a[1]} x2={c[0]} y2={c[1]} />
          {subs.map((s, j) => <line key={j} x1={c[0]} y1={c[1]} x2={s[0]} y2={s[1]} />)}
          <g className="topic" role="button" tabIndex={0} data-testid={`g2-topic-${t.name}`} onClick={() => onEcho(t.name)} onKeyDown={(e) => { if (e.key === 'Enter') onEcho(t.name); }}>
            <rect x={c[0] - (t.name.length * 3.8 + 10)} y={c[1] - 10} width={t.name.length * 7.6 + 20} height={20} rx={10} />
            <text x={c[0]} y={c[1] + 4}>{t.name}</text>
          </g>
        </g>;
      })}
      {nodes.map(({ n, at }) => <g key={n} className={`node ${sel === n ? 'sel' : ''}`} onClick={() => setSel(sel === n ? null : n)} role="button" tabIndex={0}>
        <rect x={at[0] - boxW(n) / 2} y={at[1] - 14} width={boxW(n)} height={28} rx={4} />
        <text x={at[0]} y={at[1] + 4}>{n}</text>
      </g>)}
    </svg>
    {sel && <p className="g2-stack" data-testid="g2-stack"><b>{sel}</b> (model role) — in COCO's stack: <span className="stack">STACK reference</span> {STACK_NODES[sel]?.stack ?? 'no counterpart recorded'} <small>({STACK_NODES[sel]?.source})</small></p>}
    <table className="g2-rates" data-testid="g2-rates">
      <thead><tr><th>topic (model) · type</th><th>rate</th><th>last msg</th></tr></thead>
      <tbody>{graph.topics.map((t) => {
        const r = stats.rate(t.name, now), last = stats.last(t.name, now);
        return <tr key={t.name} onClick={() => onEcho(t.name)}>
          <td><button className="link">{t.name}</button> <small>{t.type.replace('/msg/', '/')}</small>{STACK_TOPICS[t.name] && <small>Stack: {STACK_TOPICS[t.name]}</small>}</td>
          <td>{t.when === 'latched' ? 'latched' : r === null ? '—' : `${r.toFixed(1)} Hz`}</td>
          <td>{last ? `${last.sim.toFixed(1)} s` : '—'}</td>
        </tr>;
      })}</tbody>
    </table>
  </div>;
}

function EchoPanel(p: PanelsProps) {
  const f = p.frame, info = p.info;
  const grid = useMemo(() => (p.map && p.occupancy ? occupancyGrid(p.map, p.occupancy, 0) : null), [p.map, p.occupancy]);
  const lastPlan = useRef<{ pts: [number, number][]; t: number } | null>(null);
  const lastNav = useRef<Frame | null>(null);
  const lastTeleop = useRef<Frame | null>(null);
  if (f?.plan) lastPlan.current = { pts: f.plan, t: f.t };
  if (f && (f.source === 'planner' || f.source === 'mission')) lastNav.current = f;
  if (f?.teleop) lastTeleop.current = f;
  const topics = info ? info.graph.topics.map((t) => t.name) : [];
  let msg: unknown = null;
  if (f && info) {
    switch (p.echo) {
      case '/scan': msg = laserScan(info.scan, f.ranges, f.t); break;
      case '/odom': msg = f.tf ? odometry(f.tf, f.v, f.w) : null; break;
      case '/cmd_vel': msg = twistStamped(f.v, f.w, f.t); break;
      case '/cmd_vel_nav': msg = lastNav.current ? twistStamped(lastNav.current.v, lastNav.current.w, lastNav.current.t) : null; break;
      case '/cmd_vel_teleop': msg = lastTeleop.current?.teleop ? twistStamped(lastTeleop.current.teleop[0], lastTeleop.current.teleop[1], lastTeleop.current.t) : null; break;
      case '/plan': msg = lastPlan.current ? path(lastPlan.current.pts, lastPlan.current.t) : null; break;
      case '/map': msg = grid; break;
      case '/tf': msg = f.tf; break;
      case '/tf_static': msg = info.tf_static; break;
    }
  }
  const type = info?.graph.topics.find((t) => t.name === p.echo)?.type ?? '';
  return <div className="g2-echo" data-testid="g2-echo">
    <label>Topic <select value={p.echo} onChange={(e) => p.onEcho(e.target.value)} data-testid="g2-echo-topic">{topics.map((t) => <option key={t}>{t}</option>)}</select> <small>{type}</small></label>
    <pre data-testid="g2-echo-yaml">{msg ? toYaml(msg) + '\n---' : `${p.echo}: no message yet (the model has not produced one)`}</pre>
  </div>;
}

/** The last PLOT_S seconds of sim time. */
const PLOT_S = 30;

function PlotPanel({ recorder, frame, goal, info }: { recorder: Recorder; frame: Frame | null; goal: [number, number] | null; info: RosInfo | null }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c || !frame) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const W = c.clientWidth, H = c.clientHeight;
    if (c.width !== Math.round(W * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
    const g = c.getContext('2d')!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const fs = recorder.frames.filter((x) => frame.t - x.t <= PLOT_S);
    const minRange = (x: Frame) => { let m = Infinity; const lo = info?.scan.range_min ?? 0, hi = info?.scan.range_max ?? Infinity; for (const r of x.ranges) if (r >= lo && r <= hi && r < m) m = r; return Number.isFinite(m) ? m : null; };
    const series: { name: string; unit: string; colour: string; value: (x: Frame) => number | null }[] = [
      { name: 'v (/cmd_vel)', unit: 'm/s', colour: '#ff7a1a', value: (x) => x.v },
      { name: 'ω (/cmd_vel)', unit: 'rad/s', colour: '#22d3ee', value: (x) => x.w },
      { name: 'distance to goal', unit: 'm', colour: '#a3e635', value: (x) => (goal ? Math.hypot(goal[0] - x.pose[0], goal[1] - x.pose[1]) : null) },
      { name: 'nearest return (/scan)', unit: 'm', colour: '#f472b6', value: minRange },
    ];
    const rowH = H / series.length;
    g.font = '10px ui-monospace, monospace';
    series.forEach((s, k) => {
      const y0 = k * rowH, vals = fs.map((x) => s.value(x)).filter((v): v is number => v !== null);
      let lo = Math.min(0, ...vals), hi = Math.max(0.05, ...vals);
      if (hi - lo < 1e-6) hi = lo + 1;
      g.strokeStyle = 'rgba(255,255,255,.12)'; g.strokeRect(36, y0 + 4, W - 40, rowH - 18);
      g.fillStyle = '#94a3b8';
      g.fillText(`${s.name} ${vals.length ? vals[vals.length - 1].toFixed(2) : '—'} ${s.unit}`, 40, y0 + 14);
      g.fillText(hi.toFixed(2), 2, y0 + 12); g.fillText(lo.toFixed(2), 2, y0 + rowH - 14);
      g.strokeStyle = s.colour; g.lineWidth = 1.5; g.beginPath();
      let started = false;
      for (const x of fs) {
        const v = s.value(x);
        if (v === null) { started = false; continue; }
        const px = 36 + ((x.t - (frame.t - PLOT_S)) / PLOT_S) * (W - 40), py = y0 + 4 + (1 - (v - lo) / (hi - lo)) * (rowH - 18);
        if (started) g.lineTo(px, py); else { g.moveTo(px, py); started = true; }
      }
      g.stroke();
    });
    g.fillStyle = '#64748b';
    g.fillText(`sim time ${(frame.t - PLOT_S).toFixed(0)} … ${frame.t.toFixed(1)} s`, 40, H - 2);
  }, [frame, recorder, goal, info]);
  return <canvas ref={ref} className="g2-plot" data-testid="g2-plot" aria-label="Plot: v, ω, distance to goal and nearest LiDAR return over sim time (model)" />;
}
