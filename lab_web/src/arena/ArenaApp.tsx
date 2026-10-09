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

import { ATTRACT_POLICIES, AttractPlayer, DEFAULT_ATTRACT_POLICY, parseRecording, type AttractPolicy, type Recording } from './attract';
import { ArenaClient, type PyodideSource } from './client';
import { Compare, type CompareState } from './Compare';
import { Joystick } from './Joystick';
import { PerfOverlay } from './PerfOverlay';
import { perf } from './perf';
import { wallMs, type InputRow, type PlanInfo, type Tick, type World } from './protocol';
import { currentTheme, PALETTES } from './render/palette';
import { PlanStore, type CellInfo } from './render/planStore';
import { parseConverted, type ConvertedRun } from './replay';
import { ArenaRenderer, DEFAULT_LAYERS, type LayerVisibility } from './render/Renderer';
import { ArenaSession } from './session';
import { decodeRun, shareUrl, type SharedRun } from './share';
import { Timeline } from './Timeline';
import { caption } from './lens/captions';
import { drawLenses, HOVERS } from './lens/draw';
import { EventLog, LensBar, LensCharts, LensInspector } from './lens/panels';
import { DecideControls, LocaliseControls, MapControls, MoveControls } from './lens/controls';
import { MissionPanel } from './lens/mission';
import './lens/decide';
import './lens/localise';
import './lens/map';
import './lens/move';
import { defaultLayers, LENS_BY_ID, LENSES, LEVELS, packForConfig, type LensId, type Level } from './lens/registry';
import { LensLayers } from './render/lensLayers';
import { sha256Hex } from '../bundle/sha256';
import { GapChips, useGaps } from '../learn/gaps';
import { cfgFromParams, missionBackLink } from '../learn/links';

