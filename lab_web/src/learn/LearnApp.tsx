// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Learn (M2.8): the six missions, played beat by beat.
 *
 * The missions are DATA (lab_web/missions/*.yaml), checked and resolved
 * at site build (lab_web/tools/missions.py -> generated/missions.json):
 * every claim shown here carries its label and evidence references, and
 * a claim whose evidence does not resolve never reaches this page -- the
 * build refuses it. This page renders; it decides nothing.
 */

import { useEffect, useState } from 'react';

import { REPO_BLOB_URL as REPO } from '../../site.config';
import { GapChips, useGaps, type Gaps } from './gaps';
import { arenaHref, type ArenaLink } from './links';

interface Claim { id: string; text: string; label: string; evidence: string[]; resolved: string[]; v1: string[] }
interface Beat {
  beat: string; text?: string; question?: string; options?: string[]; answer?: number;
  arena?: ArenaLink; claims?: string[]; stub?: boolean;
}
interface Mission {
  id: string; number: number; title: string; question: string; lens: string; v1: string; beats: Beat[]; claims: Claim[];
  /** the model gaps its lessons depend on (M2.9) */
  gaps?: string[];
}

const BEAT_TITLE: Record<string, string> = {
  hook: 'Hook', predict: 'Predict', reveal: 'Reveal', manipulate: 'Try it', explain: 'Explain',
  stack: 'Check against the Stack', challenge: 'Challenge',
};
/** What each label means, shown beside it (CLAUDE.md "Evidence classes"). */
export const LABEL_MEANING: Record<string, string> = {
  MEASURED: 'A number from a committed run or measurement.',
  TESTED: 'A property test checks it on every case it generates, in CI.',
  'SIMULATION RESULT': 'The full ROS 2 stack in Gazebo, recorded. A simulation, not a physical robot (none exists).',
  'SIMPLIFIED MODEL': "coco_lab's model, the one running in your browser: measured, but not the stack.",
  ASSUMPTION: 'A value chosen, not measured.',
  INFERENCE: 'Reasoned from the evidence, not measured directly.',
  UNRESOLVED: 'Reproduced but unexplained, or not statistically resolved.',
};
const BASE = import.meta.env.BASE_URL;

/** GitHub's anchor for a heading (lower case, punctuation dropped, spaces to hyphens). */
export function githubSlug(heading: string): string {
  return heading.replace(/\\/g, '').toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/\s/g, '-');
}

/** A resolved evidence reference as a link to the committed file. */
export function evidenceHref(resolved: string): string {
  const h = /^docs\/RESULTS\.md > (.*)$/.exec(resolved);
  if (h) return `${REPO}docs/RESULTS.md#${githubSlug(h[1])}`;
  return REPO + resolved.split('::')[0];
}

function readQuery(): { mission: string | null; beat: number } {
  const q = new URLSearchParams(window.location.search);
  const b = Number(q.get('beat') ?? 0);
  return { mission: q.get('mission'), beat: Number.isInteger(b) && b >= 0 && b <= 6 ? b : 0 };
}

