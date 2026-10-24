// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.2: Play's game shell. `?view=play` is the mode select; a game opens as
 *
 *   ?view=play&game=fetch_rush&seed=1          Fetch Rush on the Depot
 *   ?view=play&game=free&world=depot|proving   Free Drive
 *   ?view=play&game=fetch_colour&colour=red    Fetch by colour (owner request 2026-10-24; src/game/fetch_colour.ts)
 *
 * Every M5 Play link (`&c=`, `&l=`, `&s=`, `&z=`) still opens M5's
 * challenges (main.tsx routes those to PlayApp before this shell). The
 * pause menu, settings and results live here; Play itself is PlayGame.
 */

import { chosenPlanner, PLANNER_LABEL, PLANNER_WHAT, PLAY_PLANNERS, type PlayPlanner } from './planners';
import { useEffect, useState, type CSSProperties } from 'react';
import { ArrowLeft, Lock } from 'lucide-react';
import { isBool, readPref, readRaw, writePref, writeRaw } from '../prefs';
import { navigate } from '../ui/navigation';
import { PlayGame } from './PlayGame';
import type { FetchColourId, GameKind, WorldId } from './session';
import { colourBestKey, colourFromQuery, colourHref } from './fetch_colour';
import type { Tier } from './world/build3d';
import { pickTier } from './tier';
import './fonts.css';
import './game.css';
import { FETCH_COLOURS, FETCH_RUSH_SHIFTS, colourChip, fetchRushMode, type FetchRushMode } from './rules_view';
import { saveBag } from '../ros/bag_saver';
import { PlannerInset, type InsetData } from './hud/PlannerInset';
import { FETCH_RUSH_RULES } from './rules_view';
import { ghostFor, loadGhostIndex, type GhostIndex } from './stack_ghost';

const BASE = import.meta.env.BASE_URL;

export interface GameResult {
  game: GameKind; seed: number; world: WorldId;
  card: Record<string, unknown> | null; stars: number | null; reference: Record<string, unknown> | null;
  record: Record<string, unknown> | null;
  /** the level's objects (map frame), to name the first order's goal for Compare */
  objects?: { id: string; x: number; y: number }[];
  /** G2.7: the planner's routes for the round and the path driven, for the results inset (MODEL) */
  inset?: InsetData;
  /** G2.6: the three-way comparison -- your run, the browser model's planner, Nav2 in Gazebo (STACK) */
  driven_m?: number;
  planner?: { route_m: number; reference_time_s: number | null };
  stack?: { driving_s: number; driven_m: number; legs: { id: string; status: string }[]; not: string[] };
}

// G1.12: the Full shift keeps its own bests; G2.1: rules 4 (new rounds), so new keys (rules 3's stay as they were)
// owner request 2026-10-24: bests are per AUTO planner (a like-for-like record); A*'s key is the one it always had
export const bestKey = (seed: number, mode: FetchRushMode = 'phone', planner: PlayPlanner = 'astar') =>
  `coco.play.best.v1.g1-fetch-rush.r4-${mode}.seed-${seed}${planner === 'astar' ? '' : `.planner-${planner}`}`;
export function readStars(seed: number, mode: FetchRushMode = 'phone', planner: PlayPlanner = 'astar'): number | null {
  try { const raw = readRaw(bestKey(seed, mode, planner)); return raw ? (JSON.parse(raw) as { stars: number }).stars : null; } catch { return null; }
}
function keepStars(seed: number, mode: FetchRushMode, planner: PlayPlanner, stars: number, net: number, time: number) {
  const old = readStars(seed, mode, planner);
  if (old !== null && old >= stars) return;
  writeRaw(bestKey(seed, mode, planner), JSON.stringify({ stars, net, time }));
}
/** Fetch by colour's bests: per colour, per AUTO planner (src/game/fetch_colour.ts) */
export function readColourStars(colour: FetchColourId, planner: PlayPlanner = 'astar'): number | null {
  try { const raw = readRaw(colourBestKey(colour, planner)); return raw ? (JSON.parse(raw) as { stars: number }).stars : null; } catch { return null; }
}
function keepColourStars(colour: FetchColourId, planner: PlayPlanner, stars: number, net: number, time: number) {
  const old = readColourStars(colour, planner);
  if (old !== null && old >= stars) return;
  writeRaw(colourBestKey(colour, planner), JSON.stringify({ stars, net, time }));
}
const starText = (n: number | null) => (n === null ? '☆☆☆' : '★'.repeat(n) + '☆'.repeat(3 - n));

