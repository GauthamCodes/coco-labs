// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { useEffect, useState } from 'react';

import type { Catalog } from '../bundle/load';
import { fetchBundle, requireValidated } from '../bundle/load';
import { pathCells } from '../trace/cursor';
import type { Current } from './App';
import type { LabResult } from './Editor';
import type { RecomputeSpec } from '../worker/protocol';
import { RaceView } from './Race';

type Gap = { min: number; p25: number; median: number; p75: number; max: number; n: number };
type Cmp = { differ: number; of: number; a_higher: number; a_lower: number; max_pct: number; mean_pct: number };

/** exhibit.json, written by tools/build_catalog.py (exhibit_data). */
export interface ExhibitData {
  a: {
    property: string; property_maps: number; counter: string;
    live: { bundle: string; heuristic: string; connectivity: 4 | 8 };
    real_stack: { astar_equals_dijkstra_C1: number; of: number; cite: string };
  };
  b: {
    m3: { smac_m: number; navfn_m: number; cite: string; status: string };
    analogue: { start_world: number[]; goal_world: number[]; rows: Array<{ path: string; L: number; poses: number; E?: number }>;
      paths_recorded: boolean; cite: string };
    fifty: { n: number; e_within: number; e_applies: number; e_gap_max: number; navfn_vs_smac_L: Gap; smac_vs_c1_L: Gap; cite: string };
    mechanism_cite: string;
  };
  c: {
    label: string; label_why: string;
    table1: { astar_steps: number; dijkstra_steps: number; astar_ms: number; dijkstra_ms: number; cite: string };
    steps_ratio_long: number; steps_ratio_short: number;
    m1_cost: Cmp; m1_vs_optimum: Cmp; m2_cost: Cmp; time_ratio_long: [number, number];
    live: { bundle: string }; cite: string;
  };
}

const pct = (x: number, d = 1) => `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(d)} %`;

export interface ExhibitProps {
  catalog: Catalog;
  dataUrl: (path: string) => string;
  run: (c: Current, spec: RecomputeSpec, what: string) => Promise<LabResult | null>;
  busy: boolean;
  reducedMotion: boolean;
  onOpenBundle: (id: string) => void;
}

/**
 * "The A* myth, twice." Two claims that A* returns worse paths than
 * Dijkstra, examined with this lab's evidence: every number here is read
 * from a committed record (exhibit.json is built from them) or computed
 * live by coco_lab, and every claim names its evidence.
 */
