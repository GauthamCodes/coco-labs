// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena's determinism, held in CI (M1 B.4): the first recorded
 * sessions of docs/v2/data/m1/determinism/ (random goals, teleop, stops,
 * planner switches; tools/perf/determinism.mjs) replayed in Pyodide-in-Node
 * must give the COMMITTED per-tick hashes, every tick. The same recording
 * is replayed in Chromium, Firefox and WebKit by lab.yml's browser job, and
 * all 100 sessions in all four engines by M1.10 (determinism.json).
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { gunzipSync } from 'node:zlib';

import { loadPyodide, type PyodideInterface } from 'pyodide';
import { beforeAll, describe, expect, it } from 'vitest';

import type { InputRow } from '../src/arena/protocol';
import { LAB_WEB } from './helpers';

const DIR = join(LAB_WEB, '..', 'docs', 'v2', 'data', 'm1', 'determinism');
const GEN = join(LAB_WEB, 'public', 'generated');
const N = 5;

interface Session { id: number; seed: number; ticks: number; planner: string; inputs: InputRow[] }
const sessions: Session[] = JSON.parse(readFileSync(join(DIR, 'sessions.json'), 'utf-8')).sessions.slice(0, N);
const ref: { sessions: { id: number; hashes: string[]; chain: string }[] } =
  JSON.parse(gunzipSync(readFileSync(join(DIR, 'hashes_pyodide-node.json.gz'))).toString('utf-8'));

describe('recorded sessions replay to the committed per-tick hashes (Pyodide-in-Node)', () => {
  let py: PyodideInterface;
  beforeAll(async () => {
    py = await loadPyodide({ indexURL: join(LAB_WEB, 'node_modules', 'pyodide') + '/', stdLibURL: join(GEN, 'pyodide', 'python_stdlib.zip') });
    py.unpackArchive(new Uint8Array(readFileSync(join(GEN, 'arena', 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
    py.FS.writeFile('/home/pyodide/arena_glue.py', readFileSync(join(LAB_WEB, 'src', 'arena', 'arena_glue.py'), 'utf-8'));
    py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  }, 120_000);

  it('the recording is the one the reference was made from', () => {
    expect(sessions.map((s) => s.id)).toEqual([...Array(N).keys()]);
    expect(sessions.every((s) => s.inputs.length > 0)).toBe(true);
  });

  it.each(sessions.map((s) => [s.id, s] as const))('session %i', (_, s) => {
    py.runPython('import importlib, arena_glue; importlib.reload(arena_glue)');
    const glue = py.pyimport('arena_glue');
    glue.init(readFileSync(join(GEN, 'arena', 'coco_arena_v1.json'), 'utf-8'), s.seed, s.planner, () => {}, 4096).destroy();
    const want = ref.sessions.find((x) => x.id === s.id)!;
    let chain = '';
    for (let k = 0; k < s.ticks; k += 1) {
      const out = glue.step(JSON.stringify(s.inputs.filter((x) => x.tick === k)));
      const t = JSON.parse(out.get(0));
      out.destroy();
      expect(t.hash, `session ${s.id}, tick ${k}`).toBe(want.hashes[k]);
      chain = t.chain;
    }
    glue.destroy();
    expect(chain).toBe(want.chain);
  }, 300_000);
});