export function GameApp() {
  const q = new URLSearchParams(window.location.search);
  const game = q.get('game') as GameKind | null;
  if (game === 'fetch_colour') {
    // owner request 2026-10-24: a missing or unknown colour opens the choice of colour
    const colour = colourFromQuery(q), planner = chosenPlanner(q.get('planner'));
    if (!colour) return <ColourChoice planner={planner} />;
    return <GameRun game={game} world="depot_colours" seed={1} mode="phone" race={false} planner={planner} colour={colour} />;
  }
  if (game !== 'fetch_rush' && game !== 'free') return <ModeSelect />;
  const world: WorldId = game === 'fetch_rush' ? 'depot' : q.get('world') === 'proving' ? 'proving' : 'depot';
  // Fetch Rush plays the shifts on file (rules_view); another seed opens shift 1. G1.12: &mode=full is the Full shift
  const asked = Math.max(1, Math.min(999, Number.parseInt(q.get('seed') ?? '1', 10) || 1));
  const seed = game === 'fetch_rush' && !FETCH_RUSH_SHIFTS.includes(asked) ? FETCH_RUSH_SHIFTS[0] : asked;
  const race = q.get('race') === 'nav2';
  return <GameRun game={game} world={world} seed={seed} mode={fetchRushMode(q.get('mode'))} race={race} planner={race ? 'astar' : chosenPlanner(q.get('planner'))} />;
}

function GameRun({ game, world, seed, mode, race, planner, colour }: { game: GameKind; world: WorldId; seed: number; mode: FetchRushMode; race: boolean; planner: PlayPlanner; colour?: FetchColourId }) {
  const [paused, setPaused] = useState(false);
  const [settings, setSettings] = useState(false);
  const [result, setResult] = useState<GameResult | null>(null);
  const [restartKey, setRestartKey] = useState(0);
  const [tier, setTier] = useState<Tier>(() => pickTier());
  const [tutorialSeen, setTutorialSeen] = useState(() => readPref('tutorial', false, isBool));
  // G1.11: the ghost route is precomputed with the round, so it is on unless switched off
  const [ghost, setGhost] = useState(() => readPref('ghost', true, isBool));
  const showPerf = new URLSearchParams(window.location.search).has('perf');
  useEffect(() => { document.documentElement.classList.add('playing-coco'); return () => document.documentElement.classList.remove('playing-coco'); }, []);
  const onResult = (r: GameResult) => {
    setResult(r);
    if (r.stars !== null && r.card && game === 'fetch_colour' && colour) keepColourStars(colour, planner, r.stars, Number(r.card.net_deliveries ?? 0), Number(r.card.time_used ?? 0));
    else if (r.stars !== null && r.card) keepStars(r.seed, mode, planner, r.stars, Number(r.card.net_deliveries ?? 0), Number(r.card.time_used ?? 0));
  };
  const restart = () => { setResult(null); setPaused(false); setRestartKey((k) => k + 1); };
  return <>
    <PlayGame key={`${restartKey}-${tier}`} world={world} game={game} seed={seed} mode={mode} tier={tier} paused={paused || !!result} onPause={() => setPaused((x) => !x)}
      onResult={onResult} restartKey={restartKey} showPerf={showPerf} tutorialSeen={tutorialSeen} ghost={ghost}
      onTutorialDone={() => { writePref('tutorial', true); setTutorialSeen(true); }} race={race} planner={planner} colour={colour}
      onRecommended={(to) => { writePref('quality', to.quality); writePref('phone120', to.phone120); setTier(to.quality); restart(); }} />
    {paused && !result && !settings && <section className="g1 g1-screen dim" data-testid="g1-pause-menu" style={{ position: 'fixed', zIndex: 25, background: 'rgba(8,10,14,.62)' }}>
      <div className="g1-eyebrow">PAUSED · {game === 'fetch_colour' ? `FETCH BY COLOUR · ${colourChip(colour ?? 'red')}` : game === 'fetch_rush' ? `FETCH RUSH · SHIFT ${seed}${mode === 'full' ? ' · FULL' : ''}` : `FREE DRIVE · ${world === 'depot' ? 'DEPOT' : 'PROVING GROUND'}`}</div>
      <nav className="g1-menu">
        <button className="main" autoFocus onClick={() => setPaused(false)}>RESUME</button>
        <button onClick={restart}>RESTART</button>
        <button onClick={() => setSettings(true)}>SETTINGS</button>
        <BagButton />
        <a href={`${BASE}?view=play`}>EXIT</a>
      </nav>
    </section>}
    {settings && <Settings tier={tier} onTier={setTier} ghost={ghost} onGhost={(g) => { writePref('ghost', g); setGhost(g); }} onClose={() => setSettings(false)} />}
    {result && <Results r={result} onAgain={restart} planner={race ? null : planner} colour={game === 'fetch_colour' ? colour ?? 'red' : null} />}
  </>;
}

