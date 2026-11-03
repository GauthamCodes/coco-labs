// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1 · Research Workbench: Experiments · Benchmarks · Recordings · Datasets.
 *
 * An experiment opened from a link is rebuilt from its spec and re-run here; when the
 * link carries the creator's digest the page says whether every count reproduced
 * exactly. Verify re-runs a random 10% of the runs and checks each one's hash chain
 * and counts against the records already on the page.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { ModeNav } from '../ui/ModeNav';
import { Builder } from './Builder';
import { defaultPoolSize, ExperimentPool, type PlanInfo, type Progress, type RunRecord } from './pool';
import { ProgressBar, Results, type Summary } from './Results';
import { experimentLink, readExperimentLink } from './links';
import { defaultSpec, worldId, type ExperimentSpec } from './spec';
import { downloadExport } from './exports';
import { BenchmarksTab } from './Benchmarks';
import { DatasetsTab } from './Datasets';
import { compareHrefFor } from './compare_link';
import { WorkbenchTabs, type Tab } from './tabs';
import './workbench.css';
import '../game/fonts.css';
const BASE = import.meta.env.BASE_URL;
const SITE = () => new URL(BASE, window.location.href).href;

type Check = { kind: 'link'; ok: boolean; digest: string; expected: string } | { kind: 'verify'; checked: number; bad: number[] };

function hostInfo(workers: number) {
  const nav = navigator as Navigator & { deviceMemory?: number; userAgentData?: { platform?: string } };
  return { runner: 'pyodide', user_agent: nav.userAgent, platform: nav.userAgentData?.platform ?? nav.platform,
    cores: nav.hardwareConcurrency ?? null, device_memory_gb: nav.deviceMemory ?? null, workers, page: window.location.origin };
}

