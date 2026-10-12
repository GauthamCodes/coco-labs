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
import { ArenaPlayPanel } from '../play/ArenaPlayPanel';
import { EvidenceBadge, ModeNav } from '../ui/ModeNav';
import { Compare, type CompareState } from './Compare';
import { Joystick } from './Joystick';
import { PerfOverlay } from './PerfOverlay';
import { perf } from './perf';
import { SPEC_FILES, specFileFor, wallMs, type InputRow, type PlanInfo, type Tick, type World } from './protocol';
import { currentTheme, PALETTES } from './render/palette';
import { PlanStore, type CellInfo } from './render/planStore';
import { parseConverted, type ConvertedRun } from './replay';
import { attachScans, caseLens } from './replay_case';
import { loadCase } from './case_load';
import type { ReadMessage } from '../schemas/mcap';
import { fromBinary } from '@bufbuild/protobuf';
import { WorldGridSchema } from '../schemas/gen/coco/world/v1/world_pb';

/** "x,y" or "x,y,theta" from a URL parameter (M3.3: a comparison's goal or kidnap target), else null. */
function parseXY(v: string | null, n: 2 | 3): number[] | null {
  if (!v) return null;
  const xs = v.split(',').map(Number);
  return xs.length === n && xs.every(Number.isFinite) ? xs : null;
}
import { ArenaRenderer, DEFAULT_LAYERS, type LayerVisibility } from './render/Renderer';
import { CAMERA_MODES, type CameraMode } from './render/scene3d';
import type { Elevation } from './render/drape';
import { TIER_CHOICES, type Tier, type TierChoice } from './render/quality';
import { actionFor, HOLD_TO_RESET_MS, loadBindings, rebind, resetBindings, type Action, type Bindings } from './controls';
import { Help, type Settings } from './Help';
import { Hud } from './Hud';
import { MotorSound } from './motor';
import { isBool, readPref, reducedMotion, writePref } from '../prefs';
import { PHONE_DEFAULT_CAMERA } from '../../site.config';
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
import { startLensStress } from './stress';

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