function Settings({ tier, onTier, ghost, onGhost, onClose }: { tier: Tier; onTier: (t: Tier) => void; ghost: boolean; onGhost: (g: boolean) => void; onClose: () => void }) {
  const [sound, setSound] = useState(() => readPref('sound', false, isBool));
  const [haptics, setHaptics] = useState(() => readPref('haptics', true, isBool));
  const [hz120, setHz] = useState(() => readPref('phone120', false, isBool));
  const [hints, setHints] = useState(() => readPref('bars', true, isBool));
  return <section className="g1 g1-screen dim" data-testid="g1-settings" role="dialog" aria-label="Settings" style={{ position: 'fixed', zIndex: 26, background: 'rgba(8,10,14,.75)' }}>
    <div className="g1-eyebrow">SETTINGS</div>
    <div className="g1-settings">
      <label htmlFor="g1-q">Quality</label>
      <select id="g1-q" value={tier} onChange={(e) => { const t = e.target.value as Tier; writePref('quality', t); onTier(t); }}>
        <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select>
      <label htmlFor="g1-h">Haptics</label><input id="g1-h" type="checkbox" checked={haptics} onChange={(e) => { setHaptics(e.target.checked); writePref('haptics', e.target.checked); }} />
      <label htmlFor="g1-s">Sound</label><input id="g1-s" type="checkbox" checked={sound} onChange={(e) => { setSound(e.target.checked); writePref('sound', e.target.checked); }} />
      <label htmlFor="g1-f">Frame-rate cap</label>
      <select id="g1-f" value={hz120 ? '120' : '60'} onChange={(e) => { setHz(e.target.value === '120'); writePref('phone120', e.target.value === '120'); }}><option value="60">60 fps</option><option value="120">120 fps</option></select>
      <label htmlFor="g1-g">Planner ghost</label><input id="g1-g" type="checkbox" checked={ghost} onChange={(e) => onGhost(e.target.checked)} />
      <label htmlFor="g1-k">Control hints</label><input id="g1-k" type="checkbox" checked={hints} onChange={(e) => { setHints(e.target.checked); writePref('bars', e.target.checked); }} />
    </div>
    <p className="g1-note">Quality changes take effect at once and restart the drawing, not the run's rules. Saved in this browser only.</p>
    <nav className="g1-menu"><button className="main" autoFocus onClick={onClose}>DONE</button></nav>
  </section>;
}

