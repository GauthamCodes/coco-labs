// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1: an experiment's results. Every aggregate shows its N; success rates carry
 * Wilson 95% intervals; metrics are medians with IQRs over the runs where the
 * metric is defined; paired tests (Wilcoxon signed-rank with effect sizes, McNemar
 * for success, Holm-adjusted) say "no significant difference" plainly. Every run is
 * in the table, failures and timeouts included. The numbers come from
 * coco_lab.exp_stats in a worker (summary.json); this file only lays them out.
 */
import { useMemo, useState } from 'react';
import { BoxPlot, fmt, Heatmap, Legend, Scatter, seriesColour, seriesShape, Mark, SuccessBars, SweepLine, type Series } from './charts';
import type { PlanInfo, Progress, RunRecord } from './pool';
import { FAMILY_LABEL, label, META, SUCCESS_MEANS, type ExperimentSpec, type MetricDef } from './spec';

interface Describe { n: number; median: number | null; q1: number | null; q3: number | null; iqr: number | null; min: number | null; max: number | null; timing: boolean }
interface Group { sweep_index: number; sweep: Record<string, number | string>; algorithm: string; n: number; successes: number; success: { rate: number; low: number; high: number } | null; status: Record<string, number>; metrics: Record<string, Describe> }
interface Test { n_pairs: number; n_excluded: number; p: number | null; p_holm?: number | null; verdict?: string; reason: string | null; [k: string]: unknown }
interface Paired { sweep_index: number; a: string; b: string; n_shared: number; success: Test & { a_only: number; b_only: number; risk_difference: number | null }; metrics: Record<string, Test & { median_diff: number | null; hodges_lehmann: number | null; rank_biserial: number | null; n_nonzero: number; method: string | null }> }
export interface Summary { n_runs: number; n_planned: number; complete: boolean; digest: string; groups: Group[]; paired: Paired[]; scenario_info: Record<string, unknown> }

