// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The display rule, hover and coordinates against the Python oracle
// (tools/common.py, LabMap.cell_at / cell_centre via expected.json).

import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import type { DecodedBundle } from '../src/bundle/model';
import { sha256Hex } from '../src/bundle/sha256';
import { modeLabel, sameInputs } from '../src/model/mode';
import { buildMapRGBA, buildTraceRGBA, updateTraceRGBA } from '../src/render/layers';
import { recordingOverlays, otherGroups } from '../src/render/overlays';
import { OKABE_ITO, PALETTE } from '../src/render/palette';
import { cellAt, cellCentre, metricToCell, NoGeoError } from '../src/trace/coords';
import { cellStates, pathCells, TraceCursor } from '../src/trace/cursor';
import { fMeaning, HoverIndex } from '../src/trace/hover';
import { expected, loadDir, REPO } from './helpers';

const cache = new Map<string, DecodedBundle>();
async function load(id: string): Promise<DecodedBundle> {
  const e = expected.bundles.find((b) => b.id === id)!;
  if (!cache.has(id)) cache.set(id, await loadDir(join(REPO, e.dir)));
  return cache.get(id)!;
}

describe.each(expected.bundles.map((e) => [e.id, e] as const))('trace display, %s', (id, exp) => {
  it('cursor checkpoints equal Python', async () => {
    const b = await load(id);
    const c = new TraceCursor(b.trace.events, b.trace.n, b.map.width, b.map.height);
    for (const cp of exp.cursor) {
      c.seek(cp.k); // forward, incrementally
      expect(await sha256Hex(c.state), `k=${cp.k}`).toBe(cp.sha256);
      expect(c.counts()).toEqual({ open: cp.open, closed: cp.closed, path: cp.path });
    }
  });

  it('a backward scrub equals forward replay to the same k', async () => {
    const b = await load(id);
    const c = new TraceCursor(b.trace.events, b.trace.n, b.map.width, b.map.height);
    c.seek(b.trace.n);
    for (const cp of [...exp.cursor].reverse()) {
      c.seek(cp.k); // backward
      expect(await sha256Hex(c.state)).toBe(cp.sha256);
      expect(c.state).toEqual(cellStates(b.trace.events, b.map.width, b.map.height, cp.k));
    }
  });

  it('hover samples equal Python (stored g, h, f per sub)', async () => {
    const b = await load(id);
    const hi = new HoverIndex(b.trace.events, b.trace.n, b.map.width, b.map.height);
    for (const s of exp.hover) expect(hi.at(s.row, s.col, s.k), JSON.stringify(s)).toEqual(s.states);
  });

  it('places metric points exactly where coco_lab does, or refuses without geo', async () => {
    const b = await load(id);
    if (exp.orientation === null) {
      expect(() => cellAt(b.map, 0, 0)).toThrow(NoGeoError);
      return;
    }
    expect(cellCentre(b.map, ...b.run.start)).toEqual(exp.orientation.start_centre);
    expect(cellCentre(b.map, ...b.run.goal)).toEqual(exp.orientation.goal_centre);
    const plan = b.recording!.streams.plan!;
    const ours = Array.from(plan.x, (x, i) => cellAt(b.map, x, plan.y[i]));
    expect(ours).toEqual(exp.orientation.plan_cells);
    expect(ours.length).toBeGreaterThan(100);
  });
});

describe('orientation', () => {
  it('the 1C start is stored [189, 130] = the log\'s (col 130, y-up 190)', async () => {
    const b = await load('lab1c_astar');
    expect(b.run.start).toEqual([189, 130]);
    expect(b.map.height - 1 - b.run.start[0]).toBe(190);
    // row 0 is drawn at the TOP: a larger metric y is a smaller row
    const [, yTop] = cellCentre(b.map, 0, 0);
    const [, yBottom] = cellCentre(b.map, b.map.height - 1, 0);
    expect(yTop).toBeGreaterThan(yBottom);
    const [cx, cy] = metricToCell(b.map, ...cellCentre(b.map, 0, 0));
    expect(cx).toBeCloseTo(0.5, 9);
    expect(cy).toBeCloseTo(0.5, 9);
  });

  it('the plan the robot followed lies on the trace\'s path cells', async () => {
    const b = await load('lab1c_astar');
    const path = new Set(pathCells(b.trace.events, b.trace.n).map(([r, c]) => `${r},${c}`));
    const plan = b.recording!.streams.plan!;
    const hits = Array.from(plan.x, (x, i) => cellAt(b.map, x, plan.y[i]))
      .filter((c) => c && path.has(`${c[0]},${c[1]}`)).length;
    // not asserted equal: the exporter's plan poses are the planner's output,
    // measured here only to show both use the same orientation
    expect(hits / plan.x.length).toBeGreaterThan(0.9);
  });
});

