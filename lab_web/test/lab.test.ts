// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// Lab 1.1's page logic: the settings lookups (against the table coco_lab
// wrote into the built catalog), brush strokes, race synchronisation and
// the swept footprint. Needs tools/build_catalog.py to have run, as CI does.

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import type { Catalog } from '../src/bundle/load';
import type { DecodedBundle } from '../src/bundle/model';
import { brushCells, coversEndpoint, endpointRefusal, StrokeBuilder } from '../src/lab/brush';
import { sweptFootprint } from '../src/lab/footprint';
import { costChange, fewestExpanded, revealCost, revealFewest } from '../src/lab/predict';
import { cursorAtStep, expansionEnds, raceRow } from '../src/lab/race';
import {
  analysisFor, boundFor, describeBound, sameAsBundle, settingsLocked, settingsOf, toRun,
} from '../src/lab/settings';
import { pathCells } from '../src/trace/cursor';
import { expected, LAB_WEB, loadDir, REPO } from './helpers';

const CATALOG = join(LAB_WEB, 'public/generated/catalog.json');
const catalog: Catalog = JSON.parse(readFileSync(CATALOG, 'utf-8'));

const cache = new Map<string, DecodedBundle>();
async function load(id: string): Promise<DecodedBundle> {
  if (!cache.has(id)) {
    const e = expected.bundles.find((b) => b.id === id);
    const dir = e ? join(REPO, e.dir) : join(LAB_WEB, 'public/generated/bundles', id);
    cache.set(id, await loadDir(dir));
  }
  return cache.get(id)!;
}

describe('the catalog carries coco_lab verdicts (1.1)', () => {
  it('is built', () => {
    expect(existsSync(CATALOG)).toBe(true);
    // 1.2 .. 1.5 are additive (Lab 2's `localise` block, Lab 3's `map`
    // block, Lab 4's `search` block, Lab 5's `move` block); every 1.1 member
    // below still holds
    expect(catalog.version).toBe('1.5');
    expect(catalog.settings?.weights).toEqual(Array.from({ length: 21 }, (_, i) => i / 4));
  });

  it('carries Lab 5: replayed replan and drive bundles, three controllers, cited claims', () => {
    const move = (catalog as unknown as { move: {
      replan: { bundles: Array<{ kind: string; validated: { replay: string }; summary: { costs_agree: boolean } }> };
      drive: { bundles: Array<{ id: string; validated: { replay: string } }> };
      controllers: Array<{ id: string }>; claims: Array<{ cites: string[] }>; run15: { quotes: string[] };
    } }).move;
    expect(move.replan.bundles.filter((b) => b.kind === 'sketch').length).toBeGreaterThanOrEqual(1);
    for (const b of move.replan.bundles) {
      expect(b.validated.replay).toMatch(/byte for byte/);
      expect(b.summary.costs_agree).toBe(true);
    }
    for (const b of move.drive.bundles) expect(b.validated.replay).toMatch(/recomputed/);
    expect(move.controllers.map((c) => c.id)).toEqual(['DWB', 'MPPI', 'RPP']);
    for (const c of move.claims) expect(c.cites.length).toBeGreaterThan(0);
    expect(move.run15.quotes).toContain('DWBLocalPlanner: No valid trajectories out of 819!');
  });

  it('carries Lab 3: replayed map bundles, the documented challenge score, and its evidence', () => {
    const map = (catalog as unknown as { map: any }).map;
    expect(map.version).toBe('1.0');
    const kinds = map.bundles.map((b: any) => b.kind);
    expect(kinds.filter((k: string) => k === 'sketch')).toHaveLength(3);
    expect(kinds).toContain('challenge');
    for (const b of map.bundles) {
      expect(b.validated.replay).toMatch(/byte for byte/);
      expect(b.cites.length).toBeGreaterThan(0);
      for (const r of b.runs) expect(r.summary.map.f1).toBeGreaterThanOrEqual(0);
    }
    expect(map.challenge.score).toMatch(/^round\(100 x F1\)/);
    expect(map.run_ids).toEqual(['known', 'odometry', 'ekf_slam', 'fastslam', 'pose_graph', 'pose_graph_noloop']);
  });

  it('carries Lab 2: replayed Sketch bundles at filter seed 0, and its evidence', () => {
    const loc = (catalog as unknown as { localise: any }).localise;
    expect(loc.version).toBe('1.0');
    expect(loc.bundles.map((b: any) => b.id)).toEqual(
      ['loc_tracking', 'loc_kidnap', 'loc_global', 'loc_twins', 'loc_arena_kidnap']);
    for (const b of loc.bundles) {
      expect(b.source_kind).toBe('sketch');
      expect(b.spec.filter_seed).toBe(0);
      expect(b.validated.replay).toMatch(/reproduced byte for byte/);
      expect(b.cites.length).toBeGreaterThan(0);
    }
    for (const k of ['fidelity', 'sketch_rates', 'kidnap_ab', 'ekf_drift']) {
      expect(['measured', 'not yet measured']).toContain(loc[k].status);
    }
    expect(loc.exhibits).toBe('loc_exhibits.json');
  });

  it('every ladder rung is a served bundle, lowest first', () => {
    const ids = new Set(catalog.bundles.map((b) => b.id));
    expect(catalog.ladder!.map((r) => r.rung)).toEqual([1, 2, 3]);
    for (const r of catalog.ladder!) expect(ids.has(r.id)).toBe(true);
  });

  it('the footprint is derived from coco_config, with its derivation', () => {
    const fp = catalog.footprint!;
    expect(fp.source).toBe('coco_config/coco_config/robot.py');
    expect(fp.length_m).toBeCloseTo(0.297, 6);
    expect(fp.width_m).toBeCloseTo(0.314, 6);
    expect(fp.derivation).toContain('WHEELBASE');
  });
});

