// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Share links and the attract recording (M1.8).
 *
 * The share-link round trip is exact (doubles included) and refuses bad
 * links. The REPRODUCTION claim is tested where it can be: a link's inputs
 * replayed through the Arena in Pyodide-in-Node give the same hash chain
 * as the original run. The attract recording decodes into the world, ticks
 * and searches the build made.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { loadPyodide, type PyodideInterface } from 'pyodide';
import { beforeAll, describe, expect, it } from 'vitest';

import { parseRecording } from '../src/arena/attract';
import type { InputRow } from '../src/arena/protocol';
import { decodeRun, encodeRun, type SharedRun } from '../src/arena/share';
import { LAB_WEB } from './helpers';

const GEN = join(LAB_WEB, 'public', 'generated');

describe('share links', () => {
  const run: SharedRun = {
    v: 1, spec: 'a'.repeat(64), seed: 42, ticks: 300, chain: 'b'.repeat(64),
    inputs: [{ tick: 0, kind: 'goal', x: 2.123456789012345, y: -1.000000000000001 },
      { tick: 3, kind: 'planner', choice: 'dijkstra' }, { tick: 9, kind: 'teleop', linear: 0.30000000000000004, angular: -1.2 },
      { tick: 12, kind: 'stop' }, { tick: 40, kind: 'reset' }],
  };

  it('round-trips exactly, doubles included', () => {
    expect(decodeRun(encodeRun(run))).toEqual(run);
    expect(encodeRun(run)).toMatch(/^[A-Za-z0-9_-]+$/); // URL-safe
  });

  it.each([
    ['not base64', '%%%'],
    ['wrong version', btoa(JSON.stringify({ v: 2 }))],
    ['no chain', btoa(JSON.stringify({ v: 1, s: 'a'.repeat(64), e: 1, t: 1, c: 'x', i: [] }))],
    ['unknown kind', btoa(JSON.stringify({ v: 1, s: 'a'.repeat(64), e: 1, t: 1, c: 'b'.repeat(64), i: [[0, 9]] }))],
    ['out of order', btoa(JSON.stringify({ v: 1, s: 'a'.repeat(64), e: 1, t: 1, c: 'b'.repeat(64), i: [[5, 2], [1, 2]] }))],
    ['nan goal', btoa(JSON.stringify({ v: 1, s: 'a'.repeat(64), e: 1, t: 1, c: 'b'.repeat(64), i: [[0, 0, 'x', 1]] }))],
  ])('refuses %s', (_, s) => {
    expect(() => decodeRun(s.replace(/=+$/, ''))).toThrow();
  });
});

describe('a shared run reproduces in Pyodide (same chain)', () => {
  let py: PyodideInterface;
  beforeAll(async () => {
    py = await loadPyodide({ indexURL: join(LAB_WEB, 'node_modules', 'pyodide') + '/', stdLibURL: join(GEN, 'pyodide', 'python_stdlib.zip') });
    py.unpackArchive(new Uint8Array(readFileSync(join(GEN, 'arena', 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
    py.FS.writeFile('/home/pyodide/arena_glue.py', readFileSync(join(LAB_WEB, 'src', 'arena', 'arena_glue.py'), 'utf-8'));
    py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  }, 120_000);

  function play(seed: number, inputs: InputRow[], ticks: number): string {
    py.runPython('import importlib, arena_glue; importlib.reload(arena_glue)');
    const glue = py.pyimport('arena_glue');
    glue.init(readFileSync(join(GEN, 'arena', 'coco_arena_v1.json'), 'utf-8'), seed, 'astar', () => {}, 4096).destroy();
    let chain = '';
    for (let k = 0; k < ticks; k += 1) {
      const out = glue.step(JSON.stringify(inputs.filter((r) => r.tick === k)));
      chain = JSON.parse(out.get(0)).chain;
      out.destroy();
    }
    glue.destroy();
    return chain;
  }

  it('the link\'s inputs, replayed, end on the link\'s chain; a changed input does not', () => {
    const inputs: InputRow[] = [{ tick: 0, kind: 'goal', x: 2.5, y: 2.0 }, { tick: 20, kind: 'teleop', linear: 0.4, angular: 0.3 },
      { tick: 35, kind: 'planner', choice: 'greedy' }, { tick: 36, kind: 'goal', x: -1.5, y: 1.0 }];
    const chain = play(7, inputs, 60);
    const link = decodeRun(encodeRun({ v: 1, spec: 'c'.repeat(64), seed: 7, ticks: 60, chain, inputs }));
    expect(play(link.seed, link.inputs, link.ticks)).toBe(link.chain);
    const changed = link.inputs.map((r) => (r.kind === 'teleop' ? { ...r, angular: 0.3000001 } : r));
    expect(play(link.seed, changed, link.ticks)).not.toBe(link.chain);
  }, 120_000);

  it('compare runs two planners and leaves the model untouched (same chain after)', () => {
    const goalRow: InputRow[] = [{ tick: 0, kind: 'goal', x: 2.5, y: 2.0 }];
    const plain = play(3, goalRow, 30);
    py.runPython('import importlib, arena_glue; importlib.reload(arena_glue)');
    const glue = py.pyimport('arena_glue');
    glue.init(readFileSync(join(GEN, 'arena', 'coco_arena_v1.json'), 'utf-8'), 3, 'astar', () => {}, 4096).destroy();
    let chain = '';
    const seen: Record<string, number> = {};
    for (let k = 0; k < 30; k += 1) {
      if (k === 10) {
        const res = JSON.parse(glue.compare('astar', 'bfs', 6.0, 4.0, (cols: { destroy(): void }, meta: string) => {
          const m = JSON.parse(meta);
          seen[m.compare] = m.search_id;
          cols.destroy();
        }, 2048));
        expect(res.A.planner).toBe('astar');
        expect(res.B.planner).toBe('bfs');
        expect(res.A.summary.path_cost).toBeCloseTo(res.B.summary.path_cost, 9); // both optimal here (the browser showed 175.18 each)
        expect(res.B.summary.expansions).toBeGreaterThan(res.A.summary.expansions);
      }
      const out = glue.step(JSON.stringify(goalRow.filter((r) => r.tick === k)));
      chain = JSON.parse(out.get(0)).chain;
      out.destroy();
    }
    glue.destroy();
    expect(seen).toEqual({ A: -101, B: -102 }); // never a PlanStore's empty -1, never the run's own ids
    expect(chain).toBe(plain);
  }, 120_000);
});

describe('the attract recording', () => {
  it('decodes into the world, every tick and every search the build recorded', async () => {
    const rec = await parseRecording(new Uint8Array(readFileSync(join(GEN, 'arena', 'attract.mcap'))));
    expect([rec.world.width, rec.world.height, rec.world.resolution]).toEqual([500, 380, 0.05]);
    expect(rec.occupancy.length).toBe(500 * 380);
    expect(rec.ticks.length).toBeGreaterThan(100);
    expect(rec.ticks.map((t) => t.tick)).toEqual(rec.ticks.map((_, i) => i + 1));
    const events = [...rec.batches.values()].flat().reduce((n, b) => n + b.cols.kind.length, 0);
    expect(events).toBeGreaterThan(1000);
    const planners = rec.ticks.flatMap((t) => t.plans.map((p) => p.planner));
    expect(planners).toEqual(['astar', 'dijkstra', 'greedy']);
    expect(rec.runId).toMatch(/^[0-9a-f]{64}$/);
  });
});
