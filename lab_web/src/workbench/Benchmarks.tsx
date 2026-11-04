// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.5: the Benchmarks tab -- COCO-Bench v0 (a draft for R3). Each suite is versioned,
 * with a fixed scenario list and metric set (coco_lab/coco_lab/benchmarks/<id>.v0.json),
 * the text saying what it tests, a map of all its scenarios, and reference results for
 * every built-in algorithm, computed natively (`coco experiment run`) and committed
 * (docs/v2/r1/bench/). Where Gazebo + Nav2 recordings of the same scenarios exist they
 * are linked; where none exist the page says so.
 */
import { useEffect, useState } from 'react';
import { fmt } from './charts';
import { experimentLink } from './links';
import { FAMILY_LABEL, label, META, SUCCESS_MEANS, worldOf, type ExperimentSpec, type Family } from './spec';

const BASE = import.meta.env.BASE_URL;
const GEN = `${BASE}generated/r1/`;

interface Scenario { id: string; start?: number[]; goal?: number[]; start_zone?: string | null; goal_zone?: string | null; passes?: string; colour?: string }
interface Suite { id: string; version: number; title: string; tests: string; world: string; world_sha256: string; families: Family[]; scenarios: Scenario[]; generator: Record<string, unknown>; stack?: Record<string, string> }
interface Group { algorithm: string; n: number; successes: number; success: { rate: number; low: number; high: number } | null; metrics: Record<string, { n: number; median: number | null; q1: number | null; q3: number | null }> }
interface Reference { family: Family; summary: { n_runs: number; groups: Group[]; digest: string } | null; spec: ExperimentSpec | null }

/** The families a suite has committed reference results for (docs/v2/r1/bench/<suite>/<family>/). */
export const REFERENCE_FAMILIES: Record<string, Family[]> = {
  'arena-nav-50': ['planning', 'control', 'localisation'], 'depot-nav-100': ['planning', 'control'],
  'depot-narrow-30': ['planning', 'control'], 'colour-fetch-4': ['fulltask'],
};
const KEY_METRICS: Record<Family, string[]> = {
  planning: ['expansions', 'path_length_m', 'path_cost'], control: ['time_s', 'path_length_m', 'contacts'],
  localisation: ['final_err_xy_m', 'mean_err_xy_m', 'time_s'], fulltask: ['time_to_complete_s', 'path_efficiency', 'contacts'],
};

function ScenarioMap({ suite }: { suite: Suite }) {
  const w = worldOf(suite.world);
  if (!w || !suite.scenarios.some((s) => s.start)) return null;
  const [ox, oy] = w.origin, W = w.width * w.resolution, H = w.height * w.resolution;
  const px = 640, sc = px / W, ph = H * sc;
  const X = (x: number) => (x - ox) * sc, Y = (y: number) => ph - (y - oy) * sc;
  return <figure className="wb-map"><figcaption>All {suite.scenarios.length} scenarios on {w.title} (map frame; circle = start, square = goal{Object.keys(w.regions).length ? '; shaded = region zones' : ''})</figcaption>
    <svg viewBox={`0 0 ${px} ${ph}`} width="100%" style={{ maxWidth: px }} role="img" aria-label={`Map of the ${suite.id} scenarios`}>
      <rect x={0} y={0} width={px} height={ph} fill="var(--panel2)" />
      {Object.entries(w.regions).map(([z, r]) => <g key={z}><rect x={X(r[0])} y={Y(r[3])} width={(r[1] - r[0]) * sc} height={(r[3] - r[2]) * sc} fill="var(--line)" fillOpacity={0.35} stroke="var(--line)" />
        <text x={X(r[0]) + 4} y={Y(r[3]) + 14} className="wb-tick" fill="var(--muted)" fontSize={11}>{z.replace('zone_', '').replace(/_/g, ' ')}</text></g>)}
      {suite.scenarios.filter((s) => s.start && s.goal).map((s) => <g key={s.id}>
        <line x1={X(s.start![0])} y1={Y(s.start![1])} x2={X(s.goal![0])} y2={Y(s.goal![1])} stroke="var(--wb-s1)" strokeOpacity={0.45} strokeWidth={1.2} />
        <circle cx={X(s.start![0])} cy={Y(s.start![1])} r={3.5} fill="var(--wb-s1)"><title>{`${s.id}: start (${s.start![0].toFixed(2)}, ${s.start![1].toFixed(2)})`}</title></circle>
        <rect x={X(s.goal![0]) - 3.5} y={Y(s.goal![1]) - 3.5} width={7} height={7} fill="var(--wb-s2)"><title>{`${s.id}: goal (${s.goal![0].toFixed(2)}, ${s.goal![1].toFixed(2)})`}</title></rect>
      </g>)}
    </svg></figure>;
}

