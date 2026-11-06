// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.3 · Algorithm Studio (Workbench): write a planner, controller or localiser in Python against
 * coco_lab.api, run it on one scenario and watch it think (GAME or SIM), put it beside a built-in
 * (Compare), benchmark it on a COCO-Bench suite with R1's statistics, save it, share it.
 *
 * Everything the file does happens in the user-code sandbox (sandbox.ts; ADR 0012). Code from a
 * link is shown, never run, until the reader presses "Run this code".
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { readPref, writePref } from '../prefs';
import { label as algoLabel, META, type ExperimentSpec } from '../workbench/spec';
import { Results, type Summary } from '../workbench/Results';
import type { PlanInfo, RunRecord } from '../workbench/pool';
import { Sandbox, type Chunk, type Ended, type Family } from './sandbox';
import { SandboxPool, type PoolProgress } from './sandbox_pool';
import { StudioView, type Look, type MapInfo, type RunDraw } from './StudioView';
import { codeFragment, readCodeFragment } from './codelink';
import { saveBytes, zipFiles } from '../workbench/exports';
import { codeSha256, FAMILY_OF, kindOf, TEMPLATES, templateById, type Kind } from './templates';
import type { StudioEditor } from './editor';
import { REPO_BLOB_URL } from '../../site.config';
import './studio.css';

const BASE = import.meta.env.BASE_URL;
const API_DOC = `${REPO_BLOB_URL}docs/v2/r2/API.md`;
const MAX_FILE = 256 * 1024;

interface Draft { code: string; file: string; template: string; suite: string; index: number }
const isDraft = (v: unknown): v is Draft => typeof v === 'object' && v !== null && typeof (v as Draft).code === 'string'
  && typeof (v as Draft).file === 'string' && typeof (v as Draft).suite === 'string' && Number.isInteger((v as Draft).index);

interface Scenario { id: string; start: number[]; goal: number[]; seed: number }
interface SuiteFile { id: string; version: number; world: string; families: string[]; scenarios: Scenario[] }
interface Report {
  problems: { message: string; tick: number | null }[]; n_problems: number; clamped: number; clamp_examples: string[];
  calls: number; call_ms_max?: number; call_ms_total?: number; dropped_events: number; console: string;
  error: { type: string; message: string; line: number | null; frames: { line: number; function: string }[]; problems?: { line: number; message: string }[] } | null;
}
interface Rec { status: string; success: boolean; metrics: Record<string, number | boolean | null>; chain: string; deterministic?: boolean; report?: Report; error?: string; draw?: { path_cells: number[][]; cut: number } }
interface Pane { draw: RunDraw; rec: Rec | null; failure: Ended | null; title: string }
export interface StackEntry { label: string; rows: { metric: string; model: string; stack: string; gap: string }[]; source: string }

/** R2.7: the same file in the browser's model and as a real ROS 2 node in Gazebo + Nav2, labelled. */
export function BrowserVsRos({ s }: { s: StackEntry }) {
  return <details className="studio-exp" open data-testid="studio-stack">
    <summary>Browser vs ROS 2: {s.label}</summary>
    <table className="wb-table"><thead><tr><th scope="col">Metric</th><th scope="col">MODEL (browser)</th><th scope="col">STACK (Gazebo + Nav2)</th><th scope="col">Gap</th></tr></thead>
      <tbody>{s.rows.map((r) => <tr key={r.metric}><th scope="row">{r.metric}</th><td>{r.model}</td><td>{r.stack}</td><td>{r.gap}</td></tr>)}</tbody></table>
    <p className="studio-muted">{s.source}</p>
  </details>;
}

/** What the per-call times were measured on: what the browser offers without a user-agent string. */
function deviceLabel(): string {
  const d = (navigator as Navigator & { userAgentData?: { brands?: { brand: string }[]; platform?: string } }).userAgentData;
  const brand = d?.brands?.map((b) => b.brand).find((b) => !/Not.?A.?Brand|Chromium/i.test(b));
  return `${brand ?? 'this browser'}${d?.platform ? ` on ${d.platform}` : ''}, ${navigator.hardwareConcurrency ?? '?'} cores`;
}

const fmtN = (v: unknown) => (typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toFixed(3)) : v === null || v === undefined ? '—' : String(v));
const isPhone = () => typeof matchMedia !== 'undefined' && matchMedia('(pointer: coarse)').matches;

