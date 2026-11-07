// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R3.5: "Model vs ROS 2" -- the browser model (MODEL) against real Nav2 in Gazebo (STACK) on the same
 * COCO-Bench v1 scenarios (generated/r3/gap.json, from tools/r3/gap.py over the committed paired runs).
 * Per pair: the success confusion table, agreement, where the model is optimistic or pessimistic, and
 * the median ratio STACK / MODEL. Every paired run is downloadable. No physical robot: STACK is a
 * simulation of the full ROS 2 stack.
 */
import { useEffect, useState } from 'react';
import { REPO_BLOB_URL } from '../../site.config';

const GEN = `${import.meta.env.BASE_URL}generated/`;

interface Pair {
  n: number; label: string; metric: string; model: string;
  confusion: { both: number; model_only: number; stack_only: number; neither: number };
  agreement: number | null; model_optimistic: number | null; model_pessimistic: number | null;
  ratio_median: number | null; ratio_n: number;
}
interface Gap { about: string; planning: Record<string, Record<string, Pair>>; control: Record<string, Record<string, Pair>>;
  notes?: string[]; downloads?: { label: string; path: string }[] }

const pct = (x: number | null) => (x === null ? '—' : `${Math.round(x * 100)} %`);

function PairTable({ pairs }: { pairs: Record<string, Pair> }) {
  return <div className="wb-scroll"><table className="wb-table">
    <thead><tr><th scope="col">Pair</th><th scope="col">n</th><th scope="col">both succeed</th><th scope="col">model only</th>
      <th scope="col">ROS 2 only</th><th scope="col">neither</th><th scope="col">agreement</th><th scope="col">ratio ROS 2 / model (median)</th></tr></thead>
    <tbody>{Object.entries(pairs).map(([k, p]) => <tr key={k}>
      <th scope="row">{p.label}<div className="wb-muted">{p.metric}</div></th><td>{p.n}</td>
      <td>{p.confusion.both}</td><td>{p.confusion.model_only}</td><td>{p.confusion.stack_only}</td><td>{p.confusion.neither}</td>
      <td>{pct(p.agreement)}</td><td>{p.ratio_median === null ? '—' : `${p.ratio_median.toFixed(3)} (n=${p.ratio_n})`}</td></tr>)}
    </tbody></table></div>;
}

export function ModelVsRos2Tab() {
  const [gap, setGap] = useState<Gap | null | 'none'>(null);
  useEffect(() => {
    fetch(`${GEN}r3/gap.json`, { credentials: 'omit' }).then((r) => (r.ok ? r.json() : 'none')).then(setGap).catch(() => setGap('none'));
  }, []);
  return <section className="wb-board" data-testid="model-vs-ros2">
    <p className="wb-note">The same scenarios in the browser model (<b>MODEL</b>, kinematic) and in the full ROS 2 Nav2 stack in Gazebo
      (<b>STACK</b>, a simulation; no physical robot). &quot;Model only&quot; = the model succeeds where ROS 2 fails (the model is optimistic);
      &quot;ROS 2 only&quot; = the reverse. Pairs of the same file (the A* starter as a ROS 2 node) compare one algorithm; Nav2&apos;s own
      planners and controllers are counterparts, not the same code. <a href={`${REPO_BLOB_URL}docs/v2/r3/data/r35/README.md`}>Method and findings</a></p>
    {gap === null && <p className="wb-muted" role="status">Loading…</p>}
    {gap === 'none' && <p className="wb-muted" data-testid="gap-pending">The paired Gazebo + Nav2 runs are not in this build yet.</p>}
    {gap && gap !== 'none' && <>
      {Object.entries(gap.planning).map(([suite, pairs]) => <article key={suite} className="wb-bench"><h2>{suite} · planning</h2><PairTable pairs={pairs} /></article>)}
      {Object.entries(gap.control).map(([suite, pairs]) => <article key={suite} className="wb-bench"><h2>{suite} · control</h2><PairTable pairs={pairs} /></article>)}
      {gap.notes?.length ? <ul>{gap.notes.map((n) => <li key={n}>{n}</li>)}</ul> : null}
      {gap.downloads?.length ? <p>Paired runs: {gap.downloads.map((d, i) => <span key={d.path}>{i ? ' · ' : ''}<a href={`${GEN}${d.path}`} download>{d.label}</a></span>)}</p> : null}
    </>}
  </section>;
}
