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
 */

import { useEffect, useRef, useState } from 'react';

import { ArenaClient } from '../arena/client';
import type { Tick } from '../arena/protocol';
import type { PlayResult } from './best';
import { loadLevels, type Level, type Levels } from './levels';
import { ResultView } from './Result';
import type { Submission } from './share';

const BASE = import.meta.env.BASE_URL;

export function ArenaPlayPanel({ challenge, levelId, live, liveReady, lastTick, shownTick, log }: {
  challenge: string; levelId: string;
  /** the live model's client (the map challenge); null for a Case File */
  live: ArenaClient | null; liveReady: boolean;
  lastTick: () => Tick | null; shownTick: () => number | null; log: () => unknown[];
}) {
  const [levels, setLevels] = useState<Levels | null>(null);
  const [level, setLevel] = useState<Level | null>(null);
  const [hash, setHash] = useState<string | null>(null);
  const [meter, setMeter] = useState<{ path_m: number; budget_m: number; done: boolean } | null>(null);
  const [result, setResult] = useState<{ r: PlayResult; s: Submission } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [fail, setFail] = useState<string | null>(null);
  const own = useRef<ArenaClient | null>(null);
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
    const id = window.setInterval(() => { const p = lastTick()?.play; if (p) setMeter(p); }, 250);
    return () => window.clearInterval(id);
  }, [challenge, lastTick]);

  const score = (inputs: unknown) => {
    const c = scorer();
    if (!c || !levels || !level || !hash) return;
    const s: Submission = { v: 1, challenge, level: level.id, level_hash: hash, inputs };
    setBusy(challenge === 'map-the-arena' ? 'Re-simulating your drive from its input log…' : 'Scoring…');
    setFail(null);
    void c.play<PlayResult>({ op: 'score', levels, submission: s })
      .then((r) => setResult({ r, s }))
      .catch((e) => setFail(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(null));
  };
  const finishMap = () => { const t = lastTick(); if (t) score({ ticks: t.tick, log: log() }); };
  const mark = () => { const t = shownTick(); if (t !== null) score([t]); };

  if (!level) return fail ? <p className="error" role="alert">{fail}</p> : null;
  return (
    <section className="play-panel" data-testid="play-panel" data-challenge={challenge}>
      <p><a href={`${BASE}?view=play&c=${challenge}&l=${level.id}`}>← {level.title}</a>{' '}
        <b>{challenge === 'map-the-arena' ? 'Map the arena' : 'Case File detective'}</b></p>
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
