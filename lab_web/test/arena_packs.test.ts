// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The lazily loaded Python packs (M2.2), as the worker loads them: in
 * Pyodide-in-Node on the TRIMMED stdlib (the one the site ships), core
 * first, then each lens's pack with its `requires` -- every module of
 * every pack must import. A module a pack needs that the trimmed stdlib
 * dropped would fail here, not in a visitor's browser. Also: the packs'
 * sha256s are the manifest's, and core alone no longer carries them.
 *
 * Needs `node tools/build_arena_assets.mjs` first (CI runs it).
 */

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { loadPyodide } from 'pyodide';
import { describe, expect, it } from 'vitest';

import { LAB_WEB } from './helpers';

const GEN = join(LAB_WEB, 'public', 'generated');
const ARENA = join(GEN, 'arena');
const PYODIDE = join(LAB_WEB, 'node_modules', 'pyodide') + '/';
const MANIFEST = JSON.parse(readFileSync(join(ARENA, 'manifest.json'), 'utf-8')) as {
  packs: Record<string, { file: string; sha256: string; requires: string[]; modules: string[] }>;
};

describe('lens packs', () => {
  it('are the manifest\'s bytes', () => {
    for (const p of Object.values(MANIFEST.packs)) {
      const b = readFileSync(join(ARENA, p.file));
      expect(createHash('sha256').update(b).digest('hex'), p.file).toBe(p.sha256);
    }
  });

  it('import, every module, on the trimmed stdlib, each after only what it requires', async () => {
    for (const [name, p] of Object.entries(MANIFEST.packs)) {
      const py = await loadPyodide({ indexURL: PYODIDE, stdLibURL: join(GEN, 'pyodide', 'python_stdlib.zip') });
      py.unpackArchive(new Uint8Array(readFileSync(join(ARENA, 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
      py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
      const order: string[] = [];
      const add = (n: string) => { for (const r of MANIFEST.packs[n].requires) add(r); if (!order.includes(n)) order.push(n); };
      add(name);
      for (const n of order) py.unpackArchive(new Uint8Array(readFileSync(join(ARENA, MANIFEST.packs[n].file))), 'zip', { extractDir: '/home/pyodide' });
      const failed = py.runPython(`
import importlib, json
bad = []
for m in ${JSON.stringify(p.modules)}:
    try:
        importlib.import_module('coco_lab.' + m)
    except Exception as e:
        bad.append(m + ': ' + type(e).__name__ + ': ' + str(e))
json.dumps(bad)`) as string;
      expect(JSON.parse(failed), name).toEqual([]);
    }
  }, 240_000);

  it('are not in core', async () => {
    const py = await loadPyodide({ indexURL: PYODIDE, stdLibURL: join(GEN, 'pyodide', 'python_stdlib.zip') });
    py.unpackArchive(new Uint8Array(readFileSync(join(ARENA, 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
    const mods = Object.values(MANIFEST.packs).flatMap((p) => p.modules);
    const present = py.runPython(`import os\njson_ = ${JSON.stringify(mods)}\n[m for m in json_ if os.path.exists('/home/pyodide/coco_lab/' + m + '.py')]`).toJs();
    expect(present).toEqual([]);
  }, 120_000);
});