describe('settings: looked up, never decided in TypeScript', () => {
  it('the panel starts from the bundle, and toRun sends weight only for weighted A*', async () => {
    const b = await load('weighted_astar_greedy_trap');
    const s = settingsOf(b);
    expect(s).toMatchObject({ algorithm: 'weighted_astar', weight: 2 });
    expect(sameAsBundle(s, b)).toBe(true);
    expect(toRun(s).weight).toBe(2);
    expect(toRun({ ...s, algorithm: 'astar' }).weight).toBeNull();
    expect(sameAsBundle({ ...s, weight: 2.5 }, b)).toBe(false);
  });

  it("finds coco_lab's verdict for each move model a grid bundle uses", async () => {
    const sa = catalog.settings!;
    for (const id of ['astar_open', 'dijkstra_cost_field_gz', 'weighted_astar_greedy_trap', 'bfs_no_path']) {
      const b = await load(id);
      for (const h of sa.heuristics) {
        for (const c of [4, 8] as const) expect(analysisFor(sa, b, c, h), `${id} ${c} ${h}`).not.toBeNull();
      }
    }
  });

  it('matches the analysis: manhattan overestimates a diagonal, octile does not', async () => {
    const sa = catalog.settings!;
    const b = await load('astar_open');
    expect(analysisFor(sa, b, 8, 'manhattan')!.admissible).toBe(false);
    expect(analysisFor(sa, b, 8, 'octile')!.admissible).toBe(true);
    expect(analysisFor(sa, b, 4, 'manhattan')!.admissible).toBe(true);
  });

  it('reads the bound coco_lab computed at each slider weight', async () => {
    const sa = catalog.settings!;
    const b = await load('astar_open');
    const ok = analysisFor(sa, b, 8, 'octile')!;
    expect(boundFor(sa, ok, 'weighted_astar', 2.25)).toBe(2.25);
    expect(boundFor(sa, ok, 'weighted_astar', 0.5)).toBe(1);
    expect(boundFor(sa, ok, 'weighted_astar', 2.1)).toBeUndefined(); // not a slider position
    expect(boundFor(sa, ok, 'greedy', 1)).toBeNull();
    const bad = analysisFor(sa, b, 8, 'manhattan')!;
    expect(boundFor(sa, bad, 'astar', 1)).toBeNull();
    expect(describeBound('astar', null)).toMatch(/overestimate/);
    expect(describeBound('dijkstra', 1)).toMatch(/optimal/);
    expect(describeBound('weighted_astar', 2.25)).toBe('cost ≤ 2.25 × the optimum');
  });

  it('locks the recorded runs and the heading graph', async () => {
    expect(settingsLocked(await load('lab1c_astar'))).toMatch(/recorded run/);
    expect(settingsLocked(await load('astar_turn_trap_heading'))).toMatch(/heading/);
    expect(settingsLocked(await load('astar_open'))).toBeNull();
  });
});

describe('brush strokes', () => {
  it('a square brush, clipped at the edges', () => {
    expect(brushCells([0, 0], 3, 5, 5)).toEqual([[0, 0], [0, 1], [1, 0], [1, 1]]);
    expect(brushCells([2, 2], 1, 5, 5)).toEqual([[2, 2]]);
    expect(brushCells([2, 2], 5, 5, 5)).toHaveLength(25);
  });

  it('a fast drag leaves no gaps, and a cell is listed once', () => {
    const s = new StrokeBuilder('occupied', 1, 20, 20);
    s.add([0, 0]);
    s.add([0, 9], [0, 0]);
    s.add([0, 9], [0, 9]);
    expect(s.cells).toHaveLength(10);
    expect(s.stroke()).toEqual({ value: 'occupied', cells: s.cells });
  });

  it('refuses to paint over the start or goal, but erasing there is fine', () => {
    const paint = { value: 'occupied' as const, cells: [[3, 3], [4, 4]] as Array<[number, number]> };
    expect(coversEndpoint(paint, [4, 4], [9, 9])).toEqual({ what: 'start', cell: [4, 4] });
    expect(coversEndpoint(paint, [0, 0], [3, 3])).toEqual({ what: 'goal', cell: [3, 3] });
    expect(coversEndpoint({ ...paint, value: 'free' }, [4, 4], [3, 3])).toBeNull();
    expect(endpointRefusal('start', [4, 4])).toContain('the brush covered the start cell (4, 4)');
  });
});

