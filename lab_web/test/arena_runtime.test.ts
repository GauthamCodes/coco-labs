// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena runtime in Pyodide-in-Node (M1.5), as the worker runs it:
 * self-hosted Pyodide (the pinned npm package), coco_lab unpacked from the
 * built coco_lab.zip (no wheel, no micropip), the glue, and the TRIMMED
 * stdlib (tools/arena_stdlib.txt). The trimmed stdlib must change nothing:
 * the same session gives the same per-tick hashes as the full stdlib.
 *
 * Needs `node tools/build_arena_assets.mjs` first (npm run build does it;
 * CI runs it before the tests).
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { loadPyodide, type PyodideInterface } from 'pyodide';
import { beforeAll, describe, expect, it } from 'vitest';

import { LAB_WEB } from './helpers';

const GEN = join(LAB_WEB, 'public', 'generated');
const PYODIDE = join(LAB_WEB, 'node_modules', 'pyodide') + '/';
const GLUE = readFileSync(join(LAB_WEB, 'src', 'arena', 'arena_glue.py'), 'utf-8');
const SPEC = readFileSync(join(GEN, 'arena', 'coco_arena_v1.json'), 'utf-8');
const COCO_ZIP = new Uint8Array(readFileSync(join(GEN, 'arena', 'coco_lab.zip')));

/** A scripted session: every planner, teleop, STOP, reset. */
const SESSION: { tick: number; events: Record<string, unknown>[] }[] = [
  { tick: 0, events: [{ tick: 0, kind: 'goal', x: 4.0, y: 2.0 }] },
  { tick: 25, events: [{ tick: 25, kind: 'planner', choice: 'dijkstra' }] },
  { tick: 40, events: [{ tick: 40, kind: 'planner', choice: 'greedy' }] },
  { tick: 55, events: [{ tick: 55, kind: 'teleop', linear: 0.4, angular: -0.6 }] },
  { tick: 70, events: [{ tick: 70, kind: 'stop' }] },
  { tick: 72, events: [{ tick: 72, kind: 'planner', choice: 'bfs' }, { tick: 72, kind: 'goal', x: 2.0, y: -2.0 }] },
  { tick: 90, events: [{ tick: 90, kind: 'planner', choice: 'weighted_astar' }] },
  { tick: 110, events: [{ tick: 110, kind: 'reset' }] },
];
const TICKS = 120;

async function boot(stdLibURL?: string): Promise<PyodideInterface> {
  const py = await loadPyodide({ indexURL: PYODIDE, ...(stdLibURL ? { stdLibURL } : {}) });
  py.unpackArchive(COCO_ZIP, 'zip', { extractDir: '/home/pyodide' });
  py.FS.writeFile('/home/pyodide/arena_glue.py', GLUE);
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  return py;
}

interface Run { hashes: string[]; batches: number; batchRows: number; chain: string; planSummaries: unknown[] }

function runSession(py: PyodideInterface): Run {
  const glue = py.pyimport('arena_glue');
  let batches = 0;
  let batchRows = 0;
  const post = (cols: { get(k: string): { getBuffer(): { data: ArrayLike<number>; release(): void }; destroy(): void } },
    meta: string) => {
    const seq = cols.get('seq');
    const buf = seq.getBuffer();
    batchRows += buf.data.length;
    buf.release();
    seq.destroy();
    batches += 1;
    void JSON.parse(meta);
  };
  const init = glue.init(SPEC, 11, 'astar', post, 256);
  init.destroy();
  const hashes: string[] = [];
  let chain = '';
  const planSummaries: unknown[] = [];
  for (let k = 0; k < TICKS; k += 1) {
    const events = SESSION.find((s) => s.tick === k)?.events ?? [];
    const out = glue.step(JSON.stringify(events));
    const tick = JSON.parse(out.get(0) as string);
    const ranges = out.get(1);
    const rb = ranges.getBuffer('f32');
    expect(rb.data.length).toBe(480);
    rb.release();
    ranges.destroy();
    out.destroy();
    hashes.push(tick.hash);
    chain = tick.chain;
    planSummaries.push(...tick.plans.map((p: { planner: string; status: string; summary: unknown }) =>
      [p.planner, p.status, p.summary]));
  }
  glue.destroy();
  return { hashes, batches, batchRows, chain, planSummaries };
}

describe('the Arena in Pyodide-in-Node', () => {
  let trimmed: Run;
  let full: Run;

  beforeAll(async () => {
    trimmed = runSession(await boot(join(GEN, 'pyodide', 'python_stdlib.zip')));
    full = runSession(await boot());
  }, 240_000);

  it('runs on the trimmed stdlib, every planner included', () => {
    expect(trimmed.hashes).toHaveLength(TICKS);
    const planners = (trimmed.planSummaries as [string, string][]).map((p) => p[0]);
    expect(new Set(planners)).toEqual(new Set(['astar', 'dijkstra', 'greedy', 'bfs', 'weighted_astar']));
    expect(trimmed.batches).toBeGreaterThan(planners.length);
  });

  it('the trimmed stdlib changes nothing: identical hashes, chain and plans', () => {
    expect(trimmed.hashes).toEqual(full.hashes);
    expect(trimmed.chain).toEqual(full.chain);
    expect(trimmed.planSummaries).toEqual(full.planSummaries);
    expect(trimmed.batchRows).toEqual(full.batchRows);
  });

  it('an input error is a Python error with its message, not a crash', async () => {
    const py = await boot(join(GEN, 'pyodide', 'python_stdlib.zip'));
    const glue = py.pyimport('arena_glue');
    glue.init(SPEC, 1, 'astar', () => {}, 256).destroy();
    expect(() => glue.step(JSON.stringify([{ tick: 0, kind: 'fly' }]))).toThrow(/unknown input kind/);
    expect(() => glue.step(JSON.stringify([{ tick: 5, kind: 'stop' }]))).toThrow(/input for tick 5/);
  }, 120_000);

  it('the trimmed zip is what the manifest says, and much smaller', () => {
    const m = JSON.parse(readFileSync(join(GEN, 'arena', 'manifest.json'), 'utf-8'));
    const z = m.pyodide_files['python_stdlib.zip'];
    expect(z.bytes).toBe(readFileSync(join(GEN, 'pyodide', 'python_stdlib.zip')).length);
    expect(z.bytes).toBeLessThan(z.full_bytes / 2);
  });
});
