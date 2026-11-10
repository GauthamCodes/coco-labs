// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4 · the Learn course (coco.lesson.v1, ADR 0015): ?view=learn.
 *
 * Routes (all query parameters, read on load and on popstate):
 *   (none)                        the course home: tracks, modules, privacy
 *   module=<id>                   a module and its lessons
 *   lesson=<id>&step=<step>       the lesson player: predict, observe, explain, try, check, ros2
 *   page=glossary|progress|teacher|verify|assignment   (verify reads #done=, assignment #assign=)
 *
 * The page renders data (generated/course.json) and asks the grader (coco_lab.course in the
 * sandbox worker); it decides no verdict except a predict question's, which is equality with the
 * answer in the data (the same comparison the Python grader makes when a link is re-verified).
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ModeNav } from '../ui/ModeNav';
import { codeFragment } from '../studio/codelink';
import { experimentLink } from '../workbench/links';
import { compareHrefFor } from '../workbench/compare_link';
import type { ExperimentSpec } from '../workbench/spec';
import type { RunRecord } from '../workbench/pool';
import { evidenceHref, LABEL_MEANING } from '../learn/LearnApp';
import { Diagram } from './diagrams';
import { grade as runGrade, warmUp } from './grader';
import { assignmentFragment, completionFragment, csvCell, readAssignment, readCompletion, type Assignment, type Completion } from './links';
import { exportProgress, importProgress, lessonProgress, loadProgress, resetProgress, stars, updateLesson, type LessonProgress } from './progress';
import { findLesson, STEPS, STEP_TITLE, TRACKS, type Answer, type Claim, type Course, type Exercise, type Grade, type Lesson, type Module, type Scenario, type Step, type Track } from './types';
import '../workbench/workbench.css';
import '../game/fonts.css';
import './course.css';

const BASE = import.meta.env.BASE_URL;
const SITE = () => new URL(BASE, window.location.href).href;

interface Where { module: string | null; lesson: string | null; step: Step; page: string | null; track: Track | null }
function readWhere(): Where {
  const q = new URLSearchParams(window.location.search);
  const step = q.get('step') as Step;
  const track = q.get('track') as Track;
  return {
    module: q.get('module'), lesson: q.get('lesson'), page: q.get('page'),
    step: (STEPS as readonly string[]).includes(step) ? step : 'predict',
    track: TRACKS.some((t) => t.id === track) ? track : null,
  };
}
function href(p: Record<string, string | null | undefined>): string {
  const q = new URLSearchParams({ view: 'learn' });
  for (const [k, v] of Object.entries(p)) if (v) q.set(k, v);
  return `${BASE}?${q.toString()}`;
}

export function CourseApp() {
  const [course, setCourse] = useState<Course | null>(null);
  const [error, setError] = useState('');
  const [where, setWhere] = useState<Where>(readWhere);
  const [, bump] = useState(0);
  const refresh = useCallback(() => bump((n) => n + 1), []);
  useEffect(() => { document.title = 'Learn · COCO Lab'; }, []);
  useEffect(() => {
    let alive = true;
    fetch(`${BASE}generated/course.json`, { credentials: 'omit', cache: 'no-cache' })
      .then((r) => { if (!r.ok) throw new Error(`course.json: HTTP ${r.status}`); return r.json(); })
      .then((c: Course) => { if (alive) setCourse(c); })
      .catch((e) => { if (alive) setError(String((e as Error).message)); });
    const back = () => setWhere(readWhere());
    window.addEventListener('popstate', back);
    return () => { alive = false; window.removeEventListener('popstate', back); };
  }, []);
  const go = (p: Record<string, string | null | undefined>) => {
    window.history.pushState(null, '', href(p));
    setWhere(readWhere());
    window.scrollTo(0, 0);
  };
  let body: ReactNode = null;
  if (course) {
    if (where.page === 'glossary') body = <Glossary course={course} />;
    else if (where.page === 'progress') body = <ProgressPage course={course} onChange={refresh} />;
    else if (where.page === 'teacher') body = <Teacher course={course} />;
    else if (where.page === 'verify') body = <Verify course={course} />;
    else if (where.page === 'assignment') body = <AssignmentPage course={course} />;
    else if (where.lesson) {
      const f = findLesson(course, where.lesson);
      body = f ? <LessonPlayer key={f.lesson.id} course={course} module={f.module} lesson={f.lesson} step={where.step} go={go} onChange={refresh} />
        : <p role="alert" className="wb-error">No lesson &ldquo;{where.lesson}&rdquo;.</p>;
    } else if (where.module) {
      const m = course.modules.find((x) => x.id === where.module);
      body = m ? <ModulePage course={course} module={m} go={go} /> : <p role="alert" className="wb-error">No module &ldquo;{where.module}&rdquo;.</p>;
    } else body = <Home course={course} track={where.track} go={go} />;
  }
  return (
    <main className="wb course" data-testid="course">
      <ModeNav current="learn" evidence="MODEL" />
      <nav className="course-crumbs" aria-label="Course">
        <a href={href({})} onClick={(e) => { e.preventDefault(); go({}); }}>Course</a>
        <a href={href({ page: 'glossary' })} onClick={(e) => { e.preventDefault(); go({ page: 'glossary' }); }}>Glossary</a>
        <a href={href({ page: 'progress' })} onClick={(e) => { e.preventDefault(); go({ page: 'progress' }); }}>My progress</a>
        <a href={href({ page: 'teacher' })} onClick={(e) => { e.preventDefault(); go({ page: 'teacher' }); }}>Teachers</a>
        <a href={`${BASE}?view=compare&tour=`}>Guided tours</a>
      </nav>
      {error && <p role="alert" className="wb-error">{error}</p>}
      {!course && !error && <p role="status" className="wb-section">Loading the course…</p>}
      {body}
    </main>
  );
}