export function LearnApp() {
  const [missions, setMissions] = useState<Mission[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [{ mission, beat }, setWhere] = useState(readQuery);
  const gaps = useGaps(BASE);

  useEffect(() => {
    fetch(`${BASE}generated/missions.json`, { credentials: 'omit', cache: 'no-cache' })
      .then((r) => { if (!r.ok) throw new Error(`missions.json: HTTP ${r.status}`); return r.json(); })
      .then((j) => setMissions(j.missions as Mission[]))
      .catch((e) => setError((e as Error).message));
    const back = () => setWhere(readQuery());
    window.addEventListener('popstate', back);
    return () => window.removeEventListener('popstate', back);
  }, []);

  const go = (m: string | null, b = 0) => {
    const url = m ? `?view=learn&mission=${m}&beat=${b}` : '?view=learn';
    window.history.pushState(null, '', `${BASE}${url}`);
    setWhere({ mission: m, beat: b });
    window.scrollTo(0, 0);
  };

  const current = missions?.find((m) => m.id === mission) ?? null;
  return (
    <main className="learn" data-testid="learn">
      <header className="arena-head">
        <h1><a href={`${BASE}?view=learn`} onClick={(e) => { e.preventDefault(); go(null); }}>COCO Learn</a></h1>
        <a href={`${BASE}?view=arena`} data-testid="arena-link">Arena</a>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      {!missions && !error && <p className="note">Loading the missions…</p>}
      {missions && mission && !current && <p className="error" role="alert">No mission &ldquo;{mission}&rdquo;.</p>}
      {missions && !current && <MissionIndex missions={missions} go={go} />}
      {current && <MissionPlayer key={current.id} m={current} beat={beat} go={go} gaps={gaps} />}
    </main>
  );
}

function MissionIndex({ missions, go }: { missions: Mission[]; go: (m: string, b?: number) => void }) {
  return (
    <section>
      <p className="learn-lead">Six questions a robot has to answer to fetch something. Each mission makes you
        predict, then shows you, then lets you try it in the Arena, and checks it against the full ROS 2 stack
        in Gazebo. Every claim carries its evidence.</p>
      <ol className="mission-list" data-testid="mission-list">
        {missions.map((m) => (
          <li key={m.id}>
            <a href={`${BASE}?view=learn&mission=${m.id}&beat=0`} data-testid={`mission-${m.id}`}
              onClick={(e) => { e.preventDefault(); go(m.id, 0); }}>
              <span className="mission-n">{m.number}</span>
              <span><strong>{m.title}</strong><br /><span className="note">{m.question}</span></span>
            </a>
          </li>
        ))}
      </ol>
    </section>
  );
}

function MissionPlayer({ m, beat, go, gaps }: { m: Mission; beat: number; go: (m: string, b?: number) => void; gaps: Gaps }) {
  const b = m.beats[beat];
  const [picked, setPicked] = useState<number | null>(null);
  useEffect(() => setPicked(null), [beat]);
  const byId = new Map(m.claims.map((c) => [c.id, c]));
  // a predict beat hides its evidence until the learner has committed to an answer
  const showClaims = b.beat !== 'predict' || picked !== null;
  return (
    <article className="mission" data-testid="mission" data-mission={m.id} data-beat={b.beat}>
      <p className="note">Mission {m.number} of 6</p>
      <h2>{m.title}</h2>
      <p className="learn-lead">{m.question}</p>
      <GapChips ids={m.gaps ?? []} gaps={gaps} />
      <nav className="beats" aria-label="Beats">
        {m.beats.map((x, i) => (
          <button key={x.beat} type="button" className={i === beat ? 'on' : ''} aria-current={i === beat ? 'step' : undefined}
            data-testid={`beat-${x.beat}`} onClick={() => go(m.id, i)}>{i + 1}. {BEAT_TITLE[x.beat]}</button>
        ))}
      </nav>
      <section className="beat" data-testid="beat">
        <h3>{BEAT_TITLE[b.beat]}{b.stub && <span className="note"> (stub)</span>}</h3>
        {b.question && <p className="beat-q">{b.question}</p>}
        {b.text && <p>{b.text}</p>}
        {b.options && (
          <div className="predict-options" role="group" aria-label="Your prediction">
            {b.options.map((o, i) => (
              <button key={o} type="button" data-testid={`option-${i}`} disabled={picked !== null}
                className={picked === null ? '' : i === b.answer ? 'right' : i === picked ? 'wrong' : ''}
                onClick={() => setPicked(i)}>{o}</button>
            ))}
            {picked !== null && <p className="verdict" data-testid="verdict" role="status">
              {picked === b.answer ? 'Yes.' : `Not quite: the answer is "${b.options[b.answer ?? 0]}".`} The evidence:</p>}
          </div>
        )}
        {b.arena && (
          <p><a className="arena-go" data-testid="arena-go" href={`${BASE}${arenaHref(m.id, beat, b.arena)}`}>
            {b.arena.replay ? 'Watch the recording in the Arena →' : 'Open this in the Arena →'}</a></p>
        )}
        {showClaims && (b.claims ?? []).map((id) => <ClaimCard key={id} c={byId.get(id)!} />)}
      </section>
      <nav className="beat-nav">
        <button type="button" disabled={beat === 0} onClick={() => go(m.id, beat - 1)}>← Back</button>
        {beat < m.beats.length - 1
          ? <button type="button" data-testid="next" onClick={() => go(m.id, beat + 1)}>Next →</button>
          : <button type="button" onClick={() => go('', 0)}>All missions</button>}
      </nav>
      <p className="note">This mission carries what v1's page showed: <a href={`${BASE}${m.v1}`} data-testid="v1-page">the v1 page</a>.</p>
    </article>
  );
}

function ClaimCard({ c }: { c: Claim }) {
  return (
    <div className="claim" data-testid={`claim-${c.id}`}>
      <span className={`claim-label ${c.label.toLowerCase().replace(/\s+/g, '-')}`} title={LABEL_MEANING[c.label]}>{c.label}</span>
      <p>{c.text}</p>
      <p className="cite">{LABEL_MEANING[c.label]} Evidence:{' '}
        {c.resolved.map((r, i) => (
          <span key={r}>{i > 0 && '; '}<a href={evidenceHref(r)} target="_blank" rel="noreferrer">{r}</a></span>
        ))}
      </p>
    </div>
  );
}
