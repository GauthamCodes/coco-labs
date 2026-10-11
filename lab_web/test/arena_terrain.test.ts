// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The terrain through the worker's glue, in Pyodide (M4.3): the page's own
 * path. World Spec v2 ships beside v1; its world message names the targets;
 * a planned drive climbs onto a platform (the tick's tilt), the grasp picks
 * through the Stack's gate (the tick's grasp state), and the command source
 * follows the arbiter's order. A flat (v1) tick carries no tilt.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { loadPyodide, type PyodideInterface } from 'pyodide';
import { beforeAll, describe, expect, it } from 'vitest';

import { SPEC_FILES, type InputRow, type Tick, type World } from '../src/arena/protocol';
import { LAB_WEB } from './helpers';

const GEN = join(LAB_WEB, 'public', 'generated');

describe('World Spec v2 through arena_glue (Pyodide)', () => {
  let py: PyodideInterface;
  beforeAll(async () => {
    py = await loadPyodide({ indexURL: join(LAB_WEB, 'node_modules', 'pyodide') + '/', stdLibURL: join(GEN, 'pyodide', 'python_stdlib.zip') });
    py.unpackArchive(new Uint8Array(readFileSync(join(GEN, 'arena', 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
    py.FS.writeFile('/home/pyodide/arena_glue.py', readFileSync(join(LAB_WEB, 'src', 'arena', 'arena_glue.py'), 'utf-8'));
    py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')");
  }, 120_000);

  function boot(file: string) {
    py.runPython('import importlib, arena_glue; importlib.reload(arena_glue)');
    const glue = py.pyimport('arena_glue');
    const out = glue.init(readFileSync(join(GEN, 'arena', file), 'utf-8'), 1, 'astar', () => {}, 4096);
    const world = JSON.parse(out.get(0)) as World;
    out.destroy();
    let tick = 0;
    const step = (inputs: Omit<InputRow, 'tick'>[] = []): Tick => {
      const o = glue.step(JSON.stringify(inputs.map((r) => ({ ...r, tick }))));
      tick += 1;
      const t = JSON.parse(o.get(0)) as Tick;
      o.destroy();
      return t;
    };
    return { world, step, close: () => glue.destroy() };
  }

  it('the build ships both specs; a flat tick has no tilt and no targets', () => {
    const m = JSON.parse(readFileSync(join(GEN, 'arena', 'manifest.json'), 'utf-8'));
    expect(m.specs.v1.file).toBe(SPEC_FILES.v1);
    expect(m.specs.v2.file).toBe(SPEC_FILES.v2);
    const s = boot(SPEC_FILES.v1);
    expect(s.world.targets).toBeUndefined();
    const t = s.step([{ kind: 'teleop', linear: 0.2, angular: 0 }]);
    expect(t.tilt).toBeUndefined();
    expect(t.source).toBe('teleop');
    expect(t.wheels?.[0]).toBeGreaterThan(0);
    expect(s.step([{ kind: 'grasp' }]).grasp?.reason).toMatch(/flat world/);
    s.close();
  });

  it('climbs onto the blue platform under the planner, then the grasp picks and carries', () => {
    const s = boot(SPEC_FILES.v2);
    const blue = s.world.targets?.find((x) => x.colour === 'blue');
    expect(s.world.targets?.map((x) => x.colour)).toEqual(['blue', 'green', 'red', 'yellow']);
    expect(blue?.z).toBeCloseTo(0.6498, 3);   // on the platform
    let t = s.step([{ kind: 'goal', x: 5.6, y: 2.0 }]);
    expect(t.source).toBe('planner');
    let pitched = false;
    for (let k = 0; k < 600 && !t.arrived; k += 1) { t = s.step(); pitched ||= (t.tilt?.[1] ?? 0) < -0.3; }
    expect(t.arrived).toBe(true);
    expect(pitched).toBe(true);               // nose up on the ramp (REP-103: pitch negative)
    expect(t.tilt?.[0]).toBeCloseTo(0.6498, 3);
    t = s.step([{ kind: 'grasp' }]);
    expect(t.grasp?.phase).toBe('approach');
    expect(t.source).toBe('mission');
    for (let k = 0; k < 400 && t.grasp?.phase !== 'carry'; k += 1) t = s.step();
    expect(t.grasp?.phase).toBe('carry');
    expect(t.grasp?.target).toBe('blue');
    s.close();
  }, 120_000);
});