// -- home ----------------------------------------------------------------------------------------

function Stars({ n, label }: { n: number; label?: string }) {
  return <span className="course-stars" aria-label={`${n} of 3 stars${label ? ` · ${label}` : ''}`} title={`${n} of 3 stars`}>
    {[1, 2, 3].map((i) => <span key={i} aria-hidden="true" className={i <= n ? 'on' : ''}>{i <= n ? '★' : '☆'}</span>)}
  </span>;
}

function Home({ course, track, go }: { course: Course; track: Track | null; go: (p: Record<string, string | null>) => void }) {
  const lessons = course.modules.flatMap((m) => m.lessons);
  const done = lessons.filter((l) => lessonProgress(l.id).passed).length;
  return <>
    <header className="wb-head"><p className="eyebrow">LEARN · A FREE ROBOTICS COURSE</p>
      <h1>Learn how a robot thinks, by predicting, coding and checking.</h1>
      <p>Ten modules, from finding a path to running your own algorithm in ROS 2. Every lesson asks you to predict
        first, shows you the run, explains it, lets you try it, and checks your answer automatically and exactly --
        the robot model is deterministic, so a check is a measurement, not an opinion. Each lesson ends with how
        real ROS 2 and Nav2 do the same thing, with the evidence for it.</p>
      <p className="course-privacy" data-testid="course-privacy"><b>Private by design.</b> No account, no analytics, no tracking.
        Your progress stays in this browser (export it as a file any time). Your name is never asked for, except in a
        completion link you choose to make and share.</p>
      <p className="wb-muted">{done} of {lessons.length} lessons passed.</p>
    </header>
    <section className="wb-section"><h2>Choose a track</h2>
      <div className="course-tracks">{TRACKS.map((t) => (
        <a key={t.id} className={`course-track${track === t.id ? ' on' : ''}`} href={href({ track: t.id })} data-testid={`track-${t.id}`}
          aria-current={track === t.id ? 'true' : undefined}
          onClick={(e) => { e.preventDefault(); go(track === t.id ? {} : { track: t.id }); }}>
          <strong>{t.title}</strong><span>{t.blurb}</span><span className="wb-muted">{t.phone}</span>
        </a>))}
      </div>
    </section>
    <section className="wb-section"><h2>Modules</h2>
      <ol className="course-modules" data-testid="course-modules">{course.modules.map((m) => {
        const ls = m.lessons.filter((l) => !track || l.track === track);
        return <li key={m.id} className="wb-card">
          <p className="eyebrow">MODULE {m.number}</p>
          <h3><a href={href({ module: m.id })} onClick={(e) => { e.preventDefault(); go({ module: m.id }); }}>{m.title}</a></h3>
          <p>{m.question}</p>
          {ls.length === 0 ? <p className="wb-muted">No {track} lesson in this module.</p> : <ul className="course-lessons">{ls.map((l) => (
            <li key={l.id}><a href={href({ lesson: l.id, step: 'predict' })} data-testid={`lesson-${l.id}`}
              onClick={(e) => { e.preventDefault(); go({ lesson: l.id, step: 'predict' }); }}>{l.title}</a>{' '}
              <span className={`course-chip ${l.track}`}>{l.track}</span> <Stars n={stars(lessonProgress(l.id))} /></li>))}</ul>}
        </li>;
      })}</ol>
    </section>
  </>;
}

function ModulePage({ course, module: m, go }: { course: Course; module: Module; go: (p: Record<string, string | null>) => void }) {
  const passed = m.lessons.filter((l) => lessonProgress(l.id).passed);
  return <section className="wb-section" data-testid="course-module">
    <p className="eyebrow">MODULE {m.number} OF {course.modules.length}</p>
    <h1 className="course-h1">{m.title}</h1>
    <p className="wb-text">{m.question}</p>
    <ol className="course-lesson-list">{m.lessons.map((l) => (
      <li key={l.id}><a href={href({ lesson: l.id, step: 'predict' })} onClick={(e) => { e.preventDefault(); go({ lesson: l.id, step: 'predict' }); }}>{l.title}</a>{' '}
        <span className={`course-chip ${l.track}`}>{TRACKS.find((t) => t.id === l.track)!.title}</span> <Stars n={stars(lessonProgress(l.id))} /></li>))}
    </ol>
    {m.mission && <p><a href={`${BASE}?view=compare&tour=${m.mission}`}>The guided tour for this module (claims and recordings)</a></p>}
    <CompletionMaker course={course} title={`Module ${m.number}: ${m.title}`} lessonIds={passed.map((l) => l.id)} askName />
  </section>;
}

// -- lesson player -------------------------------------------------------------------------------