const PAGE = 50;
const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`);
const pval = (p: number | null | undefined) => (p === null || p === undefined ? '—' : p < 1e-4 ? p.toExponential(1) : p.toFixed(4));

export function ProgressBar({ p, onPause, onResume, onCancel }: { p: Progress; onPause: () => void; onResume: () => void; onCancel: () => void }) {
  const eta = p.etaMs === null ? 'estimating…' : p.etaMs < 1000 ? 'under a second' : `about ${Math.round(p.etaMs / 1000)} s`;
  return <div className="wb-progress" aria-label="Experiment progress">
    <div role="progressbar" aria-valuemin={0} aria-valuemax={p.total} aria-valuenow={p.done} aria-valuetext={`${p.done} of ${p.total} runs`} className="wb-bar"><span style={{ width: `${(100 * p.done) / Math.max(1, p.total)}%` }} /></div>
    <output aria-live="polite">{p.done} / {p.total} runs · {p.running} running · {p.paused ? 'paused' : `time left ${eta}`} (this device)</output>
    {p.paused ? <button onClick={onResume}>Resume</button> : <button onClick={onPause}>Pause</button>}
    <button onClick={onCancel}>Cancel (keep results)</button>
  </div>;
}

export function Results({ spec, plan, records, summary, compareHref, onPick }: { spec: ExperimentSpec; plan: PlanInfo; records: RunRecord[]; summary: Summary | null; compareHref: (r: RunRecord) => string; onPick?: (r: RunRecord) => void }) {
  const family = spec.family;
  const metrics = META.metrics[family];
  const algos = (plan.spec.algorithms as { id: string; label: string }[]);
  const series: Series[] = algos.map((a, i) => ({ id: a.id, label: a.label || label(a.id), slot: i }));
  const byId = new Map(series.map((s) => [s.id, s]));
  const firstMetric = metrics.find((m) => m.test && !m.timing)?.id ?? metrics[0].id;
  const [metric, setMetric] = useState(firstMetric);
  const [point, setPoint] = useState(0);
  const [filterAlgo, setFilterAlgo] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [failures, setFailures] = useState(false);
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: 'index', dir: 1 });
  const [page, setPage] = useState(0);
  const m: MetricDef = metrics.find((x) => x.id === metric) ?? metrics[0];
  const sweepNames = (plan.spec.sweep as { params: { name: string; values: (number | string)[] }[] }).params.map((p) => p.name);
  const groups = summary?.groups.filter((g) => g.sweep_index === point) ?? [];
  const live = useMemo(() => {
    const out = new Map<string, { n: number; k: number }>();
    for (const r of records) { const o = out.get(r.algorithm) ?? { n: 0, k: 0 }; o.n++; if (r.success) o.k++; out.set(r.algorithm, o); }
    return out;
  }, [records]);
  const rows = useMemo(() => {
    let rs = records.filter((r) => (!filterAlgo || r.algorithm === filterAlgo) && (!filterStatus || r.status === filterStatus) && (!failures || !r.success));
    const val = (r: RunRecord): number | string => sort.key === 'index' ? r.index : sort.key === 'status' ? r.status : sort.key === 'algorithm' ? r.algorithm : sort.key === 'scenario' ? r.scenario : (r.metrics[sort.key] as number | null) ?? Number.NEGATIVE_INFINITY;
    rs = [...rs].sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : a.index - b.index) * sort.dir; });
    return rs;
  }, [records, filterAlgo, filterStatus, failures, sort]);
  const statuses = [...new Set(records.map((r) => r.status))].sort();
  const shownMetrics = metrics.filter((x) => (plan.spec.metrics as string[]).includes(x.id));
  const scatterAxes = family === 'planning' ? ['expansions', 'path_length_m'] : family === 'fulltask' ? ['time_used_s', 'path_efficiency'] : ['path_length_m', 'time_s'];
  const mdef = (id: string) => metrics.find((x) => x.id === id)!;
  const head = (key: string, text: string) => <th scope="col" aria-sort={sort.key === key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
    <button className="wb-sort" onClick={() => setSort((s) => ({ key, dir: s.key === key ? (-s.dir as 1 | -1) : 1 }))}>{text}</button></th>;

  return <section className="wb-results" aria-label="Results">
    <h2>{spec.title || 'Experiment'} <small className="wb-muted">· {FAMILY_LABEL[family]} · {records.length} of {plan.n_runs} runs</small></h2>
    <p className="wb-muted">Success means {SUCCESS_MEANS[family]}. Counts are model outputs (MODEL · kinematic) and need no device; compute time is wall time on this device.
      {plan.scenario_info.kind === 'sampled' && ` Scenario draws rejected: ${plan.scenario_info.rejected_unreachable} unreachable, ${plan.scenario_info.rejected_separation} too close (reported, not hidden).`}</p>

    {!summary && records.length > 0 && <table className="wb-table"><caption>So far (statistics follow when the runs finish or are cancelled)</caption>
      <thead><tr><th scope="col">Algorithm</th><th scope="col">Runs</th><th scope="col">Succeeded</th></tr></thead>
      <tbody>{series.map((s) => <tr key={s.id}><th scope="row">{s.label}</th><td>{live.get(s.id)?.n ?? 0}</td><td>{live.get(s.id)?.k ?? 0}</td></tr>)}</tbody></table>}

    {summary && <>
      {!summary.complete && <p className="wb-warn" role="note">Partial results: {summary.n_runs} of {summary.n_planned} runs (the experiment was cancelled). Every statistic below is over the runs that finished.</p>}
      <div className="wb-controls">
        <label>Metric<select value={metric} onChange={(e) => setMetric(e.target.value)}>{shownMetrics.map((x) => <option key={x.id} value={x.id}>{x.label} ({x.unit}){x.timing ? ' · this device' : ''}</option>)}</select></label>
        {sweepNames.length > 0 && <label>Sweep point<select value={point} onChange={(e) => setPoint(Number(e.target.value))}>{plan.sweep_points.map((pt, i) => <option key={i} value={i}>{Object.entries(pt).map(([k, v]) => `${k}=${v}`).join(', ')}</option>)}</select></label>}
      </div>
      <Legend series={series} />
      <table className="wb-table" data-testid="wb-summary"><caption>Summary per algorithm{sweepNames.length ? ` at ${Object.entries(plan.sweep_points[point]).map(([k, v]) => `${k}=${v}`).join(', ')}` : ''}</caption>
        <thead><tr><th scope="col">Algorithm</th><th scope="col">N</th><th scope="col">Success (Wilson 95%)</th><th scope="col">Outcomes</th><th scope="col">{m.label}: N · median [IQR] {m.unit}</th></tr></thead>
        <tbody>{groups.map((g) => { const s = byId.get(g.algorithm)!; const d = g.metrics[metric]; return <tr key={g.algorithm}>
          <th scope="row"><svg width="14" height="14" aria-hidden="true"><Mark shape={seriesShape(s.slot)} x={7} y={7} r={5} fill={seriesColour(s.slot)} /></svg> {s.label}</th>
          <td>{g.n}</td><td>{g.successes}/{g.n} · {pct(g.success?.rate)} [{pct(g.success?.low)}, {pct(g.success?.high)}]</td>
          <td>{Object.entries(g.status).map(([k, v]) => `${k} ${v}`).join(', ')}</td>
          <td>{d.n} · {fmt(d.median)} [{fmt(d.q1)}, {fmt(d.q3)}]</td></tr>; })}</tbody></table>

      <div className="wb-charts">
        <figure><figcaption>Success rate, Wilson 95% interval</figcaption>
          <SuccessBars title="Success rate per algorithm" rows={groups.map((g) => ({ series: byId.get(g.algorithm)!, k: g.successes, n: g.n, low: g.success?.low ?? null, high: g.success?.high ?? null }))} /></figure>
        <figure><figcaption>{m.label} ({m.unit}): box = IQR, line = median, whiskers = min–max{m.timing ? ' (wall time on this device)' : ''}</figcaption>
          <BoxPlot title={`${m.label} per algorithm`} unit={m.unit} rows={groups.map((g) => ({ series: byId.get(g.algorithm)!, stats: g.metrics[metric] }))} /></figure>
        {sweepNames.length === 1 && <figure><figcaption>{m.label} against {sweepNames[0]}: median with IQR band</figcaption>
          <SweepLine title={`${m.label} against ${sweepNames[0]}`} series={series} xLabel={sweepNames[0]} yLabel={`${m.label} (${m.unit})`}
            lines={series.map((s) => ({ series: s, pts: (summary.groups.filter((g) => g.algorithm === s.id)).map((g) => ({ x: Number(g.sweep[sweepNames[0]]), median: g.metrics[metric].median, q1: g.metrics[metric].q1, q3: g.metrics[metric].q3, n: g.metrics[metric].n })) }))} /></figure>}
        {sweepNames.length === 2 && <HeatmapBlock summary={summary} plan={plan} series={series} sweepNames={sweepNames} metric={m} />}
        <figure><figcaption>{mdef(scatterAxes[0]).label} against {mdef(scatterAxes[1]).label}, one point per run (select a point to open it in Compare)</figcaption>
          <Scatter title="Runs" series={series} xLabel={`${mdef(scatterAxes[0]).label} (${mdef(scatterAxes[0]).unit})`} yLabel={`${mdef(scatterAxes[1]).label} (${mdef(scatterAxes[1]).unit})`}
            onPick={onPick ? (i) => { const r = records.find((x) => x.index === i); if (r) onPick(r); } : undefined}
            points={records.filter((r) => r.sweep_index === point && typeof r.metrics[scatterAxes[0]] === 'number' && typeof r.metrics[scatterAxes[1]] === 'number')
              .map((r) => ({ x: r.metrics[scatterAxes[0]] as number, y: r.metrics[scatterAxes[1]] as number, slot: byId.get(r.algorithm)!.slot, run: r.index, tip: `run ${r.index}: ${byId.get(r.algorithm)!.label}, ${r.scenario}, ${r.status}` }))} /></figure>
      </div>

      {summary.paired.some((p) => p.sweep_index === point) && <table className="wb-table" data-testid="wb-paired"><caption>Paired comparison on shared scenarios: {m.label} (difference A − B) and success</caption>
        <thead><tr><th scope="col">A vs B</th><th scope="col">Pairs used (excluded)</th><th scope="col">Median diff</th><th scope="col">Hodges–Lehmann</th><th scope="col">Rank-biserial r</th><th scope="col">Wilcoxon p (Holm)</th><th scope="col">Verdict</th><th scope="col">Success: A only / B only, McNemar p (Holm)</th></tr></thead>
        <tbody>{summary.paired.filter((p) => p.sweep_index === point).map((p) => { const t = p.metrics[metric]; return <tr key={p.a + p.b}>
          <th scope="row">{byId.get(p.a)?.label} vs {byId.get(p.b)?.label}</th>
          {t ? <><td>{t.n_pairs} ({t.n_excluded})</td><td>{fmt(t.median_diff)}</td><td>{fmt(t.hodges_lehmann)}</td><td>{fmt(t.rank_biserial, 2)}</td>
            <td>{t.p === null ? <span className="wb-muted">{t.reason}</span> : `${pval(t.p)} (${pval(t.p_holm)}) · ${t.method === 'exact' ? 'exact' : 'normal approx.'}`}</td><td>{t.verdict}</td></>
            : <td colSpan={6} className="wb-muted">not tested for this metric</td>}
          <td>{p.success.a_only} / {p.success.b_only}, {p.success.p === null ? <span className="wb-muted">{p.success.reason}</span> : `${pval(p.success.p)} (${pval(p.success.p_holm)}) · ${p.success.verdict}`}</td></tr>; })}</tbody></table>}
    </>}

    <div className="wb-controls" role="group" aria-label="Filter runs">
      <label>Algorithm<select value={filterAlgo} onChange={(e) => { setFilterAlgo(e.target.value); setPage(0); }}><option value="">All</option>{series.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
      <label>Outcome<select value={filterStatus} onChange={(e) => { setFilterStatus(e.target.value); setPage(0); }}><option value="">All</option>{statuses.map((s) => <option key={s}>{s}</option>)}</select></label>
      <button aria-pressed={failures} onClick={() => { setFailures((f) => !f); setPage(0); }}>Failures only</button>
      <output aria-live="polite">{rows.length} of {records.length} runs</output>
    </div>
    <div className="wb-scroll"><table className="wb-table wb-runs" data-testid="wb-runs"><caption>Every run (failures and timeouts included)</caption>
      <thead><tr>{head('index', 'Run')}{sweepNames.map((n) => <th key={n} scope="col">{n}</th>)}{head('algorithm', 'Algorithm')}{head('scenario', 'Scenario')}{head('status', 'Outcome')}
        {shownMetrics.slice(0, 6).map((x) => <th key={x.id} scope="col" aria-sort={sort.key === x.id ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}><button className="wb-sort" onClick={() => setSort((s) => ({ key: x.id, dir: s.key === x.id ? (-s.dir as 1 | -1) : 1 }))}>{x.label}</button></th>)}
        <th scope="col">Open</th></tr></thead>
      <tbody>{rows.slice(page * PAGE, page * PAGE + PAGE).map((r) => <tr key={r.index} className={r.success ? '' : 'wb-failed'}>
        <td>{r.index}</td>{sweepNames.map((n) => <td key={n}>{String(r.sweep[n])}</td>)}<td>{byId.get(r.algorithm)?.label ?? r.algorithm}</td><td>{r.scenario}</td>
        <td>{r.success ? r.status : <b>{r.status}</b>}{r.error ? ` (${r.error})` : ''}</td>
        {shownMetrics.slice(0, 6).map((x) => <td key={x.id}>{typeof r.metrics[x.id] === 'boolean' ? String(r.metrics[x.id]) : fmt(r.metrics[x.id] as number | null)}</td>)}
        <td><a href={compareHref(r)}>{r.success ? 'Replay' : `Replay${r.fail_tick !== null ? ` at tick ${r.fail_tick}` : ''}`}</a></td></tr>)}</tbody></table></div>
    {rows.length > PAGE && <div className="wb-controls"><button disabled={page === 0} onClick={() => setPage((x) => x - 1)}>Previous</button><span>page {page + 1} of {Math.ceil(rows.length / PAGE)}</span><button disabled={(page + 1) * PAGE >= rows.length} onClick={() => setPage((x) => x + 1)}>Next</button></div>}
  </section>;
}

function HeatmapBlock({ summary, plan, series, sweepNames, metric }: { summary: Summary; plan: PlanInfo; series: Series[]; sweepNames: string[]; metric: MetricDef }) {
  const [algo, setAlgo] = useState(series[0].id);
  const params = (plan.spec.sweep as { params: { name: string; values: (number | string)[] }[] }).params;
  const xs = params[0].values, ys = params[1].values;
  const cell = (xi: number, yi: number) => {
    const g = summary.groups.find((gg) => gg.algorithm === algo && gg.sweep[sweepNames[0]] === xs[xi] && gg.sweep[sweepNames[1]] === ys[yi]);
    return { v: g?.metrics[metric.id].median ?? null, n: g?.metrics[metric.id].n ?? 0 };
  };
  return <figure><figcaption>Median {metric.label} over {sweepNames[0]} × {sweepNames[1]} for <select aria-label="Algorithm for the heatmap" value={algo} onChange={(e) => setAlgo(e.target.value)}>{series.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></figcaption>
    <Heatmap xs={xs} ys={ys} cell={cell} xLabel={sweepNames[0]} yLabel={sweepNames[1]} title={`Median ${metric.label}`} better={metric.better} /></figure>;
}
