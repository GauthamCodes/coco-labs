// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Play (M3.5): five challenges, each scored by a robotics metric.
 *
 *   ?view=play                         the challenges
 *   ?view=play&c=<challenge>&l=<level>  one level
 *   ...&s=<link>                        a friend's run, re-scored here
 *
 * Every score is coco_lab.play.score, run in the Arena worker (Pyodide):
 * the same function `coco verify` runs in Node. The page draws, collects
 * the learner's inputs and shows the result; it scores nothing itself.
 * Map the arena and the Case File detective are played in the Arena
 * (ArenaPlayPanel); their links are re-scored here.
 */

import { useEffect, useMemo, useRef, useState } from 'react';

import { ArenaClient } from '../arena/client';
import type { PlayResult } from './best';
import { readShownBest } from './best';
import { GridBoard, type Cell, type GridView } from './GridBoard';
import { arenaPlayHref, loadLevels, type Level, type Levels } from './levels';
import { ResultView, stars } from './Result';
import { decodeScore, type Submission } from './share';

const BASE = import.meta.env.BASE_URL;

/** A worker for scoring, booted once, on first need (Pyodide + coco_lab: a few seconds). */
function useScorer(need: boolean) {
  const client = useRef<ArenaClient | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!need || client.current) return;
    const c = new ArenaClient({ onError: (stage, m) => setError(`${stage}: ${m}`) });
    client.current = c;
    void c.whenReady().then(() => setReady(true)).catch((e) => setError(String(e)));
    return () => { c.close(); client.current = null; };
  }, [need]);
  return { client: client.current, ready, error };
}

export function PlayApp() {
  const params = new URLSearchParams(window.location.search);
  const c = params.get('c');
  const l = params.get('l');
  const shared = useMemo(() => (params.has('s') ? decodeScore(params) : null), []); // eslint-disable-line react-hooks/exhaustive-deps
  const [levels, setLevels] = useState<Levels | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { loadLevels().then(setLevels).catch((e) => setError(String(e))); }, []);
  const ch = c && levels ? levels.challenges[c] : null;
  const lv = ch && l ? ch.levels.find((x) => x.id === l) ?? null : null;

  return (
    <main className="play" data-testid="play">
      <header className="arena-head">
        <h1>COCO Play</h1>
        <span className="evidence-badge model" data-testid="evidence-badge" title="Scored on the Arena model and coco_lab's algorithms; the detective plays STACK recordings">MODEL</span>
        <a href={`${BASE}?view=play`}>Challenges</a>
        <a href={`${BASE}?view=learn`}>Learn</a>
        <a href={`${BASE}?view=arena`}>Sandbox</a>
        <a href={`${BASE}?view=casefiles`}>Case Files</a>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      {params.has('s') && !shared && <p className="error" role="alert">This challenge link is malformed; nothing was scored.</p>}
      {!levels && !error && <p>Loading the challenges…</p>}
      {levels && !c && <ChallengeList levels={levels} />}
      {levels && c && !ch && <p className="error" role="alert">There is no challenge called {c}.</p>}
      {levels && ch && !lv && <ChallengePage id={c!} levels={levels} />}
      {levels && ch && lv && <LevelPage challenge={c!} level={lv} levels={levels} shared={shared} />}
    </main>
  );
}

function ChallengeList({ levels }: { levels: Levels }) {
  return (
    <section className="play-list">
      <p className="lede">Five challenges, each scored by a real robotics metric, with stars set by reference algorithms
        on the same level (<code>docs/v2/CHALLENGES.md</code>). No server, no accounts: a score is re-computed from its
        inputs by anyone, with <code>coco verify</code>.</p>
      {levels.order.map((id) => <ChallengePage key={id} id={id} levels={levels} compact />)}
    </section>
  );
}

