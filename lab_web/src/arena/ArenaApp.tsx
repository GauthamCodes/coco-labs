// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * `?view=arena`: the Glass-box Arena (M1).
 *
 * Opening the page plays a build-time recording at once (attract mode,
 * attract.ts) while the worker boots Pyodide; the first goal, key, joystick
 * move or planner choice takes over with the LIVE model. A share link
 * (`?run=`) replays a run from its seed and input log and says whether it
 * reproduced the recorded hash chain. `?replay=<id>` plays one of Lab 1's
 * bundles converted to a v2 run (replay.ts; a recorded full-stack run is
 * labelled STACK) and starts no model at all. The renderer (Three.js) draws
 * whatever the active ArenaSession shows; React draws only panels.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { AttractPlayer, parseRecording, type Recording } from './attract';
import { ArenaClient, type PyodideSource } from './client';
import { Compare, type CompareState } from './Compare';
import { Joystick } from './Joystick';
import { PerfOverlay } from './PerfOverlay';
import { perf } from './perf';
import { wallMs, type InputRow, type PlanInfo, type Tick, type World } from './protocol';
import { currentTheme } from './render/palette';
import { PlanStore, type CellInfo } from './render/planStore';
import { parseConverted, type ConvertedRun } from './replay';
import { ArenaRenderer, DEFAULT_LAYERS, type LayerVisibility } from './render/Renderer';
import { ArenaSession } from './session';
import { decodeRun, shareUrl, type SharedRun } from './share';
import { Timeline } from './Timeline';
import { sha256Hex } from '../bundle/sha256';

declare global {
  interface Window {
    /** Harness hooks (tools/perf). */
    __cocoArena?: {
      client: ArenaClient | null; queue: Omit<InputRow, 'tick'>[]; last: Tick | null;
      renderer: ArenaRenderer | null; session: () => ArenaSession | null; goal: (x: number, y: number) => void;
      mode: () => string; log: () => InputRow[];
    };
  }
}

type Mode = 'attract' | 'live' | 'replay' | 'recording';
interface RunEntry { id: string; title: string; group: string; evidence: string }
const KEYS: Record<string, [number, number]> = {
  w: [1, 0], ArrowUp: [1, 0], s: [-1, 0], ArrowDown: [-1, 0], a: [0, 1], ArrowLeft: [0, 1], d: [0, -1], ArrowRight: [0, -1],
};