export function ArenaApp() {
  const params = new URLSearchParams(window.location.search);
  /**
   * M4.3: ?world=v2 is the terrain (World Spec v2); v1 stays the default for every existing link.
   * The attract recording was made on v1, so a v2 page has none (M4.9 makes the 3D landing): it
   * opens live, and the live v2 world is the one drawn.
   */
  const specFile = specFileFor(params.get('world'));
  const showPerf = params.has('perf');
  const source: PyodideSource = params.get('pyodide') === 'cdn' ? 'cdn' : 'self';
  const runParam = params.get('run');
  const replayParam = params.get('replay');
  const attractPolicy: AttractPolicy = ATTRACT_POLICIES.includes(params.get('attract') as AttractPolicy)
    ? params.get('attract') as AttractPolicy : DEFAULT_ATTRACT_POLICY;
  const recId = replayParam && /^[a-z0-9_]{1,64}$/.test(replayParam) ? replayParam : null;
  // M3.3: a Case File (a recording of the full stack, converted by the ROS-to-event adapter)
  const caseParam = recId ? null : params.get('casefile');
  const caseId = caseParam && /^[a-z0-9_]{1,64}$/.test(caseParam) ? caseParam : null;
  const recordedId = recId ?? caseId;
  // M3.3: the model side of a Case File comparison starts from the recording's own goal or kidnap target
  const urlGoal = parseXY(params.get('goal'), 2);
  const urlKidnap = parseXY(params.get('kidnap'), 3);
  // a Learn mission's beat (M2.8): its settings, sent once the live model is up, in place of the lens's defaults
  const cfgLines = cfgFromParams(params);
  const allLayers = params.get('layers') === 'all';
  const missionBack = missionBackLink(params);
  // M3.5: a Play challenge played here (map the arena; the Case File detective)
  const playParam = params.get('play');
  const playLevel = params.get('pl');
  const playOn = (playParam === 'map-the-arena' || playParam === 'case-file-detective' || playParam === 'race-the-ghost')
    && !!playLevel && /^[a-z0-9-]{1,64}$/.test(playLevel);
  /** M4.8: a race takes only teleop and STOP (coco_lab.race): goals, grasps, hand-backs and resets are off */
  const raceOn = playOn && playParam === 'race-the-ghost';
  const gaps = useGaps(import.meta.env.BASE_URL);
  const cfgInitial = Object.fromEntries(cfgLines.map((c) => [c.slice(0, c.indexOf('=')), c.slice(c.indexOf('=') + 1)]));
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const [world, setWorld] = useState<World | null>(null);
  const [liveReady, setLiveReady] = useState(false);
  const [mode, setModeState] = useState<Mode>(runParam ? 'replay' : recordedId ? 'recording' : specFile === SPEC_FILES.v2 ? 'live' : 'attract');
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
  /** The World Spec's world -> map offset: where the 3D arena (in Gazebo's world frame) sits. */
  const worldToMap = useRef<[number, number]>([0, 0]);
  /** M4.4: World Spec v2's ramps and platforms (none on v1), for decals that follow the terrain */
  const elevation = useRef<Elevation[]>([]);
  /** M4.4: what the quality tiers last said (a tier change, or the fallback to top-down) */
  const [qualityNote, setQualityNote] = useState<string | null>(null);
  /** M4.4: the tier override (settings; ?quality= for harnesses) and the tier drawing now. M4.5 persists the choice. */
  const [tierChoice, setTierChoice] = useState<TierChoice>(TIER_CHOICES.find((t) => t === params.get('quality')) ?? 'auto');
  const [tierNow, setTierNow] = useState<Tier | null>(null);
  // M4.1: `?camera=follow|orbit|robot_eye` opens a perspective camera; top-down otherwise (until M4.5)
  /**
   * M4.5 (D1): 3D is the default experience on the plain Arena; a page opened for a mission, a challenge,
   * a Case File, a replay or a run link stays top-down until M4.6-M4.8 bring those into 3D. A phone follows
   * PHONE_DEFAULT_CAMERA (site.config.ts: the feasibility gate's verdict). ?camera= wins, then the
   * camera the person last chose (the preferences module).
   */
  const coarse = (() => { try { return window.matchMedia?.('(pointer: coarse)').matches ?? false; } catch { return false; } })();
  const plainArena = !runParam && !replayParam && !recordedId && !playParam && !params.get('mission');
  const storedCamera = readPref<CameraMode | null>('camera', null, (v): v is CameraMode | null => v === null || CAMERA_MODES.includes(v as CameraMode));
  // M4.6: precision tasks open in top-down: the Inspect level (cell by cell, value by value)
  const precision = params.get('level') === 'inspect';
  // M4.7: a Case File opens in 3D too (its recording carries Gazebo's 3D truth), as does its MODEL pane
  const threeD = (plainArena || !!caseId) && !precision && !(coarse && PHONE_DEFAULT_CAMERA === 'topdown');
  const defaultCamera: CameraMode = threeD ? 'follow' : 'topdown';
  const initialCamera: CameraMode = CAMERA_MODES.find((m) => m === params.get('camera'))
    ?? (plainArena && !precision ? storedCamera : null) ?? defaultCamera;
  const [camera, setCamera] = useState<CameraMode>(initialCamera);
  /** the robot's level of detail: low on a touch screen, else high; ?lod= overrides (harnesses) */
  const robotLod: 'low' | 'high' = params.get('lod') === 'low' || params.get('lod') === 'high'
    ? params.get('lod') as 'low' | 'high' : coarse ? 'low' : 'high';
  /** M4.5: STOP is latched until R releases it; holding R resets the robot home */
  const [latched, setLatched] = useState(false);
  const latchedRef = useRef(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [bindings, setBindings] = useState<Bindings>(() => loadBindings());
  const bindingsRef = useRef(bindings);
  bindingsRef.current = bindings;
  const [settings, setSettings] = useState<Settings>(() => ({
    motion: reducedMotion(), sound: false,   // the sound is off by default, and starts only on a click
    bars: readPref('bars', false, isBool), tank: readPref('tank', false, isBool),
  }));
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const motor = useRef(new MotorSound());
  /** M4.5: starts the 3D view (its assets load once); set when the world is known */
  const start3D = useRef<(() => Promise<void>) | null>(null);
  /** the lenses keys 1-5 can open now (as the lens bar offers them) */
  const lensesNow = useRef<Set<string>>(new Set(['plan']));
  /** wheel speed that fills a HUD bar: the teleop maximum over the spec's wheel radius (rad/s) */
  const fullWheel = useRef(1);
  /** M4.6: the view turned 3D or top-down: redraw the lens layers at their new height */
  const lensRedraw = useRef(false);
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
    if (latchedRef.current || raceOn) return;   // STOP is latched: R releases it (M4.5); no goals in a race (M4.8)
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
      ll.current.onDecal = (m) => rr?.registerDecal(m);
      // M4.6: in 3D every lens mark stands on the walkable surface, and beliefs are columns
      ll.current.lift = (x, y) => rr?.liftAt(x, y) ?? 0;
      rr.onViewChange = (on) => { if (ll.current) ll.current.columns = on; lensRedraw.current = true; };
      rr.onQuality = (e) => {
        if (e.kind === 'tier') setTierNow(e.tier);
        if (e.kind === 'fallback') setQualityNote(`3D is too slow on this device (${e.reason}), so this is the top-down view.`);
        perf.mark(e.kind === 'fallback' ? 'quality_fallback' : `quality_${e.tier}`, wallMs());
      };
    } catch (e) {
      // M4.4: no WebGL 2, no view at all (three.js has no WebGL 1 path, so top-down needs it too);
      // the model and the panels still run
      setError((e as Error).message === 'WebGL 2 is required'
        ? 'This browser has no WebGL 2, so the arena cannot be drawn here. The panels still run.'
        : `renderer: ${(e as Error).message}`);
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
      // the 3D arena (M4.1): loaded once, when a 3D camera is first wanted (D1: at once on the plain Arena)
      let started: Promise<void> | null = null;
      start3D.current = () => {
        if (started) return started;
        const base = import.meta.env.BASE_URL;
        const lod = robotLod;
        started = specP.then(() => rr!.enable3D({ arena: `${base}assets3d/arena.glb`, robot: `${base}assets3d/robot_${lod}.glb`,
          buffers: early3D ?? undefined },
          worldToMap.current, w.targets, elevation.current, tierChoice))
          .then(() => {
            setTierNow(rr!.quality?.tier ?? null);
            perf.mark('world3d_ready', wallMs());   // the arena drawn (the robot may still be its placeholder)
            void rr!.three?.robotReady.then(() => perf.mark('world3d_robot', wallMs()));
          })
          .catch((e) => { setError(`3D arena: ${(e as Error).message}`); rr!.setCameraMode('topdown'); setCamera('topdown'); });
        return started;
      };
      if (initialCamera !== 'topdown') {
        rr.setCameraMode(initialCamera);
        void start3D.current();
      }
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

    // M4.7: a page that opens in 3D starts its 3D assets at once, beside the recording or the model, so the
    // first 3D frame waits for the slower of the two, not for both in turn
    const bytes = (u: string) => fetch(u, { credentials: 'omit' }).then((x) => { if (!x.ok) throw new Error(u); return x.arrayBuffer(); });
    // a recording's first frame comes first: there the robot's file waits for it (the arena is 28 KB; the
    // body is a placeholder until the robot lands), so on 4G it does not share the line with the recording
    const robotUrl = `${import.meta.env.BASE_URL}assets3d/robot_${robotLod}.glb`;
    const early3D = initialCamera === 'topdown' ? null : {
      arena: bytes(`${import.meta.env.BASE_URL}assets3d/arena.glb`),
      robot: recordedId ? perf.when('recording_ready').then(() => bytes(robotUrl)) : bytes(robotUrl),
    };
    if (early3D) void Promise.all([early3D.arena, early3D.robot]).then(() => perf.mark('world3d_assets', wallMs())).catch(() => {});
    const outlineP = fetch(`${import.meta.env.BASE_URL}generated/arena/robot_outline.json`, { credentials: 'omit' })
      .then((x) => x.json()).then((j) => { outline.current = j.polygon; }).catch(() => {});
    const specP = fetch(`${import.meta.env.BASE_URL}generated/arena/${specFile}`, { credentials: 'omit' })
      .then((x) => x.arrayBuffer()).then((b) => {
        try {
          const spec = JSON.parse(new TextDecoder().decode(b));
          worldToMap.current = spec.world_to_map;
          elevation.current = spec.elevation ?? [];
          fullWheel.current = spec.robot.limits.teleop_linear / spec.robot.wheel_radius;
        } catch { /* the 3D arena then sits at the world origin, decals flat */ }
        return sha256Hex(new Uint8Array(b));
      }).then((h) => { specSha.current = h; });

    // the runs list is for the nav: on a recording's page it waits for the first frame (M4.7, 4G)
    void (recordedId ? perf.when('recording_ready') : Promise.resolve(0))
      .then(() => fetch(`${import.meta.env.BASE_URL}generated/v2/index.json`, { credentials: 'omit' }))
      .then((x) => (x.ok ? x.json() : { runs: [] })).then((j) => setRuns(j.runs ?? [])).catch(() => {});
    if (replayParam && !recId) setError(`no recorded run "${replayParam}"`);
    if (caseParam && !caseId) setError(`no Case File "${caseParam}"`);
    // a converted Lab 1 run, or a Case File: played, never simulated
    if (recordedId) {
      const base = import.meta.env.BASE_URL;
      const fetchBytes = (url: string, what: string) => fetch(url, { credentials: 'omit' })
        .then((x) => { if (!x.ok) throw new Error(what); return x.arrayBuffer(); }).then((b) => new Uint8Array(b));
      if (caseId) perf.mark('casefile_fetch_start', wallMs());
      // a Case File's first frame needs everything but its scans; the scans follow (D6)
      let caseScans: Promise<ReadMessage[]> | null = null;
      const loaded = caseId
        ? loadCase(base, caseId, fetchBytes(`${base}generated/casefiles/world.grid.bin`, 'the Case Files\' map is missing')
          .then((g) => fromBinary(WorldGridSchema, g))).then(({ rec, scans }) => { caseScans = scans; return rec; })
        : fetchBytes(`${base}generated/v2/${recId}.mcap`, `no recorded run "${recId}"`).then((b) => parseConverted(b));
      void loaded
        .then(async (rec) => {
          await outlineP;
          const s = new ArenaSession(rec.world.width, rec.world.height, rec.world.dt);
          attract.current = { rec, session: s, player: new AttractPlayer(rec, s) };
          setWorldOnce(rec.world, rec.occupancy);
          setSession(s);
          setConverted(rec);
          // a Case File's LiDAR is the stack's recorded scans: shown when it has them
          setLayers((l) => ({ ...l, lidar: !!caseId && rec.world.lidar.samples > 0, footprint: false,
            ...(rec.evidence === 'MODEL' ? { robot: false, truth: false } : {}) }));
          if (caseId) {
            setLens(caseLens(rec));
            // a Case File is loaded whole, then played from its start: every moment is a seek away
            // (mission 7 and the detective challenge scrub straight to one)
            const p = attract.current.player;
            while (p.step()) { /* every recorded tick into the session's history */ }
            // a mission's beat (M3.4) opens it at the moment it is about, paused there
            const at = Number(params.get('tick'));
            if (Number.isInteger(at) && at >= 1) {
              s.seekTick(at);
              s.playing = false;
            } else {
              s.seekTick(rec.ticks[0]?.tick ?? 1);
              s.playing = true;
            }
            perf.mark('recording_ready', wallMs());
            // the recorded scans, onto every tick already loaded; then the LiDAR layer shows them
            void caseScans?.then((msgs) => {
              if (attachScans(rec, s, msgs)) {
                rr?.setLidar(rec.world.lidar);
                setLayers((l) => ({ ...l, lidar: true }));
              }
              perf.mark('scans_ready', wallMs());
            }).catch((e) => setError(`Case File: ${(e as Error).message}`));
          }
          // a converted Lab 5 drive (M2.7) is shown through the Move lens: Nav2's own candidates
          else if (rec.headers?.some((h) => h.channel === 'coco.control.local.header.v1')) setLens('move');
        })
        .catch((e) => setError(`${caseId ? 'Case File' : 'recorded run'}: ${(e as Error).message}`));
    }
    // attract: the recording (not in a replay), started as the policy says (M2.0, measured)
    if (!runParam && !recordedId && specFile === SPEC_FILES.v1) {
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
        if (ll.current && worldRef.current && (lensRedraw.current || s.families.version !== drawnVersion || (t?.tick ?? 0) !== drawnTick)) {
          lensRedraw.current = false;
          drawnVersion = s.families.version; drawnTick = t?.tick ?? 0;
          drawLenses({ layers: ll.current, session: s, tick: drawnTick, world: worldRef.current,
            on: (id) => lensOnRef.current[id] ?? false });
        }
        if (t && t.tick !== shownTick) {
          shownTick = t.tick;
          rr!.setPose(t.pose, t.truth ?? t.pose, t.tilt, t.truth_tilt);
          rr!.setWheels(t.wheels ?? [0, 0]);
          motor.current.update(t.wheels ?? [0, 0], fullWheel.current);
          if (t.grasp) rr!.setGrasp(t.grasp);
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

    if (!recordedId) client.current = new ArenaClient({
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
    }, { pyodide: source, seed: replayRun?.seed ?? Number(params.get('seed') ?? 1), spec: specFile });

    window.__cocoArena = {
      client: client.current, queue: queue.current, last: null, renderer: rr, session: active, goal,
      mode: () => modeRef.current, log: () => log.current, layerIds: () => ll.current?.ids() ?? [],
    };
    // ?stress: M1's renderer load; ?stress=m2: M2's lens load, rebuilt at 10 Hz (stress.ts)
    let stopStress: (() => void) | null = null;
    void client.current?.whenReady().then(() => {
      if (params.get('stress') === 'm2') {
        const wait = setInterval(() => {
          if (!ll.current || !worldRef.current) return;
          clearInterval(wait);
          stopStress = startLensStress(ll.current, worldRef.current);
        }, 100);
      } else if (params.has('stress')) rr?.addStress(50_000, 20_000);
    }, () => {});
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

    // the keyboard (M4.5; README §5.5): every action through the remappable bindings (./controls)
    const held = new Set<Action>();
    let resetTimer = 0;
    const sendTeleop = () => {
      const lim = client.current?.world?.limits;
      if (!lim || latchedRef.current) return;
      let f = 0; let turn = 0;
      if (held.has('forward')) f += 1;
      if (held.has('reverse')) f -= 1;
      if (held.has('left')) turn += 1;
      if (held.has('right')) turn -= 1;
      // precision halves the speed, never above the real maximum
      const k = 0.6 * (held.has('precision') ? 0.5 : 1);
      takeOver();
      queue.current.push({ kind: 'teleop', linear: Math.sign(f) * lim.teleop_linear * k, angular: Math.sign(turn) * lim.teleop_angular * k });
    };
    const DRIVE: Action[] = ['forward', 'reverse', 'left', 'right', 'precision'];
    const keydown = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.matches?.('input, select, textarea, button')) return;
      const a = actionFor(e.code, bindingsRef.current);
      if (!a) return;
      const onPage = document.activeElement === document.body || document.activeElement === cv;
      // Tab keeps walking the controls unless the page itself has focus
      if (a === 'autonomy' && (e.shiftKey || !onPage)) return;
      if (a === 'help') { e.preventDefault(); if (!e.repeat) setHelpOpen((o) => !o); return; }
      if (a === 'camera_next' || a === 'camera_follow') {
        e.preventDefault();
        if (!e.repeat) chooseCameraRef.current(a === 'camera_follow' ? 'follow' : 'next');
        return;
      }
      if (a.startsWith('lens_')) {
        const L = LENSES[Number(a.slice(5)) - 1];
        if (L && lensesNow.current.has(L.id) && !e.repeat) { e.preventDefault(); setLens(L.id); }
        return;
      }
      const s = active();
      if (a === 'pause' || a === 'step_back' || a === 'step_forward') {
        e.preventDefault();
        if (!s) return;
        if (a === 'pause') { if (!e.repeat) s.playing = !s.playing; return; }
        s.playing = false;
        const at = s.shownTick?.tick ?? 0;
        s.seekTick(Math.max(0, at + (a === 'step_back' ? -1 : 1)));
        return;
      }
      if (['replay', 'recording'].includes(modeRef.current)) return;
      if (a === 'stop') {
        e.preventDefault(); held.clear(); takeOver(); queue.current.push({ kind: 'stop' });
        latchedRef.current = true; setLatched(true);
        return;
      }
      if (a === 'release') {
        e.preventDefault();
        if (e.repeat) return;
        latchedRef.current = false; setLatched(false);
        clearTimeout(resetTimer);
        if (!raceOn) resetTimer = window.setTimeout(() => { takeOver(); queue.current.push({ kind: 'reset' }); }, HOLD_TO_RESET_MS);
        return;
      }
      if (a === 'context' || a === 'autonomy') {
        e.preventDefault();
        if (e.repeat || latchedRef.current || raceOn) return;
        held.clear(); takeOver();
        queue.current.push({ kind: a === 'context' ? 'grasp' : 'autonomy' });
        return;
      }
      if (DRIVE.includes(a)) {
        e.preventDefault();
        if (e.repeat) return;
        held.add(a);
        sendTeleop();
      }
    };
    const keyup = (e: KeyboardEvent) => {
      const a = actionFor(e.code, bindingsRef.current);
      if (a === 'release') clearTimeout(resetTimer);   // released before the hold: release only
      if (a && held.delete(a)) sendTeleop();
    };
    window.addEventListener('keydown', keydown);
    window.addEventListener('keyup', keyup);
    return () => {
      clearInterval(ui);
      stopStress?.();
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
    // ?layers=all (the M2 laptop budget): every lens's default layers at once
    if (allLayers) for (const L of LENSES) if (L.id !== 'plan') for (const id of defaultLayers(L, level)) on[id] = true;
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
  // M3.3: a Case File comparison's model side -- the recording's own kidnap target, then its goal, once, as inputs
  const urlInputsSent = useRef(false);
  useEffect(() => {
    if ((!urlGoal && !urlKidnap) || urlInputsSent.current || !liveReady || mode === 'replay' || mode === 'recording') return;
    urlInputsSent.current = true;
    if (urlKidnap) queue.current.push({ kind: 'kidnap', x: urlKidnap[0], y: urlKidnap[1], theta: urlKidnap[2], has_theta: true });
    if (urlGoal) goal(urlGoal[0], urlGoal[1]);
  }, [liveReady, mode, goal]); // eslint-disable-line react-hooks/exhaustive-deps -- the URL's, fixed
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
    if (!lim || ['replay', 'recording'].includes(modeRef.current) || latchedRef.current) return;
    const lin = Math.round(dy * 10) / 10;
    const ang = Math.round(-dx * 10) / 10;
    if (lin === lastJoy.current[0] && ang === lastJoy.current[1]) return;
    lastJoy.current = [lin, ang];
    takeOver();
    queue.current.push({ kind: 'teleop', linear: lin * lim.teleop_linear, angular: ang * lim.teleop_angular });
  };
  /** M4.5: a camera by name, 'next' (C: follow, orbit, robot-eye, top-down, around) or back to follow (V). */
  const chooseCamera = (want: CameraMode | 'next') => {
    const order: CameraMode[] = ['follow', 'orbit', 'robot_eye', 'topdown'];
    const mode = want === 'next' ? order[(order.indexOf(camera) + 1) % order.length] : want;
    const dur = settingsRef.current.motion ? 0 : 0.4;
    setCamera(mode);
    setQualityNote(null);
    writePref('camera', mode);
    if (mode === 'topdown') { r.current?.setCameraMode('topdown', dur); return; }
    const go = start3D.current?.();
    if (go) void go.then(() => r.current?.setCameraMode(mode, dur));
  };
  const chooseCameraRef = useRef(chooseCamera);
  chooseCameraRef.current = chooseCamera;
  /** M4.5: tank mode: a slider per side, as wheel speeds; the command is the (v, w) they make */
  const onTank = (left: number, right: number) => {
    const lim = client.current?.world?.limits;
    if (!lim || latchedRef.current || ['replay', 'recording'].includes(modeRef.current)) return;
    const v = ((left + right) / 2) * lim.teleop_linear;
    const w = ((right - left) / 2) * lim.teleop_angular;
    takeOver();
    queue.current.push({ kind: 'teleop', linear: v, angular: w });
  };
  const changeSetting = (k: keyof Settings, v: boolean) => {
    setSettings((o) => ({ ...o, [k]: v }));
    if (k === 'sound') { if (v) motor.current.start(); else motor.current.stop(); }
    else writePref(k, v);
  };
  const makeShare = () => {
    const t = lastTick.current;
    if (!t || !specSha.current) return;
    setShare(shareUrl({ v: 1, spec: specSha.current, seed: Number(params.get('seed') ?? 1), ticks: t.tick, chain: t.chain,
      inputs: log.current }, import.meta.env.BASE_URL) + (specFile === SPEC_FILES.v2 ? '&world=v2' : ''));
  };

  const tick = session?.shownTick ?? null;
  const lensesAvailable = new Set<LensId>(LENSES.filter((l) => l.id === 'plan' || packs.has(l.pack)
    || (converted?.headers ?? []).some((h) => l.families.some((f) => h.channel.includes(f)))).map((l) => l.id));
  lensesNow.current = lensesAvailable;
  const plan = tick ? [...(session?.history ?? [])].reverse().find((h) => h.tick <= tick.tick && h.plans.length)?.plans.at(-1) ?? null : null;
  const res = world?.resolution ?? 0.05;
  const evidence = converted?.evidence ?? 'MODEL';
  const note = converted && tick ? converted.notes.filter((n) => n.tick <= tick.tick).at(-1)?.text ?? null : null;
  const stats = converted?.results as Record<string, any> | null | undefined; // eslint-disable-line @typescript-eslint/no-explicit-any
  const m2 = (v: unknown) => (typeof v === 'number' ? `${v.toFixed(3)} m` : '—');
  const showLive = mode !== 'recording';

  return (
    <main className="arena" data-testid="arena">
      {/* a pane inside the Case Files comparison (embed=1) shows its badge, not the modes again */}
      {params.get('embed') === '1'
        ? <p className="embed-head"><EvidenceBadge evidence={evidence} /></p>
        : <ModeNav current={params.has('casefile') ? 'casefiles' : 'sandbox'} evidence={evidence} />}
      {missionBack && <p className="mission-back"><a href={`${import.meta.env.BASE_URL}${missionBack}`} data-testid="mission-back">
        ← Back to the mission</a></p>}
      {error && <p className="error" role="alert">{error}</p>}
      {qualityNote && <p className="notice" role="status">{qualityNote}</p>}
      {helpOpen && (
        <Help bindings={bindings} settings={settings} coarse={coarse}
          onRebind={(a, code) => setBindings((b) => rebind(b, a, code))}
          onReset={() => setBindings(resetBindings())}
          onSetting={changeSetting} onClose={() => setHelpOpen(false)} />
      )}
      {playOn && <ArenaPlayPanel challenge={playParam!} levelId={playLevel!}
        live={playParam === 'map-the-arena' || raceOn ? client.current : null} liveReady={liveReady}
        lastTick={() => lastTick.current} shownTick={() => session?.shownTick?.tick ?? null} log={() => log.current}
        onGhost={(flag, ghost) => r.current?.setRace(flag, ghost)} />}
      <p className={`arena-banner ${mode}`} data-testid="arena-mode" data-mode={mode}>
        {mode === 'attract' && (liveReady
          ? 'A recorded demo (MODEL, made when this site was built). Click or tap the map to give COCO a goal — the live model takes over.'
          : 'A recorded demo (MODEL, made when this site was built) while the live model loads… Click or tap the map to take over.')}
        {mode === 'live' && (coarse
          ? 'Live model: coco_lab running in your browser. Tap the floor for a goal, drive with the joystick; STOP latches until you release it. Two fingers orbit and zoom.'
          : 'Live model: coco_lab running in your browser. Click a goal, drive with W A S D / arrows or the joystick; Space is a latched STOP (R releases it). H shows every control.')}
        {mode === 'replay' && `Shared run: ${replay.status}`}
        {mode === 'recording' && converted && (converted.evidence === 'STACK'
          ? `Recorded run (STACK): COCO driven by the full ROS 2 stack in Gazebo — ${converted.title}. The solid robot is where the stack believed it was (AMCL); the outline is ground truth.`
            + (converted.pose3d ? ' In 3D the robot\'s body is Gazebo\'s ground truth, with the height and tilt it recorded; the solid footprint is the belief.' : '')
          : `Glass-box trace (MODEL): ${converted.title}, computed by coco_lab. No world, no robot: the search alone.`)}
      </p>
      {mode === 'recording' && converted && converted.evidence === 'STACK' && !converted.pose3d && (
        <p className="chip planar" data-testid="planar-chip" title="This recording kept only x, y and heading: its height, roll and pitch were never recorded, so they are not drawn or guessed">
          planar recording · no height or tilt recorded
        </p>
      )}
      <LensBar lens={lens} level={level} focus={focus} available={lensesAvailable}
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
        {world && mode === 'live' && (
          <Hud tick={tick} latched={latched} fullWheel={fullWheel.current} showBars={settings.bars} camera={camera} coarse={coarse}
            tank={settings.tank}
            onStop={() => { takeOver(); queue.current.push({ kind: 'stop' }); latchedRef.current = true; setLatched(true); }}
            onContext={() => { if (!latchedRef.current) { takeOver(); queue.current.push({ kind: 'grasp' }); } }}
            onCamera={() => chooseCamera('next')}
            onAutonomy={() => { if (!latchedRef.current) { takeOver(); queue.current.push({ kind: 'autonomy' }); } }}
            onTank={onTank} />
        )}
        {latched && coarse && (
          <button type="button" className="hud-release" onClick={() => { latchedRef.current = false; setLatched(false); }}
            data-testid="hud-release">Release STOP</button>
        )}
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
            {tierNow && (
              <div className="arena-row">
                <label className="layer-toggle">3D quality{' '}
                  <select value={tierChoice} data-testid="quality-tier" onChange={(e) => {
                    const c = e.target.value as TierChoice;
                    setTierChoice(c);
                    r.current?.setTier(c);
                    setTierNow(r.current?.quality?.tier ?? null);
                  }}>
                    {TIER_CHOICES.map((t) => <option key={t} value={t}>{t === 'auto' ? `auto (now ${tierNow})` : t}</option>)}
                  </select>
                </label>
                <label className="layer-toggle" title="Walls, columns and landmarks stop at 0.35 m, so every layer stays in view">
                  <input type="checkbox" data-testid="low-walls" onChange={(e) => { if (r.current?.three) r.current.three.lowWalls = e.target.checked; }} />
                  low walls
                </label>
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
                <button type="button" className="seg-btn" data-testid="help-open" onClick={() => setHelpOpen(true)}>Controls (H)</button>
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
