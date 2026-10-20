// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G1.2: Play's game shell. `?view=play` is the mode select; a game opens as
 *
 *   ?view=play&game=fetch_rush&seed=1          Fetch Rush on the Depot
 *   ?view=play&game=free&world=depot|proving   Free Drive
 *
 * Every M5 Play link (`&c=`, `&l=`, `&s=`, `&z=`) still opens M5's
 * challenges (main.tsx routes those to PlayApp before this shell). The
 * pause menu, settings and results live here; Play itself is PlayGame.
 */

import { useEffect, useState } from 'react';
import { ArrowLeft, Lock } from 'lucide-react';
import { isBool, readPref, readRaw, writePref, writeRaw } from '../prefs';
import { navigate } from '../ui/navigation';
import { PlayGame } from './PlayGame';
import type { GameKind, WorldId } from './session';
import type { Tier } from './world/build3d';
import { pickTier } from './tier';
import './fonts.css';
import './game.css';

const BASE = import.meta.env.BASE_URL;

export interface GameResult {
  game: GameKind; seed: number; world: WorldId;
  card: Record<string, unknown> | null; stars: number | null; reference: Record<string, unknown> | null;
  record: Record<string, unknown> | null;
}

const bestKey = (seed: number) => `coco.play.best.v1.g1-fetch-rush.seed-${seed}`;
export function readStars(seed: number): number | null {
  try { const raw = readRaw(bestKey(seed)); return raw ? (JSON.parse(raw) as { stars: number }).stars : null; } catch { return null; }
}
function keepStars(seed: number, stars: number, net: number, time: number) {
  const old = readStars(seed);
  if (old !== null && old >= stars) return;
  writeRaw(bestKey(seed), JSON.stringify({ stars, net, time }));
}
const starText = (n: number | null) => (n === null ? '☆☆☆' : '★'.repeat(n) + '☆'.repeat(3 - n));

export function GameApp() {
  const q = new URLSearchParams(window.location.search);
  const game = q.get('game') as GameKind | null;
  if (game !== 'fetch_rush' && game !== 'free') return <ModeSelect />;
  const world: WorldId = game === 'fetch_rush' ? 'depot' : q.get('world') === 'proving' ? 'proving' : 'depot';
  const seed = Math.max(1, Math.min(999, Number.parseInt(q.get('seed') ?? '1', 10) || 1));
  return <GameRun game={game} world={world} seed={seed} />;
}

function GameRun({ game, world, seed }: { game: GameKind; world: WorldId; seed: number }) {
  const [paused, setPaused] = useState(false);
  const [settings, setSettings] = useState(false);
  const [result, setResult] = useState<GameResult | null>(null);
  const [restartKey, setRestartKey] = useState(0);
  const [tier, setTier] = useState<Tier>(() => pickTier());
  const [tutorialSeen, setTutorialSeen] = useState(() => readPref('tutorial', false, isBool));
  const showPerf = new URLSearchParams(window.location.search).has('perf');
  useEffect(() => { document.documentElement.classList.add('playing-coco'); return () => document.documentElement.classList.remove('playing-coco'); }, []);
  const onResult = (r: GameResult) => {
    setResult(r);
    if (r.stars !== null && r.card) keepStars(r.seed, r.stars, Number(r.card.net_deliveries ?? 0), Number(r.card.time_used ?? 0));
  };
  const restart = () => { setResult(null); setPaused(false); setRestartKey((k) => k + 1); };
  return <>
    <PlayGame key={`${restartKey}-${tier}`} world={world} game={game} seed={seed} tier={tier} paused={paused || !!result} onPause={() => setPaused((x) => !x)}
      onResult={onResult} restartKey={restartKey} showPerf={showPerf} tutorialSeen={tutorialSeen}
      onTutorialDone={() => { writePref('tutorial', true); setTutorialSeen(true); }} />
    {paused && !result && !settings && <section className="g1 g1-screen dim" data-testid="g1-pause-menu" style={{ position: 'fixed', zIndex: 25, background: 'rgba(8,10,14,.62)' }}>
      <div className="g1-eyebrow">PAUSED · {game === 'fetch_rush' ? `FETCH RUSH · SHIFT ${seed}` : `FREE DRIVE · ${world === 'depot' ? 'DEPOT' : 'PROVING GROUND'}`}</div>
      <nav className="g1-menu">
        <button className="main" autoFocus onClick={() => setPaused(false)}>RESUME</button>
        <button onClick={restart}>RESTART</button>
        <button onClick={() => setSettings(true)}>SETTINGS</button>
        <a href={`${BASE}?view=play`}>EXIT</a>
      </nav>
    </section>}
    {settings && <Settings tier={tier} onTier={setTier} onClose={() => setSettings(false)} />}
    {result && <Results r={result} onAgain={restart} />}
  </>;
}

function Settings({ tier, onTier, onClose }: { tier: Tier; onTier: (t: Tier) => void; onClose: () => void }) {
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
      <label htmlFor="g1-k">Control hints</label><input id="g1-k" type="checkbox" checked={hints} onChange={(e) => { setHints(e.target.checked); writePref('bars', e.target.checked); }} />
    </div>
    <p className="g1-note">Quality changes take effect at once and restart the drawing, not the run's rules. Saved in this browser only.</p>
    <nav className="g1-menu"><button className="main" autoFocus onClick={onClose}>DONE</button></nav>
  </section>;
}

