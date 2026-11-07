// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.6: the COCO-Bench leaderboard (generated/r2/leaderboard.json: ranked by tools/r2/leaderboard.py
 * from leaderboard/results/ at every build).
 * One table per suite and family; deterministic metrics only rank; compute time is shown per
 * device and never ranks. Every entry: its code, a reproduce link (the Studio opens the file and
 * waits for "Run this code"), the replay of its worst run, its failures, public beside held-out,
 * and -- where it has run as a real ROS 2 node -- MODEL beside STACK.
 */
import { useEffect, useState } from 'react';
import { fmt } from './charts';
import { REPO_BLOB_URL } from '../../site.config';
import '../studio/studio.css';

const BASE = import.meta.env.BASE_URL;
const GITHUB = REPO_BLOB_URL;

interface Q { n: number; median: number | null; q1: number | null; q3: number | null }
interface Score {
  n: number; successes: number; success_rate: number | null; wilson95: [number, number] | null;
  path_ratio?: Q; expansions?: Q; min_clearance_m?: Q; time_s?: Q; final_err_xy_m?: Q; mean_err_xy_m?: Q; contacts?: number;
  compute_ms: Q; failures: { scenario: string; scenario_index: number; status: string }[];
}
interface Tier { n: number; successes: number; wilson95: [number, number] | null }
interface Part { score: Score; worst: { scenario_index: number; scenario: string; why: string } | null; digest: string; scenarios: number; merge_base?: string; tiers?: Record<'easy' | 'medium' | 'hard', Tier> }
interface Entry {
  entry: { suite: string; name: string; kind: 'submission' | 'builtin'; family: string; display_name: string; author: string; description: string; licence: string; paper: string | null; code_path: string; code_sha256: string | null };
  public: Part; held_out: Part; versions: Record<string, number | string>; checks: { deterministic: boolean; contract_problems: number; clamped_outputs: number };
  host: { cpu?: string; python?: string; workers?: number };
  stack?: { label: string; rows: { metric: string; model: string; stack: string; gap: string }[]; source: string };
}
interface Index { boards: Record<string, Entry[]>; verifier: number }

const pct = (s: Score) => (s.n ? `${s.successes}/${s.n}` : '—');
const ci = (s: Score) => (s.wilson95 ? ` [${(s.wilson95[0] * 100).toFixed(0)}–${(s.wilson95[1] * 100).toFixed(0)}%]` : '');
const med = (q?: Q) => (q && q.median !== null ? fmt(q.median) : '—');

function headline(fam: string): { key: keyof Score; label: string }[] {
  if (fam === 'planning') return [{ key: 'path_ratio', label: 'Path ÷ grid-optimal (median)' }, { key: 'min_clearance_m', label: 'Min clearance (m, median)' }, { key: 'expansions', label: 'Expansions (median, self-reported)' }];
  if (fam === 'control') return [{ key: 'time_s', label: 'Time to goal (s, median)' }, { key: 'min_clearance_m', label: 'Min clearance (m, median)' }];
  return [{ key: 'final_err_xy_m', label: 'Final error (m, median)' }, { key: 'mean_err_xy_m', label: 'Mean error (m, median)' }];
}