export function Exhibit({ catalog, dataUrl, run, busy, reducedMotion, onOpenBundle }: ExhibitProps) {
  const [ex, setEx] = useState<ExhibitData | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [live, setLive] = useState<LabResult | null>(null);

  useEffect(() => {
    if (!catalog.exhibit) return;
    fetch(dataUrl(catalog.exhibit), { credentials: 'omit' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setEx)
      .catch((e: Error) => setProblem(`cannot load the exhibit's evidence: ${e.message}`));
  }, [catalog, dataUrl]);

  if (problem) return <p className="error">{problem}</p>;
  if (!ex) return <p className="loading">Loading the exhibit's evidence…</p>;

  const runLive = async () => {
    const entry = catalog.bundles.find((b) => b.id === ex.a.live.bundle);
    if (!entry) return;
    const { bundle, files } = await fetchBundle(dataUrl(entry.path));
    const base: Current = { entry, bundle, files, validated: requireValidated(bundle, entry)! };
    const mk = (algorithm: string) => ({ algorithm, heuristic: ex.a.live.heuristic, weight: null, tie_break: 'low_h' });
    const r = await run(base, { strokes: [], connectivity: ex.a.live.connectivity, runs: [mk('dijkstra'), mk('astar')],
      optimal: true }, 'running A* and Dijkstra on identical inputs');
    if (r) setLive(r);
  };
  const liveCosts = live?.bundles.map((b) => b.bundle.trace.summary.path_cost);
  const sameCells = live ? JSON.stringify(pathCells(live.bundles[0].bundle.trace.events, live.bundles[0].bundle.trace.n)) ===
    JSON.stringify(pathCells(live.bundles[1].bundle.trace.events, live.bundles[1].bundle.trace.n)) : null;
  const m3gap = (ex.b.m3.navfn_m - ex.b.m3.smac_m) / ex.b.m3.navfn_m;
  const rows = ex.b.analogue.rows;
  const anaGap = (rows[1].L - rows[0].L) / rows[1].L;
  const t1 = ex.c.table1;

  return (
    <article className="exhibit" data-testid="exhibit">
      <h2>The A* myth, twice</h2>
      <p className="lede">
        Twice, a result was read as “A* finds worse (or better) paths than Dijkstra”. With an admissible heuristic
        and the same edge costs, both return a path of the same, optimal cost: the heuristic changes how much is
        searched, not the answer. Both results came from somewhere else.
      </p>

      <section data-testid="exhibit-a">
        <h3>(a) Same costs, same answer — live</h3>
        <p>
          coco_lab runs A* ({ex.a.live.heuristic}, admissible on {ex.a.live.connectivity}-connectivity) and Dijkstra on
          one map, one start and goal, here in your browser.
        </p>
        <button type="button" className="run" disabled={busy} onClick={runLive} data-testid="exhibit-run">
          Run A* and Dijkstra
        </button>
        {live && liveCosts && (
          <>
            <p className="verdict" data-testid="exhibit-a-verdict">
              Path cost: Dijkstra <strong>{liveCosts[0]?.toFixed(6) ?? 'no path'}</strong>, A*{' '}
              <strong>{liveCosts[1]?.toFixed(6) ?? 'no path'}</strong> —{' '}
              {liveCosts[0] === liveCosts[1] ? 'equal.' : 'NOT equal.'}{' '}
              Expansions: {live.bundles[0].bundle.trace.summary.expansions} against{' '}
              {live.bundles[1].bundle.trace.summary.expansions}.{' '}
              {sameCells ? 'The two paths are the same cells.' : 'The paths differ in cells where equal-cost paths tie; the cost does not.'}
            </p>
            <RaceView entrants={live.bundles} optimalCost={live.optimalCost} reducedMotion={reducedMotion}
              onClose={() => setLive(null)} reveal={null} />
          </>
        )}
        <p className="cite">
          Why it holds on every map, not just this one: {ex.a.property} ({ex.a.property_maps.toLocaleString('en')}{' '}
          random maps, costs equal to networkx's Dijkstra). What breaks it — a heuristic that overestimates: {ex.a.counter}.
          On the real costmap too: coco_lab's A* cost equalled its Dijkstra cost on {ex.a.real_stack.astar_equals_dijkstra_C1} of{' '}
          {ex.a.real_stack.of} pairs ({ex.a.real_stack.cite}).
        </p>
      </section>

      <section data-testid="exhibit-b">
        <h3>(b) COCO's 6.2 %: SmacPlanner2D against NavFn</h3>
        <p>
          In M3, Nav2's SmacPlanner2D returned a path of <strong>{ex.b.m3.smac_m} m</strong> and NavFn (Dijkstra) one of{' '}
          <strong>{ex.b.m3.navfn_m} m</strong> on the same start and goal: {(m3gap * 100).toFixed(1)} % shorter (derived). It
          was once read as A* beating Dijkstra. It is two <em>planner implementations</em>: NavFn does not read its path
          off its search but descends the gradient of a potential field (<code>calcPath</code>); SmacPlanner2D back-traces
          its node chain and then smooths it. <span className="cite">({ex.b.m3.cite}; mechanism: {ex.b.mechanism_cite})</span>
        </p>
        <p className="note">
          <strong>Not reproduced, not refuted.</strong> M3's goal and gate no longer exist in the current world, and the
          robot's lidar has moved, so 1C did not re-run it ({ex.b.m3.status}). What 1C measured instead, on the recorded
          costmap, from map ({ex.b.analogue.start_world.join(', ')}) to ({ex.b.analogue.goal_world.join(', ')}):
        </p>
        <table className="rows-table" data-testid="exhibit-b-table">
          <thead><tr><th>path</th><th>length L</th><th>poses</th><th>cell cost E</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.path}><td>{r.path}</td><td>{r.L.toFixed(3)} m</td><td>{r.poses}</td>
                <td>{r.E === undefined ? '—' : r.E.toFixed(4)}</td></tr>
            ))}
          </tbody>
        </table>
        <p>
          Here Smac's returned path is {(anaGap * 100).toFixed(3)} % shorter than NavFn's (derived) — not 6.2 %; one pair is
          not a rate. Smac's <em>raw</em> A* path has exactly coco_lab's optimal cell cost E. Over {ex.b.fifty.n} random
          pairs, Smac's raw A* cost equalled coco_lab's optimum on {ex.b.fifty.e_within} of {ex.b.fifty.e_applies} pairs
          where it reached the goal (largest relative gap {ex.b.fifty.e_gap_max.toExponential(2)}), and NavFn's length was a
          median {pct(ex.b.fifty.navfn_vs_smac_L.median, 3)} against Smac's returned path (range{' '}
          {pct(ex.b.fifty.navfn_vs_smac_L.min, 3)} … {pct(ex.b.fifty.navfn_vs_smac_L.max, 3)}).
        </p>
        <p className="cite">
          1C recorded these paths' lengths, not their coordinates, so they are not drawn. {ex.b.analogue.cite};{' '}
          {ex.b.fifty.cite}.
        </p>
      </section>

      <section data-testid="exhibit-c">
        <h3>(c) The ISRO “4 %” — a {ex.c.label}</h3>
        <p className="label-note" data-testid="exhibit-c-label"><strong>Labelled a {ex.c.label}.</strong> {ex.c.label_why}</p>
        <p>
          The internship report's Table 1 averaged A* at {t1.astar_steps} “Steps” and Dijkstra at {t1.dijkstra_steps}:{' '}
          {((t1.astar_steps / t1.dijkstra_steps - 1) * 100).toFixed(1)} % more (derived) — a count of smoothed waypoints,
          not path length or cost — and {t1.astar_ms} ms against {t1.dijkstra_ms} ms. <span className="cite">({t1.cite})</span>
        </p>
        <ul className="notes">
          <li>
            <strong>Not reproduced.</strong> On fixed inputs the Steps ratio A*/Dijkstra was{' '}
            {ex.c.steps_ratio_long.toFixed(4)} (long trips) and {ex.c.steps_ratio_short.toFixed(4)} (short).
          </li>
          <li>
            The simulator's search keeps only the cell in its state, but its turn penalty depends on the direction of
            arrival. So both of its searches miss the optimum on some maps: A* on {ex.c.m1_vs_optimum.differ} of{' '}
            {ex.c.m1_vs_optimum.of} (by up to {ex.c.m1_vs_optimum.max_pct.toFixed(2)} %). Its A* and Dijkstra differ in cost on{' '}
            {ex.c.m1_cost.differ} maps — {ex.c.m1_cost.a_higher} one way, {ex.c.m1_cost.a_lower} the other, a mean of{' '}
            {ex.c.m1_cost.mean_pct.toFixed(3)} %: no bias.
          </li>
          <li>
            Put the heading in the state and A* equals Dijkstra on {ex.c.m2_cost.of - ex.c.m2_cost.differ} of{' '}
            {ex.c.m2_cost.of} maps. The time ratio Dijkstra/A* was {ex.c.time_ratio_long[0].toFixed(2)}× (means),{' '}
            {ex.c.time_ratio_long[1].toFixed(2)}× (medians) — the report's magnitude, on a different machine.
          </li>
        </ul>
        <button type="button" className="seg-btn" onClick={() => onOpenBundle(ex.c.live.bundle)} data-testid="exhibit-c-open">
          Open the corrected search on the turn-trap map
        </button>
        <p className="cite">{ex.c.cite}</p>
      </section>
    </article>
  );
}