function Results({ r, onAgain, planner, colour }: { r: GameResult; onAgain: () => void; planner: PlayPlanner | null; colour: FetchColourId | null }) {
  const what = colour ? 'colour' : 'shift';
  const c = r.card ?? {};
  const delivered = (c.delivered as { ghost: number | null; driven: number }[] | undefined) ?? [];
  const driven = delivered.reduce((s, d) => s + d.driven, 0), ghost = delivered.reduce((s, d) => s + (d.ghost ?? 0), 0);
  // the same level and the shift's first order: the planners from COCO's start to that object
  const first = (c.delivered as { object: string }[] | undefined)?.[0]?.object ?? ((c.orders as [string, string][] | undefined)?.[0]?.[0]);
  const obj = first ? r.objects?.find((o) => o.id === first) : undefined;
  const compare = `${BASE}?view=compare&world=depot${obj ? `&goal=${obj.x.toFixed(2)},${obj.y.toFixed(2)}` : ''}`;
  return <section className="g1 g1-screen dim" data-testid="g1-results" style={{ position: 'fixed', zIndex: 27, background: 'rgba(8,10,14,.8)' }}>
    <div className="g1-eyebrow" data-testid="results-title">{colour ? <>FETCH BY COLOUR · <span className="g2-colour-dot" data-colour={colour} aria-hidden /> {colourChip(colour)} ROD</> : <>FETCH RUSH · SHIFT {r.seed}</>} · RESULT</div>
    <div className="g1-bigstars" aria-label={`${r.stars ?? 0} of 3 stars`}>{r.stars === null ? <span className="off">☆☆☆</span> : <>{'★'.repeat(r.stars)}<span className="off">{'★'.repeat(3 - r.stars)}</span></>}</div>
    <div className="g1-cards">
      <div className="g1-stat g1-glass"><div className="k">TIME USED</div><div className="v num">{Number(c.time_used ?? 0).toFixed(1)}<small> s</small></div></div>
      <div className="g1-stat g1-glass"><div className="k">DELIVERIES</div><div className="v num">{String(c.deliveries ?? 0)}</div></div>
      <div className="g1-stat g1-glass"><div className="k">CONTACTS</div><div className="v num">{String(c.contacts ?? 0)}</div></div>
      <div className="g1-stat g1-glass"><div className="k">PATH vs PLANNER</div><div className="v num">{delivered.length ? <>{driven.toFixed(1)}<small> m / {ghost.toFixed(1)} m</small></> : '—'}</div></div>
    </div>
    {r.inset && <PlannerInset d={r.inset} still={typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches} />}
    {r.stack && <ThreeWay r={r} />}
    <nav className="g1-cards"><button className="g1-big small" autoFocus onClick={onAgain}>▶ PLAY AGAIN</button>
      <a className="g1-big small ghost" href={compare}>WATCH HOW THE PLANNER DID IT</a>
      <a className="g1-big small ghost" href={`${BASE}?view=play`}>GAMES</a></nav>
    <nav className="g1-menu g2-bag"><BagButton /></nav>
    {planner && planner !== 'astar' && <p className="g1-note" data-testid="results-planner">AUTO planned with <b>{PLANNER_LABEL[planner]}</b> this run (on its record). The {what}'s routes, ghost and reference bot are A*, so stars compare against A*; bests are kept per planner.</p>}
    {colour && <nav className="g2-colour-chips again" aria-label="Fetch another colour"><span className="g1-eyebrow">FETCH ANOTHER</span>{FETCH_COLOURS.filter((c) => c.id !== colour).map((c) => <a key={c.id} data-colour={c.id} href={colourHref(BASE, c.id, planner ?? 'astar')}>{c.label} · {c.mm} mm</a>)}</nav>}
    <p className="g1-note">{r.reference ? `Stars against the reference bot's run for this ${what} (coco_lab.games.stars; GAMES.md): ★ one delivery, ★★ as many net deliveries, ★★★ ranked at or above it. Reference: ${String(r.reference.deliveries)} delivery(ies), ${Number(r.reference.time_used).toFixed(1)} s.` : `No reference run exists for this ${what}, so no stars are given.`} MODEL · kinematic.</p>
  </section>;
}

function ModeSelect() {
  useEffect(() => { document.title = 'COCO Lab · Play'; }, []);
  // owner request 2026-10-24: which planner AUTO uses (saved; Race Nav2 is always A*)
  const [planner, setPlanner] = useState<PlayPlanner>(() => chosenPlanner(null));
  const pick = (id: PlayPlanner) => { setPlanner(id); writePref('planner', id); };
  const withPlanner = (href: string) => (planner === 'astar' ? href : `${href}&planner=${planner}`);
  // G2.6: Race Nav2 is offered for a round only when a recorded Gazebo + Nav2 run of it exists
  const [ghosts, setGhosts] = useState<GhostIndex | null>(null);
  useEffect(() => { void loadGhostIndex().then(setGhosts); }, []);
  const art = (pos: string) => ({ backgroundImage: `url(${BASE}g1/modes.svg)`, backgroundPosition: pos });
  return <main className="g1 g1-screen" data-testid="play" data-g1="modes" data-ready="true" style={{ position: 'fixed', overflow: 'auto', touchAction: 'pan-x pan-y' }}>
    <a className="g1-icon g1-glass" href={BASE} aria-label="Back to the title" style={{ position: 'absolute', left: 'calc(12px + env(safe-area-inset-left))', top: 'calc(12px + env(safe-area-inset-top))', color: 'inherit' }}><ArrowLeft size={20} /></a>
    <div className="g1-eyebrow">CHOOSE A GAME</div>
    <div className="g1-modes" role="list">
      {[1].map((seed) => {
        const go = (mode: FetchRushMode) => (e: { preventDefault(): void }) => { e.preventDefault(); navigate(withPlanner(`${BASE}?view=play&game=fetch_rush&seed=${seed}${mode === 'full' ? '&mode=full' : ''}`)); };
        return <div key={seed} role="listitem" className="g1-modecard hero">
          <div className="art" style={art('0% 0%')} /><span className="g1-eyebrow" style={{ color: 'var(--g1-coco)' }}>NEW · DEPOT</span><h3>Fetch Rush</h3>
          <p>Pick-and-deliver orders in one zone, against the reference clock.</p><div className="st" aria-label={`best stars with ${PLANNER_LABEL[planner]}`}>{starText(readStars(seed, 'phone', planner))}</div>
          <div className="opts"><a data-testid="mode-fetch-rush" href={`${BASE}?view=play&game=fetch_rush&seed=${seed}`} onClick={go('phone')}>PLAY · 2 ORDERS</a>
            <a data-testid="mode-fetch-rush-full" href={`${BASE}?view=play&game=fetch_rush&seed=${seed}&mode=full`} onClick={go('full')}>FULL SHIFT · 3</a>
            {ghostFor(ghosts, FETCH_RUSH_RULES, 'phone', seed) && <a data-testid="mode-race-nav2" href={`${BASE}?view=play&game=fetch_rush&seed=${seed}&race=nav2`}
              onClick={(e) => { e.preventDefault(); navigate(`${BASE}?view=play&game=fetch_rush&seed=${seed}&race=nav2`); }}>RACE NAV2 · REAL ROS 2 RECORDING</a>}</div>
        </div>;
      })}
      <ColourCard planner={planner} art={art('0% 0%')} />
      <div role="listitem" className="g1-modecard" data-testid="mode-free-drive"><div className="art" style={art('50% 0%')} /><h3>Free Drive</h3><p>No clock. Drive, explore, pick things up.</p>
        <div className="opts"><a href={withPlanner(`${BASE}?view=play&game=free&world=depot`)}>DEPOT</a><a href={withPlanner(`${BASE}?view=play&game=free&world=proving`)}>PROVING GROUND</a></div></div>
      {[['Rush Hour', 'Cross the forklift lanes.'], ['Fog Scout', 'The map starts dark.'], ['Lost & Found', 'Where am I?']].map(([t, d]) => <div role="listitem" key={t} className="g1-modecard locked" aria-disabled="true"><div className="art" style={art('100% 0%')} /><span className="lock"><Lock size={9} /> SOON</span><h3>{t}</h3><p>{d}</p></div>)}
      <a role="listitem" className="g1-modecard" data-testid="mode-challenges" href={`${BASE}?view=play&c=`} onClick={(e) => { e.preventDefault(); navigate(`${BASE}?view=play&list=challenges`); }}><div className="art" style={art('25% 0%')} /><span className="g1-eyebrow">M5</span><h3>Challenges</h3><p>Beat the planner, race the ghost, and three more.</p></a>
    </div>
    <section className="g2-planner-pick g1-glass" data-testid="planner-pick" aria-label="The planner AUTO uses">
      <div className="g1-eyebrow">AUTO PLANNER</div>
      <div className="row" role="radiogroup" aria-label="AUTO planner">{PLAY_PLANNERS.map((id) => <button key={id} role="radio" aria-checked={planner === id}
        data-testid={`planner-${id}`} className={planner === id ? 'is-on' : ''} onClick={() => pick(id)}>{PLANNER_LABEL[id]}</button>)}</div>
      <p>{PLANNER_WHAT[planner]} The shift's reference stays A*, so stars compare against A*; bests are kept per planner.</p>
    </section>
    <p className="g1-note">Fetch Rush, Fetch by colour and Free Drive run COCO's model in your browser (MODEL · kinematic). Stars and bests stay in this browser.</p>
  </main>;
}

/**
 * Owner request 2026-10-24: Fetch by colour's card. Four chips, each with its colour's NAME and
 * diameter (colour is never the only cue); each opens that colour's round (with the AUTO planner).
 */
function ColourCard({ planner, art }: { planner: PlayPlanner; art: CSSProperties }) {
  return <div role="listitem" className="g1-modecard g2-colour-card" data-testid="mode-fetch-colour">
    <div className="art" style={art} /><span className="g1-eyebrow" style={{ color: 'var(--g1-coco)' }}>NEW · DEPOT</span><h3>Fetch by colour</h3>
    <p>Four rods in a row. Pick a colour: COCO fetches that rod to Dispatch.</p>
    <div className="g2-colour-chips" role="group" aria-label="Choose the rod's colour">{FETCH_COLOURS.map((c) => {
      const href = colourHref(BASE, c.id, planner), best = readColourStars(c.id, planner);
      return <a key={c.id} data-testid={`mode-fetch-colour-${c.id}`} data-colour={c.id} href={href} aria-label={`${c.label}, ${c.mm} millimetre rod${best !== null ? `, best ${best} of 3 stars` : ''}`}
        onClick={(e) => { e.preventDefault(); navigate(href); }}><b>{c.label}</b> · {c.mm} mm{best !== null && <i className="st"> {starText(best)}</i>}</a>;
    })}</div>
    <p className="src">As COCO's first Gazebo fetch: four rods, one per colour.</p>
  </div>;
}

/** Fetch by colour with no (or an unknown) colour in the link: choose one. */
function ColourChoice({ planner }: { planner: PlayPlanner }) {
  useEffect(() => { document.title = 'COCO Lab · Fetch by colour'; }, []);
  return <main className="g1 g1-screen" data-testid="colour-choice" data-ready="true" style={{ position: 'fixed', overflow: 'auto' }}>
    <a className="g1-icon g1-glass" href={`${BASE}?view=play`} aria-label="Back to the games" style={{ position: 'absolute', left: 'calc(12px + env(safe-area-inset-left))', top: 'calc(12px + env(safe-area-inset-top))', color: 'inherit' }}><ArrowLeft size={20} /></a>
    <div className="g1-eyebrow">FETCH BY COLOUR · CHOOSE THE ROD</div>
    <nav className="g2-colour-chips big" aria-label="Choose the rod's colour">{FETCH_COLOURS.map((c) => {
      const href = colourHref(BASE, c.id, planner);
      return <a key={c.id} data-testid={`choose-colour-${c.id}`} data-colour={c.id} href={href} onClick={(e) => { e.preventDefault(); navigate(href); }}><b>{c.label}</b> · {c.mm} mm</a>;
    })}</nav>
    <p className="g1-note">Four rods stand in a row by COCO's start, as in COCO's first Gazebo fetch. COCO fetches the one you choose to Dispatch. MODEL · kinematic.</p>
  </main>;
}

/** G2.5: the run's model messages as a rosbag2 file (src/ros/bag.ts): ros2 bag info / play and Foxglove open it. */
function BagButton() {
  const [state, setState] = useState<string | null>(null);
  return <>
    <button data-testid="g2-save-bag" onClick={async () => { setState('Writing…'); const r = await saveBag(); setState(r.ok ? `Saved ${r.name} (${(r.bytes / 1e6).toFixed(1)} MB) · MODEL` : `Not saved: ${r.why}`); }}>SAVE AS ROSBAG2 (MCAP)</button>
    {state && <p className="g1-note" role="status" data-testid="g2-save-bag-status">{state}</p>}
  </>;
}

/** G2.6: your run, the browser model's planner, and real Nav2 in Gazebo, side by side (their labels say which is which). */
function ThreeWay({ r }: { r: GameResult }) {
  const c = r.card ?? {};
  const st = r.stack!;
  return <section className="g2-threeway g1-glass" data-testid="g2-threeway" aria-label="Your run, the model's planner, Nav2 in Gazebo">
    <div><h4>YOU</h4><p className="num">{Number(c.time_used ?? 0).toFixed(1)} s</p><small>{(r.driven_m ?? 0).toFixed(1)} m driven · {String(c.deliveries ?? 0)} delivered · {String(c.contacts ?? 0)} contacts</small></div>
    <div><h4>PLANNER <b className="tag">MODEL</b></h4><p className="num">{r.planner?.reference_time_s != null ? `${r.planner.reference_time_s.toFixed(1)} s` : '—'}</p><small>the reference bot · A* routes {(r.planner?.route_m ?? 0).toFixed(1)} m</small></div>
    <div><h4>NAV2 IN GAZEBO <b className="tag stack">STACK</b></h4><p className="num">{st.driving_s.toFixed(1)} s</p><small>{st.driven_m.toFixed(1)} m · {st.legs.filter((l) => l.status === 'SUCCEEDED').length}/{st.legs.length} legs · driving only, no grasp</small></div>
    <p className="note">{st.not.join(' · ')}.</p>
  </section>;
}