describe('race synchronisation', () => {
  it('step s is just after the s-th expansion; past the last, the finished trace', async () => {
    const b = await load('astar_open');
    const ends = expansionEnds(b.trace.events, b.trace.n);
    expect(ends.length).toBe(b.trace.summary.expansions);
    expect(cursorAtStep(ends, b.trace.n, 0)).toBe(0);
    for (let s = 1; s < ends.length; s++) {
      const k = cursorAtStep(ends, b.trace.n, s);
      expect(b.trace.events.kind[k - 1]).toBe(1); // the event just shown is an expansion
    }
    // the last expansion is the goal's: the pane shows the finished trace, path included
    expect(cursorAtStep(ends, b.trace.n, ends.length)).toBe(b.trace.n);
    expect(cursorAtStep(ends, b.trace.n, ends.length + 5)).toBe(b.trace.n);
  });

  it('the row is the summary coco_lab wrote; the gap is relative to the optimum', async () => {
    const b = await load('weighted_astar_greedy_trap');
    const s = b.trace.summary;
    const row = raceRow(b, s.path_cost! / 1.25);
    expect(row).toMatchObject({ expansions: s.expansions, cost: s.path_cost, length: s.path_length, lengthUnit: 'cells' });
    expect(row.gap).toBeCloseTo(0.25, 12);
    const none = await load('bfs_no_path');
    expect(raceRow(none, 3).gap).toBeNull();
  });
});

describe('the swept footprint', () => {
  it('is not placed without geo', async () => {
    const b = await load('astar_open');
    const r = sweptFootprint(pathCells(b.trace.events, b.trace.n), b.map.geo, catalog.footprint);
    expect(r.placed).toBe(false);
  });

  it('on the costmap rung: one rectangle per path cell, at the footprint scale', async () => {
    const b = await load('costmap_0_10m');
    const path = pathCells(b.trace.events, b.trace.n);
    const r = sweptFootprint(path, b.map.geo, catalog.footprint);
    if (!r.placed) throw new Error(r.reason);
    expect(r.polygons).toHaveLength(path.length);
    const res = b.map.geo!.resolution;
    const [p0, p1, , p3] = r.polygons[0];
    expect(Math.hypot(p0[0] - p1[0], p0[1] - p1[1]) * res).toBeCloseTo(catalog.footprint!.width_m, 9);
    expect(Math.hypot(p0[0] - p3[0], p0[1] - p3[1]) * res).toBeCloseTo(catalog.footprint!.length_m, 9);
  });
});

describe('predict-then-reveal reads the summaries coco_lab wrote', () => {
  const sum = (path_cost: number | null) => ({
    status: path_cost === null ? 'no_path' : 'found', expansions: 1, pushes: 1, relaxes: 0, path_cost,
    path_length: path_cost, path_steps: 1,
  }) as DecodedBundle['trace']['summary'];

  it('classifies every cost change', () => {
    expect(costChange(sum(10), sum(12))).toBe('more');
    expect(costChange(sum(12), sum(10))).toBe('less');
    expect(costChange(sum(10), sum(10 + 1e-12))).toBe('same');
    expect(costChange(sum(null), sum(3))).toBe('found');
    expect(costChange(sum(3), sum(null))).toBe('lost');
    expect(costChange(sum(null), sum(null))).toBe('none');
  });

  it('judges a prediction, and a skipped question is not judged', () => {
    expect(revealCost('more', sum(1), sum(2), String).right).toBe(true);
    expect(revealCost('less', sum(1), sum(2), String).right).toBe(false);
    expect(revealCost(null, sum(1), sum(2), String).right).toBeNull();
  });

  it('a tie for fewest expansions credits every tied algorithm', () => {
    const rows = [{ algorithm: 'astar', expansions: 87 }, { algorithm: 'greedy', expansions: 21 },
      { algorithm: 'bfs', expansions: 21 }];
    expect(fewestExpanded(rows)).toEqual({ min: 21, algorithms: ['greedy', 'bfs'] });
    expect(revealFewest('bfs', rows, (a) => a).right).toBe(true);
    expect(revealFewest('astar', rows, (a) => a).right).toBe(false);
    expect(revealFewest('greedy', rows, (a) => a).measured).toContain('a tie');
  });
});