declare global {
  interface Window {
    /** Harness hooks (tools/perf). */
    __cocoArena?: {
      client: ArenaClient | null; queue: Omit<InputRow, 'tick'>[]; last: Tick | null;
      renderer: ArenaRenderer | null; session: () => ArenaSession | null; goal: (x: number, y: number) => void;
      mode: () => string; log: () => InputRow[]; layerIds: () => string[];
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
  const attractPolicy: AttractPolicy = ATTRACT_POLICIES.includes(params.get('attract') as AttractPolicy)
    ? params.get('attract') as AttractPolicy : DEFAULT_ATTRACT_POLICY;
  const recId = replayParam && /^[a-z0-9_]{1,64}$/.test(replayParam) ? replayParam : null;
  // a Learn mission's beat (M2.8): its settings, sent once the live model is up, in place of the lens's defaults
  const cfgLines = cfgFromParams(params);
  const missionBack = missionBackLink(params);
  const gaps = useGaps(import.meta.env.BASE_URL);
  const cfgInitial = Object.fromEntries(cfgLines.map((c) => [c.slice(0, c.indexOf('=')), c.slice(c.indexOf('=') + 1)]));
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [world, setWorld] = useState<World | null>(null);
  const [liveReady, setLiveReady] = useState(false);
  const [mode, setModeState] = useState<Mode>(runParam ? 'replay' : recId ? 'recording' : 'attract');
  const [session, setSession] = useState<ArenaSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inspect, setInspect] = useState(false);
  const [picked, setPicked] = useState<CellInfo | null>(null);
  const [layers, setLayers] = useState<LayerVisibility>(DEFAULT_LAYERS);
  // M2.2 lenses: which one, how much detail, Focus, and the lens layers' toggles
  const [lens, setLens] = useState<LensId>(LENSES.some((l) => l.id === params.get('lens')) ? params.get('lens') as LensId : 'plan');
  // a recorded run opens at Explain: its search (closed set included) is what it is there to show
  const [level, setLevel] = useState<Level>(LEVELS.includes(params.get('level') as Level) ? params.get('level') as Level
    : replayParam ? 'explain' : 'watch');
  const [focus, setFocus] = useState(params.has('focus'));
  const [lensOn, setLensOn] = useState<Record<string, boolean>>({});
  const [packs, setPacks] = useState<Set<string>>(new Set(['core']));
  const [hover, setHover] = useState<{ text: string; x: number; y: number } | null>(null);
  const levelRef = useRef<Level>(level);
  levelRef.current = level;
  const lensRef = useRef<LensId>(lens);
  lensRef.current = lens;
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
  const ll = useRef<LensLayers | null>(null);
  const lensOnRef = useRef<Record<string, boolean>>({});
  lensOnRef.current = lensOn;
  const client = useRef<ArenaClient | null>(null);
  const modeRef = useRef<Mode>(mode);
  const live = useRef<ArenaSession | null>(null);
  const attract = useRef<{ rec: Recording; session: ArenaSession; player: AttractPlayer } | null>(null);
  const queue = useRef<Omit<InputRow, 'tick'>[]>([]);
  const log = useRef<InputRow[]>([]);
  const occupancy = useRef<Uint8Array | null>(null);
  const outline = useRef<[number, number][]>([[0.12, 0], [-0.12, 0.137], [-0.12, -0.137]]);
  const lastTick = useRef<Tick | null>(null);
  const worldRef = useRef<World | null>(null);
  worldRef.current = world;
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

  /** A whole-loop setting: a config input, so it is in the run's log (M2.3). */
  // a config for a pack not loaded yet waits for it: the model refuses a subsystem it has not got (M2.6)
  const readyPacks = useRef<Set<string>>(new Set(['core']));
  const waitingConfigs = useRef<string[]>([]);
  const sendConfig = useCallback((choice: string) => {
    takeOver();
    const pack = packForConfig(choice);
    if (!readyPacks.current.has(pack)) {
      waitingConfigs.current.push(choice);
      client.current?.loadPack(pack);
      return;
    }
    queue.current.push({ kind: 'config', choice });
  }, [takeOver]);
  const locOn = useRef(cfgLines.length > 0);
  const mapOn = useRef(cfgLines.length > 0);
  const moveOn = useRef(cfgLines.length > 0);
  const cfgSent = useRef(false);

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
      ll.current = new LensLayers(rr.scene, PALETTES[currentTheme()]);
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
    let drawnVersion = -1;
    let drawnTick = -1;
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
        const need = [...new Set(replayRun.inputs.filter((x) => x.kind === 'config').map((x) => packForConfig(x.choice ?? '')))];
        const missing = need.filter((p) => !c.packs.has(p));
        if (missing.length) { missing.forEach((p) => c.loadPack(p)); return; }
        queue.current.push(...replayRun.inputs.filter((x) => x.tick === c.tick));
      }
      inFlight = true;
      c.step(queue.current.splice(0)); // the log is what the model reports it applied (onTick)
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
          // a converted Lab 5 drive (M2.7) is shown through the Move lens: Nav2's own candidates
          if (rec.headers?.some((h) => h.channel === 'coco.control.local.header.v1')) setLens('move');
        })
        .catch((e) => setError(`recorded run: ${(e as Error).message}`));
    }
    // attract: the recording (not in a replay), started as the policy says (M2.0, measured)
    if (!runParam && !recId) {
      const startAttract = attractPolicy === 'after_live' ? perf.when('arena_ready')
        : attractPolicy === 'after_pyodide' ? perf.when('pyodide_ready') : Promise.resolve(0);
      void startAttract
        .then(() => fetch(`${import.meta.env.BASE_URL}generated/arena/attract.mcap`,
          { credentials: 'omit', priority: attractPolicy === 'low' ? 'low' : 'auto' }))
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
          // M2.0: an input made while a step is planning joins that step (its search is cancelled), not the next one
          else if (inFlight && queue.current.length && modeRef.current !== 'replay') client.current?.amend(queue.current.splice(0));
        }
        const s = active();
        if (!s) return;
        if (s !== shown) { shown = s; shownTick = -1; }
        const st = s.shownSearch;
        if (st !== shownStore) { shownStore = st; rr!.setPlan(st); }
        const t = s.shownTick;
        if (ll.current && worldRef.current && (s.families.version !== drawnVersion || (t?.tick ?? 0) !== drawnTick)) {
          drawnVersion = s.families.version; drawnTick = t?.tick ?? 0;
          drawLenses({ layers: ll.current, session: s, tick: drawnTick, world: worldRef.current,
            on: (id) => lensOnRef.current[id] ?? false });
        }
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
      onFamily: (m) => live.current?.onFamily(m),
      onPackReady: (pack) => {
        readyPacks.current.add(pack);
        const go = waitingConfigs.current.filter((c) => readyPacks.current.has(packForConfig(c)));
        waitingConfigs.current = waitingConfigs.current.filter((c) => !readyPacks.current.has(packForConfig(c)));
        for (const choice of go) queue.current.push({ kind: 'config', choice });
        setPacks((p) => new Set([...p, pack]));
      },
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
        if (t.inputs) log.current.push(...t.inputs);
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
      // a refused amendment leaves its step running; any other failure ends the step
      onError: (stage, message) => { if (stage !== 'amend') inFlight = false; setError(`${stage}: ${message}`); },
    }, { pyodide: source, seed: replayRun?.seed ?? Number(params.get('seed') ?? 1) });

    window.__cocoArena = {
      client: client.current, queue: queue.current, last: null, renderer: rr, session: active, goal,
      mode: () => modeRef.current, log: () => log.current, layerIds: () => ll.current?.ids() ?? [],
    };
    void client.current?.whenReady().then(() => { if (params.has('stress')) rr?.addStress(50_000, 20_000); }, () => {});
    const ui = setInterval(() => setFrame((n) => n + 1), 200);

    // a click (not a drag): a goal, a compare goal, or an inspected cell
    let down: [number, number] | null = null;
    let kidnapping = false;
    const onDown = (e: PointerEvent) => {
      down = [e.clientX, e.clientY];
      // Localise lens: grabbing the robot (its TRUE pose) starts a kidnap
      const t = lastTick.current;
      kidnapping = false;
      if (lensRef.current === 'localise' && modeRef.current === 'live' && t && rr) {
        const truth = t.truth ?? t.pose;
        const [x, y] = rr.toWorld(e.clientX, e.clientY);
        if (Math.hypot(x - truth[0], y - truth[1]) < 0.35) { kidnapping = true; rr.panSuspended = true; }
      }
    };
    const onUp = (e: PointerEvent) => {
      if (rr) rr.panSuspended = false;
      if (kidnapping && rr && down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 6) {
        kidnapping = false;
        down = null;
        const [x, y] = rr.toWorld(e.clientX, e.clientY);
        const t = lastTick.current;
        const th = (t?.truth ?? t?.pose ?? [0, 0, 0])[2];
        queue.current.push({ kind: 'kidnap', x, y, theta: th, has_theta: true });
        return;
      }
      kidnapping = false;
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
    // Explain and Inspect: a value label under the mouse (M2.2), read from what the model emitted
    const onMove = (e: PointerEvent) => {
      if (levelRef.current === 'watch' || e.pointerType !== 'mouse' || !rr || !worldSet) { setHover(null); return; }
      const [x, y] = rr.toWorld(e.clientX, e.clientY);
      const s = active();
      let text: string | null = null;
      if (lensRef.current === 'plan') {
        const cell = rr.cellAt(x, y);
        const info = cell && s?.shownSearch ? s.shownSearch.info(cell[0], cell[1]) : null;
        if (info && info.state !== 'none') {
          text = `${info.state}${info.expansion !== null ? ` · expanded #${info.expansion}` : ''}`
            + (info.g !== null ? ` · g ${info.g.toFixed(2)} h ${(info.h ?? 0).toFixed(2)} f ${(info.f ?? 0).toFixed(2)}` : '');
        }
      } else if (s && worldRef.current && ll.current) {
        text = HOVERS[lensRef.current]?.({ layers: ll.current, session: s, tick: s.shownTick?.tick ?? 0, world: worldRef.current,
          on: (id) => lensOnRef.current[id] ?? false }, x, y) ?? null;
      }
      const b = cv.getBoundingClientRect();
      setHover(text ? { text, x: e.clientX - b.left + 12, y: e.clientY - b.top + 12 } : null);
    };
    const onLeave = () => setHover(null);
    cv.addEventListener('pointermove', onMove);
    cv.addEventListener('pointerleave', onLeave);

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
      cv.removeEventListener('pointermove', onMove);
      cv.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('keydown', keydown);
      window.removeEventListener('keyup', keyup);
      client.current?.close();
      rr?.dispose();
    };
    // the client and renderer live as long as the view
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { r.current?.setLayers(layers); }, [layers]);
  // a lens and a level choose the default layers (Watch: at most two computation layers)
  useEffect(() => {
    const plan = new Set(defaultLayers(LENS_BY_ID.plan, lens === 'plan' ? level : 'watch'));
    setLayers((l) => ({ ...l, frontier: lens === 'plan' && plan.has('frontier'), path: plan.has('path'),
      closed: lens === 'plan' && plan.has('closed'), heatmap: lens === 'plan' && plan.has('heatmap') }));
    const on: Record<string, boolean> = {};
    for (const L of LENSES) if (L.id !== 'plan') for (const x of L.layers) on[x.id] = false;
    if (lens !== 'plan') for (const id of defaultLayers(LENS_BY_ID[lens], level)) on[id] = true;
    setLensOn(on);
    client.current?.loadPack(LENS_BY_ID[lens].pack);
  }, [lens, level]);
  useEffect(() => {
    for (const [id, v] of Object.entries(lensOn)) ll.current?.setVisible(id, v);
  }, [lensOn]);
  // the Localise lens switches localisation on, once its pack is loaded and the live model drives (M2.3)
  useEffect(() => {
    if (lens !== 'localise' || locOn.current || !packs.has('localise') || mode === 'replay' || mode === 'recording') return;
    locOn.current = true;
    sendConfig('arena.range_sigma=0.02');
    sendConfig('localise.filter=both');
  }, [lens, packs, mode, sendConfig]);
  // the Map lens starts an occupancy grid from known poses (Lab 3's first lesson), once (M2.4)
  useEffect(() => {
    if (lens !== 'map' || mapOn.current || !packs.has('map') || mode === 'replay' || mode === 'recording') return;
    mapOn.current = true;
    sendConfig('arena.range_sigma=0.02');
    sendConfig('map.algorithm=occupancy');
  }, [lens, packs, mode, sendConfig]);
  // the Move lens hands the wheels to the DWA sampler, once (M2.5)
  useEffect(() => {
    if (lens !== 'move' || moveOn.current || !packs.has('move') || mode === 'replay' || mode === 'recording') return;
    moveOn.current = true;
    sendConfig('move.controller=dwa');
  }, [lens, packs, mode, sendConfig]);
  // a mission's settings: once, when the live model is ready (sendConfig waits for each pack)
  useEffect(() => {
    if (!cfgLines.length || cfgSent.current || !liveReady || mode === 'replay' || mode === 'recording') return;
    cfgSent.current = true;
    for (const c of cfgLines) sendConfig(c);
  }, [liveReady, mode, sendConfig]); // eslint-disable-line react-hooks/exhaustive-deps -- cfgLines is the URL's, fixed
  // Focus: everything outside the lens dims (the robot and truth never do)
  useEffect(() => {
    r.current?.setFocusDim(!focus || lens === 'plan' ? 1 : 0.25, focus ? 0.5 : 1);
    for (const L of LENSES) for (const x of L.layers) ll.current?.setDim(x.id, !focus || L.id === lens ? 1 : 0.25);
  }, [focus, lens]);

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
        <a href={`${import.meta.env.BASE_URL}?view=learn`} data-testid="learn-link">Learn</a>
        <a href={`${import.meta.env.BASE_URL}v1/`} data-testid="v1-labs-link">v1 labs (archive)</a>
      </header>
      {missionBack && <p className="mission-back"><a href={`${import.meta.env.BASE_URL}${missionBack}`} data-testid="mission-back">
        ← Back to the mission</a></p>}
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
      <LensBar lens={lens} level={level} focus={focus}
        available={new Set(LENSES.filter((l) => l.id === 'plan' || packs.has(l.pack) || (converted?.headers ?? []).some((h) => l.families.some((f) => h.channel.includes(f)))).map((l) => l.id))}
        onLens={setLens} onLevel={setLevel} onFocus={setFocus} />
      {/* M2.9: the measured gaps between this lens's model and the Stack */}
      <GapChips ids={LENS_BY_ID[lens].gaps} gaps={gaps} />
      {lens === 'localise' && <LocaliseControls send={sendConfig} live={mode === 'live'} initial={cfgInitial} />}
      {lens === 'map' && <MapControls send={sendConfig} live={mode === 'live'} initial={cfgInitial} />}
      {lens === 'move' && (converted?.headers?.some((h) => h.channel === 'coco.control.local.header.v1')
        ? <p className="lens-hint" data-testid="move-recorded">Recorded (STACK): Nav2's own candidates as it logged them and the trajectory it chose each cycle — nothing here is computed by the model.</p>
        : <MoveControls send={sendConfig} live={mode === 'live'} initial={cfgInitial} />)}
      {lens === 'decide' && <DecideControls send={sendConfig} live={mode === 'live'} initial={cfgInitial} />}
      {lens === 'decide' && session && <MissionPanel session={session} tick={tick?.tick ?? 0} />}
      {level !== 'watch' && session && (() => { const c = caption(lens, session.families, tick?.tick ?? 0);
        return c ? <p className="lens-caption" data-testid="lens-caption" role="status">{c}</p> : null; })()}
      <div className="arena-stage">
        <canvas ref={canvas} className="arena-canvas" data-testid="arena-canvas"
          aria-label="The arena: click or tap to give COCO a goal" />
        {!world && <p className="arena-loading" data-testid="arena-status">Loading…</p>}
        {hover && <span className="hover-label" data-testid="hover-label" style={{ left: hover.x, top: hover.y }}>{hover.text}</span>}
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
      {converted?.card && (
        <section className="run-card" data-testid="stack-results" aria-label="Measured in this recorded run">
          <b>Measured in this run</b> (STACK, docs/labs/LAB5_MOVE.md): <span>{converted.card}</span>
        </section>
      )}
      {converted?.evidence === 'STACK' && stats && !converted.card && (
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
            {lens !== 'plan' && (
              <div className="arena-row" role="group" aria-label={`${LENS_BY_ID[lens].title} layers`}>
                {LENS_BY_ID[lens].layers.map((x) => (
                  <label key={x.id} className="layer-toggle" title={x.meaning}><input type="checkbox" checked={lensOn[x.id] ?? false}
                    onChange={() => setLensOn((o) => ({ ...o, [x.id]: !o[x.id] }))} data-testid={`lens-layer-${x.id}`} data-role={x.role} />{x.label}</label>
                ))}
              </div>
            )}
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
          <nav className="arena-row recorded-runs" aria-label="Recorded and computed runs in this viewer" data-testid="recorded-runs">
            <span>Runs in this viewer:</span>
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
        {level === 'inspect' && session && (
          <section className="lens-inspect" data-testid="lens-inspect" aria-label={`${LENS_BY_ID[lens].title} lens, Inspect`}>
            <LensInspector lens={LENS_BY_ID[lens]} store={session.families} tick={tick?.tick ?? 0} />
            <EventLog lens={LENS_BY_ID[lens]} store={session.families} tick={tick?.tick ?? 0} />
            <LensCharts lens={LENS_BY_ID[lens]} store={session.families} tick={tick?.tick ?? 0} />
          </section>
        )}
      </section>
      {showPerf && <PerfOverlay />}
    </main>
  );
}
