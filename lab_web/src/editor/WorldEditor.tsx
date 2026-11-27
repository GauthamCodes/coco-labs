// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.5: the world editor (Workbench), first version: place, move, rotate and delete COCO Lab's kit pieces
 * on a 0.5 m grid, set the start and the goals, undo and redo. The Python reader checks the level live
 * (coco_lab.level_check in a worker: the World Spec validator's own words, COCO fitting at the start, each
 * goal reachable), and the level can be played (Free drive), used in an experiment (R1's planners on it),
 * downloaded as a ROS 2 package (R5.4) and shared as a link. MODEL only: nothing here runs ROS 2.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArenaClient } from '../arena/client';
import { saveBytes, zipFiles } from '../workbench/exports';
import { encodeLevel, levelFromHash } from './level_link';
import { PIECES, History, addDoor, asLevel, addGoal, addSolid, addWall, levelId, move, newLevel, remove, removeGoal, resize, rotate, setStart, toSpec, turnStart, type Level, type Piece } from './model';

const BASE = import.meta.env.BASE_URL;
type Tool = 'select' | 'erase' | 'start' | 'goal' | (typeof PIECES)[number];
const TOOLS: [Tool, string][] = [['select', 'Select / move'], ['wall', 'Wall'], ['door', 'Door'], ['rack', 'Rack'], ['bench', 'Bench'],
  ['pallet', 'Pallet'], ['box', 'Box'], ['start', 'Start'], ['goal', 'Goal'], ['erase', 'Delete']];
interface Check { ok: boolean; errors: string[]; goals: { goal: [number, number]; reachable: boolean; path_m: number | null }[]; spec?: Record<string, unknown> }
interface Depot { robot: unknown; arena: unknown }

function pieceRect(p: Piece): [number, number, number, number] | null {        // x0, y0, x1, y1
  if (p.kind === 'wall') { const t = 0.075; return [Math.min(p.from[0], p.to[0]) - t, Math.min(p.from[1], p.to[1]) - t, Math.max(p.from[0], p.to[0]) + t, Math.max(p.from[1], p.to[1]) + t]; }
  if (p.kind === 'door') return null;
  return [p.center[0] - p.size[0] / 2, p.center[1] - p.size[1] / 2, p.center[0] + p.size[0] / 2, p.center[1] + p.size[1] / 2];
}