function Results({ r, onAgain }: { r: GameResult; onAgain: () => void }) {
  const c = r.card ?? {};
  const delivered = (c.delivered as { ghost: number | null; driven: number }[] | undefined) ?? [];
  const driven = delivered.reduce((s, d) => s + d.driven, 0), ghost = delivered.reduce((s, d) => s + (d.ghost ?? 0), 0);
  const compare = `${BASE}?view=compare&world=depot`;
  return <section className="g1 g1-screen dim" data-testid="g1-results" style={{ position: 'fixed', zIndex: 27, background: 'rgba(8,10,14,.8)' }}>
    <div className="g1-eyebrow">FETCH RUSH · SHIFT {r.seed} · RESULT</div>
    <div className="g1-bigstars" aria-label={`${r.stars ?? 0} of 3 stars`}>{r.stars === null ? <span className="off">☆☆☆</span> : <>{'★'.repeat(r.stars)}<span className="off">{'★'.repeat(3 - r.stars)}</span></>}</div>
    <div className="g1-cards">
      <div className="g1-stat g1-glass"><div className="k">TIME USED</div><div className="v num">{Number(c.time_used ?? 0).toFixed(1)}<small> s</small></div></div>
      <div className="g1-stat g1-glass"><div className="k">DELIVERIES</div><div className="v num">{String(c.deliveries ?? 0)}</div></div>
      <div className="g1-stat g1-glass"><div className="k">CONTACTS</div><div className="v num">{String(c.contacts ?? 0)}</div></div>
      <div className="g1-stat g1-glass"><div className="k">PATH vs PLANNER</div><div className="v num">{delivered.length ? <>{driven.toFixed(1)}<small> m / {ghost.toFixed(1)} m</small></> : '—'}</div></div>
    </div>
    <nav className="g1-cards"><button className="g1-big small" autoFocus onClick={onAgain}>▶ PLAY AGAIN</button>
      <a className="g1-big small ghost" href={compare}>WATCH HOW THE PLANNER DID IT</a>
      <a className="g1-big small ghost" href={`${BASE}?view=play`}>GAMES</a></nav>
    <p className="g1-note">{r.reference ? `Stars against the reference bot's run for this shift (coco_lab.games.stars; GAMES.md): ★ one delivery, ★★ as many net deliveries, ★★★ ranked at or above it. Reference: ${String(r.reference.deliveries)} delivery(ies), ${Number(r.reference.time_used).toFixed(1)} s.` : 'No reference run exists for this shift, so no stars are given.'} MODEL · kinematic.</p>
  </section>;
}

function ModeSelect() {
  useEffect(() => { document.title = 'COCO Lab · Play'; }, []);
  const art = (pos: string) => ({ backgroundImage: `url(${BASE}g1/modes.svg)`, backgroundPosition: pos });
  return <main className="g1 g1-screen" data-g1="modes" data-ready="true" style={{ position: 'fixed', overflow: 'auto', touchAction: 'pan-x pan-y' }}>
    <a className="g1-icon g1-glass" href={BASE} aria-label="Back to the title" style={{ position: 'absolute', left: 'calc(12px + env(safe-area-inset-left))', top: 'calc(12px + env(safe-area-inset-top))', color: 'inherit' }}><ArrowLeft size={20} /></a>
    <div className="g1-eyebrow">CHOOSE A GAME</div>
    <div className="g1-modes" role="list">
      {[1, 2, 3].slice(0, 1).map((seed) => <a key={seed} role="listitem" className="g1-modecard hero" data-testid="mode-fetch-rush" href={`${BASE}?view=play&game=fetch_rush&seed=${seed}`} onClick={(e) => { e.preventDefault(); navigate(`${BASE}?view=play&game=fetch_rush&seed=${seed}`); }}>
        <div className="art" style={art('0% 0%')} /><span className="g1-eyebrow" style={{ color: 'var(--g1-coco)' }}>NEW · DEPOT</span><h3>Fetch Rush</h3><p>Fill pick-and-deliver orders in 3 minutes.</p><div className="st" aria-label="best stars">{starText(readStars(seed))}</div></a>)}
      <div role="listitem" className="g1-modecard" data-testid="mode-free-drive"><div className="art" style={art('50% 0%')} /><h3>Free Drive</h3><p>No clock. Drive, explore, pick things up.</p>
        <div className="opts"><a href={`${BASE}?view=play&game=free&world=depot`}>DEPOT</a><a href={`${BASE}?view=play&game=free&world=proving`}>PROVING GROUND</a></div></div>
      {[['Rush Hour', 'Cross the forklift lanes.'], ['Fog Scout', 'The map starts dark.'], ['Lost & Found', 'Where am I?']].map(([t, d]) => <div role="listitem" key={t} className="g1-modecard locked" aria-disabled="true"><div className="art" style={art('100% 0%')} /><span className="lock"><Lock size={9} /> SOON</span><h3>{t}</h3><p>{d}</p></div>)}
      <a role="listitem" className="g1-modecard" data-testid="mode-challenges" href={`${BASE}?view=play&c=`} onClick={(e) => { e.preventDefault(); navigate(`${BASE}?view=play&list=challenges`); }}><div className="art" style={art('25% 0%')} /><span className="g1-eyebrow">M5</span><h3>Challenges</h3><p>Beat the planner, race the ghost, and three more.</p></a>
    </div>
    <p className="g1-note">Fetch Rush and Free Drive run COCO's model in your browser (MODEL · kinematic). Stars and bests stay in this browser.</p>
  </main>;
}