export default function StudioTab() {
  const asked = useMemo(() => templateById(new URLSearchParams(window.location.search).get('template') ?? ''), []);
  const draft = useMemo(() => (asked ? null : readPref<Draft | null>('studio', null, (v): v is Draft | null => v === null || isDraft(v))), [asked]);
  const first = asked ?? templateById(draft?.template ?? 'planner_astar') ?? TEMPLATES[0];
  const [code, setCode] = useState(draft?.code ?? first.source);
  const [file, setFile] = useState(draft?.file ?? `${first.id}.py`);
  const [template, setTemplate] = useState(draft?.template ?? first.id);
  const [suiteId, setSuiteId] = useState(draft?.suite ?? 'arena-nav-50');
  const [index, setIndex] = useState(draft?.index ?? 0);
  const [look, setLook] = useState<Look>(() => readPref<Look>('view', 'game', (v): v is Look => v === 'game' || v === 'sim'));
  const [linked, setLinked] = useState<{ consented: boolean } | null>(null);
  const [linkError, setLinkError] = useState('');
  const [suites, setSuites] = useState<Record<string, SuiteFile>>({});
  const [map, setMap] = useState<{ world: string; info: MapInfo } | null>(null);
  const [panes, setPanes] = useState<Pane[]>([]);
  const [busy, setBusy] = useState('');
  const [guard, setGuard] = useState<{ line: number; message: string }[]>([]);
  const [rival, setRival] = useState('astar');
  const [share, setShare] = useState<{ url?: string; error?: string } | null>(null);
  const [tab, setTab] = useState<'results' | 'console' | 'validation'>('results');
  const [exp, setExp] = useState<{ spec: ExperimentSpec; plan: PlanInfo; records: RunRecord[]; summary: Summary | null; progress: PoolProgress | null } | null>(null);
  const [rivals, setRivals] = useState<string[]>(['astar']);
  const [probe, setProbe] = useState<Record<string, string> | null>(null);
  const [stack, setStack] = useState<StackEntry | null>(null);
  // R2.7: Browser vs ROS 2 -- shown only for the exact file (sha256) that ran in Gazebo + Nav2
  useEffect(() => {
    let alive = true;
    void codeSha256(code).then((sha) => fetch(`${BASE}generated/r2/stack.json`).then((r) => (r.ok ? r.json() : null))
      .then((d: { entries?: Record<string, StackEntry> } | null) => { if (alive) setStack(d?.entries?.[sha] ?? null); })).catch(() => {});
    return () => { alive = false; };
  }, [code]);
  const editor = useRef<StudioEditor | null>(null);
  // the code the editor must show when it is created: a link or an entry may arrive before CodeMirror
  // has loaded, and the editor must never show other code than the code Run would run
  const codeRef = useRef(code);
  codeRef.current = code;
  const host = useRef<HTMLDivElement>(null);
  const sandbox = useRef<Sandbox | null>(null);
  const pool = useRef<SandboxPool | null>(null);
  const kind: Kind | null = kindOf(code);
  const family = kind ? FAMILY_OF[kind] : null;
  const suiteOptions = META.suites.filter((s) => family && (s.families as string[]).includes(family));
  const suite = suites[suiteId];
  const blocked = linked !== null && !linked.consented;

  useEffect(() => { document.title = 'Algorithm Studio · COCO Lab'; }, []);
  // a code link (or a leaderboard entry): show it, never run it until the reader says so
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const entry = q.get('entry');
    if (entry && /^[a-z0-9-]+\/[a-z0-9_-]+$/.test(entry)) {
      const [s, n] = entry.split('/');
      void fetch(`${BASE}generated/r2/submissions/${s}/${n}.py`).then((r) => { if (!r.ok) throw new Error(`no entry ${entry}`); return r.text(); }).then((t) => {
        codeRef.current = t;
        setCode(t); setFile(`${n}.py`); setTemplate(''); setSuiteId(s);
        const sc = Number(q.get('scenario'));
        if (Number.isInteger(sc) && sc >= 0) setIndex(sc);
        setLinked({ consented: false });
        editor.current?.setText(t);
      }).catch((e: Error) => setLinkError(e.message));
      return;
    }
    void readCodeFragment(window.location.hash).then((l) => {
      if (!l) return;
      codeRef.current = l.code;
      setCode(l.code); setFile(l.file); setTemplate(l.template ?? '');
      if (l.suite) setSuiteId(l.suite);
      if (l.index !== undefined) setIndex(l.index);
      setLinked({ consented: false });
      editor.current?.setText(l.code);
    }).catch((e: Error) => setLinkError(e.message));
  }, []);
  // the editor (CodeMirror loads only here)
  useEffect(() => {
    let alive = true;
    void import('./editor').then(({ createEditor }) => {
      if (!alive || !host.current) return;
      editor.current = createEditor(host.current, codeRef.current, (s) => setCode(s));
    });
    return () => { alive = false; editor.current?.destroy(); editor.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // the local draft (prefs; storage may be unavailable): not a stranger's code before consent
  useEffect(() => {
    if (blocked) return;
    const t = setTimeout(() => writePref('studio', { code, file, template, suite: suiteId, index } satisfies Draft), 500);
    return () => clearTimeout(t);
  }, [code, file, template, suiteId, index, blocked]);
  useEffect(() => () => { sandbox.current?.terminate(); pool.current?.close(); }, []);
  // the suite's scenarios (R1's frozen files, as shipped)
  useEffect(() => {
    const s = META.suites.find((x) => x.id === suiteId);
    if (!s || suites[suiteId]) return;
    void fetch(`${BASE}generated/r1/benchmarks/${s.id}.v${s.version}.json`).then((r) => r.json()).then((j: SuiteFile) => setSuites((m) => ({ ...m, [suiteId]: j })));
  }, [suiteId, suites]);
  useEffect(() => { if (family && !suiteOptions.some((s) => s.id === suiteId) && suiteOptions[0]) setSuiteId(suiteOptions[0].id); }, [family]); // eslint-disable-line react-hooks/exhaustive-deps

  const box = () => (sandbox.current ??= new Sandbox());

  const pickTemplate = (id: string) => {
    const t = templateById(id);
    if (!t) return;
    setTemplate(id); setFile(`${id}.py`); setCode(t.source); editor.current?.setText(t.source);
    setPanes([]); setGuard([]); editor.current?.mark([]); setExp(null);
  };

  /** Check the file in the sandbox (its top level runs there, guarded). */
  const check = useCallback(async (fam: Family): Promise<boolean> => {
    setBusy('Checking the file in the sandbox…');
    const e = await box().run({ op: 'check', code: [code] }, fam);
    if (!e.ok) { setBusy(''); setGuard([{ line: 0, message: e.message }]); return false; }
    const c = JSON.parse(e.result) as { ok: boolean; problems?: { line: number; message: string }[]; error?: Report['error'] };
    const probs = c.ok ? [] : c.problems ?? (c.error ? [{ line: c.error.line ?? 0, message: `${c.error.type}: ${c.error.message}` }] : []);
    setGuard(probs);
    editor.current?.mark(probs.map((p) => ({ line: p.line, message: p.message })));
    setBusy('');
    return c.ok;
  }, [code]);

  const ensureMap = async (world: string, fam: Family) => {
    if (map?.world === world) return;
    const e = await box().run({ op: 'map', world }, fam);
    if (e.ok) setMap({ world, info: JSON.parse(e.result) as MapInfo });
  };

  const specFor = async (algos: { name: string; id: string; label: string }[]): Promise<ExperimentSpec> => {
    const sha = await codeSha256(code);
    return { schema: 'coco.experiment.v1', family: family!, world: suite.world,
      algorithms: algos.map((a) => (a.name === 'user' ? { ...a, api: 1, code_sha256: sha } : a)) as ExperimentSpec['algorithms'],
      scenarios: { kind: 'suite', id: suite.id }, limits: { max_ticks: 3000 } };
  };

  /** One run, drawn as it streams; returns its pane. */
  const runPane = async (spec: ExperimentSpec, runIndex: number, title: string, slot: number): Promise<void> => {
    const sc = suite.scenarios[index];
    const draw: RunDraw = { family: family!, frames: [], expand: [], push: [], pathCells: [], start: sc.start, goal: sc.goal, done: false, label: `${title} · ${sc.id}` };
    const update = () => setPanes((ps) => { const next = [...ps]; next[slot] = { ...next[slot], draw: { ...draw } }; return next; });
    setPanes((ps) => { const next = [...ps]; next[slot] = { draw, rec: null, failure: null, title }; return next; });
    let pendingFrame = 0;
    const onChunk = (c: Chunk) => {
      draw.frames.push(...c.frames);
      for (const [k, list] of Object.entries(c.events)) {
        const dst = k === 'expand' ? draw.expand : k === 'push' || k === 'frontier' ? draw.push : null;
        if (dst) for (const d of list) { const x = Number(d.x), y = Number(d.y); if (Number.isFinite(x) && Number.isFinite(y)) dst.push(x, y); }
      }
      if (!pendingFrame) pendingFrame = requestAnimationFrame(() => { pendingFrame = 0; update(); });
    };
    const e = await box().run({ op: 'scenario', spec, code: [code], indices: [runIndex] }, family!, onChunk);
    draw.done = true;
    let rec: Rec | null = null;
    if (e.ok) {
      rec = JSON.parse(e.result) as Rec;
      draw.pathCells = rec.draw?.path_cells ?? [];
    }
    setPanes((ps) => { const next = [...ps]; next[slot] = { draw: { ...draw }, rec, failure: e.ok ? null : e, title }; return next; });
    const err = rec?.report?.error;
    if (slot === 0 && err?.line) editor.current?.mark([{ line: err.line, message: `${err.type}: ${err.message}` }]);
  };

  const runOne = async (compare: boolean) => {
    if (blocked || !family || !suite) return;
    setExp(null); setPanes([]); setTab('results');
    try {
      if (!(await check(family))) return;
      setBusy('Running in the sandbox…');
      await ensureMap(suite.world, family);
      const algos = [{ name: 'user', id: 'yours', label: file.replace(/\.py$/, '') }];
      if (compare) algos.push({ name: rival, id: rival, label: algoLabel(rival) });
      const spec = await specFor(algos);
      await runPane(spec, index, `Yours: ${file}`, 0);
      if (compare) await runPane(spec, suite.scenarios.length + index, `Built-in: ${algoLabel(rival)}`, 1);
    } catch (e) { setGuard([{ line: 0, message: String((e as Error).message) }]); }
    setBusy('');
  };

  const runExperiment = async () => {
    if (blocked || !family || !suite) return;
    setPanes([]);
    if (!(await check(family))) return;
    const spec = await specFor([{ name: 'user', id: 'yours', label: file.replace(/\.py$/, '') },
      ...rivals.map((r) => ({ name: r, id: r, label: algoLabel(r) }))]);
    const phone = isPhone();
    const size = Math.max(1, Math.min(phone ? 1 : 4, (navigator.hardwareConcurrency ?? 2) - 1));
    pool.current?.close();
    const p = (pool.current = new SandboxPool(size));
    try {
      setBusy(`Planning the experiment (${size} sandbox${size === 1 ? '' : 'es'})…`);
      const plan = JSON.parse(await p.call('plan', { spec, code: [code] }, family)) as PlanInfo;
      const nScen = plan.scenarios.length;
      const algos = plan.spec.algorithms as { id: string; name: string }[];
      setExp({ spec, plan, records: [], summary: null, progress: { done: 0, total: plan.n_runs, failed: 0 } });
      setBusy('');
      const got: RunRecord[] = [];
      const all = await p.run(spec, [code], family, [...Array(plan.n_runs).keys()], (r) => { got.push(r); setExp((x) => x && { ...x, records: [...got] }); },
        (pr) => setExp((x) => x && { ...x, progress: pr }),
        (i) => ({ algorithm: algos[Math.floor(i / nScen)].id, name: algos[Math.floor(i / nScen)].name, scenario_index: i % nScen, scenario: plan.scenarios[i % nScen].id as string }));
      setBusy('Computing the statistics…');
      const summary = JSON.parse(await p.call('summary', { spec, code: [code], records: all }, family)) as Summary;
      setExp((x) => x && { ...x, records: all, summary, progress: null });
    } catch (e) { setGuard([{ line: 0, message: String((e as Error).message) }]); }
    setBusy('');
  };

  const download = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([code], { type: 'text/x-python' }));
    a.download = file.endsWith('.py') ? file : `${file}.py`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  };
  const upload = (f: File | undefined) => {
    if (!f) return;
    if (f.size > MAX_FILE) { setGuard([{ line: 0, message: `${f.name} is over ${MAX_FILE / 1024} KB` }]); return; }
    void f.text().then((t) => { setCode(t); setFile(f.name.replace(/[^\w.-]/g, '_')); setTemplate(''); editor.current?.setText(t); setPanes([]); setGuard([]); });
  };
  /** R2.7: the same file as a ROS 2 package (coco_lab.ros2_export, run in the sandbox). */
  const exportRos = async () => {
    if (blocked || !family) return;
    const name = file.replace(/\.py$/, '').toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/^[^a-z]+/, '').slice(0, 40) || 'algorithm';
    setBusy('Generating the ROS 2 package…');
    const e = await box().run({ op: 'export', code: [code], name }, family);
    setBusy('');
    if (!e.ok) { setGuard([{ line: 0, message: e.message }]); return; }
    const files = JSON.parse(e.result) as Record<string, string>;
    const enc = new TextEncoder();
    saveBytes(`coco_user_${name}.zip`, zipFiles(Object.fromEntries(Object.entries(files).map(([k, v]) => [k, enc.encode(v)]))));
  };
  const copyLink = async () => {
    try {
      const frag = await codeFragment({ code, file, suite: suiteId, index, template });
      const url = `${new URL(BASE, window.location.href).href}?view=workbench&tab=studio#${frag}`;
      try { await navigator.clipboard.writeText(url); } catch { /* shown below anyway */ }
      setShare({ url });
    } catch (e) { setShare({ error: (e as Error).message }); }
  };

  const main = panes[0];
  const rep = main?.rec?.report;
  return <section className="studio" data-testid="studio">
    <div className="studio-intro">
      <p>Write a <b>planner</b>, <b>controller</b> or <b>localiser</b> in Python against <code>coco_lab.api</code> (ROS 2 message shapes). It runs in a sandbox in your browser: no network, no storage, a time and a memory limit. The same file runs natively and as a ROS 2 node. <a href={API_DOC} target="_blank" rel="noreferrer">API reference</a></p>
    </div>
    {linkError && <p className="wb-error" role="alert">{linkError}</p>}
    {linked && !linked.consented && <div className="studio-consent" role="alert" data-testid="studio-consent">
      <p><b>This link carries code someone else wrote.</b> Read it below first. It runs only in the sandbox (no network, no storage, time and memory limits), and only when you press the button.</p>
      <button className="primary" onClick={() => setLinked({ consented: true })} data-testid="studio-consent-run">Run this code</button>
    </div>}
    {isPhone() && <p className="studio-note" role="note">On a phone the editor is basic: reading, running and comparing work fully, but for long edits upload a .py file or use a laptop.</p>}
    <div className="studio-toolbar">
      <label>Start from <select value={template} onChange={(e) => pickTemplate(e.target.value)} data-testid="studio-template">
        {!templateById(template) && <option value="">{file}</option>}
        {TEMPLATES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}</select></label>
      <label className="studio-file">File <input value={file} onChange={(e) => setFile(e.target.value.replace(/[^\w.-]/g, '_').slice(0, 64))} aria-label="File name" /></label>
      <span className="studio-kind" data-testid="studio-kind">{kind ? `${kind} · ${family}` : 'define one of plan(), control(), localise()'}</span>
    </div>
    <div className="studio-grid">
      <div className="studio-code" ref={host} data-testid="studio-editor" />
      <div className="studio-right">
        <div className="studio-scenario">
          <label>Suite <select value={suiteId} onChange={(e) => { setSuiteId(e.target.value); setIndex(0); }}>
            {suiteOptions.map((s) => <option key={s.id} value={s.id}>{s.id}</option>)}</select></label>
          <span className="studio-stepper">
            <button onClick={() => setIndex((i) => Math.max(0, i - 1))} aria-label="Previous scenario" disabled={index <= 0}>‹</button>
            <span>scenario {suite ? `${index + 1} / ${suite.scenarios.length} (${suite.scenarios[index]?.id ?? '…'})` : '…'}</span>
            <button onClick={() => setIndex((i) => Math.min((suite?.scenarios.length ?? 1) - 1, i + 1))} aria-label="Next scenario" disabled={!suite || index >= suite.scenarios.length - 1}>›</button>
          </span>
        </div>
        <div className="studio-actions">
          <button className="primary" onClick={() => void runOne(false)} disabled={blocked || !!busy || !family || !suite} data-testid="studio-run">Run on this scenario</button>
          <span className="studio-compare">
            <button onClick={() => void runOne(true)} disabled={blocked || !!busy || !family || !suite} data-testid="studio-compare">Compare with</button>
            <select value={rival} onChange={(e) => setRival(e.target.value)} aria-label="Built-in to compare with">
              {(family ? META.algorithms[family] : []).map((a) => <option key={a} value={a}>{algoLabel(a)}</option>)}</select>
          </span>
        </div>
        {busy && <p role="status" className="studio-muted">{busy}</p>}
        {guard.length > 0 && <div className="wb-error" role="alert" data-testid="studio-guard">{guard.map((g, i) => <p key={i}>{g.line ? <button className="linkish" onClick={() => editor.current?.goto(g.line)}>line {g.line}</button> : null} {g.message}</p>)}</div>}
        <div className={`studio-panes n${Math.max(1, panes.length)}`}>
          {(panes.length ? panes : [null]).map((p, i) => <StudioView key={i} map={map?.info ?? null} run={p?.draw ?? null} look={look} title={p?.title}
            onLook={(l) => { setLook(l); writePref('view', l); }} />)}
        </div>
        {main && <div className="studio-tabs" role="tablist">
          {(['results', 'console', 'validation'] as const).map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t === 'results' ? 'Results' : t === 'console' ? 'Console' : 'Validation'}</button>)}
        </div>}
        {main && tab === 'results' && <ResultsTable panes={panes} />}
        {main && tab === 'console' && <pre className="studio-console" data-testid="studio-console">{rep?.console || '(nothing printed)'}{rep?.error ? `\n${rep.error.type}: ${rep.error.message}${rep.error.frames.map((f) => `\n  line ${f.line}, in ${f.function}`).join('')}` : ''}</pre>}
        {main && tab === 'validation' && <Validation pane={main} onLine={(l) => editor.current?.goto(l)} />}
      </div>
    </div>
    <div className="studio-toolbar studio-save">
      <button onClick={download}>Download .py</button>
      <label className="studio-upload">Upload .py<input type="file" accept=".py,text/x-python,text/plain" onChange={(e) => upload(e.target.files?.[0])} /></label>
      <button onClick={() => void copyLink()} data-testid="studio-share">Copy share link</button>
      <button onClick={() => void exportRos()} disabled={blocked || !family || !!busy} data-testid="studio-ros2"
        title="A ready ament_python package: your file unchanged, as a node in COCO's Nav2 (README inside)">Export as ROS 2 package</button>
      <span className="studio-muted">Your draft is kept in this browser (if storage is allowed).</span>
      {share?.url && <label className="wb-copied">Link (the code rides in the # part, never sent to a server):<input readOnly value={share.url} onFocus={(e) => e.currentTarget.select()} data-testid="studio-link" /></label>}
      {share?.error && <p className="wb-error" role="alert">{share.error}</p>}
    </div>
    {stack && <BrowserVsRos s={stack} />}
    <details className="studio-exp" data-testid="studio-probe">
      <summary>What the sandbox blocks (ADR 0012)</summary>
      <p className="studio-muted">Your code runs in its own worker with the network, storage, other tabs and devices taken away, a time limit per call and a memory ceiling. This runs the worker’s own fixed checks (none of your code) and shows each result.</p>
      <button onClick={() => void box().probe().then((r) => setProbe({ ...r.js, ...r.python })).catch((e: Error) => setProbe({ error: e.message }))} data-testid="studio-probe-run">Check the sandbox</button>
      {probe && <table className="wb-table"><tbody>{Object.entries(probe).map(([k, v]) => <tr key={k}><th scope="row"><code>{k}</code></th><td data-testid={`probe-${k}`}>{v}</td></tr>)}</tbody></table>}
    </details>
    <details className="studio-exp" open={!!exp}>
      <summary>Benchmark it: an experiment on the whole suite, against built-ins, with R1’s statistics</summary>
      <p className="studio-muted">Every run (yours and the built-ins’) runs in user-code sandboxes; each of yours runs twice for the determinism check. MODEL results.</p>
      <fieldset className="studio-rivals"><legend>Against</legend>
        {(family ? META.algorithms[family] : []).map((a) => <label key={a}><input type="checkbox" checked={rivals.includes(a)}
          onChange={(e) => setRivals((r) => (e.target.checked ? [...r, a] : r.filter((x) => x !== a)))} /> {algoLabel(a)}</label>)}
      </fieldset>
      <button onClick={() => void runExperiment()} disabled={blocked || !!busy || !family || !suite} data-testid="studio-experiment">Run on {suite ? `all ${suite.scenarios.length} scenarios of ${suite.id}` : 'the suite'}</button>
      {exp?.progress && <p role="status" className="studio-muted">{exp.progress.done} / {exp.progress.total} runs{exp.progress.failed ? ` · ${exp.progress.failed} stopped by the sandbox` : ''} <button onClick={() => pool.current?.cancel()}>Cancel</button></p>}
      {exp && <Results spec={exp.spec} plan={exp.plan} records={exp.records} summary={exp.summary} compareHref={() => '#'} />}
    </details>
  </section>;
}

function ResultsTable({ panes }: { panes: Pane[] }) {
  const keys = META.metrics[panes[0].draw.family].filter((m) => !m.timing);
  return <div className="studio-results" data-testid="studio-results">
    <table className="wb-table"><thead><tr><th scope="col">Metric (MODEL)</th>{panes.map((p, i) => <th key={i} scope="col">{p.title}</th>)}</tr></thead>
      <tbody>
        <tr><th scope="row">Status</th>{panes.map((p, i) => <td key={i} data-testid={`studio-status-${i}`}>{p.rec ? `${p.rec.status}${p.rec.success ? ' ✓' : ''}` : p.failure && !p.failure.ok ? `stopped: ${p.failure.reason}` : 'running…'}</td>)}</tr>
        <tr><th scope="row">Deterministic (ran twice)</th>{panes.map((p, i) => <td key={i} data-testid={`studio-det-${i}`}>{p.rec?.deterministic === undefined ? '— (built-in)' : p.rec.deterministic ? 'yes: identical hash chains' : 'NO: the two runs differ — labelled non-deterministic, cannot be submitted'}</td>)}</tr>
        {keys.map((m) => <tr key={m.id}><th scope="row">{m.label}{m.unit ? ` (${m.unit})` : ''}</th>{panes.map((p, i) => <td key={i}>{fmtN(p.rec?.metrics[m.id])}</td>)}</tr>)}
        <tr><th scope="row">Compute time (wall, {deviceLabel()})</th>{panes.map((p, i) => <td key={i}>{fmtN(p.rec?.metrics.compute_ms)} ms</td>)}</tr>
      </tbody></table>
    {panes.map((p, i) => p.failure && !p.failure.ok ? <p key={i} className="wb-error" role="alert">{p.title}: {p.failure.message}</p> : null)}
  </div>;
}

function Validation({ pane, onLine }: { pane: Pane; onLine: (l: number) => void }) {
  const r = pane.rec?.report;
  if (!r) return <p className="studio-muted">{pane.failure && !pane.failure.ok ? pane.failure.message : 'No report (a built-in, or still running).'}</p>;
  const mean = r.calls && r.call_ms_total !== undefined ? r.call_ms_total / r.calls : null;
  return <div className="studio-validation" data-testid="studio-validation">
    <ul>
      <li>Contract problems: <b>{r.n_problems}</b>{r.problems.map((p, i) => <div key={i} className="studio-muted">{p.tick !== null ? `tick ${p.tick}: ` : ''}{p.message}</div>)}</li>
      <li>Clamped outputs (logged, never silent): <b>{r.clamped}</b>{r.clamp_examples.slice(0, 5).map((c, i) => <div key={i} className="studio-muted">{c}</div>)}</li>
      <li>Determinism: {pane.rec?.deterministic ? 'ran twice, identical hash chains' : <b>NOT deterministic: the two runs’ chains differ</b>}</li>
      <li>Calls: {r.calls}; per call {mean !== null ? `${mean.toFixed(2)} ms mean` : '—'}, {r.call_ms_max !== undefined ? `${r.call_ms_max.toFixed(1)} ms max` : '—'} (wall time on {deviceLabel()}; never a ranking metric)</li>
      <li>Thinking events dropped past the per-call cap: {r.dropped_events}{pane.rec?.draw?.cut ? `; ${pane.rec.draw.cut} not drawn` : ''}</li>
      {r.error && <li className="wb-error">{r.error.type}: {r.error.message}{r.error.frames.map((f, i) => <div key={i}><button className="linkish" onClick={() => onLine(f.line)}>line {f.line}</button>, in {f.function}</div>)}</li>}
    </ul>
  </div>;
}
