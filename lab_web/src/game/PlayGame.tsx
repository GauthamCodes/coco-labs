// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.3 / G1.6: Play, as a phone game. The world renders at once; the model
 * (Pyodide + coco_lab in the worker) loads behind a loading screen driven by
 * its real stages; PLAY lights when it is ready.
 *
 * Eight always-visible controls (G1 §1.2): joystick, primary action, AUTO,
 * CAM, STOP, minimap, pause, vision. Everything the HUD shows is a quantity
 * the model has: its speed, its command source, its clock, Grasp Assist's
 * own phase and refusal reasons, Fetch Rush's own orders and counts.
 */

import { registerRunSaver } from '../offline/updates';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Camera, Hand, Pause, PackageCheck, Route, Navigation2, Info, Network } from 'lucide-react';
import type { InputRow, World } from '../arena/protocol';
import { readPref, isBool } from '../prefs';
import { GameRenderer, type Led, type View } from './render/GameRenderer';
import { ViewSwitch } from './hud/ViewSwitch';
import { GazeboBar, RosoutConsole, TelemetryStrip } from './hud/RosHud';
import { Rosout, type LogLine } from '../ros/rosout';
import { SimClock, strip } from '../ros/telemetry';
import { Recorder, TopicStats, topicsOf } from '../ros/recorder';
import { Panels } from './panels/Panels';
import { bagName, registerBagSource } from '../ros/bag_saver';
import type { PanelId } from './panels/learn';
import { parseDisplays, type Displays } from '../ros/displays';
import { writePref } from '../prefs';
import { perf } from '../arena/perf';
import type { CamMode } from './render/camera';
import { describe, type Spec, type WorldLook } from './world/describe';
import type { Tier } from './world/build3d';
import { GameSession, SPEC_FOR, type Candidate, type GameInfo, type GameKind, type GameTick, type WorldId } from './session';
import { FloatJoystick } from './hud/FloatJoystick';
import { Minimap, TacticalMap, type MapMarks } from './hud/Maps';
import { GameSound, haptic } from './sound';
import { LOAD_STAGES, TIPS, primaryAction, type FetchRushMode, type Primary } from './rules_view';
import type { GameResult } from './GameApp';
import { enterPhonePlay, FrameGate, isPhone, leavePhonePlay, phoneFrameCap } from '../play/phone';
import { FpsWatch, heavier, recommendedSettings, type PlaySettings } from './fps_watch';

const BASE = import.meta.env.BASE_URL;
const STOP_HOLD_MS = 600;

export interface PlayProps {
  world: WorldId; game: GameKind; seed: number; tier: Tier;
  /** G1.12: Fetch Rush's mode: the phone round (2 orders) or the Full shift (3) */
  mode?: FetchRushMode;
  onPause: () => void; paused: boolean; onResult: (r: GameResult) => void; restartKey: number;
  showPerf: boolean; tutorialSeen: boolean; onTutorialDone: () => void;
  /** draw the planner ghost: the A* route for the current order (Settings) */
  ghost: boolean;
  /** G2.1: the player tapped "Switch to recommended settings" (never called otherwise) */
  onRecommended?: (s: PlaySettings) => void;
}