function LessonPlayer({ course, module: m, lesson: l, step, go, onChange }: {
  course: Course; module: Module; lesson: Lesson; step: Step; go: (p: Record<string, string | null>) => void; onChange: () => void;
}) {
  const i = STEPS.indexOf(step);
  const [last, setLast] = useState<Grade | null>(null);
  const tryEx = course.exercises[l.try];
  const claims = useMemo(() => new Map(m.claims.map((c) => [c.id, c])), [m]);
  useEffect(() => { if (tryEx && tryEx.type !== 'predict') warmUp(); }, [tryEx]);
  const to = (s: Step) => go({ lesson: l.id, step: s });
  return <article className="wb-section course-lesson" data-testid="lesson" data-lesson={l.id}>
    <p className="eyebrow"><a href={href({ module: m.id })} onClick={(e) => { e.preventDefault(); go({ module: m.id }); }}>Module {m.number} · {m.title}</a>
      {' '}· <span className={`course-chip ${l.track}`}>{TRACKS.find((t) => t.id === l.track)!.title}</span></p>
    <h1 className="course-h1">{l.title}</h1>
    {l.track !== 'explorer' && <p className="course-phone-note">Coding is easier on a laptop; on a phone you can read the lesson and check an answer.</p>}
    <nav className="course-steps" aria-label="Lesson steps">{STEPS.map((s, k) => (
      <a key={s} href={href({ lesson: l.id, step: s })} aria-current={s === step ? 'step' : undefined} data-testid={`step-${s}`}
        onClick={(e) => { e.preventDefault(); to(s); }}>{k + 1}. {STEP_TITLE[s]}</a>))}
    </nav>
    <section className="course-step" data-testid="lesson-step" data-step={step} aria-live="polite">
      <h2>{STEP_TITLE[step]}</h2>
      {step === 'predict' && <PredictStep e={course.exercises[l.predict]} lessonId={l.id} kind="predict" onChange={onChange} />}
      {step === 'observe' && <ObserveStep o={l.observe} course={course} lesson={l} />}
      {step === 'explain' && <><Paragraphs text={l.explain.text} /><Diagram id={l.explain.diagram} /><Claims ids={l.explain.claims ?? []} claims={claims} /></>}
      {step === 'try' && tryEx && <TryStep e={tryEx} lesson={l} onGraded={(g) => { setLast(g); onChange(); to('check'); }} onChange={onChange} />}
      {step === 'check' && <CheckStep e={tryEx} grade={last} lesson={l} onRetry={() => to('try')} />}
      {step === 'ros2' && <><p><span className={`claim-label ${l.ros2.label.toLowerCase().replace(/\s+/g, '-')}`} title={LABEL_MEANING[l.ros2.label]}>{l.ros2.label}</span></p>
        <Paragraphs text={l.ros2.text} /><Claims ids={l.ros2.claims} claims={claims} /></>}
    </section>
    <nav className="beat-nav course-nav">
      <button type="button" disabled={i === 0} onClick={() => to(STEPS[i - 1])}>← Back</button>
      {i < STEPS.length - 1 ? <button type="button" data-testid="next" onClick={() => to(STEPS[i + 1])}>Next →</button>
        : <button type="button" onClick={() => go({ module: m.id })}>Back to the module</button>}
    </nav>
  </article>;
}

function Paragraphs({ text }: { text: string }) {
  return <>{text.split(/\n+/).map((p, k) => <p key={k} className="course-p">{p}</p>)}</>;
}

function Claims({ ids, claims }: { ids: string[]; claims: Map<string, Claim> }) {
  if (!ids.length) return null;
  return <details className="course-claims" open><summary>The evidence ({ids.length})</summary>
    {ids.map((id) => { const c = claims.get(id); if (!c) return null; return (
      <div className="claim" key={id} data-testid={`claim-${id}`}>
        <span className={`claim-label ${c.label.toLowerCase().replace(/\s+/g, '-')}`} title={LABEL_MEANING[c.label]}>{c.label}</span>
        <p>{c.text}</p>
        <p className="cite">{LABEL_MEANING[c.label]} Evidence:{' '}{c.resolved.map((r, k) => <span key={r}>{k > 0 && '; '}<a href={sourceHref(r)} target="_blank" rel="noreferrer">{r}</a></span>)}</p>
      </div>); })}
  </details>;
}

function sourceHref(r: string): string {
  const m = /^docs\/v2\/r4\/SOURCES\.md > (.*)$/.exec(r);
  return m ? evidenceHref('docs/v2/r4/SOURCES.md') : evidenceHref(r);
}

// -- predict -------------------------------------------------------------------------------------

function PredictStep({ e, lessonId, kind, onChange, onGraded }: { e: Exercise; lessonId: string; kind: 'predict' | 'try'; onChange: () => void; onGraded?: (g: Grade) => void }) {
  const saved = kind === 'predict' ? lessonProgress(lessonId).predicted : undefined;
  const [picked, setPicked] = useState<number | null>(saved ?? null);
  const pick = (i: number) => {
    setPicked(i);
    if (kind === 'predict') { updateLesson(lessonId, (p) => ({ ...p, predicted: p.predicted ?? i })); onChange(); }
    else if (onGraded) {
      const ok = i === e.answer;
      const g: Grade = { schema: 'coco.lesson.grade.v1', exercise: e.id, type: 'predict', answer_sha256: '', passed: ok, checks_passed: ok ? 1 : 0, checks: 1, digest: '',
        results: [{ check: 'choice', label: 'your answer', passed: ok, which: 'public', scenario: null, measured: i, target: e.answer, message: ok ? 'right' : e.misconceptions?.[String(i)] ?? '' }] };
      onGraded(g);
    }
  };
  return <div>
    <p className="beat-q" id={`q-${e.id}`}>{e.question}</p>
    <div className="predict-options" role="radiogroup" aria-labelledby={`q-${e.id}`}>
      {e.options!.map((o, i) => (
        <button key={o} type="button" role="radio" aria-checked={picked === i} data-testid={`option-${i}`} disabled={kind === 'predict' && picked !== null}
          className={picked === null ? '' : i === e.answer ? 'right' : i === picked ? 'wrong' : ''} onClick={() => pick(i)}>
          {picked !== null && i === e.answer && <span className="sr-only">Correct answer: </span>}{o}</button>))}
    </div>
    {picked !== null && kind === 'predict' && <div className="verdict" role="status" data-testid="verdict">
      {picked === e.answer ? <p><b>Yes.</b> Now watch it happen.</p>
        : <><p><b>A common prediction -- and not what happens.</b> The answer is &ldquo;{e.options![e.answer!]}&rdquo;.</p>
          <p className="course-misconception" data-testid="misconception">{e.misconceptions?.[String(picked)]}</p></>}
    </div>}
  </div>;
}