export function ArenaApp() {
  const params = new URLSearchParams(window.location.search);
  const showPerf = params.has('perf');
  const source: PyodideSource = params.get('pyodide') === 'cdn' ? 'cdn' : 'self';
  const runParam = params.get('run');
  const replayParam = params.get('replay');
  const recId = replayParam && /^[a-z0-9_]{1,64}$/.test(replayParam) ? replayParam : null;
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [world, setWorld] = useState<World | null>(null);
  const [liveReady, setLiveReady] = useState(false);
  const [mode, setModeState] = useState<Mode>(runParam ? 'replay' : recId ? 'recording' : 'attract');
  const [session, setSession] = useState<ArenaSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inspect, setInspect] = useState(false);
  const [picked, setPicked] = useState<CellInfo | null>(null);
  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);
  const [planner, setPlanner] = useState('astar');
  const [cmpPick, setCmpPick] = useState(false);
  const [cmpA, setCmpA] = useState('astar');
  const [cmpB, setCmpB] = useState('dijkstra');
  const [compare, setCompare] = useState<CompareState | null>(null);
  const [runCard, setRunCard] = useState<PlanInfo | null>(null);
  const [share, setShare] = useState<string | null>(null);
  const [replay, setReplay] = useState<{ run: SharedRun | null; status: string }>({ run: null, status: '' });
  const [converted, setConverted] = useState<ConvertedRun | null>(null);
  const [runs, setRuns] = useState<RunEntry[]>([]);
  const [, setFrame] = useState(0);

  const r = useRef<ArenaRenderer | null>(null);
  const client = useRef<ArenaClient | null>(null);
  const modeRef = useRef<Mode>(mode);
  const live = useRef<ArenaSession | null>(null);
  const attract = useRef<{ rec: Recording; session: ArenaSession; player: AttractPlayer } | null>(null);
  const queue = useRef<Omit<InputRow, 'tick'>[]>([]);
  const log = useRef<InputRow[]>([]);
  const occupancy = useRef<Uint8Array | null>(null);
  const outline = useRef<[number, number][]>([[0.12, 0], [-0.12, 0.137], [-0.12, -0.137]]);
  const lastTick = useRef<Tick | null>(null);
  const specSha = useRef<string>('');
  const pendingTakeover = useRef(false);
  const inspectRef = useRef(false);
  const cmpPickRef = useRef(false);
  const cmpRef = useRef<[string, string]>(['astar', 'dijkstra']);
  inspectRef.current = inspect;
  cmpPickRef.current = cmpPick;
  cmpRef.current = [cmpA, cmpB]; // read at click time, not from the first render

  const setMode = useCallback((m: Mode) => { modeRef.current = m; setModeState(m); }, []);
  const recorded = () => modeRef.current === 'attract' || modeRef.current === 'recording';
  const active = () => (recorded() ? attract.current?.session ?? null : live.current);

  /** The visitor acted: switch to the live model (now, or as soon as it is ready). */
  const takeOver = useCallback(() => {
    if (modeRef.current !== 'attract') return true;
    if (!live.current) { pendingTakeover.current = true; return false; }
    setMode('live');
    setSession(live.current);
    return true;
  }, [setMode]);

  const goal = useCallback((x: number, y: number) => {
    takeOver();
    perf.goalSent(wallMs(), live.current?.shownSearch?.searchId ?? null);
    r.current?.setGoal([x, y]);
    setRunCard(null);
    if (live.current && !live.current.live) live.current.goLive();
    queue.current.push({ kind: 'goal', x, y });
  }, [takeOver]);

  useEffect(() => {
    const cv = canvas.current!;
    let rr: ArenaRenderer | null = null;
    try {
      rr = new ArenaRenderer(cv, currentTheme());
    } catch (e) {
      setError(`renderer: ${(e as Error).message}`);
    }
    r.current = rr;
    let worldSet = false;
    let inFlight = false;
    let owed = 0;
    let lastFrame = performance.now();
    let shown: ArenaSession | null = null;
    let shownStore: PlanStore | null = null;
    let shownTick = -1;
    let firstFrame = true;
    let firstComputation = true;
    const replayRun = runParam ? (() => { try { return decodeRun(runParam); } catch (e) { setError(`share link: ${(e as Error).message}`); return null; } })() : null;
    setReplay({ run: replayRun, status: replayRun ? 'waiting for the live model' : '' });

    const setWorldOnce = (w: World, occ: Uint8Array) => {
      if (worldSet || !rr) return;
      worldSet = true;
      occupancy.current = occ;
      rr.setWorld(w, occ, outline.current);
      setWorld(w);
    };

    const stepLive = () => {
      const c = client.current;
      if (!c?.world || inFlight) return;
      if (modeRef.current === 'replay' && replayRun) {
        if (c.tick >= replayRun.ticks) return;
        queue.current.push(...replayRun.inputs.filter((x) => x.tick === c.tick));
      }
      inFlight = true;
      log.current.push(...c.step(queue.current.splice(0)));
    };

    const outlineP = fetch(`${import.meta.env.BASE_URL}generated/arena/robot_outline.json`, { credentials: 'omit' })
      .then((x) => x.json()).then((j) => { outline.current = j.polygon; }).catch(() => {});
    const specP = fetch(`${import.meta.env.BASE_URL}generated/arena/coco_arena_v1.json`, { credentials: 'omit' })
      .then((x) => x.arrayBuffer()).then((b) => sha256Hex(new Uint8Array(b))).then((h) => { specSha.current = h; });

    void fetch(`${import.meta.env.BASE_URL}generated/v2/index.json`, { credentials: 'omit' })
      .then((x) => (x.ok ? x.json() : { runs: [] })).then((j) => setRuns(j.runs ?? [])).catch(() => {});
    if (replayParam && !recId) setError(`no recorded run "${replayParam}"`);
    // a converted Lab 1 run: played, never simulated
    if (recId) {
      void fetch(`${import.meta.env.BASE_URL}generated/v2/${recId}.mcap`, { credentials: 'omit' })
        .then((x) => { if (!x.ok) throw new Error(`no recorded run "${recId}"`); return x.arrayBuffer(); })
        .then((b) => parseConverted(new Uint8Array(b)))
        .then(async (rec) => {
          await outlineP;
          const s = new ArenaSession(rec.world.width, rec.world.height, rec.world.dt);
          attract.current = { rec, session: s, player: new AttractPlayer(rec, s) };
          setWorldOnce(rec.world, rec.occupancy);
          setSession(s);
          setConverted(rec);
          setLayers((l) => ({ ...l, lidar: false, footprint: false, ...(rec.evidence === 'MODEL' ? { robot: false, truth: false } : {}) }));
        })
        .catch((e) => setError(`recorded run: ${(e as Error).message}`));
    }
    // attract: the recording, at once (not in a replay)
    if (!runParam && !recId) {
      void fetch(`${import.meta.env.BASE_URL}generated/arena/attract.mcap`, { credentials: 'omit' })
        .then((x) => x.arrayBuffer()).then((b) => parseRecording(new Uint8Array(b)))
        .then(async (rec) => {
          await outlineP;
          perf.mark('attract_ready', wallMs());
          const s = new ArenaSession(rec.world.width, rec.world.height, rec.world.dt);
          attract.current = { rec, session: s, player: new AttractPlayer(rec, s) };
          if (modeRef.current === 'attract') { setWorldOnce(rec.world, rec.occupancy); setSession(s); }
        })
        .catch((e) => setError(`attract: ${(e as Error).message}`));
    }

    if (rr) {
      rr.onFrame = () => {
        const now = performance.now();
        const dt = now - lastFrame;
        lastFrame = now;
        const a = attract.current;
        if (recorded() && a) {
          let due = a.session.frame(dt);
          while (due-- > 0) {
            if (a.player.done && modeRef.current === 'recording') break; // a recording ends; attract loops
            if (a.player.done) {
              a.session = new ArenaSession(a.rec.world.width, a.rec.world.height, a.rec.world.dt);
              a.player = new AttractPlayer(a.rec, a.session);
              setSession(a.session);
            }
            a.player.step();
          }
        } else if (live.current) {
          owed = Math.min(4, owed + live.current.frame(dt));
          if (queue.current.length) owed = Math.max(owed, 1); // an input is applied at once
          if (owed > 0 && !inFlight) { owed -= 1; stepLive(); }
        }
        const s = active();
        if (!s) return;
        if (s !== shown) { shown = s; shownTick = -1; }
        const st = s.shownSearch;
        if (st !== shownStore) { shownStore = st; rr!.setPlan(st); }
        const t = s.shownTick;
        if (t && t.tick !== shownTick) {
          shownTick = t.tick;
          rr!.setPose(t.pose, t.truth ?? t.pose);
          if (t.ranges) rr!.setScan(t.pose, t.ranges);
        }
      };
      rr.onAfterRender = () => {
        if (firstFrame && worldSet) { firstFrame = false; perf.mark('first_frame', wallMs()); }
        const st = active()?.shownSearch;
        if (st && st.cursor > 0) {
          if (firstComputation) { firstComputation = false; perf.mark('first_computation_shown', wallMs()); }
          // goal timing is the LIVE model's: a recording's search ids are its own
          if (active() === live.current) perf.frontierDrawn(st.searchId);
        }
      };
      rr.start();
    }

    if (!recId) client.current = new ArenaClient({
      onWorld: (w, occ) => {
        const s = new ArenaSession(w.width, w.height, w.dt);
        live.current = s;
        void outlineP.then(() => setWorldOnce(w, occ));
        setLiveReady(true);
        if (modeRef.current !== 'attract') setSession(s);
        else if (pendingTakeover.current) { setMode('live'); setSession(s); }
        if (replayRun) {
          void specP.then(() => {
            if (specSha.current !== replayRun.spec) {
              setError('This link was made with a different World Spec; it cannot be reproduced here.');
              s.playing = false;
            } else setReplay({ run: replayRun, status: `replaying ${replayRun.inputs.length} inputs over ${replayRun.ticks} ticks` });
          });
        }
      },
      onPlanBatch: (meta, cols) => live.current?.onPlanBatch(meta, cols),
      onCompareBatch: (meta, cols) => {
        setCompare((c) => {
          if (!c) return c;
          const st = c.stores[meta.compare!];
          if (st.searchId !== meta.search_id) st.begin(meta.search_id, meta.planner);
          st.append(cols, meta.final);
          if (st.cursor === 0) st.advance(1);
          return c;
        });
      },
      onCompareDone: (result) => setCompare((c) => (c ? { ...c, result } : c)),
      onTick: (t, ranges) => {
        inFlight = false;
        lastTick.current = t;
        live.current?.onTick(t, ranges);
        if (window.__cocoArena) window.__cocoArena.last = t;
        if (t.arrived && modeRef.current === 'live') {
          const p = [...(live.current?.history ?? [])].reverse().find((h) => h.plans.length)?.plans.at(-1) ?? null;
          setRunCard(p);
          setLayers((l) => ({ ...l, heatmap: true }));
        }
        if (modeRef.current === 'replay' && replayRun && t.tick >= replayRun.ticks) {
          live.current!.playing = false;
          setReplay({ run: replayRun, status: t.chain === replayRun.chain
            ? `reproduced exactly: the hash chain after tick ${t.tick} matches the link`
            : `DIFFERS: the hash chain after tick ${t.tick} is not the link's` });
        }
      },
      onError: (stage, message) => { inFlight = false; setError(`${stage}: ${message}`); },
    }, { pyodide: source, seed: replayRun?.seed ?? Number(params.get('seed') ?? 1) });

    window.__cocoArena = {
      client: client.current, queue: queue.current, last: null, renderer: rr, session: active, goal,
      mode: () => modeRef.current, log: () => log.current,
    };
    void client.current?.whenReady().then(() => { if (params.has('stress')) rr?.addStress(50_000, 20_000); }, () => {});
    const ui = setInterval(() => setFrame((n) => n + 1), 200);

    // a click (not a drag): a goal, a compare goal, or an inspected cell
    let down: [number, number] | null = null;
    const onDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6 || !rr || !worldSet) return;
      down = null;
      const [x, y] = rr.toWorld(e.clientX, e.clientY);
      const cell = rr.cellAt(x, y);
      if (inspectRef.current) {
        rr.showPick(cell);
        const st = active()?.shownSearch ?? null;
        setPicked(cell && st ? st.info(cell[0], cell[1]) : null);
      } else if (cell && cmpPickRef.current) {
        setCmpPick(false);
        if (!takeOver() || !client.current?.world || !live.current) { setError('compare needs the live model: try again in a moment'); return; }
        const w = client.current.world;
        const start = live.current.shownTick?.pose ?? w.start;
        const mk = () => new PlanStore(w.width, w.height);
        setCompare({ goal: [x, y], start, stores: { A: mk(), B: mk() }, result: null });
        client.current.compare(cmpRef.current[0], cmpRef.current[1], x, y);
      } else if (cell && !['replay', 'recording'].includes(modeRef.current)) {
        goal(x, y);
      }
    };
    cv.addEventListener('pointerdown', onDown);
    cv.addEventListener('pointerup', onUp);

    // keyboard teleop: WASD / arrows, space = STOP
    const held = new Set<string>();
    const sendTeleop = () => {
      const lim = client.current?.world?.limits;
      if (!lim) return;
      let f = 0; let turn = 0;
      for (const k of held) { f += KEYS[k][0]; turn += KEYS[k][1]; }
      takeOver();
      queue.current.push({ kind: 'teleop', linear: Math.sign(f) * lim.teleop_linear * 0.6, angular: Math.sign(turn) * lim.teleop_angular * 0.6 });
    };
    const keydown = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.matches?.('input, select, textarea') || ['replay', 'recording'].includes(modeRef.current)) return;
      if (e.code === 'Space') { e.preventDefault(); held.clear(); takeOver(); queue.current.push({ kind: 'stop' }); return; }
      if (!(e.key in KEYS) || e.repeat) return;
      e.preventDefault();
      held.add(e.key);
      sendTeleop();
    };
    const keyup = (e: KeyboardEvent) => { if (held.delete(e.key)) sendTeleop(); };
    window.addEventListener('keydown', keydown);
    window.addEventListener('keyup', keyup);
    return () => {
      clearInterval(ui);
      cv.removeEventListener('pointerdown', onDown);
      cv.removeEventListener('pointerup', onUp);
      window.removeEventListener('keydown', keydown);
      window.removeEventListener('keyup', keyup);
      client.current?.close();
      rr?.dispose();
    };
    // the client and renderer live as long as the view
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { r.current?.setLayers(layers); }, [layers]);

  const toggle = (k: keyof LayerVisibility) => setLayers((l) => ({ ...l, [k]: !l[k] }));
  const choosePlanner = (p: string) => { setPlanner(p); takeOver(); queue.current.push({ kind: 'planner', choice: p }); };
  const lastJoy = useRef<[number, number]>([0, 0]);
  const onJoystick = (dx: number, dy: number) => {
    const lim = client.current?.world?.limits;
    if (!lim || ['replay', 'recording'].includes(modeRef.current)) return;
    const lin = Math.round(dy * 10) / 10;
    const ang = Math.round(-dx * 10) / 10;
    if (lin === lastJoy.current[0] && ang === lastJoy.current[1]) return;
    lastJoy.current = [lin, ang];
    takeOver();
    queue.current.push({ kind: 'teleop', linear: lin * lim.teleop_linear, angular: ang * lim.teleop_angular });
  };
  const makeShare = () => {
    const t = lastTick.current;
    if (!t || !specSha.current) return;
    setShare(shareUrl({ v: 1, spec: specSha.current, seed: Number(params.get('seed') ?? 1), ticks: t.tick, chain: t.chain,
      inputs: log.current }, import.meta.env.BASE_URL));
  };

  const tick = session?.shownTick ?? null;
  const plan = tick ? [...(session?.history ?? [])].reverse().find((h) => h.tick <= tick.tick && h.plans.length)?.plans.at(-1) ?? null : null;
  const res = world?.resolution ?? 0.05;
  const evidence = converted?.evidence ?? 'MODEL';
  const note = converted && tick ? converted.notes.filter((n) => n.tick <= tick.tick).at(-1)?.text ?? null : null;
  const stats = converted?.results as Record<string, any> | null | undefined; // eslint-disable-line @typescript-eslint/no-explicit-any
  const m2 = (v: unknown) => (typeof v === 'number' ? `${v.toFixed(3)} m` : '—');
  const showLive = mode !== 'recording';

  return (
    <main className="arena" data-testid="arena">
      <header className="arena-head">
        <h1>COCO Arena</h1>
        <span className={`evidence-badge ${evidence.toLowerCase()}`} data-testid="evidence-badge"
          title={evidence === 'STACK' ? 'Recorded from the full ROS 2 stack in Gazebo (simulation), not a robot'
            : 'A model in your browser: coco_lab, not the robot'}>{evidence}</span>
        <a href={`${import.meta.env.BASE_URL}?view=plan`} data-testid="v1-labs-link">v1 labs</a>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      <p className={`arena-banner ${mode}`} data-testid="arena-mode" data-mode={mode}>
        {mode === 'attract' && (liveReady
          ? 'A recorded demo (MODEL, made when this site was built). Click or tap the map to give COCO a goal — the live model takes over.'
          : 'A recorded demo (MODEL, made when this site was built) while the live model loads… Click or tap the map to take over.')}
        {mode === 'live' && 'Live model: coco_lab running in your browser. Click a goal, drive with W A S D / arrows (space = STOP) or the joystick.'}
        {mode === 'replay' && `Shared run: ${replay.status}`}
        {mode === 'recording' && converted && (converted.evidence === 'STACK'
          ? `Recorded run (STACK): COCO driven by the full ROS 2 stack in Gazebo — ${converted.title}. The solid robot is where the stack believed it was (AMCL); the outline is ground truth.`
          : `Glass-box trace (MODEL): ${converted.title}, computed by coco_lab. No world, no robot: the search alone.`)}
      </p>
      <div className="arena-stage">
        <canvas ref={canvas} className="arena-canvas" data-testid="arena-canvas"
          aria-label="The arena: click or tap to give COCO a goal" />
        {!world && <p className="arena-loading" data-testid="arena-status">Loading…</p>}
      </div>
      {compare && world && occupancy.current && (
        <Compare state={compare} world={world} occupancy={occupancy.current} outline={outline.current} onClose={() => setCompare(null)} />
      )}
      {runCard && (
        <section className="run-card" data-testid="run-card" aria-label="Run finished">
          <b>Goal reached.</b> The heatmap shows the order {runCard.planner} expanded cells: dark first, bright last.
          <span data-testid="run-totals"> {Number(runCard.summary.expansions).toLocaleString()} expansions
            {runCard.summary.path_cost != null ? ` · path cost ${Number(runCard.summary.path_cost).toFixed(2)} · path length ${(Number(runCard.summary.path_length) * res).toFixed(2)} m` : ''}</span>
          <button type="button" className="seg-btn" onClick={() => setRunCard(null)}>OK</button>
        </section>
      )}
      {converted?.evidence === 'STACK' && stats && (
        <section className="run-card" data-testid="stack-results" aria-label="Measured in this recorded run">
          <b>Measured in this run</b> (Phase 1C, docs/RESULTS.md):
          <span> {stats.result?.phase ?? '—'} after {typeof stats.duration_sim_s === 'number' ? stats.duration_sim_s.toFixed(1) : '—'} s sim time ·
            tracking error mean {m2(stats.tracking_error_m?.mean)}, p95 {m2(stats.tracking_error_m?.p95)} ·
            endpoint error {m2(stats.endpoint_error_m)} · belief gap mean {m2(stats.belief_gap_m?.mean)}</span>
        </section>
      )}
      <section className="arena-panels">
        <Timeline session={session} />
        {note && <p className="stack-note" data-testid="stack-note">{note}</p>}
        {showLive && <>
        <div className="arena-row" role="group" aria-label="Planner">
          {(world?.planners ?? []).map((p) => (
            <button key={p} type="button" className={p === planner ? 'seg-btn active' : 'seg-btn'}
              aria-pressed={p === planner} data-testid={`planner-${p}`} onClick={() => choosePlanner(p)}>{p}</button>
          ))}
          <button type="button" className={inspect ? 'seg-btn active' : 'seg-btn'} aria-pressed={inspect}
            data-testid="inspect-toggle" onClick={() => setInspect((v) => !v)}>Inspect a cell</button>
        </div>
        <div className="arena-row" role="group" aria-label="Compare two planners">
          <span>Compare</span>
          <select value={cmpA} onChange={(e) => setCmpA(e.target.value)} data-testid="compare-a" aria-label="Planner A">
            {(world?.planners ?? []).map((p) => <option key={p}>{p}</option>)}</select>
          <span>with</span>
          <select value={cmpB} onChange={(e) => setCmpB(e.target.value)} data-testid="compare-b" aria-label="Planner B">
            {(world?.planners ?? []).map((p) => <option key={p}>{p}</option>)}</select>
          <button type="button" className={cmpPick ? 'seg-btn active' : 'seg-btn'} data-testid="compare-pick"
            onClick={() => setCmpPick((v) => !v)}>{cmpPick ? 'Click the map for the goal…' : 'Pick a goal to compare'}</button>
        </div>
        </>}
        {!showLive && (
          <div className="arena-row">
            <button type="button" className={inspect ? 'seg-btn active' : 'seg-btn'} aria-pressed={inspect}
              data-testid="inspect-toggle" onClick={() => setInspect((v) => !v)}>Inspect a cell</button>
            <a href={`${import.meta.env.BASE_URL}?view=arena`}>Back to the live arena</a>
          </div>
        )}
        <div className="arena-row">
          {showLive && <Joystick onChange={onJoystick} />}
          <div className="layers-and-share">
            <div className="arena-row" role="group" aria-label="Layers">
              {(Object.keys(layers) as (keyof LayerVisibility)[]).map((k) => (
                <label key={k} className="layer-toggle"><input type="checkbox" checked={layers[k]} onChange={() => toggle(k)}
                  data-testid={`layer-${k}`} />{k}</label>
              ))}
            </div>
            {mode === 'live' && (
              <div className="arena-row">
                <button type="button" className="seg-btn" data-testid="share-make" onClick={makeShare}>Share this run</button>
                {share && <input className="share-url" readOnly value={share} data-testid="share-url" onFocus={(e) => e.target.select()} />}
              </div>
            )}
          </div>
        </div>
        {runs.length > 0 && (
          <nav className="arena-row recorded-runs" aria-label="Lab 1 runs in this viewer" data-testid="recorded-runs">
            <span>Lab 1 runs in this viewer:</span>
            {runs.map((x) => (
              <a key={x.id} href={`${import.meta.env.BASE_URL}?view=arena&replay=${x.id}`} data-testid={`replay-${x.id}`}
                aria-current={x.id === recId ? 'page' : undefined}>{x.evidence === 'STACK' ? `${x.title} · STACK` : x.title}</a>
            ))}
          </nav>
        )}
        <p data-testid="arena-tick">
          {world ? `tick ${tick?.tick ?? 0} · t = ${(tick?.t_world ?? 0).toFixed(1)} s · ${tick?.mode ?? 'idle'}` : ''}
          {plan ? ` · ${plan.planner}: ${plan.status}, ${plan.summary.expansions} expansions` +
            (plan.summary.path_cost != null ? `, path cost ${Number(plan.summary.path_cost).toFixed(2)}` : '') : ''}
        </p>
        {picked && (
          <dl className="inspector" data-testid="inspector">
            <dt>cell</dt><dd>({picked.row}, {picked.col}) · {picked.state}</dd>
            <dt>expansion order</dt><dd data-testid="inspector-order">{picked.expansion ?? '—'}</dd>
            <dt>g</dt><dd data-testid="inspector-g">{picked.g?.toFixed(3) ?? '—'}</dd>
            <dt>h</dt><dd>{picked.h?.toFixed(3) ?? '—'}</dd>
            <dt>f</dt><dd>{picked.f?.toFixed(3) ?? '—'}</dd>
            <dt>parent</dt><dd>{picked.parent ? `(${picked.parent[0]}, ${picked.parent[1]})` : '—'}</dd>
            <dt>latest event</dt><dd>{picked.event != null ? `#${picked.event} ${picked.kind}` : '—'}</dd>
          </dl>
        )}
      </section>
      {showPerf && <PerfOverlay />}
    </main>
  );
}