export function Experiments() {
  const opened = useMemo(() => { try { return { link: readExperimentLink(window.location.search, window.location.hash), error: '' }; } catch (e) { return { link: null, error: String((e as Error).message) }; } }, []);
  const [spec, setSpec] = useState<ExperimentSpec>(() => opened.link?.spec ?? defaultSpec('planning'));
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [records, setRecords] = useState<RunRecord[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [error, setError] = useState(opened.error);
  const [check, setCheck] = useState<Check | null>(null);
  const [copied, setCopied] = useState('');
  const [busy, setBusy] = useState('');
  const pool = useRef<ExperimentPool | null>(null);
  const handle = useRef<ReturnType<ExperimentPool['run']> | null>(null);
  const ran = useRef<string>('');
  const below = useRef<HTMLDivElement>(null);
  // the results open below a long form: bring them into view when a run starts (phones above all)
  const reveal = () => requestAnimationFrame(() => below.current?.scrollIntoView({
    behavior: document.documentElement.dataset.motion === 'reduced' ? 'auto' : 'smooth', block: 'start' }));
  // phones get at most two interpreters (each is a full Pyodide); others their cores less one, capped
  const phone = typeof matchMedia !== 'undefined' && matchMedia('(pointer: coarse)').matches && Math.min(screen.width, screen.height) < 600;
  const getPool = () => (pool.current ??= new ExperimentPool(defaultPoolSize(navigator as Navigator & { deviceMemory?: number }, phone)));
  useEffect(() => () => pool.current?.close(), []);
  useEffect(() => { document.title = 'Workbench · COCO Lab'; }, []);

  const run = async (s: ExperimentSpec = spec) => {
    setError(''); setCheck(null); setSummary(null); setRecords([]); setPlan(null);
    const text = JSON.stringify(s), world = worldId(s);
    try {
      setBusy('Preparing the model in the workers…');
      const p = await getPool().plan(text, world);
      setPlan(p); setBusy(''); reveal();
      const got: RunRecord[] = [];
      const h = getPool().run(text, world, [...Array(p.n_runs).keys()], {
        onRecord: (r) => { got.push(r); if (got.length % 4 === 0 || got.length === p.n_runs) setRecords([...got]); },
        onProgress: setProgress,
      });
      handle.current = h;
      const all = await h.done;
      handle.current = null;
      setRecords(all); setProgress(null);
      setBusy('Computing the statistics…');
      const sum = await getPool().summary(text, world, all) as unknown as Summary;
      setSummary(sum); setBusy('');
      ran.current = text;
      if (opened.link?.digest && JSON.stringify(opened.link.spec) === text && sum.complete) {
        setCheck({ kind: 'link', ok: sum.digest === opened.link.digest, digest: sum.digest, expected: opened.link.digest });
      }
    } catch (e) { handle.current = null; setProgress(null); setBusy(''); setError(String((e as Error).message)); }
  };
  useEffect(() => { if (opened.link) void run(opened.link.spec); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const cancel = async () => {
    const h = handle.current; if (!h) return;
    h.cancel(); handle.current = null;
    const partial = await h.done; setRecords(partial); setProgress(null);
    if (!partial.length) return;
    const text = JSON.stringify(spec);
    try { setSummary(await getPool().summary(text, worldId(spec), partial) as unknown as Summary); } catch (e) { setError(String((e as Error).message)); }
  };

  const verify = async () => {
    if (!records.length) return;
    const n = Math.max(1, Math.round(records.length * 0.1));
    const pick = [...records].map((r) => [crypto.getRandomValues(new Uint32Array(1))[0], r] as const).sort((a, b) => a[0] - b[0]).slice(0, n).map((x) => x[1]);
    setBusy(`Verifying ${n} randomly chosen run${n === 1 ? '' : 's'}…`);
    try {
      const again = await getPool().run(ran.current, worldId(spec), pick.map((r) => r.index)).done;
      const want = new Map(pick.map((r) => [r.index, r]));
      const counts = (r: RunRecord) => JSON.stringify(Object.entries(r.metrics).filter(([k]) => k !== 'compute_ms').sort());
      const bad = again.filter((r) => r.chain !== want.get(r.index)!.chain || counts(r) !== counts(want.get(r.index)!) || r.status !== want.get(r.index)!.status).map((r) => r.index);
      setCheck({ kind: 'verify', checked: again.length, bad });
    } catch (e) { setError(String((e as Error).message)); }
    setBusy('');
  };

  const link = () => experimentLink(spec, SITE(), summary?.complete && ran.current === JSON.stringify(spec) ? summary.digest : undefined);
  const copy = async () => {
    const l = link();
    try { await navigator.clipboard.writeText(l); setCopied('Link copied.'); } catch { setCopied(l); }
  };
  const running = handle.current !== null || busy !== '';
  return <>
    {opened.link && <p className="wb-note" role="note">Opened from a link: this experiment is being rebuilt from its spec and re-run in your browser.{opened.link.digest ? ' The page will say whether every count matches the creator’s.' : ''}</p>}
    {check?.kind === 'link' && <p className={check.ok ? 'wb-ok' : 'wb-error'} role="status" data-testid="wb-link-check">{check.ok
      ? `Reproduced exactly: every run's status, hash chain and counts match the link (digest ${check.digest.slice(0, 16)}…).`
      : `DIFFERS from the link: digest ${check.digest.slice(0, 16)}… here, ${check.expected.slice(0, 16)}… in the link. Please report this.`}</p>}
    <Builder spec={spec} onSpec={setSpec} onRun={() => void run()} running={running} error={error} />
    <div ref={below} />
    {busy && <p role="status" className="wb-muted">{busy}</p>}
    {progress && <ProgressBar p={progress} onPause={() => handle.current?.pause()} onResume={() => handle.current?.resume()} onCancel={() => void cancel()} />}
    {plan && <div className="wb-actions">
      <button onClick={() => void copy()} disabled={!summary}>Copy link</button>
      <button onClick={() => void verify()} disabled={!summary || running} data-testid="wb-verify">Verify (re-run a random 10%)</button>
      <button onClick={() => void downloadExport(getPool(), spec, records, hostInfo(getPool().size), false)} disabled={!summary || running}>Export results (zip)</button>
      <button onClick={() => void downloadExport(getPool(), spec, records, hostInfo(getPool().size), true)} disabled={!summary || running || spec.family === 'planning'} title={spec.family === 'planning' ? 'A search has no ticks to trace' : undefined}>Export with traces</button>
      {summary && <span className="wb-muted" data-testid="wb-digest">Digest {summary.digest.slice(0, 16)}… · {getPool().size} worker{getPool().size === 1 ? '' : 's'}</span>}
      {copied && <output aria-live="polite" className="wb-copied">{copied}</output>}
    </div>}
    {check?.kind === 'verify' && <p className={check.bad.length ? 'wb-error' : 'wb-ok'} role="status" data-testid="wb-verify-result">{check.bad.length
      ? `Verify: ${check.bad.length} of ${check.checked} re-run(s) differ (runs ${check.bad.join(', ')}).`
      : `Verify: ${check.checked} randomly chosen run(s) re-run; every hash chain and count matches.`}</p>}
    {plan && <Results spec={spec} plan={plan} records={records} summary={summary} compareHref={(r) => compareHrefFor(spec, r)} />}
  </>;
}

export function WorkbenchApp() {
  const tab = (new URLSearchParams(window.location.search).get('tab') ?? 'experiments') as Tab;
  return <main className="wb" data-testid="workbench">
    <ModeNav current="workbench" evidence="MODEL" />
    <header className="wb-head"><p className="eyebrow">WORKBENCH</p><h1>Run it yourself.</h1>
      <p>Every experiment runs the model in your browser and gives the same counts on every run and every browser (hash-verified), so any result can be shared as a link and checked by anyone. MODEL results; real Gazebo + Nav2 recordings are under Recordings.</p>
      <WorkbenchTabs current={tab} /></header>
    {tab === 'benchmarks' ? <BenchmarksTab /> : tab === 'datasets' ? <DatasetsTab /> : <Experiments />}
  </main>;
}