function ReferenceTable({ suite, r }: { suite: Suite; r: Reference }) {
  if (!r.summary || !r.spec) return <p className="wb-muted">{FAMILY_LABEL[r.family]}: reference results not committed.</p>;
  const metrics = META.metrics[r.family].filter((m) => KEY_METRICS[r.family].includes(m.id));
  const site = new URL(BASE, window.location.href).href;
  return <div className="wb-scroll"><table className="wb-table" data-testid={`ref-${suite.id}-${r.family}`}>
    <caption>{FAMILY_LABEL[r.family]} · reference results ({r.summary.n_runs} runs; success = {SUCCESS_MEANS[r.family]}) · digest {r.summary.digest.slice(0, 12)}…</caption>
    <thead><tr><th scope="col">Algorithm</th><th scope="col">N</th><th scope="col">Success (Wilson 95%)</th>{metrics.map((m) => <th key={m.id} scope="col">{m.label} ({m.unit}): median [IQR]</th>)}</tr></thead>
    <tbody>{r.summary.groups.map((g) => <tr key={g.algorithm}><th scope="row">{label(g.algorithm)}</th><td>{g.n}</td>
      <td>{g.successes}/{g.n} · {g.success ? `${(g.success.rate * 100).toFixed(1)}% [${(g.success.low * 100).toFixed(1)}, ${(g.success.high * 100).toFixed(1)}]` : '—'}</td>
      {metrics.map((m) => { const d = g.metrics[m.id]; return <td key={m.id}>{d ? `${fmt(d.median)} [${fmt(d.q1)}, ${fmt(d.q3)}] · N=${d.n}` : '—'}</td>; })}</tr>)}</tbody>
  </table>
    <p><a href={experimentLink(r.spec, site, r.summary.digest)}>Re-run this in your browser (and check it reproduces)</a>
      <a href={`${GEN}bench/${suite.id}/${r.family}/results.csv`} download>results.csv</a>
      <a href={`${GEN}bench/${suite.id}/${r.family}/summary.json`} download>summary.json</a>
      <a href={`${GEN}bench/${suite.id}/${r.family}/manifest.json`} download>manifest.json</a></p></div>;
}

export function BenchmarksTab() {
  const [suites, setSuites] = useState<Suite[]>([]);
  const [refs, setRefs] = useState<Record<string, Reference[]>>({});
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    const get = (path: string) => fetch(GEN + path, { credentials: 'omit' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    void Promise.all(META.suites.map(async (s) => {
      const suite = await get(`benchmarks/${s.id}.v${s.version}.json`) as Suite | null;
      const rs = await Promise.all((REFERENCE_FAMILIES[s.id] ?? []).map(async (family) => ({ family,
        summary: await get(`bench/${s.id}/${family}/summary.json`), spec: await get(`bench/${s.id}/${family}/spec.json`) }) as Reference));
      return { suite, rs };
    })).then((all) => {
      if (!alive) return;
      setSuites(all.map((a) => a.suite).filter((x): x is Suite => !!x));
      setRefs(Object.fromEntries(all.filter((a) => a.suite).map((a) => [a.suite!.id, a.rs])));
      if (!all.length) setError('No benchmark suites in this build.');
    });
    return () => { alive = false; };
  }, []);
  return <section className="wb-section" aria-label="Benchmarks">
    <h2>COCO-Bench v0 <small className="wb-muted">· a draft for R3</small></h2>
    <p className="wb-muted">Each suite is frozen: a fixed list of scenarios and metrics, versioned (v0). Reference results are MODEL runs of every built-in algorithm at its default parameters, computed with <code>coco experiment run</code> and committed; re-running one in the browser gives the same counts and digest.</p>
    {error && <p role="alert">{error}</p>}
    {!suites.length && !error && <p role="status">Loading the suites…</p>}
    {suites.map((s) => <article key={s.id} className="wb-bench" id={s.id} data-testid={`suite-${s.id}`}>
      <h3>{s.id} <small className="wb-muted">v{s.version} · {s.scenarios.length} scenarios · {worldOf(s.world)?.title ?? s.world}</small></h3>
      <p><b>{s.title}.</b> {s.tests}</p>
      <ScenarioMap suite={s} />
      {(refs[s.id] ?? []).map((r) => <ReferenceTable key={r.family} suite={s} r={r} />)}
      <p className="wb-muted">{s.stack
        ? <>Gazebo + Nav2 recordings of these rounds (STACK, simulation): {Object.keys(s.stack).map((c) => <a key={c} href={`${BASE}?view=play&game=fetch_colour&colour=${c}&race=nav2`}>Race Nav2: {c}</a>)} · <a href={`${BASE}${s.stack[Object.keys(s.stack)[0]].replace('lab_web/public/', '')}`}>the ghost files</a></>
        : 'No Gazebo + Nav2 recording exists for these scenarios yet (recording them is R3 work).'}</p>
    </article>)}
  </section>;
}