describe('heading grid (turn_trap)', () => {
  it('aggregates subs path > closed > open and keeps every sub on hover', async () => {
    const b = await load('astar_turn_trap_heading');
    expect(b.run.graph.kind).toBe('heading_grid');
    const subs = new Set(b.trace.events.sub);
    expect(subs.has(8)).toBe(true); // the start state
    expect(subs.has(9)).toBe(true); // the goal sink, which repeats the goal cell
    const hi = new HoverIndex(b.trace.events, b.trace.n, b.map.width, b.map.height);
    const [gr, gc] = b.run.goal;
    const atGoal = hi.at(gr, gc, b.trace.n);
    expect(atGoal.map((s) => s.sub)).toContain(9);
    expect(atGoal.length).toBeGreaterThan(1);
    const st = cellStates(b.trace.events, b.map.width, b.map.height, b.trace.n);
    expect(st[gr * b.map.width + gc]).toBe(3);
  });
});

describe('recorded-run overlays', () => {
  it('places gt, amcl and plan for every 1C run', async () => {
    for (const id of ['lab1c_astar', 'lab1c_dijkstra', 'lab1c_greedy']) {
      const b = await load(id);
      const o = recordingOverlays(b);
      expect(o.map((x) => [x.group, x.placed])).toEqual([['gt', true], ['amcl', true], ['plan', true]]);
      const gt = o[0] as { points: Array<[number, number]> };
      expect(gt.points.length).toBe(b.recording!.groups.gt!.count); // no decimation
      expect(otherGroups(b)[0]).toMatch(/^cmd: \d+ wheel commands/);
    }
  });

  it('refuses to place the synthetic fixture (geo null) and names cmd as not captured', async () => {
    const b = await load('recorded_run_synthetic_1_1');
    const o = recordingOverlays(b);
    expect(o.every((x) => !x.placed)).toBe(true);
    expect(o.map((x) => (x as { reason: string }).reason)).toEqual([
      'no geo — cannot place (the map has no resolution/origin)',
      'no geo — cannot place (the map has no resolution/origin)',
      'no geo — cannot place (the map has no resolution/origin)',
    ]);
    expect(otherGroups(b)).toEqual(['cmd: not captured']);
  });
});

describe('labels and rules', () => {
  it('mode labels follow provenance.source_kind', () => {
    expect(modeLabel({ source_kind: 'recorded-run', tool: 'coco_lab_ros.lab_export' }).text)
      .toBe('Replay — recorded real run');
    expect(modeLabel({ source_kind: 'glass-box', tool: 'lab_web/pyodide' }).text)
      .toBe('Replay — computed in your browser by coco_lab');
    expect(modeLabel({ source_kind: 'glass-box', tool: 'coco_lab/test/golden_bundles.py' }).text)
      .toBe('Replay — coco_lab computation (glass-box)');
    expect(modeLabel({ source_kind: 'sketch', tool: null }).mode).toBe('Sketch');
  });

  it('sameInputs holds only on identical map, start, goal, model and seed', async () => {
    const a = await load('lab1c_astar');
    const d = await load('lab1c_dijkstra');
    const t = await load('astar_open');
    expect(sameInputs(a, d)).toBe(true); // the three 1C runs share inputs
    expect(sameInputs(a, t)).toBe(false);
  });

  it('the f column is labelled by what the algorithm used', () => {
    expect(fMeaning('bfs', null)).toMatch(/depth/);
    expect(fMeaning('weighted_astar', 2)).toBe('f = g + w·h (w = 2)');
  });

  it('the palette is Okabe–Ito for states and markers', () => {
    expect([PALETTE.open, PALETTE.closed, PALETTE.path, PALETTE.start, PALETTE.goal])
      .toEqual(['#56B4E9', '#E69F00', '#D55E00', '#009E73', '#CC79A7']);
    const oi = new Set<string>(Object.values(OKABE_ITO));
    for (const c of [PALETTE.open, PALETTE.closed, PALETTE.path, PALETTE.start, PALETTE.goal,
      PALETTE.groundTruth, PALETTE.amcl, PALETTE.plan]) expect(oi.has(c)).toBe(true);
  });
});

describe('layer builders (pure, pinned)', () => {
  it('produce stable pixels for fixed fixtures and k', async () => {
    const snap: Record<string, string> = {};
    for (const id of ['astar_open', 'dijkstra_cost_field_gz', 'lab1c_greedy']) {
      const b = await load(id);
      snap[`${id}:map`] = await sha256Hex(new Uint8Array(buildMapRGBA(b.map).buffer));
      const k = Math.floor(b.trace.n / 2);
      const st = cellStates(b.trace.events, b.map.width, b.map.height, k);
      snap[`${id}:trace@${k}`] = await sha256Hex(new Uint8Array(buildTraceRGBA(st).buffer));
    }
    expect(snap).toMatchSnapshot();
  });

  it('incremental updates equal a full rebuild', async () => {
    const b = await load('lab1c_dijkstra');
    const c = new TraceCursor(b.trace.events, b.trace.n, b.map.width, b.map.height);
    const rgba = buildTraceRGBA(c.state);
    c.takeChanges();
    for (const k of [100, 5000, 40000, b.trace.n]) {
      c.seek(k);
      updateTraceRGBA(rgba, c.state, c.takeChanges());
      expect(rgba).toEqual(buildTraceRGBA(c.state));
    }
  });
});