function ChallengePage({ id, levels, compact }: { id: string; levels: Levels; compact?: boolean }) {
  const ch = levels.challenges[id];
  return (
    <section className="play-challenge" data-testid={`challenge-${id}`}>
      <h2><a href={`${BASE}?view=play&c=${id}`}>{ch.title}</a></h2>
      {!compact && <p>{ch.goal}</p>}
      <ul className="play-levels">
        {ch.levels.map((lv) => {
          const best = readShownBest(id, lv.id);
          return (
            <li key={lv.id}>
              <a href={`${BASE}?view=play&c=${id}&l=${lv.id}`} data-testid={`level-${id}-${lv.id}`}>{lv.title}</a>
              {best && <span className="play-best"> {stars(best.stars)}</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

const IN_ARENA = new Set(['map-the-arena', 'case-file-detective']);

function LevelPage({ challenge, level, levels, shared }: {
  challenge: string; level: Level; levels: Levels; shared: ReturnType<typeof decodeScore>;
}) {
  const ch = levels.challenges[challenge];
  const isShared = !!shared && shared.submission.challenge === challenge && shared.submission.level === level.id;
  const needPython = isShared || !IN_ARENA.has(challenge);
  const { client, ready, error } = useScorer(needPython);
  const [view, setView] = useState<Record<string, unknown> | null>(null);
  const [result, setResult] = useState<{ r: PlayResult; s: Submission; reproduced?: boolean } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [fail, setFail] = useState<string | null>(null);

  useEffect(() => {
    if (!ready || !client) return;
    void client.play<Record<string, unknown>>({ op: 'view', levels, challenge, level: level.id })
      .then(setView).catch((e) => setFail(String(e)));
  }, [ready, client, levels, challenge, level.id]);

  const score = (inputs: unknown, reproduce?: string) => {
    if (!client || !view) return;
    const s: Submission = { v: 1, challenge, level: level.id, level_hash: String(view.level_hash), inputs };
    setBusy(challenge === 'map-the-arena' ? 'Re-simulating the drive from its input log…' : 'Scoring…');
    setFail(null);
    void client.play<PlayResult>({ op: 'score', levels, submission: s })
      .then((r) => setResult({ r, s, reproduced: reproduce === undefined ? undefined : r.hash === reproduce }))
      .catch((e) => setFail(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(null));
  };
  // a friend's link: re-score its inputs once the level is in view
  const sharedDone = useRef(false);
  useEffect(() => {
    if (!isShared || !view || sharedDone.current) return;
    sharedDone.current = true;
    if (shared!.submission.level_hash !== view.level_hash) {
      setFail('This link was made for a different version of this level; it cannot be re-scored here.');
      return;
    }
    score(shared!.submission.inputs, shared!.result_hash);
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="play-level" data-testid="play-level" data-challenge={challenge} data-level={level.id}>
      <p><a href={`${BASE}?view=play&c=${challenge}`}>← {ch.title}</a></p>
      <h2>{level.title}</h2>
      <p>{ch.goal}</p>
      {level.story && <p className="play-story">{level.story}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {fail && <p className="error" role="alert" data-testid="play-fail">{fail}</p>}
      {needPython && !view && !error && <p data-testid="play-loading">Loading the scorer: coco_lab, in Python, in your browser…</p>}
      {isShared && <p className="play-shared">A challenge link: its inputs are re-scored here.</p>}
      {!isShared && IN_ARENA.has(challenge) && (
        <p><a className="arena-go" data-testid="play-arena-go" href={`${BASE}${arenaPlayHref(challenge, level)}`}>
          {challenge === 'map-the-arena' ? 'Drive in the Arena →' : 'Open the Case File →'}</a></p>
      )}
      {!isShared && view && challenge === 'beat-the-planner' && <BeatThePlanner view={view} onScore={score} result={result?.r ?? null} />}
      {!isShared && view && challenge === 'next-node' && <NextNode view={view} onScore={score} />}
      {!isShared && view && challenge === 'search-the-bays' && <SearchTheBays level={level} onScore={score} />}
      {busy && <p data-testid="play-busy" role="status">{busy}</p>}
      {result && <ResultView result={result.r} submission={result.s} reproduced={result.reproduced} />}
    </section>
  );
}

// -- beat the planner ------------------------------------------------------------

function BeatThePlanner({ view, onScore, result }: {
  view: Record<string, unknown>; onScore: (inputs: unknown) => void; result: PlayResult | null;
}) {
  const grid = view.grid as GridView;
  const S = grid.marks.S;
  const [path, setPath] = useState<Cell[]>([S]);
  const add = (c: Cell) => {
    const last = path[path.length - 1];
    if (c[0] === last[0] && c[1] === last[1]) { if (path.length > 1) setPath(path.slice(0, -1)); return; }
    if (Math.max(Math.abs(c[0] - last[0]), Math.abs(c[1] - last[1])) === 1) setPath([...path, c]);
  };
  return (
    <div className="play-board">
      <p className="hint">Click the cell next to your path's end to extend it (diagonals too); click the end to take a
        step back. Dark cells are walls; brown cells cost more to cross, darker costing more.</p>
      <GridBoard grid={grid} label="Beat the planner: the level's grid" onCell={add}
        overlay={{ path, ghost: result ? (view.optimal_path as Cell[]) : undefined }} />
      <p className="play-controls">
        <button type="button" onClick={() => setPath(path.length > 1 ? path.slice(0, -1) : path)}>Undo</button>
        <button type="button" onClick={() => setPath([S])}>Clear</button>
        <button type="button" data-testid="play-submit" onClick={() => onScore(path)}>Score my path</button>
        <span> {path.length - 1} moves</span>
      </p>
      {result && <p className="hint">The dashed green line is A*'s optimal path.</p>}
    </div>
  );
}

// -- next node ----------------------------------------------------------------------

interface Frame { closed: Cell[]; open: [number, number, number, number][]; expanded: Cell; f: number; h: number; tied: Cell[] }

function NextNode({ view, onScore }: { view: Record<string, unknown>; onScore: (inputs: unknown) => void }) {
  const grid = view.grid as GridView;
  const frames = view.frames as Frame[];
  const [i, setI] = useState(0);
  const [guesses, setGuesses] = useState<Cell[]>([]);
  const [hover, setHover] = useState<Cell | null>(null);
  const fr = frames[Math.min(i, frames.length - 1)];
  const revealed = guesses.length > i;
  const openAt = (c: Cell | null) => (c ? fr.open.find((o) => o[0] === c[0] && o[1] === c[1]) : undefined);
  const pick = (c: Cell) => {
    if (revealed || i >= frames.length || !openAt(c)) return;
    setGuesses([...guesses, c]);
  };
  const h = openAt(hover);
  const hit = revealed && fr.tied.some((t) => t[0] === guesses[i][0] && t[1] === guesses[i][1]);
  return (
    <div className="play-board">
      <p className="hint">Prediction {Math.min(i + 1, 10)} of 10. Hover an open cell to read its g and h; click the one
        A* expands next.</p>
      <GridBoard grid={grid} label="Next node: A*'s search part-way" onCell={pick} onHover={setHover}
        overlay={{ closed: fr.closed, open: fr.open.map((o) => [o[0], o[1]] as Cell), mark: revealed ? guesses[i] : null,
          truth: revealed ? fr.expanded : null, tied: revealed ? fr.tied : undefined }} />
      <p className="play-readout" data-testid="play-readout">{h ? `cell (${h[0]}, ${h[1]}): g ${h[2].toFixed(3)}, h ${h[3].toFixed(3)}` : ' '}</p>
      {revealed && (
        <p role="status" data-testid="play-step">{hit ? 'Yes' : 'No'}: A* expanded ({fr.expanded[0]}, {fr.expanded[1]}),
          f = {fr.f.toFixed(3)}, h = {fr.h.toFixed(3)}{fr.tied.length > 1 ? ` -- any of the ${fr.tied.length} green cells counts: they tie on f and h` : ''}.</p>
      )}
      <p className="play-controls">
        {revealed && i < frames.length - 1 && <button type="button" data-testid="play-next" onClick={() => setI(i + 1)}>Next expansion</button>}
        {guesses.length === frames.length && <button type="button" data-testid="play-submit" onClick={() => onScore(guesses)}>Score my predictions</button>}
      </p>
    </div>
  );
}

// -- search the bays ------------------------------------------------------------------

interface Problem {
  regions: { id: string; label: string; survey_cost: number }[]; start: string; travel: Record<string, Record<string, number>>;
  detection: number[]; prior: number[];
}

function SearchTheBays({ level, onScore }: { level: Level; onScore: (inputs: unknown) => void }) {
  const p = level.problem as Problem;
  const [order, setOrder] = useState<number[]>([]);
  const ids = p.regions.map((r) => r.id);
  const leg = (from: string, i: number) => p.travel[from]?.[ids[i]];
  return (
    <div className="play-board">
      <table className="play-bays">
        <thead><tr><th>bay</th><th>chance it is there</th><th>camera finds it</th><th>drive from the start</th><th>looking costs</th></tr></thead>
        <tbody>
          {p.regions.map((r, i) => (
            <tr key={r.id}><td>{r.label}</td><td>{p.prior[i]}</td><td>{p.detection[i]}</td><td>{leg(p.start, i)?.toFixed(2)} m</td><td>{r.survey_cost} m</td></tr>
          ))}
        </tbody>
      </table>
      <details><summary>Driving between bays (m)</summary>
        <table className="play-bays">
          <thead><tr><th>from \ to</th>{p.regions.map((r) => <th key={r.id}>{r.label}</th>)}</tr></thead>
          <tbody>
            {p.regions.map((a) => (
              <tr key={a.id}><td>{a.label}</td>{p.regions.map((b, j) => <td key={b.id}>{a.id === b.id ? '—' : leg(a.id, j)?.toFixed(2)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </details>
      <p className="hint">Click the bays in the order to look (each one once). Each look adds its cost, in metres of
        driving, to the drive there; the search stops at the first find.</p>
      <p className="play-controls">
        {p.regions.map((r, i) => (
          <button type="button" key={r.id} disabled={order.includes(i)} data-testid={`bay-${i}`}
            onClick={() => setOrder([...order, i])}>{r.label}</button>
        ))}
      </p>
      <p data-testid="play-order">Your order: {order.length ? order.map((i) => p.regions[i].label).join(' → ') : '—'}</p>
      <p className="play-controls">
        <button type="button" onClick={() => setOrder([])}>Clear</button>
        <button type="button" data-testid="play-submit" disabled={order.length !== ids.length} onClick={() => onScore(order)}>Score my order</button>
      </p>
    </div>
  );
}