export function LeaderboardTab() {
  const [idx, setIdx] = useState<Index | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    void fetch(`${BASE}generated/r2/leaderboard.json`).then((r) => (r.ok ? r.json() : { boards: {}, verifier: 1 }))
      .then(setIdx).catch((e: Error) => setError(e.message));
  }, []);
  if (error) return <section className="wb-board"><p className="wb-error" role="alert">The leaderboard could not load: {error}</p></section>;
  if (!idx) return <section className="wb-board"><p className="wb-muted" role="status">Loading the leaderboard…</p></section>;
  if (!Object.keys(idx.boards).length) return <section className="wb-board"><p className="wb-note">No verified entries yet. <a href={`${REPO_BLOB_URL}leaderboard/CONTRIBUTING.md`}>How to submit</a></p></section>;
  return <section className="wb-board" data-testid="leaderboard">
    <details className="wb-submit" data-testid="lb-submit"><summary>Submit your algorithm</summary>
      <ol>
        <li>Write a planner, controller or localiser against <code>coco_lab.api</code> (the <a href="?view=workbench&amp;tab=studio">Algorithm Studio</a> has starters).</li>
        <li>Pick a board below: a COCO-Bench v1 suite and your file's family.</li>
        <li>Open a pull request adding <code>leaderboard/submissions/&lt;suite&gt;/&lt;name&gt;/</code> with <code>algorithm.py</code>, <code>meta.yaml</code> and <code>summary.json</code> (your claim, made by the verifier's own command).</li>
        <li>The verifier re-runs it in a sandbox (no network) on the public scenarios and on held-out ones drawn for your pull request; a maintainer merges a verified entry.</li>
      </ol>
      <p><a href={`${REPO_BLOB_URL}leaderboard/CONTRIBUTING.md`}>The full guide (CONTRIBUTING)</a> · <a href={`${REPO_BLOB_URL}docs/bench/v1/README.md`}>Suite datasheets</a></p>
    </details>
    <p className="wb-note">Every entry was re-run by the verifier (verifier {idx.verifier}) on the suite’s public scenarios and on held-out ones, each run twice for determinism. Ranked by deterministic metrics only; compute time is per device and never ranks. MODEL evidence (COCO Lab’s kinematic model); STACK results (real ROS 2 in Gazebo + Nav2) appear where an entry has them. <a href={`${REPO_BLOB_URL}leaderboard/CONTRIBUTING.md`}>How to submit</a></p>
    {Object.entries(idx.boards).map(([board, entries]) => {
      const [suite, fam] = board.split(':');
      const cols = headline(fam);
      return <article key={board} className="wb-bench" id={`board-${suite}-${fam}`}>
        <h2>{suite} · {fam}</h2>
        <div className="wb-scroll"><table className="wb-table" data-testid={`board-${suite}-${fam}`}>
          <thead><tr><th scope="col">#</th><th scope="col">Algorithm</th><th scope="col">Success, public (Wilson 95%)</th>
            {cols.map((c) => <th key={c.key} scope="col">{c.label}</th>)}
            <th scope="col">Held-out success</th><th scope="col">Compute (ms, median; device)</th><th scope="col">Links</th></tr></thead>
          <tbody>{entries.map((e, i) => <EntryRow key={e.entry.name} e={e} rank={i + 1} cols={cols} />)}</tbody>
        </table></div>
      </article>;
    })}
  </section>;
}

function EntryRow({ e, rank, cols }: { e: Entry; rank: number; cols: { key: keyof Score; label: string }[] }) {
  const s = e.public.score, h = e.held_out.score;
  const sub = e.entry.kind === 'submission';
  const studio = `${BASE}?view=workbench&tab=studio&entry=${encodeURIComponent(`${e.entry.suite}/${e.entry.name}`)}`;
  const worst = e.public.worst;
  return <>
    <tr data-testid={`entry-${e.entry.name}`}>
      <td>{rank}</td>
      <th scope="row"><b>{e.entry.display_name}</b>{sub ? '' : ' (built-in)'}<div className="wb-muted">{e.entry.author} · {e.entry.licence}{e.entry.paper ? <> · <a href={e.entry.paper}>paper</a></> : null}</div></th>
      <td>{pct(s)}{ci(s)}</td>
      {cols.map((c) => <td key={c.key}>{med(s[c.key] as Q | undefined)}</td>)}
      <td>{pct(h)}{ci(h)}{h.path_ratio ? ` · ratio ${med(h.path_ratio)}` : ''}</td>
      <td>{med(s.compute_ms)}<div className="wb-muted">{e.host.cpu ?? '?'}</div></td>
      <td className="wb-links">
        <a href={`${GITHUB}${e.entry.code_path}`}>code</a>
        {sub && <> · <a href={studio}>reproduce in the Studio</a></>}
        {sub && worst && <> · <a href={`${studio}&scenario=${worst.scenario_index}`}>worst run ({worst.scenario}: {worst.why})</a></>}
      </td>
    </tr>
    {(s.failures.length > 0 || e.stack || e.public.tiers) && <tr className="wb-sub"><td /><td colSpan={cols.length + 5}>
      {e.public.tiers && <p className="wb-muted" data-testid="lb-tiers">By tier (public): {(['easy', 'medium', 'hard'] as const).map((t) => `${t} ${e.public.tiers![t].successes}/${e.public.tiers![t].n}`).join(' · ')}</p>}
      {s.failures.length > 0 && <details><summary>{s.failures.length} failed scenario{s.failures.length === 1 ? '' : 's'}</summary>
        <ul>{s.failures.slice(0, 50).map((f) => <li key={f.scenario}>{f.scenario}: {f.status}</li>)}</ul></details>}
      {e.stack && <details open><summary>Browser vs ROS 2: {e.stack.label}</summary>
        <table className="wb-table"><thead><tr><th scope="col">Metric</th><th scope="col">MODEL (browser)</th><th scope="col">STACK (Gazebo + Nav2)</th><th scope="col">Gap</th></tr></thead>
          <tbody>{e.stack.rows.map((r) => <tr key={r.metric}><th scope="row">{r.metric}</th><td>{r.model}</td><td>{r.stack}</td><td>{r.gap}</td></tr>)}</tbody></table>
        <p className="wb-muted">{e.stack.source}</p></details>}
    </td></tr>}
  </>;
}