// -- observe -------------------------------------------------------------------------------------

function specFor(course: Course, family: string, world: string, algorithms: string[], scen: Scenario[], maxTicks?: number): ExperimentSpec {
  const s: ExperimentSpec = { schema: 'coco.experiment.v1', title: 'From the Learn course', world, family: family as ExperimentSpec['family'], seed: 1,
    algorithms: algorithms.map((name) => ({ name })) as ExperimentSpec['algorithms'],
    scenarios: { kind: 'inline', scenarios: scen.map(({ id, start, goal, seed, config }) => ({ id, start, goal, seed, ...(config ? { config } : {}) })) } as unknown as ExperimentSpec['scenarios'] };
  if (family !== 'planning') s.limits = { max_ticks: maxTicks ?? 1500 };
  void course;
  return s;
}

function ObserveStep({ o, course, lesson }: { o: Lesson['observe']; course: Course; lesson: Lesson }) {
  const [studio, setStudio] = useState<string | null>(null);
  useEffect(() => {
    if (!o.studio) return;
    const e = course.exercises[o.studio];
    if (e?.starter_code) codeFragment({ code: e.starter_code, file: `${e.id}.py` }).then((f) => setStudio(`${BASE}?view=workbench&tab=studio#${f}`)).catch(() => setStudio(null));
  }, [o.studio, course]);
  const ex = o.experiment ? course.exercises[o.experiment.from] : null;
  return <div>
    <Paragraphs text={o.text} />
    <div className="course-links">
      {o.experiment && ex?.public_scenarios && <a className="arena-go" data-testid="observe-experiment"
        href={experimentLink(specFor(course, o.experiment.family, o.experiment.world, o.experiment.algorithms, ex.public_scenarios, ex.max_ticks), SITE())}>
        Run it in the Workbench (MODEL, in your browser) →</a>}
      {o.arena && <a className="arena-go" data-testid="observe-arena" href={arenaLink(o.arena, lesson.id)}>Open it in the Arena →</a>}
      {studio && <a className="arena-go" data-testid="observe-studio" href={studio}>Open the starter in the Algorithm Studio →</a>}
      {o.link && <a className="arena-go" href={`${BASE}?view=${o.link.view}${o.link.tab ? `&tab=${o.link.tab}` : ''}`}>Open it →</a>}
    </div>
    {o.timeline && course.exercises[o.timeline]?.timeline && <Timeline e={course.exercises[o.timeline]} readOnly />}
  </div>;
}

function arenaLink(a: NonNullable<Lesson['observe']['arena']>, lessonId: string): string {
  const q = new URLSearchParams({ view: 'arena' });
  if (a.lens) q.set('lens', a.lens);
  if (a.level) q.set('level', a.level);
  if (a.camera) q.set('camera', a.camera);
  for (const c of a.cfg ?? []) q.append('cfg', c);
  void lessonId;
  return `${BASE}?${q.toString()}`;
}

// -- try -----------------------------------------------------------------------------------------

