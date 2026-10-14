// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The two challenges played in the Arena (M3.5):
 *
 * - **Map the arena** (`?view=arena&play=map-the-arena&pl=<level>&cfg=...`):
 *   the live model maps on wheel odometry; the panel shows the ground-truth
 *   distance against the budget (coco_lab.play.MapBudget, in the worker) and
 *   scores the drive by re-simulating its input log -- never by reading the
 *   live Arena -- exactly as `coco verify` will.
 * - **Case File detective** (`?view=arena&casefile=<id>&play=case-file-detective&pl=<level>`):
 *   the learner scrubs the STACK recording and marks a tick. A Case File
 *   has no live model, so the panel boots its own scorer.
 * - **Race the planner's ghost** (M4.8; `?view=arena&play=race-the-ghost&pl=<level>`): the
 *   learner drives to the flag; the clock starts at their first input; the ghost (the
 *   level's committed track, coco_lab.race) is drawn beside them on the same clock;
 *   reaching the flag scores the drive by re-simulating its input log.
 */

import { useEffect, useRef, useState } from 'react';

import { ArenaClient } from '../arena/client';
import type { Tick } from '../arena/protocol';
import type { PlayResult } from './best';
import { loadLevels, type Level, type Levels } from './levels';
import { ResultView } from './Result';
import type { Submission } from './share';

const BASE = import.meta.env.BASE_URL;

export function ArenaPlayPanel({ challenge, levelId, live, liveReady, lastTick, shownTick, log, onGhost }: {
  challenge: string; levelId: string;
  /** the live model's client (the map challenge, the race); null for a Case File */
  live: ArenaClient | null; liveReady: boolean;
  lastTick: () => Tick | null; shownTick: () => number | null; log: () => unknown[];
  /** M4.8: the flag [x, y, finish radius] and the ghost's pose now (nulls: none), for the renderer */
  onGhost?: (flag: [number, number, number] | null, ghost: [number, number, number] | null) => void;
}) {
  const [levels, setLevels] = useState<Levels | null>(null);
  const [level, setLevel] = useState<Level | null>(null);
  const [hash, setHash] = useState<string | null>(null);
  const [meter, setMeter] = useState<{ path_m: number; budget_m: number; done: boolean } | null>(null);
  const [race, setRace] = useState<{ t_s: number; to_flag_m: number; contacts: number; started: boolean } | null>(null);
  const raced = useRef({ contacts: 0, lastTick: -1, scored: false });
  const [result, setResult] = useState<{ r: PlayResult; s: Submission } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [fail, setFail] = useState<string | null>(null);
  const own = useRef<ArenaClient | null>(null);
  // the Arena re-renders every tick with new getters: read them through refs, so the
  // meter's interval is not torn down (and never fires) on every render
  const get = useRef({ lastTick, shownTick, log, onGhost });
  get.current = { lastTick, shownTick, log, onGhost };
  const scorer = () => live ?? own.current;

  useEffect(() => {
    loadLevels().then((L) => {
      const lv = L.challenges[challenge]?.levels.find((x) => x.id === levelId) ?? null;
      if (!lv) setFail(`There is no ${challenge} level called ${levelId}.`);
      setLevels(L); setLevel(lv);
    }).catch((e) => setFail(String(e)));
  }, [challenge, levelId]);
  // the detective's scorer: its own worker, booting while the learner scrubs
  useEffect(() => {
    if (live || challenge !== 'case-file-detective') return;
    const c = new ArenaClient({ onError: (st, m) => setFail(`${st}: ${m}`) });
    own.current = c;
    return () => { c.close(); own.current = null; };
  }, [live, challenge]);
  // the level's hash, from coco_lab.play itself (a submission names it); the map budget begins
  const begun = useRef(false);
  useEffect(() => {
    const c = scorer();
    if (!levels || !level || !c || begun.current || (live && !liveReady)) return;
    begun.current = true;
    void c.whenReady()
      .then(() => c.play<{ level_hash: string }>({ op: 'view', levels, challenge, level: level.id }))
      .then((v) => {
        setHash(v.level_hash);
        if (challenge === 'map-the-arena') return c.play({ op: 'map_begin', budget_m: level.budget_m }).then(() => undefined);
        return undefined;
      })
      .catch((e) => setFail(e instanceof Error ? e.message : String(e)));
  }, [levels, level, live, liveReady]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (challenge !== 'map-the-arena') return;
    const id = window.setInterval(() => { const p = get.current.lastTick()?.play; if (p) setMeter(p); }, 250);
    return () => window.clearInterval(id);
  }, [challenge]);

  const score = (inputs: unknown) => {
    const c = scorer();
    if (!c || !levels || !level || !hash) return;
    const s: Submission = { v: 1, hash_version: 2, challenge, level: level.id, level_hash: hash, inputs };
    setBusy(challenge === 'map-the-arena' ? 'Re-simulating your drive from its input log…' : 'Scoring…');
    setFail(null);
    void c.play<PlayResult>({ op: 'score', levels, submission: s })
      .then((r) => setResult({ r, s }))
      .catch((e) => setFail(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(null));
  };
  const finishMap = () => { const t = get.current.lastTick(); if (t) score({ ticks: t.tick, log: get.current.log() }); };
  // M4.8: the race: the clock from the first input, the ghost on the same clock, scored at the flag
  const scoreRef = useRef(score);
  scoreRef.current = score;
  useEffect(() => {
    if (challenge !== 'race-the-ghost' || !level || !hash) return undefined;
    const goal = level.goal as [number, number];
    const track = level.ghost_track as [number, number, number][];
    const finish = Number(level.finish_m);
    const id = window.setInterval(() => {
      const t = get.current.lastTick();
      const lg = get.current.log() as { tick: number }[];
      if (!t) { get.current.onGhost?.([goal[0], goal[1], finish], track[0]); return; }
      const start = lg.length ? lg[0].tick : null;
      if (t.tick !== raced.current.lastTick) {
        if (t.blocked && start !== null) raced.current.contacts += 1;
        raced.current.lastTick = t.tick;
      }
      const dist = Math.hypot(goal[0] - t.pose[0], goal[1] - t.pose[1]);
      const k = start === null ? 0 : Math.max(0, t.tick - start);
      get.current.onGhost?.([goal[0], goal[1], finish], track[Math.min(k, track.length - 1)]);
      setRace({ t_s: k * 0.1, to_flag_m: dist, contacts: raced.current.contacts, started: start !== null });
      if (start !== null && dist <= finish && !raced.current.scored) {
        raced.current.scored = true;
        scoreRef.current(lg);
      }
    }, 100);
    return () => { window.clearInterval(id); get.current.onGhost?.(null, null); };
  }, [challenge, level, hash]);
  const mark = () => { const t = get.current.shownTick(); if (t !== null) score([t]); };

  if (!level) return fail ? <p className="error" role="alert">{fail}</p> : null;
  return (
    <section className="play-panel" data-testid="play-panel" data-challenge={challenge}>
      <p><a href={`${BASE}?view=play&c=${challenge}&l=${level.id}`}>← {level.title}</a>{' '}
        <b>{challenge === 'map-the-arena' ? 'Map the arena' : challenge === 'race-the-ghost' ? "Race the planner's ghost" : 'Case File detective'}</b></p>
      {challenge === 'map-the-arena' && (
        <>
          <p className="hint">Drive with goals, the keys or the joystick. The map is built from what the wheels say
            (<code>{(level.config as string[]).join(' ')}</code>); its F1 and ATE are scored when the budget is spent or you finish.</p>
          <p data-testid="play-meter">{meter ? `driven ${meter.path_m.toFixed(1)} of ${meter.budget_m} m${meter.done ? ': budget spent' : ''}` : 'waiting for the live model…'}</p>
          <progress max={1} value={meter ? Math.min(1, meter.path_m / meter.budget_m) : 0} />
          <p className="play-controls"><button type="button" data-testid="play-submit" disabled={!hash || !!busy} onClick={finishMap}>
            Finish and score my map</button></p>
        </>
      )}
      {challenge === 'race-the-ghost' && (() => {
        const g = (level.reference as { ghost: { time_s: number; path_m: number; contacts: number } }).ghost;
        return (
          <>
            <p className="hint">Drive to the flag with W A S D (or the joystick), at the same limits the ghost has; the
              clock starts when you first move. The ghost (the translucent robot) is the model following A*'s path with
              pure pursuit: {g.time_s.toFixed(1)} s, {g.path_m.toFixed(2)} m, {g.contacts} contacts. Goals, grasps and
              hand-backs are off in a race.</p>
            <p data-testid="play-meter">{race ? (race.started
              ? `${race.t_s.toFixed(1)} s · ${race.to_flag_m.toFixed(2)} m to the flag · ${race.contacts} contacts`
              : 'ready: the clock starts when you move') : 'waiting for the live model…'}</p>
          </>
        );
      })()}
      {challenge === 'case-file-detective' && (
        <>
          <p className="hint">Scrub the recording to the first moment the solid robot (where the stack believed it was)
            leaves the outline (the truth) by more than {String(level.divergence_m)} m, then mark it. Stated tolerance:
            {' '}{String(level.tolerance_s)} s.</p>
          <p className="play-controls"><button type="button" data-testid="play-submit" disabled={!hash || !!busy} onClick={mark}>
            Mark this moment</button></p>
        </>
      )}
      {fail && <p className="error" role="alert" data-testid="play-fail">{fail}</p>}
      {busy && <p role="status" data-testid="play-busy">{busy}</p>}
      {result && <ResultView result={result.r} submission={result.s} />}
    </section>
  );
}