export function WorldEditor() {
  const hist = useRef(new History(newLevel()));
  const [level, setLevel] = useState<Level>(hist.current.now);
  const [tool, setTool] = useState<Tool>('wall');
  const [sel, setSel] = useState<string | null>(null);
  const [check, setCheck] = useState<Check | null>(null);
  const [status, setStatus] = useState('');
  const [exp, setExp] = useState<{ planner: string; goal: number; status: string; path_m: number | null }[] | null>(null);
  const depot = useRef<Depot | null>(null);
  const client = useRef<ArenaClient | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const drag = useRef<{ from: [number, number]; id?: string; moved?: [number, number] } | null>(null);
  const [ghost, setGhost] = useState<[[number, number], [number, number]] | null>(null);

  const apply = useCallback((next: Level | null, why?: string) => {
    if (hist.current.push(next)) setLevel(hist.current.now);
    else if (why) setStatus(why);
  }, []);
  const undo = () => { if (hist.current.undo()) setLevel(hist.current.now); };
  const redo = () => { if (hist.current.redo()) setLevel(hist.current.now); };

  // the Depot's robot and arena blocks; a level from the link; one worker for checks, experiments, packages
  useEffect(() => {
    void (async () => {
      const d = await (await fetch(`${BASE}generated/arena/coco_depot_v1.json`, { credentials: 'omit' })).json() as Depot;
      depot.current = { robot: d.robot, arena: d.arena };
      const fromLink = await levelFromHash(window.location.hash).catch(() => null);
      const linked = asLevel(fromLink?.editor);           // untrusted: checked field by field, else ignored
      if (linked) { hist.current = new History(linked); setLevel(hist.current.now); }
      client.current = new ArenaClient({}, { hashVersion: 3 });
      await client.current.whenReady();
      setStatus('ready');
    })().catch((e) => setStatus(`could not start: ${String(e)}`));
    return () => client.current?.close();
  }, []);

  const spec = useMemo(() => (depot.current ? toSpec(level, depot.current) : null), [level, status]);   // eslint-disable-line react-hooks/exhaustive-deps

  // the live check, a moment after each edit
  useEffect(() => {
    if (!spec || !client.current || status === '') return;
    const t = setTimeout(() => {
      void client.current!.game<Check | { error: string }>('level_check', { spec, goals: level.goals })
        .then((r) => setCheck('error' in r && typeof r.error === 'string' ? { ok: false, errors: [r.error], goals: [] } : r as Check));
    }, 300);
    return () => clearTimeout(t);
  }, [spec, level.goals, status]);

  // drawing
  const view = useRef({ scale: 40, ox: 20, oy: 20 });
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const box = c.parentElement!.getBoundingClientRect();
    const scale = Math.max(12, Math.min(60, Math.min((box.width - 40) / level.w, 520 / level.h)));
    c.width = Math.round(level.w * scale + 40); c.height = Math.round(level.h * scale + 40);
    view.current = { scale, ox: 20, oy: 20 };
    const ctx = c.getContext('2d')!;
    const X = (x: number) => 20 + x * scale, Y = (y: number) => 20 + (level.h - y) * scale;
    ctx.fillStyle = '#10141c'; ctx.fillRect(0, 0, c.width, c.height);
    ctx.fillStyle = '#1b2230'; ctx.fillRect(X(0), Y(level.h), level.w * scale, level.h * scale);
    for (let x = 0; x <= level.w + 1e-9; x += 0.5) { ctx.strokeStyle = x % 1 === 0 ? '#2c3648' : '#222a38'; ctx.beginPath(); ctx.moveTo(X(x), Y(0)); ctx.lineTo(X(x), Y(level.h)); ctx.stroke(); }
    for (let y = 0; y <= level.h + 1e-9; y += 0.5) { ctx.strokeStyle = y % 1 === 0 ? '#2c3648' : '#222a38'; ctx.beginPath(); ctx.moveTo(X(0), Y(y)); ctx.lineTo(X(level.w), Y(y)); ctx.stroke(); }
    ctx.strokeStyle = '#cbd5e1'; ctx.lineWidth = 3; ctx.strokeRect(X(0), Y(level.h), level.w * scale, level.h * scale); ctx.lineWidth = 1;
    const doors = level.pieces.filter((p): p is Extract<Piece, { kind: 'door' }> => p.kind === 'door');
    for (const p of level.pieces) {
      const r = pieceRect(p);
      if (!r) continue;
      ctx.fillStyle = p.kind === 'wall' ? '#cbd5e1' : p.kind === 'rack' ? '#d97706' : p.kind === 'pallet' ? '#a16207' : p.kind === 'bench' ? '#64748b' : '#7c3aed';
      ctx.fillRect(X(r[0]), Y(r[3]), (r[2] - r[0]) * scale, (r[3] - r[1]) * scale);
      if (p.id === sel) { ctx.strokeStyle = '#22d3ee'; ctx.lineWidth = 2; ctx.strokeRect(X(r[0]) - 2, Y(r[3]) - 2, (r[2] - r[0]) * scale + 4, (r[3] - r[1]) * scale + 4); ctx.lineWidth = 1; }
      if (p.kind === 'wall') for (const d of doors.filter((x) => x.wall === p.id)) {      // the opening
        const horiz = p.from[1] === p.to[1];
        ctx.fillStyle = '#1b2230';
        if (horiz) ctx.fillRect(X(p.from[0] + d.at - d.width / 2), Y(p.from[1]) - 4, d.width * scale, 8);
        else ctx.fillRect(X(p.from[0]) - 4, Y(p.from[1] + d.at + d.width / 2), 8, d.width * scale);
      }
    }
    if (ghost) { ctx.strokeStyle = '#22d3ee'; ctx.setLineDash([6, 4]); ctx.beginPath(); ctx.moveTo(X(ghost[0][0]), Y(ghost[0][1])); ctx.lineTo(X(ghost[1][0]), Y(ghost[1][1])); ctx.stroke(); ctx.setLineDash([]); }
    const s = level.start;                                                                      // COCO at the start
    ctx.strokeStyle = '#22c55e'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(X(s.x), Y(s.y), 0.22 * scale, 0, 2 * Math.PI); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(X(s.x), Y(s.y)); ctx.lineTo(X(s.x + 0.4 * Math.cos(s.theta)), Y(s.y + 0.4 * Math.sin(s.theta))); ctx.stroke(); ctx.lineWidth = 1;
    level.goals.forEach((g, k) => {
      const ok = check?.goals[k]?.reachable;
      ctx.fillStyle = ok === false ? '#ef4444' : '#f59e0b';
      ctx.beginPath(); ctx.arc(X(g[0]), Y(g[1]), 7, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = '#10141c'; ctx.font = 'bold 10px system-ui'; ctx.textAlign = 'center'; ctx.fillText(String(k + 1), X(g[0]), Y(g[1]) + 3.5);
    });
  }, [level, sel, ghost, check]);

  const at = (e: React.PointerEvent): [number, number] => {
    const r = canvas.current!.getBoundingClientRect(), v = view.current;
    const px = (e.clientX - r.left) * (canvas.current!.width / r.width), py = (e.clientY - r.top) * (canvas.current!.height / r.height);
    return [(px - v.ox) / v.scale, level.h - (py - v.oy) / v.scale];
  };
  const hit = (p: [number, number]) => [...level.pieces].reverse().find((q) => { const r = pieceRect(q); return r && p[0] >= r[0] && p[0] <= r[2] && p[1] >= r[1] && p[1] <= r[3]; });

  const down = (e: React.PointerEvent) => {
    const p = at(e);
    if (tool === 'wall') { drag.current = { from: p }; return; }
    if (tool === 'select') { const h = hit(p); setSel(h?.id ?? null); if (h) drag.current = { from: p, id: h.id }; return; }
    if (tool === 'erase') { const h = hit(p); if (h) { apply(remove(level, h.id)); setSel(null); } else { const k = level.goals.findIndex((g) => Math.hypot(g[0] - p[0], g[1] - p[1]) < 0.4); if (k >= 0) apply(removeGoal(level, k)); } return; }
    if (tool === 'door') { apply(addDoor(level, p), 'a door goes on a wall: click on one (not near its ends)'); return; }
    if (tool === 'start') { apply(setStart(level, p)); return; }
    if (tool === 'goal') { apply(addGoal(level, p)); return; }
    apply(addSolid(level, tool, p));
  };
  const moveP = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    if (tool === 'wall') setGhost([d.from, at(e)]);
  };
  const up = (e: React.PointerEvent) => {
    const d = drag.current; drag.current = null; setGhost(null);
    if (!d) return;
    const p = at(e);
    if (tool === 'wall') apply(addWall(level, d.from, p), 'drag to draw a wall (along x or y)');
    else if (tool === 'select' && d.id && (Math.abs(p[0] - d.from[0]) >= 0.25 || Math.abs(p[1] - d.from[1]) >= 0.25)) apply(move(level, d.id, p[0] - d.from[0], p[1] - d.from[1]));
  };
  const onKey = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { if (sel) { apply(remove(level, sel)); setSel(null); } }
    else if (e.key.toLowerCase() === 'r') { apply(sel ? rotate(level, sel) : turnStart(level)); }
  };

  // the level as the reader lowered it (boxes, elevation): what Play's world look and the experiments read
  const lowered = check?.ok && check.spec ? check.spec : null;
  const link = async (view: 'play' | 'editor') => {
    if (!spec) return '';
    const token = await encodeLevel({ spec: lowered ?? spec, goals: level.goals, editor: level });
    const q = view === 'play' ? '?view=play&game=free' : '?view=workbench&tab=editor';
    return `${window.location.origin}${BASE}${q}#level=${token}`;
  };
  const play = async () => { window.open(await link('play'), '_blank', 'noopener'); };
  const share = async () => { const u = await link('editor'); await navigator.clipboard?.writeText(u).catch(() => {}); setStatus(`share link copied: ${u.length} characters`); };
  const download = async () => {
    if (!spec || !client.current) return;
    if (!level.goals.length) { setStatus('add a goal first: it becomes the package\'s scenario'); return; }
    setStatus('building the ROS 2 package…');
    const templatesJson = await (await fetch(`${BASE}generated/levels/templates.json`, { credentials: 'omit' })).text();
    const res = await client.current.game<Record<string, string> | { error: string }>('level_package', { spec, goals: level.goals, scenario: 'editor_goals', templates_json: templatesJson });
    if ('error' in res && typeof res.error === 'string') { setStatus(`could not build the package: ${res.error}`); return; }
    const files = Object.fromEntries(Object.entries(res as Record<string, string>).map(([k, v]) => [k, Uint8Array.from(atob(v), (c) => c.charCodeAt(0))]));
    const name = Object.keys(files)[0]?.split('/')[0] ?? 'coco_level';
    saveBytes(`${name}.zip`, zipFiles(files));
    setStatus(`downloaded ${name}.zip (its README has the commands)`);
  };
  const experiment = async () => {
    if (!spec || !client.current || !level.goals.length) { setStatus('add a goal first'); return; }
    setStatus('running the experiment…'); setExp(null);
    const world = levelId(level), specJson = JSON.stringify(lowered ?? spec);
    const eSpec = JSON.stringify({ schema: 'coco.experiment.v1', world, family: 'planning', seed: 1, algorithms: [{ name: 'astar' }, { name: 'dijkstra' }],
      scenarios: { kind: 'inline', scenarios: level.goals.map((g, k) => ({ id: `goal_${k + 1}`, seed: 1, start: [level.start.x, level.start.y, level.start.theta], goal: g })) } });
    try {
      const p = await client.current.experiment<{ n_runs: number }>('plan', eSpec, world, undefined, specJson);
      const n = p.n_runs;                                                         // the plan's run count
      const recs = await client.current.experiment<{ name: string; scenario_index: number; status: string; metrics: Record<string, number | null> }[]>('run', eSpec, world, [...Array(n).keys()], specJson);
      setExp(recs.map((r) => ({ planner: r.name, goal: r.scenario_index + 1, status: r.status, path_m: r.metrics.path_length_m ?? null })));
      setStatus(`experiment: ${recs.length} runs (MODEL)`);
    } catch (e) { setStatus(`the experiment could not run: ${String(e)}`); }
  };

  return <section className="r5-editor" data-testid="r5-editor" aria-label="World editor">
    <div className="r5-ed-tools" role="toolbar" aria-label="Tools">
      {TOOLS.map(([t, label]) => <button key={t} aria-pressed={tool === t} data-testid={`r5-tool-${t}`} onClick={() => { setTool(t); setSel(null); }}>{label}</button>)}
      <button onClick={undo} disabled={!hist.current.canUndo} data-testid="r5-undo" aria-label="Undo (Ctrl+Z)">Undo</button>
      <button onClick={redo} disabled={!hist.current.canRedo} data-testid="r5-redo" aria-label="Redo (Ctrl+Y)">Redo</button>
      {sel && <button onClick={() => apply(rotate(level, sel))} data-testid="r5-rotate">Rotate (R)</button>}
    </div>
    <div className="r5-ed-main">
      <div className="r5-ed-canvas"><canvas ref={canvas} tabIndex={0} onKeyDown={onKey} onPointerDown={down} onPointerMove={moveP} onPointerUp={up}
        data-testid="r5-canvas" aria-label={`The level, ${level.w} by ${level.h} m, top view; the tool is ${tool}. Keys: R rotates, Delete deletes, Ctrl+Z undoes.`} /></div>
      <aside className="r5-ed-side">
        <label>Name <input data-testid="r5-title" value={level.title} onChange={(e) => apply({ ...level, title: e.target.value })} /></label>
        <label>Size (m) <input type="number" step={0.5} min={4} max={60} value={level.w} onChange={(e) => apply(resize(level, Number(e.target.value), level.h))} aria-label="Width (m)" />
          × <input type="number" step={0.5} min={4} max={60} value={level.h} onChange={(e) => apply(resize(level, level.w, Number(e.target.value)))} aria-label="Height (m)" /></label>
        <h4>Check <small>MODEL · the World Spec reader</small></h4>
        <div role="status" data-testid="r5-check">{!check ? 'checking…' : check.ok ? '✓ the level is valid; COCO fits at its start; every goal is reachable'
          : <ul>{check.errors.map((x, i) => <li key={i}>{x}</li>)}</ul>}</div>
        <h4>Goals</h4>
        <ol data-testid="r5-goals">{level.goals.map((g, k) => <li key={k}>({g[0]}, {g[1]}) {check?.goals[k] ? (check.goals[k].reachable ? `reachable, ${check.goals[k].path_m} m` : 'NOT reachable') : ''}
          <button aria-label={`Delete goal ${k + 1}`} onClick={() => apply(removeGoal(level, k))}>✕</button></li>)}</ol>
        <h4>Pieces</h4>
        <ul className="r5-ed-list">{level.pieces.map((p) => <li key={p.id}><button aria-pressed={sel === p.id} onClick={() => { setSel(p.id); setTool('select'); }}>{p.id}</button>
          <button aria-label={`Delete ${p.id}`} onClick={() => { apply(remove(level, p.id)); setSel(null); }}>✕</button></li>)}</ul>
        <div className="r5-ed-actions">
          <button data-testid="r5-play" onClick={() => void play()} disabled={!check?.ok}>Play this level</button>
          <button data-testid="r5-experiment" onClick={() => void experiment()} disabled={!check?.ok}>Use in an experiment</button>
          <button data-testid="r5-package" onClick={() => void download()} disabled={!check?.ok}>Download as ROS 2 package</button>
          <button data-testid="r5-share" onClick={() => void share()}>Copy share link</button>
        </div>
        {exp && <table data-testid="r5-exp"><thead><tr><th>planner</th><th>goal</th><th>status</th><th>path</th></tr></thead>
          <tbody>{exp.map((r, i) => <tr key={i}><td>{r.planner}</td><td>{r.goal}</td><td>{r.status}</td><td>{r.path_m === null ? '—' : `${r.path_m.toFixed(2)} m`}</td></tr>)}</tbody></table>}
        <p className="wb-muted" role="status" data-testid="r5-status">{status === 'ready' ? '' : status}</p>
      </aside>
    </div>
  </section>;
}