const fmt = (s: number) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, '0')}`;

export function PlayGame(p: PlayProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const r = useRef<GameRenderer | null>(null);
  const s = useRef<GameSession | null>(null);
  const sound = useRef(new GameSound(readPref('sound', false, isBool)));
  const hapticsOn = readPref('haptics', true, isBool);
  const [stage, setStage] = useState<string>('worker');
  const [sceneReady, setSceneReady] = useState(false);
  const [modelReady, setModelReady] = useState(false);
  const [started, setStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [world, setWorld] = useState<(World & { game: GameInfo }) | null>(null);
  const occ = useRef<Uint8Array | null>(null);
  const [tick, setTick] = useState<GameTick | null>(null);
  const [latched, setLatched] = useState(false);
  // G2.2: GAME or SIM (the eye's place), and SIM's displays; both remembered in this browser
  const [view, setView] = useState<View>(() => readPref<View>('view', 'game', (v): v is View => v === 'game' || v === 'sim'));
  const [displays, setDisplays] = useState<Displays>(() => parseDisplays(readPref<unknown>('displays', null, (_v): _v is unknown => true)));
  // G2.4: the panels (Displays, ROS 2 graph, Topic echo, Plot), the run's frames and each topic's rate
  const [panels, setPanels] = useState(false);
  const [panelTab, setPanelTab] = useState<PanelId>('displays');
  const [echo, setEcho] = useState('/scan');
  const recorder = useRef(new Recorder());
  const stats = useRef(new TopicStats());
  const planGoal = useRef<[number, number] | null>(null);
  // G2.3: the /rosout console's lines and the Gazebo-style clock (model events and times)
  const rosout = useRef(new Rosout());
  const clock = useRef(new SimClock());
  const [log, setLog] = useState<LogLine[]>([]);
  const [cam, setCam] = useState<CamMode>('chase');
  const [mapOpen, setMapOpen] = useState(false);
  const [toast, setToast] = useState<{ text: string; key: number } | null>(null);
  const [flash, setFlash] = useState<{ side: string; key: number } | null>(null);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [goal, setGoal] = useState<[number, number] | null>(null);
  const [auto, setAuto] = useState(false);
  const [info, setInfo] = useState(false);
  const [tip, setTip] = useState(0);
  const [holdStart, setHoldStart] = useState<number | null>(null);
  /** a tick the model is still computing after 0.8 s (never expected in normal play since G1.11; shown if it happens) */
  const [busy, setBusy] = useState(false);
  const [tutorial, setTutorial] = useState(false);
  const look = useRef<WorldLook | null>(null);
  const prev = useRef<GameTick | null>(null);
  const shown = useRef<{ from: [number, number, number]; to: [number, number, number]; at: number; z0: number; z1: number }>({ from: [0, 0, 0], to: [0, 0, 0], at: 0, z0: 0, z1: 0 });
  const held = useRef(new Set<string>());
  const stick = useRef<[number, number]>([0, 0]);
  const fps = useRef({ frames: 0, t0: performance.now(), fps: 0 });
  const [perfText, setPerfText] = useState('');
  // G2.1: a phone drawing under 55 fps for 10 s while playing, on settings heavier than recommended
  const watch = useRef(new FpsWatch());
  const [recommend, setRecommend] = useState<{ fps: number; to: PlaySettings } | null>(null);
  const say = useCallback((text: string) => setToast({ text, key: performance.now() }), []);

  // the frame loop calls the latest input handlers (they close over this render's state)
  const live = useRef({ pollGamepad: () => {}, applyHeld: () => {}, watching: false, onSlow: (_fps: number) => {} });
  // the world (renders at once) and the model (loads behind it)
  useEffect(() => {
    const c = canvas.current!;
    const renderer = new GameRenderer(c, p.tier);
    r.current = renderer;
    renderer.cam.reducedMotion = readPref('motion', false, isBool) || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    renderer.cam.setMode('orbit');
    let alive = true;
    const specUrl = `${BASE}generated/arena/${SPEC_FOR[p.world]}`;
    void (async () => {
      try {
        const spec = await (await fetch(specUrl, { credentials: 'omit' })).json() as Spec & { start: { x: number; y: number; theta: number } };
        const lk = describe(spec);
        look.current = lk;
        const lightName = p.world === 'depot' ? 'depot' : 'proving_v1';
        await renderer.loadWorld(lk, `${BASE}generated/g1/${lightName}.light.png`, (spec as unknown as { robot?: { radius?: number } }).robot?.radius ?? 0.22);
        const st = spec.start as unknown as { x: number; y: number; theta: number };
        const pose: [number, number, number] = [st.x + spec.world_to_map[0], st.y + spec.world_to_map[1], st.theta];
        renderer.pose = pose;
        shown.current = { from: pose, to: pose, at: 0, z0: 0, z1: 0 };
        await renderer.loadRobot(`${BASE}assets3d/robot_${p.tier === 'high' ? 'high' : 'low'}.glb`);
        // G1.11: every shader now, behind the loading screen, not on first use in play
        await renderer.precompile();
        if (alive) setSceneReady(true);
      } catch (e) { if (alive) setError(`The world could not load: ${String(e)}`); }
    })();
    const session = new GameSession(p.world, p.game, p.seed, {
      onWorld: (w, o) => {
        occ.current = o; setWorld(w); setModelReady(true); setStage('ready');
        // G2.2: SIM view's map, frames and scan constants; their materials compile now, behind the loading screen
        if (w.game.ros) { renderer.setRos(w.game.ros, { width: w.width, height: w.height, resolution: w.resolution, origin: w.origin }, o); void renderer.precompile(); }
      },
      onTick: (t, ranges) => onTick(t, ranges),
      onError: (stg, m) => setError(`${stg}: ${m}`),
      onFamily: (msg) => {
        // SIM's Global and Local Costmap displays: the model's costmap cells (coco_lab.costmap)
        if (msg.channel === 'coco.costmap.layers.cells.v1' && msg.columns) {
          const c = msg.columns as Record<string, ArrayLike<number>>;
          r.current?.costmapCells(c.row, c.col, c.combined_cost);
        }
        // Grasp Assist's arm script, on COCO's real joints (presentation of the model's own state)
        if (msg.channel === 'coco.arm.state.v1' && msg.columns) {
          const cols = msg.columns as Record<string, ArrayLike<number>>;
          const n = cols.joint1?.length ?? 0;
          if (n) { const row = Object.fromEntries(['joint1', 'joint2', 'finger_left', 'finger_right'].map((k) => [k, Number(cols[k]?.[n - 1])])); r.current?.setArm(row); recorder.current.setArm(row); }
        }
      },
    }, p.mode ?? 'phone');
    s.current = session;
    session.client.worker.addEventListener('message', (m: MessageEvent) => {
      const d = m.data as { type: string; name?: string };
      if (d.type === 'mark' && d.name) {
        const k = LOAD_STAGES.findIndex((x) => (x.marks as readonly string[]).includes(d.name!));
        if (k >= 0) setStage(LOAD_STAGES[k + 1]?.id ?? 'ready'); // that stage is done: the next one is under way
      }
    });
    let raf = 0, last = performance.now();
    // G1.13: on a phone, draw at most phoneFrameCap() frames a second (M5's 60, or 120 when chosen
    // in settings), as M5's Play does. Measured on the real Nothing Phone (1): uncapped, full-screen
    // Play drew at the display's 120 Hz. Drawing only: the model's clock never depends on it.
    const gate = new FrameGate(), phone = isPhone();
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (phone && !gate.due(now, phoneFrameCap())) return;
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const sh = shown.current, rr = r.current!;
      const f = Math.min(1, (now - sh.at) / 100);
      const lerpA = (a: number, b: number) => a + Math.atan2(Math.sin(b - a), Math.cos(b - a)) * f;
      rr.pose = [sh.from[0] + (sh.to[0] - sh.from[0]) * f, sh.from[1] + (sh.to[1] - sh.from[1]) * f, lerpA(sh.from[2], sh.to[2])];
      rr.z = sh.z0 + (sh.z1 - sh.z0) * f;
      live.current.pollGamepad();
      live.current.applyHeld();
      if (!document.hidden) { rr.frame(dt); perf.drawnPose(rr.pose); }
      if (live.current.watching && !document.hidden) { if (watch.current.frame(now)) live.current.onSlow(watch.current.last); }
      else watch.current.reset();
      const fp = fps.current;
      fp.frames += 1;
      if (now - fp.t0 > 1000) { fp.fps = (fp.frames * 1000) / (now - fp.t0); fp.frames = 0; fp.t0 = now; if (p.showPerf) setPerfText(`${fp.fps.toFixed(0)} fps · ${rr.stats.draws} draws · ${(rr.stats.triangles / 1000).toFixed(0)}k tris · ${p.tier}`); }
    };
    raf = requestAnimationFrame(frame);
    const resize = () => renderer.resize();
    window.addEventListener('resize', resize);
    (window as unknown as { __cocoGame?: unknown }).__cocoGame = { renderer, session, get tick() { return s.current?.lastTick; } };
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      // G1.13: leaving Play releases the landscape lock (M5's leavePhonePlay; it keeps the lock
      // when the next view is Play again). Seen on the real phone: the lock outlived the game.
      void leavePhonePlay();
      window.removeEventListener('resize', resize);
      session.close();
      renderer.dispose();
      sound.current.dispose();
    };
  }, [p.restartKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (modelReady && sceneReady) (canvas.current!.parentElement as HTMLElement).dataset.ready = 'true'; }, [modelReady, sceneReady]);
  useEffect(() => { const t = setInterval(() => setTip((k) => (k + 1) % TIPS.length), 4000); return () => clearInterval(t); }, []);
  // G1.8: "Save run" on the New version notice downloads this session's record (spec, seed, input log)
  useEffect(() => registerRunSaver(async () => {
    const g = s.current;
    if (!g || !g.client.world) return null;
    return { name: `coco-${p.game}-${p.world}-seed-${p.seed}-run.json`, data: await g.query('record') };
  }), [p.game, p.world, p.seed]);
  useEffect(() => { if (p.paused) s.current?.pause(); else if (started) s.current?.resume(); }, [p.paused, started]);
  // G2.5: "Save as rosbag2 (MCAP)" (pause menu, results): this run's model messages, written in the browser
  useEffect(() => registerBagSource(async () => {
    const w = s.current?.world;
    if (!w?.game.ros || !occ.current) throw new Error('the model has not started yet');
    const { writeBag } = await import('../ros/bag');
    const name = bagName(p.game, p.game === 'fetch_rush' ? p.mode ?? 'phone' : undefined, p.seed);
    const rec = recorder.current;
    const bytes = await writeBag(rec.frames, w.game.ros, { width: w.width, height: w.height, resolution: w.resolution, origin: w.origin }, occ.current,
      { game: p.game, seed: p.seed, mode: p.game === 'fetch_rush' ? p.mode ?? 'phone' : undefined, world: p.world, hashVersion: 3, app: `COCO Lab ${__BUILD_COMMIT__}`, ticks: rec.frames.length, dropped: rec.dropped }, name);
    return { name, bytes };
  }), [p.game, p.mode, p.seed, p.world]);
  useEffect(() => { const now = performance.now(); if (started && !p.paused) clock.current.resume(now); else clock.current.pause(now); }, [p.paused, started]);
  // G2.2: the view and the displays (presentation only: the model is never told)
  useEffect(() => { r.current?.setView(view); writePref('view', view); }, [view, sceneReady]);
  useEffect(() => { r.current?.setDisplays(displays); }, [displays, sceneReady, modelReady]);
  const changeDisplays = useCallback((d: Displays) => { setDisplays(d); writePref('displays', d); }, []);
  useEffect(() => { r.current?.setCandidates(view === 'sim' ? cands : []); }, [view, cands]);
  const toggleView = useCallback(() => setView((v) => (v === 'game' ? 'sim' : 'game')), []);

  /** Every tick from the model: draw it, and turn its changes into toasts, flashes and sounds. */
  const onTick = (t: GameTick, ranges: Float32Array) => {
    const rr = r.current;
    if (!rr) return;
    const before = prev.current;
    prev.current = t;
    const now = performance.now();
    const cur = shown.current;
    shown.current = { from: rr.pose, to: t.pose, at: now, z0: rr.z, z1: t.tilt?.[0] ?? 0 };
    void cur;
    rr.tilt = t.tilt ? [t.tilt[1], t.tilt[2]] : [0, 0];
    rr.speed = t.v;
    rr.wheelSpeed = t.wheels ?? [0, 0];
    const led: Led = t.source === 'stop' ? 'stop' : t.source === 'teleop' ? 'manual' : t.source === 'planner' || t.source === 'mission' ? 'auto' : 'idle';
    rr.setLed(s.current?.latched ? 'stop' : led);
    const w = s.current?.world;
    const g = t.game;
    if (g?.objects && w?.game.objects) rr.setObjects(new Map(w.game.objects.map((o) => [o.id, o])), g.objects);
    if (g?.actors) rr.setActors(g.actors);
    const last = t.plans.length ? t.plans[t.plans.length - 1] : null;
    if (last) { rr.setPlan([[t.pose[0], t.pose[1]], ...last.waypoints]); planGoal.current = last.goal; }
    if (t.arrived || (t.source === 'teleop' && before?.source !== 'teleop')) { rr.setPlan([]); setGoal(null); rr.setGoal(null); setAuto(false); planGoal.current = null; }
    rr.setScan(ranges, { min: w?.lidar.angle_min ?? -2.09, max: w?.lidar.angle_max ?? 2.09, samples: w?.lidar.samples ?? ranges.length }, (w?.lidar.mount ?? [0, 0, 0]) as [number, number, number], w?.lidar.range_max ?? 12,
      { tf: t.ros?.tf ?? null, tickPose: t.pose, v: t.v, w: t.w, goal: planGoal.current });
    sound.current.motor(t.v, (w?.limits as Record<string, number> | undefined)?.teleop_linear ?? 0.5);
    // transitions
    const bf = before?.game?.fetch, f = g?.fetch;
    if (f && bf && f.deliveries > bf.deliveries) { say('Delivered +1'); sound.current.deliver(); haptic('deliver', hapticsOn); }
    const contact = (f && bf && f.contacts > bf.contacts) || (t.blocked && !before?.blocked);
    if (contact) {
      setFlash({ side: t.v < -0.01 ? 'back' : 'front', key: now });
      sound.current.contact(); haptic('contact', hapticsOn);
      if (f) say('Contact! −1');
    }
    const a = g?.assist, ba = before?.game?.assist;
    if (a && ba && a.phase !== ba.phase) {
      if (a.phase === 'carry') { say('Got it! Take it to the drop zone'); sound.current.grab(); haptic('grab', hapticsOn); }
      else if (a.phase === 'idle' && ba.phase !== 'idle' && ba.phase !== 'release' && a.reason) { say(a.reason.length > 46 ? a.reason.slice(0, 44) + '…' : a.reason); sound.current.refuse(); }
    }
    if (g?.clearance !== undefined && g.clearance < 1.2 && (before?.game?.clearance ?? 9) >= 1.2) say('Forklift ahead!');
    if (f?.over && !bf?.over) void finish();
    // G2.3: the model's events as /rosout lines; the clock's sim time and iterations
    const scan = w?.game.ros?.scan;
    if (rosout.current.feed({ tick: t.tick, t_world: t.t_world, source: t.source ?? 'idle', blocked: t.blocked, arrived: t.arrived, plans: t.plans, pose: t.pose },
      ranges, scan ?? null, { resolution: w?.resolution ?? 0.1 }).length) setLog([...rosout.current.lines]);
    clock.current.tick(t.t_world, t.tick, performance.now());
    // G2.4 / G2.5: the frame (what the model produced this tick) and the topics it published
    const tele = (t.inputs ?? []).filter((x) => x.kind === 'teleop').pop() as { linear?: number; angular?: number } | undefined;
    const frame = { tick: t.tick, t: t.t_world, pose: t.pose, v: t.v, w: t.w, source: t.source ?? 'idle', tf: t.ros?.tf ?? null, ranges: ranges.slice(),
      plan: last ? last.waypoints as [number, number][] : null, goal: planGoal.current, teleop: tele ? [tele.linear ?? 0, tele.angular ?? 0] as [number, number] : null, arm: recorder.current.arm };
    const first = recorder.current.frames.length === 0;
    recorder.current.push(frame);
    const wall = performance.now();
    for (const topic of topicsOf(frame, first)) stats.current.mark(topic, wall, t.t_world);
    setTick(t);
  };

  // SIM's costmap displays ask the model for its costmap: at once, then every 4 s while shown
  // (view-only, no tick; only the cells that changed after the first: G1.13's delta view)
  const costmapOn = view === 'sim' && (displays.global_costmap.on || displays.local_costmap.on);
  useEffect(() => {
    if (!costmapOn || !started) return;
    s.current?.client.requestCostmap(true);
    const t = setInterval(() => s.current?.client.requestCostmap(true), 4000);
    return () => clearInterval(t);
  }, [costmapOn, started]);

  // the planner ghost: the round's precomputed route for each order (G1.11: no search while playing)
  const ghostOrder = useRef<number | null>(null);
  const [ghostPts, setGhostPts] = useState<[number, number][] | null>(null);
  useEffect(() => {
    const k = tick?.game?.fetch?.k;
    if (!p.ghost || k === undefined) { if (!p.ghost) { r.current?.setGhost(null); setGhostPts(null); ghostOrder.current = null; } return; }
    if (ghostOrder.current === k) return;
    ghostOrder.current = k;
    void s.current?.query<{ order: number; points: [number, number][] } | null>('ghost').then((g) => { r.current?.setGhost(g?.points ?? null); setGhostPts(g?.points ?? null); });
  }, [p.ghost, tick?.game?.fetch?.k]); // eslint-disable-line react-hooks/exhaustive-deps

  // a long tick is shown, never hidden: the model's clock waits with it (every timer is model time)
  useEffect(() => {
    if (!started) return;
    const t = setInterval(() => { const ss = s.current; setBusy(!!ss && !ss.paused && ss.stepAge() > 800); }, 200);
    return () => clearInterval(t);
  }, [started]);

  // GRAB's preview: Grasp Assist's own candidates near COCO, asked twice a second while idle
  useEffect(() => {
    if (!started || !world?.game.v3) return;
    let alive = true;
    const t = setInterval(async () => {
      const lt = s.current?.lastTick, objs = world.game.objects ?? [];
      if (!lt || lt.game?.assist?.phase !== 'idle') { if (cands.length) setCands([]); return; }
      const near = objs.some((o) => { const row = lt.game?.objects?.find((x) => x[0] === o.id); return row && row[4] === 'placed' && Math.hypot(row[1] - lt.pose[0], row[2] - lt.pose[1]) < 1.6; });
      if (!near) { setCands([]); return; }
      const res = await s.current!.query<{ rows: Candidate[] }>('preview');
      if (alive && res?.rows) {
        const was = cands.some((c) => !c.reason);
        setCands(res.rows);
        if (!was && res.rows.some((c) => !c.reason && (p.game !== 'fetch_rush' || c.object_id === lt.game?.fetch?.order?.[0]))) say('In range: tap GRAB');
      }
    }, 500);
    return () => { alive = false; clearInterval(t); };
  }, [started, world, cands]); // eslint-disable-line react-hooks/exhaustive-deps

  const order = tick?.game?.fetch?.order ?? null;
  const zones = world?.game.zones ?? [];
  const primary: Primary = useMemo(() => primaryAction({ game: p.game, tick, cands, zones, goal, auto, latched }), [p.game, tick, cands, zones, goal, auto, latched]);

  // the target glow and the drop zone glow follow the objective
  useEffect(() => {
    const rr = r.current;
    if (!rr || !tick) return;
    const a = tick.game?.assist;
    const target = p.game === 'fetch_rush' ? (a?.carried ? null : order?.[0] ?? null) : (primary.kind === 'grab' ? primary.target ?? null : a?.target ?? null);
    const stages = ['approach', 'align', 'reach'];
    rr.setTarget(target, a && stages.includes(a.phase) ? (stages.indexOf(a.phase) + 1) / (stages.length + 1) : null);
    rr.setDropZone(p.game === 'fetch_rush' ? order?.[1] ?? null : primary.kind === 'drop' ? primary.target ?? null : null, !!a?.carried);
  }, [tick, primary]); // eslint-disable-line react-hooks/exhaustive-deps

  const begin = () => {
    if (!modelReady || !sceneReady) return;
    // G1.13: on a phone, PLAY (a user gesture) asks for full screen and a landscape lock, as
    // M5's Play did (src/play/phone.ts); a refusal leaves the rotate card. Found on the real
    // Nothing Phone (1): without it Play stayed in the tab, 710 x 269 CSS px under the address bar.
    void enterPhonePlay();
    sound.current.unlock();
    r.current!.cam.setMode('chase');
    setCam('chase');
    s.current!.start();
    setStarted(true);
    if (!p.tutorialSeen) setTutorial(true);
  };

  const stop = useCallback(() => {
    if (!s.current) return;
    s.current.stop();
    setLatched(true); setAuto(false);
    r.current?.setLed('stop');
    sound.current.stop(); haptic('stop', hapticsOn);
  }, [hapticsOn]);
  const release = useCallback(() => { s.current?.release(); setLatched(false); setHoldStart(null); }, []);

  const doPrimary = () => {
    const ss = s.current;
    if (!ss || latched) return;
    sound.current.unlock();
    if (primary.kind === 'grab') { ss.grasp(primary.target); haptic('tick', hapticsOn); }
    else if (primary.kind === 'drop') { ss.grasp(); haptic('tick', hapticsOn); }
    else if (primary.kind === 'go' && goal) { ss.goal(goal[0], goal[1]); setAuto(true); }
    else { say(primary.why ?? 'Nothing to do here'); sound.current.refuse(); }
  };

  const toggleAuto = async () => {
    const ss = s.current;
    if (!ss || latched) return;
    if (auto) { ss.manual(); setAuto(false); say('Manual: you drive'); return; }
    if (p.game === 'fetch_rush') {
      const gTo = await ss.query<{ x: number; y: number; why: string } | null>('auto_goal');
      if (!gTo) { say('No path for the planner from here'); return; }
      ss.goal(gTo.x, gTo.y); setGoal([gTo.x, gTo.y]); r.current?.setGoal([gTo.x, gTo.y]);
      say(gTo.why === 'drop' ? 'AUTO: to the drop zone' : 'AUTO: to the next pick');
    } else if (goal) ss.goal(goal[0], goal[1]);
    else { say('Set a goal on the map first'); return; }
    setAuto(true);
  };

  const setGoalAt = (x: number, y: number) => {
    setGoal([x, y]);
    r.current?.setGoal([x, y]);
    setMapOpen(false);
    say('Goal set: tap GO or AUTO');
  };

  const cycleCam = () => { const m = r.current!.cam.next(); setCam(m); say(m === 'chase' ? 'Chase camera' : m === 'tactical' ? 'Tactical view' : 'Free orbit'); };

  const finish = async () => {
    const ss = s.current!;
    ss.pause();
    // the reference card for this shift (committed M6 reference runs); no reference, no stars
    const refs = await fetch(`${BASE}generated/g1/references.json`, { credentials: 'omit' }).then((x) => x.json()).catch(() => null) as { fetch_rush?: Record<string, unknown> } | null;
    const reference = refs?.fetch_rush?.[String(p.seed)] ?? null;
    const [card, rec] = await Promise.all([ss.query<{ card: Record<string, unknown>; stars: number | null; reference: Record<string, unknown> | null }>('stars', reference), ss.query<Record<string, unknown>>('record')]);
    p.onResult({ game: p.game, seed: p.seed, world: p.world, card: card?.card ?? null, stars: card?.stars ?? null, reference: card?.reference ?? null, record: rec, objects: ss.world?.game.objects });
  };

  // keyboard: WASD/arrows drive; G grab; F auto; C camera; V vision; Space STOP; R release; M map; Esc pause
  useEffect(() => {
    const keyMap: Record<string, string> = { KeyW: 'f', ArrowUp: 'f', KeyS: 'b', ArrowDown: 'b', KeyA: 'l', ArrowLeft: 'l', KeyD: 'r', ArrowRight: 'r' };
    const down = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.target instanceof Element && e.target.closest('input,select,textarea')) return;
      if (e.code === 'Space') { e.preventDefault(); if (!latched) stop(); return; }
      if (e.code === 'Escape') { e.preventDefault(); if (mapOpen) setMapOpen(false); else p.onPause(); return; }
      if (!started || p.paused) return;
      if (keyMap[e.code]) { e.preventDefault(); if (!e.repeat && !held.current.size) perf.driveInput(e.timeStamp); held.current.add(keyMap[e.code]); sound.current.unlock(); return; }
      if (e.repeat) return;
      if (e.code === 'KeyG' || e.code === 'KeyE') doPrimary();
      else if (e.code === 'KeyF') void toggleAuto();
      else if (e.code === 'KeyC') { if (view === 'game') cycleCam(); }
      else if (e.code === 'KeyV' || e.code === 'KeyX') toggleView();
      else if (e.code === 'KeyR' && latched) release();
      else if (e.code === 'KeyP') setPanels((x) => !x);
      else if (e.code === 'KeyM') setMapOpen((m) => !m);
    };
    const up = (e: KeyboardEvent) => { if (keyMap[e.code]) held.current.delete(keyMap[e.code]); };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  });

  const lastKeys = useRef('');
  const applyHeld = () => {
    const h = held.current, ss = s.current;
    if (!ss || !started) return;
    const k = [...h].sort().join('');
    if (k === lastKeys.current && stick.current[0] === 0 && stick.current[1] === 0) return;
    if (stick.current[0] !== 0 || stick.current[1] !== 0) return;
    lastKeys.current = k;
    const f = (h.has('f') ? 1 : 0) - (h.has('b') ? 1 : 0), t = (h.has('l') ? 1 : 0) - (h.has('r') ? 1 : 0);
    if (f || t) setAuto(false);
    ss.drive(f, t);
  };

  // gamepad: left stick drives, triggers scale throttle and brake; A grab, X auto, Y camera, B STOP, Start pause
  const pads = useRef<boolean[]>([]);
  const pollGamepad = () => {
    const gp = navigator.getGamepads?.().find((x) => x);
    if (!gp || !s.current || !started) return;
    const b = gp.buttons.map((x) => x.pressed);
    const edge = (i: number) => b[i] && !pads.current[i];
    if (edge(1)) { if (!s.current.latched) stop(); else release(); }
    if (edge(9)) p.onPause();
    if (!p.paused) {
      if (edge(0)) doPrimary();
      if (edge(2)) void toggleAuto();
      if (edge(3)) cycleCam();
      const ax = Math.abs(gp.axes[0]) > 0.12 ? gp.axes[0] : 0, ay = Math.abs(gp.axes[1]) > 0.12 ? gp.axes[1] : 0;
      const rt = gp.buttons[7]?.value ?? 0, lt = gp.buttons[6]?.value ?? 0;
      const fwd = rt > 0.05 || lt > 0.05 ? rt - lt : -ay;
      if (ax || ay || rt > 0.05 || lt > 0.05) { if (!stick.current[0] && !stick.current[1]) perf.driveInput(); stick.current = [fwd, -ax]; s.current.drive(fwd, -ax); }
      else if (stick.current[0] || stick.current[1]) { stick.current = [0, 0]; s.current.drive(0, 0); }
    }
    pads.current = b;
  };

  const onSlow = (fps: number) => {
    if (!isPhone()) return;
    const coarse = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
    const now: PlaySettings = { quality: p.tier, phone120: readPref('phone120', false, isBool) };
    const rec = recommendedSettings(coarse);
    if (heavier(now, rec)) setRecommend({ fps, to: rec });
  };
  live.current = { pollGamepad, applyHeld, watching: started && !p.paused, onSlow };

  // canvas: mouse drag orbits, wheel zooms, a click on the floor sets a goal (desktop); two fingers orbit and pinch
  const touches = useRef(new Map<number, { x: number; y: number; x0: number; y0: number; t0: number }>());
  const onCanvasDown = (e: React.PointerEvent) => {
    canvas.current!.setPointerCapture(e.pointerId);
    touches.current.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY, t0: performance.now() });
  };
  const onCanvasMove = (e: React.PointerEvent) => {
    const t = touches.current.get(e.pointerId);
    if (!t || !r.current) return;
    const dx = e.clientX - t.x, dy = e.clientY - t.y;
    const all = [...touches.current.values()];
    const sim = r.current.view === 'sim';
    if (all.length === 2) {
      const [a, b] = all;
      const before = Math.hypot(a.x - b.x, a.y - b.y);
      t.x = e.clientX; t.y = e.clientY;
      const after = Math.hypot(all[0].x - all[1].x, all[0].y - all[1].y);
      if (before > 0) r.current.cam.zoom(before / Math.max(1, after));
      // SIM (RViz's Orbit view): two fingers pan; GAME: they orbit, as in G1
      if (sim) r.current.cam.pan(dx / 2, dy / 2); else r.current.cam.drag(dx / 2, dy / 2);
    } else {
      t.x = e.clientX; t.y = e.clientY;
      if (Math.hypot(e.clientX - t.x0, e.clientY - t.y0) > 6) {
        if (sim && (e.shiftKey || (e.buttons & 2) || (e.buttons & 4))) r.current.cam.pan(dx, dy);   // RViz: right / middle / shift drag
        else r.current.cam.drag(dx, dy);
      }
    }
    setCam(r.current.cam.mode);
  };
  const onCanvasUp = (e: React.PointerEvent) => {
    const t = touches.current.get(e.pointerId);
    touches.current.delete(e.pointerId);
    if (!t || !r.current || !started) return;
    if (e.pointerType === 'mouse' && Math.hypot(e.clientX - t.x0, e.clientY - t.y0) < 5 && performance.now() - t.t0 < 400) {
      const at = r.current.pick(e.clientX, e.clientY);
      if (at) setGoalAt(at[0], at[1]);
    }
  };

  // STOP: down stops at once (any finger, any time); latched, a HOLD releases it
  const stopDown = (e: React.PointerEvent) => {
    e.stopPropagation();
    if (!s.current) return;
    if (!s.current.latched) { stop(); return; }
    setHoldStart(performance.now());
  };
  useEffect(() => {
    if (holdStart === null) return;
    const t = setTimeout(() => release(), STOP_HOLD_MS);
    return () => clearTimeout(t);
  }, [holdStart, release]);

  const fr = tick?.game?.fetch;
  const v = tick?.v ?? 0;
  const vmax = (world?.limits as Record<string, number> | undefined)?.teleop_linear ?? 0.5;
  const mode = latched || tick?.source === 'stop' ? 'stopped' : tick?.source === 'teleop' ? 'manual' : tick?.source === 'planner' || tick?.source === 'mission' ? 'auto' : 'idle';
  const angle = Math.PI * Math.min(1, Math.abs(v) / vmax);
  const marks: MapMarks = {
    pose: tick?.pose ?? null,
    plan: tick?.plans.length ? tick.plans[tick.plans.length - 1].waypoints : [],
    target: (() => { const o = order?.[0] ? tick?.game?.objects?.find((x) => x[0] === order[0]) : null; return o && !tick?.game?.assist?.carried ? [o[1], o[2]] as [number, number] : null; })(),
    drop: (() => { const z = order?.[1] ? zones.find((x) => x.id === order[1]) : null; return z ? { min: [z.center[0] - z.size[0] / 2, z.center[1] - z.size[1] / 2] as [number, number], max: [z.center[0] + z.size[0] / 2, z.center[1] + z.size[1] / 2] as [number, number] } : null; })(),
    goal,
    actors: (tick?.game?.actors ?? []).map((a) => [a[1], a[2]] as [number, number]),
    ghost: ghostPts ?? undefined,
  };
  const desktop = typeof window !== 'undefined' && window.matchMedia?.('(hover: hover) and (pointer: fine)').matches;
  const loadIndex = Math.max(0, LOAD_STAGES.findIndex((x) => x.id === stage));

  return <div className={`g1 g1-play coco-play ${view === 'sim' ? 'is-sim' : ''} ${panels ? 'has-panels' : ''}`} data-g1="play" data-testid="arena" data-ready="false" data-view={view}>
    <canvas ref={canvas} className="g1-canvas" data-testid="arena-canvas" data-scene-ready={sceneReady ? 'true' : 'false'} tabIndex={0}
      onPointerDown={onCanvasDown} onPointerMove={onCanvasMove} onPointerUp={onCanvasUp} onPointerCancel={onCanvasUp} onContextMenu={(e) => e.preventDefault()}
      onWheel={(e) => { r.current?.cam.zoom(e.deltaY > 0 ? 1.1 : 1 / 1.1); setCam(r.current?.cam.mode ?? 'chase'); }}
      aria-label="COCO's world. Drive with WASD or the left thumb; click the floor for a goal" />
    {!started && <section className="g1-screen" data-testid="g1-loading" style={{ justifyContent: 'flex-end' }}>
      <div className="g1-eyebrow">{modelReady ? 'COCO IS AWAKE' : `LOADING COCO'S BRAIN · STEP ${Math.min(loadIndex + 1, LOAD_STAGES.length)} OF ${LOAD_STAGES.length}`}</div>
      <div className="g1-loading-bar">
        <div className="g1-bar" role="progressbar" aria-valuemin={0} aria-valuemax={LOAD_STAGES.length} aria-valuenow={modelReady ? LOAD_STAGES.length : loadIndex}><i style={{ width: `${(modelReady ? 1 : loadIndex / LOAD_STAGES.length) * 100}%` }} /></div>
        <div className="g1-stages">{LOAD_STAGES.map((x, k) => <span key={x.id} className={modelReady || k < loadIndex ? 'done' : k === loadIndex ? 'now' : ''}>{modelReady || k < loadIndex ? '✓' : k === loadIndex ? '●' : '○'} {x.label}</span>)}</div>
      </div>
      <p className="g1-tip g1-glass">💡 {TIPS[tip]}</p>
      <button className="g1-big" data-testid="g1-play" onClick={begin} disabled={!modelReady || !sceneReady}>▶ PLAY</button>
      <p className="g1-eyebrow">{sceneReady ? 'DRAG TO LOOK AROUND WHILE COCO WAKES UP' : 'BUILDING THE WORLD'}</p>
      {error && <p role="alert" className="g1-note" style={{ color: 'var(--g1-danger)' }}>{error}</p>}
    </section>}
    {started && <div className="g1-safe">
      <FloatJoystick enabled={!latched && !p.paused} hint={desktop ? 'WASD / ARROWS' : 'DRAG TO DRIVE'} onChange={(f, t) => { if ((f || t) && !stick.current[0] && !stick.current[1]) perf.driveInput(); stick.current = [f, t]; if (f || t) setAuto(false); s.current?.drive(f, t); }} />
      {world && occ.current && <Minimap world={world} occupancy={occ.current} marks={marks} headingUp={false} onOpen={() => setMapOpen(true)} />}
      <div className="g1-pill g1-glass" data-testid="objective">{p.game === 'fetch_rush'
        ? fr ? <><span>DELIVER {fr.deliveries}/{fr.orders}</span><span className="sep">·</span><span className={`num${fr.seconds - fr.t < 30 ? ' low' : ''}`}>⏱ {fmt(fr.seconds - fr.t)}</span>{fr.contacts > 0 && <><span className="sep">·</span><span className="num">✖ {fr.contacts}</span></>}</> : <span>FETCH RUSH</span>
        : <><span>FREE DRIVE</span><span className="sep">·</span><span>{p.world === 'depot' ? 'DEPOT' : 'PROVING GROUND'}</span></>}</div>
      <div className="g1-top-right">
        <button className="g1-icon g1-glass" data-testid="g1-pause" aria-label="Pause (Esc)" onClick={p.onPause}><Pause size={20} />{desktop && <kbd>ESC</kbd>}</button>
        <button className={`g1-icon g1-glass ${panels ? 'is-on' : ''}`} data-testid="g2-panels-button" aria-pressed={panels} aria-label="ROS 2 panels (P): displays, graph, topic echo, plot (model)" onClick={() => setPanels((x) => !x)}><Network size={20} />{desktop && <kbd>P</kbd>}</button>
        <ViewSwitch view={view} desktop={!!desktop} onView={(v) => { setView(v); if (v !== view) say(v === 'sim' ? 'SIM: the same moment, as RViz would show it (model)' : 'GAME view'); }} />
      </div>
      {view === 'sim' && <p className="g2-sim-caption g1-glass" data-testid="g2-sim-caption">SIM · RViz-style view of the browser model <b>MODEL</b> · Fixed Frame: map</p>}
      <button className="g1-chip g1-glass" onClick={() => setInfo((x) => !x)} aria-expanded={info} aria-label="What is real here"><Info size={11} style={{ verticalAlign: '-2px' }} /> MODEL · kinematic</button>
      {info && <div className="g1-sheet g1-glass" role="note">
        <h3>WHAT IS REAL HERE</h3>
        <p><b>MODEL · kinematic.</b> COCO is driven by the Arena model (coco_lab, in your browser): planar kinematics with the robot's real speed and acceleration limits, its real LiDAR geometry. No physics engine; nothing tips or slips.</p>
        {world?.game.v3 && <p><b>MODEL · MoveIt-style.</b> Grasp Assist decides each pick from COCO's own reach envelope and gripper limits. Two fingers and a magnet; the magnet holds.</p>}
        {p.game === 'fetch_rush' && <p><b>Game rules are not physics.</b> Orders, timer and stars are scoring rules (GAMES.md); stars compare with the reference bot's run.</p>}
        <p>No physical robot exists. Real ROS 2 runs are in Research › Recordings (STACK).</p>
      </div>}
      <section className="g1-gauge" data-testid="speed"><svg viewBox="0 0 150 66" aria-hidden><path d="M20 62 A55 55 0 0 1 130 62" stroke="#2A3344" strokeWidth="7" fill="none" strokeLinecap="round" />
        {Math.abs(v) > 0.002 && <path d={`M20 62 A55 55 0 0 1 ${(75 - 55 * Math.cos(angle)).toFixed(2)} ${(62 - 55 * Math.sin(angle)).toFixed(2)}`} stroke={v < 0 ? '#22D3EE' : '#FF7A1A'} strokeWidth="7" fill="none" strokeLinecap="round" />}</svg>
        <div className="v num">{Math.abs(v).toFixed(2)}<small>m/s{v < -0.002 ? ' ◂' : ''}</small></div><span className={`g1-mode ${mode}`} data-testid="mode-chip">{mode.toUpperCase()}</span></section>
      <TelemetryStrip s={tick ? strip(tick) : null} />
      {panels && <Panels tab={panelTab} onTab={setPanelTab} onClose={() => setPanels(false)} displays={displays} onDisplays={changeDisplays}
        info={world?.game.ros ?? null} stats={stats.current} recorder={recorder.current} frame={recorder.current.frames[recorder.current.frames.length - 1] ?? null}
        map={world ? { width: world.width, height: world.height, resolution: world.resolution, origin: world.origin } : null} occupancy={occ.current} goal={planGoal.current}
        echo={echo} onEcho={(topic) => { setEcho(topic); setPanelTab('echo'); }} />}
      {desktop && view === 'sim' && <GazeboBar clock={clock.current} now={performance.now()} />}
      <RosoutConsole lines={log} />
      <button className={`g1-btn g1-primary ${primary.enabled ? (primary.kind === 'drop' ? 'is-drop' : '') : 'is-grey'}`} data-testid="hud-primary" aria-disabled={!primary.enabled} onClick={doPrimary}
        aria-label={`${primary.label}${primary.why ? `: ${primary.why}` : ''} (G)`}>
        {primary.progress !== undefined && <span className="ring" style={{ background: `conic-gradient(var(--g1-safe) 0 ${Math.round(primary.progress * 100)}%, transparent ${Math.round(primary.progress * 100)}%)` }} />}
        <span>{primary.kind === 'drop' ? <PackageCheck className="ic" size={24} /> : primary.kind === 'go' ? <Navigation2 className="ic" size={24} /> : <Hand className="ic" size={24} />}{primary.label}{!primary.enabled && primary.why && <span className="why">{primary.why}</span>}{desktop && <kbd>G</kbd>}</span>
      </button>
      <button className={`g1-btn g1-small g1-auto ${auto ? 'is-on' : ''}`} data-testid="hud-autonomy" aria-pressed={auto} onClick={() => void toggleAuto()} aria-label="AUTO (F): the planner drives"><span><Route className="ic" size={20} />AUTO{desktop && <kbd>F</kbd>}</span></button>
      <button className="g1-btn g1-small g1-cam" data-testid="hud-camera" onClick={cycleCam} aria-label={`Camera (C): ${cam}`}><span><Camera className="ic" size={20} />CAM{desktop && <kbd>C</kbd>}</span></button>
      {busy && <p className="g1-busy g1-glass" role="status" data-testid="g1-busy">COCO's planner is computing… <small>(the clock waits)</small></p>}
      {toast && <p key={toast.key} className="g1-toast g1-glass" role="status">{toast.text}</p>}
      {recommend && <div className="g2-recommend g1-glass" role="status" data-testid="g2-recommend">
        <span>Drawing {recommend.fps.toFixed(0)} fps on your saved settings.</span>
        <button className="go" onClick={() => { const to = recommend.to; setRecommend(null); p.onRecommended?.(to); }}>Switch to recommended settings<small>{recommend.to.quality} quality · 60 fps cap · restarts this run</small></button>
        <button className="x" aria-label="Keep my settings" onClick={() => setRecommend(null)}>✕</button>
      </div>}
      {flash && <div key={flash.key} className={`g1-flash ${flash.side}`} />}
      {p.showPerf && <details className="g1-perf g1-glass"><summary>perf</summary>{perfText}</details>}
    </div>}
    {/* STOP: always visible, never covered: its own top layer above every overlay (the rotate card carries its own) */}
    {createPortal(<div className="g1 g1-stop-layer"><button className={`g1-stop ${latched ? 'is-latched' : ''}`} data-testid={latched ? 'hud-release' : 'hud-stop'} onPointerDown={stopDown}
      onPointerUp={() => setHoldStart(null)} onPointerLeave={() => setHoldStart(null)} onClick={(e) => { if (e.detail === 0) { if (latched) release(); else stop(); } }}
      aria-label={latched ? 'STOPPED: hold to release (R)' : 'STOP (Space)'}>
      <span>{latched ? 'HOLD' : 'STOP'}{desktop && <kbd>{latched ? 'R' : 'SPACE'}</kbd>}</span>
      {holdStart !== null && <i className="hold" style={{ width: '100%', transition: `width ${STOP_HOLD_MS}ms linear` }} />}
    </button></div>, document.body)}
    {mapOpen && world && occ.current && <TacticalMap world={world} occupancy={occ.current} marks={marks} onGoal={setGoalAt} onClose={() => setMapOpen(false)} />}
    {tutorial && <Tutorial onDone={() => { setTutorial(false); p.onTutorialDone(); }} />}
    <section className="g1-rotate"><Navigation2 size={32} /><h2>Rotate your phone</h2><p className="g1-note">COCO has room to play in landscape.</p>
      {/* G1.13: on the real Nothing Phone (1) the card covered PLAY, so nothing could ask for full
          screen; this tap can (a user gesture): full screen + a landscape lock, then the game starts.
          A browser that refuses (iPhone Safari) leaves this card, as before. */}
      <button className="g1-big small" data-testid="g1-rotate-play" onClick={() => { void enterPhonePlay(); if (!started) begin(); }}>▶ PLAY IN LANDSCAPE</button>
      <button className={`g1-stop ${latched ? 'is-latched' : ''}`} onPointerDown={(e) => { e.stopPropagation(); if (!latched) stop(); }} onClick={(e) => { if (e.detail === 0 && !latched) stop(); }}>STOP</button>
      <a className="g1-big ghost small" href={`${BASE}?view=play`}>Back to games</a></section>
  </div>;
}

const TUT = [
  { title: 'Drag to drive', text: 'Put your left thumb anywhere on the left half and drag.', thumb: { left: '18%', bottom: '22%' } },
  { title: 'Tap GRAB when the can glows', text: 'Grasp Assist drives in and picks it up with the arm.', thumb: { right: '6%', bottom: '8%' } },
  { title: 'STOP stops everything', text: 'Hold it to release. STOP always wins.', thumb: { right: '6%', bottom: '36%' } },
  { title: 'SIM shows what COCO computes', text: 'The same moment as RViz would draw it: frames, LiDAR, costmaps, the plan.', thumb: { right: '4%', top: '4%' } },
];
function Tutorial({ onDone }: { onDone: () => void }) {
  const [k, setK] = useState(0);
  useEffect(() => { const t = setTimeout(() => (k + 1 < TUT.length ? setK(k + 1) : onDone()), 5000); return () => clearTimeout(t); }, [k, onDone]);
  const step = TUT[k];
  return <div className="g1-tut" data-testid="g1-tutorial" onClick={() => (k + 1 < TUT.length ? setK(k + 1) : onDone())}>
    <div className="g1-thumb" style={step.thumb} />
    <div className="g1-tut-card g1-glass"><div className="g1-eyebrow">{k + 1} / {TUT.length}</div><h2>{step.title}</h2><p className="g1-note">{step.text}</p>
      <button className="g1-big ghost small" onClick={(e) => { e.stopPropagation(); onDone(); }}>SKIP</button></div>
  </div>;
}

export type { InputRow };
