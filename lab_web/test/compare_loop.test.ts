// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { loadPyodide, type PyodideInterface } from 'pyodide';
import { beforeAll, expect, it } from 'vitest';
import { LAB_WEB } from './helpers';
import type { LoopFrame } from '../src/arena/protocol';
let py: PyodideInterface;
const generated = join(LAB_WEB, 'public/generated');
beforeAll(async () => {
  py = await loadPyodide({ indexURL: join(LAB_WEB, 'node_modules/pyodide') + '/', stdLibURL: join(generated, 'pyodide/python_stdlib.zip') });
  const manifest = JSON.parse(readFileSync(join(generated, 'arena/manifest.json'), 'utf8'));
  for (const file of ['coco_lab.zip', ...['localise', 'move', 'compare'].map(name => manifest.packs[name].file)]) py.unpackArchive(new Uint8Array(readFileSync(join(generated, 'arena', file))), 'zip', { extractDir: '/home/pyodide' });
  py.FS.writeFile('/home/pyodide/arena_glue.py', readFileSync(join(LAB_WEB, 'src/arena/arena_glue.py'), 'utf8'));
  py.globals.set('spec_json', readFileSync(join(generated, 'arena/coco_arena_v1.json'), 'utf8'));
  py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')\nimport arena_glue\narena_glue.init(spec_json, 1, 'astar', lambda *a: None, hash_version=2)\noriginal_bytes = arena_glue._arena.state_bytes()\noriginal_chain = arena_glue._arena.chain");
}, 180_000);
it.each([['control', ['dwa', 'mppi']], ['localise', ['mcl', 'mcl_augmented']]] as const)('streams reference %s outputs on the trimmed worker runtime without changing the live Arena', (family, names) => {
  py.globals.set('request', JSON.stringify({ family, names, goal: [2.5, 2], steps: 2, inflation: { inflation_radius: .5, cost_scaling_factor: 10, robot_radius: .25 } }));
  py.runPython('arena_glue.loop_compare_begin(request)');
  let rows: LoopFrame[] = [];
  for (let i = 0; i < 2; i++) rows = JSON.parse(py.runPython('arena_glue.loop_compare_advance()') as string);
  expect(rows).toHaveLength(2);
  expect(rows.every(row => row.pose.every(Number.isFinite) && row.hash.length === 64)).toBe(true);
  if (family === 'localise') { expect(py.runPython("from coco_lab.state_v2 import snapshot\nall(snapshot(arm) == snapshot(arm, memo_vectors=False) for arm in arena_glue._loop_comparison.arms)")).toBe(true); expect(rows[0].truth).toEqual(rows[1].truth); expect(rows[0].particles?.[0]).toHaveLength(60); }
  expect(py.runPython('arena_glue._arena.state_bytes() == original_bytes and arena_glue._arena.chain == original_chain')).toBe(true);
}, 180_000);