function TryStep({ e, lesson, onGraded, onChange }: { e: Exercise; lesson: Lesson; onGraded: (g: Grade) => void; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const submit = async (answer: Answer, attemptIsReal = true) => {
    setBusy(true); setErr('');
    try {
      const g = await runGrade(e, answer);
      updateLesson(lesson.id, (p) => ({ ...p, attempts: p.attempts + (attemptIsReal ? 1 : 0),
        ...(g.passed && !p.passed ? { passed: true, answer, digest: g.digest, at: new Date().toISOString() } : {}) }));
      onGraded(g);
    } catch (x) { setErr(String((x as Error).message)); } finally { setBusy(false); }
  };
  const predictGraded = (g: Grade) => {
    updateLesson(lesson.id, (p) => ({ ...p, attempts: p.attempts + 1,
      ...(g.passed && !p.passed ? { passed: true, answer: { choice: g.results[0].measured as number }, at: new Date().toISOString() } : {}) }));
    onGraded(g);
  };
  return <div>
    {e.type === 'predict' && <PredictStep e={e} lessonId={lesson.id} kind="try" onChange={onChange} onGraded={predictGraded} />}
    {e.type === 'tune' && <Tune e={e} busy={busy} onCheck={(params) => submit({ params })} />}
    {e.type === 'failure' && <Timeline e={e} busy={busy} onCheck={(tick) => submit({ tick })} />}
    {(e.type === 'code' || e.type === 'benchmark') && <CodeTry e={e} lesson={lesson} busy={busy} onCheck={(code) => submit({ code }, code !== e.starter_code)} onChange={onChange} />}
    {busy && <p role="status" className="course-busy" data-testid="grading">Checking in your browser… (the first check starts Python: a few seconds)</p>}
    {err && <p role="alert" className="wb-error">{err}</p>}
    {e.type !== 'predict' && e.hints && <Hints e={e} lesson={lesson} onChange={onChange} />}
  </div>;
}

function Tune({ e, busy, onCheck }: { e: Exercise; busy: boolean; onCheck: (p: Record<string, number>) => void }) {
  const [vals, setVals] = useState<Record<string, number>>(() => Object.fromEntries(Object.entries(e.params!).map(([k, r]) => [k, r.default])));
  return <div>
    <p>Targets: {(e.checks ?? []).map((c) => c.label).filter(Boolean).join('; ')}.</p>
    <div className="course-sliders">{Object.entries(e.params!).map(([k, r]) => (
      <label key={k}><span>{r.label}: <output data-testid={`value-${k}`}>{vals[k]}</output></span>
        <input type="range" min={r.min} max={r.max} step={r.step} value={vals[k]} aria-label={r.label} data-testid={`slider-${k}`}
          onChange={(ev) => setVals({ ...vals, [k]: Number(ev.target.value) })} />
      </label>))}
    </div>
    <button type="button" className="wb-primary" disabled={busy} data-testid="check" onClick={() => onCheck(vals)}>Check these values</button>
  </div>;
}

const COLS = { v: 3, clearance: 4, contact: 5 } as const;

function Timeline({ e, readOnly = false, busy = false, onCheck }: { e: Exercise; readOnly?: boolean; busy?: boolean; onCheck?: (tick: number) => void }) {
  const tl = e.timeline!;
  const n = tl.series.length;
  const [i, setI] = useState(Math.floor(n / 2));
  const w = 600, h = 160;
  const maxTick = tl.series[n - 1][0] || 1;
  const x = (t: number) => 30 + (t / maxTick) * (w - 40);
  const maxV = Math.max(0.3, ...tl.series.map((r) => r[COLS.v]));
  const maxC = Math.max(0.5, ...tl.series.map((r) => r[COLS.clearance]));
  const line = (col: number, max: number) => tl.series.map((r) => `${x(r[0]).toFixed(1)},${(h - 20 - Math.max(0, r[col]) / max * (h - 40)).toFixed(1)}`).join(' ');
  const row = tl.series[i];
  return <div className="course-timeline">
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label={`Timeline of the run: ${n} ticks, speed and clearance; status ${tl.status}`}>
      <polyline points={line(COLS.v, maxV)} fill="none" stroke="#0072B2" strokeWidth={2} />
      <polyline points={line(COLS.clearance, maxC)} fill="none" stroke="#E69F00" strokeWidth={2} strokeDasharray="5 3" />
      {tl.series.filter((r) => r[COLS.contact]).map((r) => <rect key={r[0]} x={x(r[0]) - 1.5} y={4} width={3} height={12} fill="#D55E00" />)}
      <line x1={x(row[0])} y1={0} x2={x(row[0])} y2={h} stroke="currentColor" strokeWidth={1.5} />
      <text x={30} y={h - 4} fontSize="11" fill="currentColor">solid: speed · dashed: clearance · marks at top: contact</text>
    </svg>
    <label className="course-tick">Tick <output data-testid="tick">{row[0]}</output> · t = {(row[0] * 0.1).toFixed(1)} s · speed {row[COLS.v].toFixed(2)} m/s · clearance {row[COLS.clearance].toFixed(2)} m{row[COLS.contact] ? ' · CONTACT' : ''}
      <input type="range" min={0} max={n - 1} value={i} onChange={(ev) => setI(Number(ev.target.value))} aria-label="Pick a tick of the run" data-testid="tick-slider" />
    </label>
    <p className="wb-muted">Run status at the end: {tl.status} · {tl.ticks} ticks · MODEL</p>
    {!readOnly && <button type="button" className="wb-primary" disabled={busy} data-testid="check" onClick={() => onCheck?.(row[0])}>This is the tick</button>}
  </div>;
}

function CodeTry({ e, lesson, busy, onCheck, onChange }: { e: Exercise; lesson: Lesson; busy: boolean; onCheck: (code: string) => void; onChange: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  const editor = useRef<{ text(): string; setText(s: string): void; destroy(): void } | null>(null);
  const [plain, setPlain] = useState<string | null>(null);
  const progress = lessonProgress(lesson.id);
  const initial = (progress.answer?.code as string | undefined) ?? e.starter_code!;
  const [showSolution, setShowSolution] = useState(progress.solution);
  useEffect(() => {
    let dead = false;
    void import('../studio/editor').then(({ createEditor }) => {
      if (dead || !host.current) return;
      editor.current = createEditor(host.current, initial, () => {});
    }).catch(() => setPlain(initial));
    return () => { dead = true; editor.current?.destroy(); };
  }, []);
  const text = () => editor.current?.text() ?? plain ?? initial;
  const canSee = progress.attempts > 0;
  return <div>
    <p>Edit the file, then check it. The check runs your file on the scenarios below and on hidden ones drawn from your file's own hash.</p>
    {plain === null ? <div ref={host} className="course-editor" data-testid="editor" /> :
      <textarea aria-label="Your code (Python)" value={plain} onChange={(ev) => setPlain(ev.target.value)} rows={24} />}
    <div className="wb-runbar">
      <button type="button" className="wb-primary" disabled={busy} data-testid="check" onClick={() => onCheck(text())}>Check my code</button>
      <button type="button" disabled={busy} onClick={() => { editor.current?.setText(e.starter_code!); if (plain !== null) setPlain(e.starter_code!); }}>Back to the starter</button>
      <button type="button" disabled={!canSee} data-testid="show-solution" title={canSee ? '' : 'Unlocks after your first real attempt'}
        onClick={() => { updateLesson(lesson.id, (p) => ({ ...p, solution: true })); setShowSolution(true); onChange(); }}>
        {canSee ? 'Show the reference solution (recorded: 1 star)' : 'Reference solution: after a real attempt'}</button>
    </div>
    {e.public_scenarios && <p className="wb-muted">Public scenarios: {e.public_scenarios.map((s) => `${s.id} (${s.start[0].toFixed(1)}, ${s.start[1].toFixed(1)}) → (${s.goal[0].toFixed(1)}, ${s.goal[1].toFixed(1)})`).join('; ')}</p>}
    {showSolution && <details open className="course-solution"><summary>The reference solution</summary><pre>{e.solution_code}</pre></details>}
  </div>;
}

function Hints({ e, lesson, onChange }: { e: Exercise; lesson: Lesson; onChange: () => void }) {
  const [n, setN] = useState(lessonProgress(lesson.id).hints);
  const names = ['A nudge', 'The concept', 'Nearly the answer'];
  return <div className="course-hints">
    {e.hints!.slice(0, n).map((h, k) => <p key={k} className="wb-note"><b>{names[k]}:</b> {h}</p>)}
    {n < 3 && <button type="button" data-testid="hint" onClick={() => { const m = n + 1; setN(m); updateLesson(lesson.id, (p) => ({ ...p, hints: Math.max(p.hints, m) })); onChange(); }}>
      Show a hint: {names[n].toLowerCase()} {n === 2 ? '(recorded: 1 star)' : n === 0 ? '(recorded: 2 stars)' : ''}</button>}
  </div>;
}

// -- check ---------------------------------------------------------------------------------------

function CheckStep({ e, grade: g, lesson, onRetry }: { e: Exercise; grade: Grade | null; lesson: Lesson; onRetry: () => void }) {
  const p = lessonProgress(lesson.id);
  if (!g) return <div><p>{p.passed ? <>You passed this lesson <Stars n={stars(p)} label="this lesson" />.</> : 'Nothing checked yet.'}</p>
    <button type="button" onClick={onRetry}>Go to Try</button></div>;
  const scen = new Map([...(g.scenarios?.public ?? []), ...(g.scenarios?.hidden ?? [])].map((s) => [s.id, s]));
  return <div data-testid="check-result">
    <p className={g.passed ? 'wb-ok' : 'wb-error'} role="status" data-testid="verdict" data-digest={g.digest} data-passed={String(g.passed)}>
      {g.passed ? <><b>Passed.</b> {g.checks_passed} of {g.checks} checks. <Stars n={stars(p)} label="this lesson" /></>
        : <><b>Not yet.</b> {g.checks_passed} of {g.checks} checks passed. Read what failed, then try again.</>}</p>
    <div className="course-table-wrap"><table className="course-results">
      <thead><tr><th scope="col">Result</th><th scope="col">Check</th><th scope="col">Set</th><th scope="col">Scenario</th><th scope="col">What was measured</th><th scope="col">See it</th></tr></thead>
      <tbody>{g.results.map((r, k) => (
        <tr key={k} className={r.passed ? 'ok' : 'bad'}>
          <td>{r.passed ? '✓ pass' : '✗ fail'}</td><td>{r.label}</td><td>{r.which}</td><td>{r.scenario ?? 'all'}</td><td>{r.message}</td>
          <td>{!r.passed && r.scenario && scen.get(r.scenario) && e.world && e.family && <a href={compareFor(e, scen.get(r.scenario)!)} data-testid="open-compare">Open in Compare</a>}</td>
        </tr>))}</tbody>
    </table></div>
    {!g.passed && <button type="button" onClick={onRetry}>Try again</button>}
    {g.digest && <p className="wb-muted">Grade digest {g.digest.slice(0, 16)}… (the same answer gives the same digest in every browser and natively).</p>}
  </div>;
}

function compareFor(e: Exercise, s: Scenario): string {
  const algos = e.family === 'control' ? ['rpp', 'dwa'] : e.type === 'tune' && e.algorithm ? [e.algorithm, 'astar'] : ['astar', 'dijkstra'];
  const spec = specFor({} as Course, e.family!, e.world!, [...new Set(algos)], [s], e.max_ticks);
  return compareHrefFor(spec, { index: 0, fail_tick: null, success: false } as unknown as RunRecord);
}

// -- glossary, progress --------------------------------------------------------------------------

function Glossary({ course }: { course: Course }) {
  return <section className="wb-section" data-testid="glossary"><h1 className="course-h1">Glossary</h1>
    <p className="wb-muted">{course.glossary.length} terms, each introduced once in the lessons. ROS 2 terms included.</p>
    <dl className="course-glossary">{course.glossary.map((t) => <div key={t.term} id={`g-${t.term.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}>
      <dt>{t.term}{t.module > 0 && <span className="wb-muted"> · module {t.module}</span>}</dt><dd>{t.text}</dd></div>)}</dl>
  </section>;
}

function download(name: string, text: string, type = 'application/json') {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function ProgressPage({ course, onChange }: { course: Course; onChange: () => void }) {
  const [msg, setMsg] = useState('');
  const p = loadProgress();
  return <section className="wb-section" data-testid="progress"><h1 className="course-h1">My progress</h1>
    <p>Kept in this browser only. Export it as a file to move it to another browser or keep a copy.</p>
    <div className="wb-runbar">
      <button type="button" onClick={() => download('coco-lab-progress.json', exportProgress())}>Export progress (file)</button>
      <label className="course-file">Import progress<input type="file" accept="application/json,.json" onChange={async (ev) => {
        const f = ev.target.files?.[0]; if (!f) return;
        try { importProgress(await f.text()); setMsg('Imported.'); onChange(); } catch (x) { setMsg(String((x as Error).message)); }
      }} /></label>
      <button type="button" onClick={() => { resetProgress(); setMsg('Progress cleared.'); onChange(); }}>Clear my progress</button>
    </div>
    {msg && <p role="status">{msg}</p>}
    <div className="course-table-wrap"><table className="course-results"><thead><tr><th scope="col">Module</th><th scope="col">Lesson</th><th scope="col">Track</th><th scope="col">Stars</th><th scope="col">Hints</th><th scope="col">Solution viewed</th></tr></thead>
      <tbody>{course.modules.flatMap((m) => m.lessons.map((l) => { const lp: LessonProgress = p.lessons[l.id] ?? lessonProgress(l.id); return (
        <tr key={l.id}><td>{m.number}</td><td><a href={href({ lesson: l.id, step: 'predict' })}>{l.title}</a></td><td>{l.track}</td>
          <td><Stars n={stars(lp)} /></td><td>{lp.hints}</td><td>{lp.solution ? 'yes' : 'no'}</td></tr>); }))}</tbody></table></div>
  </section>;
}

// -- completion links, assignments, verification, the class dashboard ----------------------------

function CompletionMaker({ course, title, lessonIds, askName, assignment }: { course: Course; title: string; lessonIds: string[]; askName: boolean; assignment?: string }) {
  const [name, setName] = useState('');
  const [link, setLink] = useState('');
  const [err, setErr] = useState('');
  const make = async () => {
    setErr('');
    const entries = lessonIds.map((id) => {
      const f = findLesson(course, id)!; const p = lessonProgress(id);
      return p.passed && p.answer ? { lesson: id, exercise: f.lesson.try, answer: p.answer, hints: p.hints, solution: p.solution } : null;
    }).filter((x): x is NonNullable<typeof x> => x !== null);
    if (!entries.length) { setErr('Pass at least one lesson first.'); return; }
    try {
      const frag = await completionFragment({ title, name: name.trim() || undefined, assignment, issued: new Date().toISOString().slice(0, 10), entries });
      setLink(`${SITE()}?view=learn&page=verify#${frag}`);
    } catch (x) { setErr(String((x as Error).message)); }
  };
  return <fieldset className="course-completion"><legend>Completion link</legend>
    <p>A link that carries your passed answers{askName ? ' and, if you type it, your name' : ''}. Anyone who opens it re-checks every answer in their own
      browser. <b>Self-verified, not proctored:</b> it proves the answers pass, not who wrote them.</p>
    {askName && <label>Your name (optional; it is only in the link you share)<input value={name} maxLength={80} onChange={(ev) => setName(ev.target.value)} autoComplete="off" /></label>}
    <button type="button" data-testid="make-completion" onClick={make}>Make my completion link ({lessonIds.filter((id) => lessonProgress(id).passed).length} passed)</button>
    {err && <p role="alert" className="wb-error">{err}</p>}
    {link && <p><a href={link} data-testid="completion-link">Your completion link</a> <button type="button" onClick={() => navigator.clipboard?.writeText(link)}>Copy</button></p>}
  </fieldset>;
}

interface VerifiedRow { lesson: string; title: string; passed: boolean; hints: number; solution: boolean; message: string }

async function verifyCompletion(course: Course, c: Completion, onRow?: (r: VerifiedRow) => void): Promise<VerifiedRow[]> {
  const rows: VerifiedRow[] = [];
  for (const en of c.entries) {
    const f = findLesson(course, en.lesson);
    const e = course.exercises[en.exercise];
    let row: VerifiedRow;
    if (!f || !e || f.lesson.try !== en.exercise) row = { lesson: en.lesson, title: en.lesson, passed: false, hints: en.hints, solution: en.solution, message: 'not a lesson of this course' };
    else if (e.type === 'predict') {
      const ok = en.answer.choice === e.answer;
      row = { lesson: en.lesson, title: f.lesson.title, passed: ok, hints: en.hints, solution: en.solution, message: ok ? 'right answer' : 'wrong answer' };
    } else {
      const g = await runGrade(e, en.answer);
      row = { lesson: en.lesson, title: f.lesson.title, passed: g.passed, hints: en.hints, solution: en.solution,
        message: `${g.checks_passed}/${g.checks} checks${g.passed ? '' : ': ' + (g.results.find((r) => !r.passed)?.message ?? '')}` };
    }
    rows.push(row);
    onRow?.(row);
  }
  return rows;
}

function Verify({ course }: { course: Course }) {
  const [c, setC] = useState<Completion | null>(null);
  const [rows, setRows] = useState<VerifiedRow[]>([]);
  const [err, setErr] = useState('');
  const [done, setDone] = useState(false);
  useEffect(() => {
    readCompletion(window.location.hash).then(async (x) => {
      setC(x);
      await verifyCompletion(course, x, (r) => setRows((rs) => [...rs, r]));
      setDone(true);
    }).catch((e) => setErr(String((e as Error).message)));
  }, [course]);
  return <section className="wb-section" data-testid="verify"><h1 className="course-h1">Completion link</h1>
    <p className="wb-note"><b>Self-verified, not proctored.</b> Every answer below is re-checked now, in this browser, by the same grader the
      lesson used. The name and the hint counts are what the learner declared.</p>
    {err && <p role="alert" className="wb-error">{err}</p>}
    {c && <><p><b>{c.title}</b>{c.name && <> · {c.name}</>} · issued {c.issued}{c.assignment && <> · assignment: {c.assignment}</>}</p>
      <VerifyTable rows={rows} />
      <p role="status" data-testid="verify-status">{done ? `Re-verified: ${rows.filter((r) => r.passed).length} of ${rows.length} pass.` : `Re-checking ${rows.length + 1} of ${c.entries.length}…`}</p></>}
  </section>;
}

function VerifyTable({ rows }: { rows: VerifiedRow[] }) {
  return <div className="course-table-wrap"><table className="course-results" data-testid="verify-table"><thead><tr><th scope="col">Lesson</th><th scope="col">Re-verified</th><th scope="col">Hints used</th><th scope="col">Solution viewed</th><th scope="col">Detail</th></tr></thead>
    <tbody>{rows.map((r) => <tr key={r.lesson} className={r.passed ? 'ok' : 'bad'}><td>{r.title}</td><td>{r.passed ? '✓ pass' : '✗ fail'}</td><td>{r.hints}</td><td>{r.solution ? 'yes' : 'no'}</td><td>{r.message}</td></tr>)}</tbody></table></div>;
}

function AssignmentPage({ course }: { course: Course }) {
  const [a, setA] = useState<Assignment | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { readAssignment(window.location.hash).then(setA).catch((e) => setErr(String((e as Error).message))); }, []);
  return <section className="wb-section" data-testid="assignment"><h1 className="course-h1">{a?.title ?? 'Assignment'}</h1>
    {err && <p role="alert" className="wb-error">{err}</p>}
    {a && <>{a.deadline && <p><b>Deadline:</b> {a.deadline}</p>}
      <ol className="course-lesson-list">{a.lessons.map((id) => { const f = findLesson(course, id); return f ? <li key={id}><a href={href({ lesson: id, step: 'predict' })}>{f.lesson.title}</a> (module {f.module.number}) <Stars n={stars(lessonProgress(id))} /></li> : null; })}</ol>
      <CompletionMaker course={course} title={a.title} lessonIds={a.lessons} askName={a.askName} assignment={a.title} /></>}
  </section>;
}

function Teacher({ course }: { course: Course }) {
  const all = course.modules.flatMap((m) => m.lessons.map((l) => ({ m, l })));
  const [chosen, setChosen] = useState<string[]>([]);
  const [title, setTitle] = useState('Robotics: modules 1 and 2');
  const [deadline, setDeadline] = useState('');
  const [askName, setAskName] = useState(true);
  const [assignLink, setAssignLink] = useState('');
  const [links, setLinks] = useState('');
  const [table, setTable] = useState<{ who: string; title: string; rows: VerifiedRow[]; error?: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const makeAssignment = async () => setAssignLink(`${SITE()}?view=learn&page=assignment#${await assignmentFragment({ title, lessons: chosen, deadline: deadline || undefined, askName })}`);
  const check = async () => {
    setBusy(true); setTable([]);
    for (const line of links.split(/\s+/).filter(Boolean)) {
      const hash = line.includes('#') ? line.slice(line.indexOf('#')) : line;
      try {
        const c = await readCompletion(hash);
        const rows = await verifyCompletion(course, c);
        setTable((t) => [...t, { who: c.name ?? '(no name)', title: c.title, rows }]);
      } catch (e) { setTable((t) => [...t, { who: '?', title: line.slice(0, 40), rows: [], error: String((e as Error).message) }]); }
    }
    setBusy(false);
  };
  const csv = () => {
    const head = ['name', 'link title', 'lesson', 're-verified', 'hints used', 'solution viewed', 'detail'];
    const lines = [head.map(csvCell).join(',')];
    for (const t of table) {
      if (t.error) lines.push([t.who, t.title, '', 'link error', '', '', t.error].map(csvCell).join(','));
      for (const r of t.rows) lines.push([t.who, t.title, r.title, r.passed ? 'pass' : 'fail', r.hints, r.solution ? 'yes' : 'no', r.message].map(csvCell).join(','));
    }
    download('coco-lab-class.csv', lines.join('\r\n') + '\r\n', 'text/csv');
  };
  return <section className="wb-section" data-testid="teacher"><h1 className="course-h1">For teachers</h1>
    <p>Everything here runs in your browser. Nothing is uploaded: an assignment is a link, and checking your students' completion links
      re-runs their answers on this device.</p>
    <fieldset><legend>1 · Make an assignment link</legend>
      <label>Title<input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} /></label>
      <label>Deadline label (optional, shown to students; nothing enforces it)<input value={deadline} maxLength={60} onChange={(e) => setDeadline(e.target.value)} /></label>
      <label className="wb-check"><input type="checkbox" checked={askName} onChange={(e) => setAskName(e.target.checked)} /> Ask students for a name (it stays in their link)</label>
      <div className="course-pick">{all.map(({ m, l }) => <label key={l.id} className="wb-check"><input type="checkbox" checked={chosen.includes(l.id)} data-testid={`pick-${l.id}`}
        onChange={(e) => setChosen(e.target.checked ? [...chosen, l.id] : chosen.filter((x) => x !== l.id))} /> M{m.number} · {l.title} <span className={`course-chip ${l.track}`}>{l.track}</span></label>)}</div>
      <button type="button" disabled={!chosen.length} data-testid="make-assignment" onClick={makeAssignment}>Make the assignment link</button>
      {assignLink && <p><a href={assignLink} data-testid="assignment-link">Assignment link</a> <button type="button" onClick={() => navigator.clipboard?.writeText(assignLink)}>Copy</button></p>}
    </fieldset>
    <fieldset><legend>2 · Class dashboard</legend>
      <label>Paste your students' completion links (one per line)<textarea value={links} onChange={(e) => setLinks(e.target.value)} data-testid="class-links" rows={6} /></label>
      <div className="wb-runbar"><button type="button" className="wb-primary" disabled={busy || !links.trim()} data-testid="check-class" onClick={check}>Re-verify all</button>
        <button type="button" disabled={!table.length} data-testid="class-csv" onClick={csv}>Export CSV</button></div>
      {busy && <p role="status">Re-checking… code exercises take up to a minute each.</p>}
      {table.map((t, k) => <div key={k} data-testid="class-row"><h3>{t.who} · {t.title}</h3>{t.error ? <p className="wb-error">{t.error}</p> : <VerifyTable rows={t.rows} />}</div>)}
      <p className="wb-muted">Self-verified, not proctored: a link proves its answers pass, not who wrote them.</p>
    </fieldset>
  </section>;
}
