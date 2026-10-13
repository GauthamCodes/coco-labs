// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The 3D asset pipeline (M4.2; ADR 0006) regenerates every committed file in
 * lab_web/public/assets3d/ byte for byte, and docs/v2/ASSETS.md, within the size
 * budgets: lab_web/tools/assets/build_assets.mjs --check (the converters are
 * standard-library Python; the compression is meshoptimizer, pinned).
 */

import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { REPO } from './helpers';

describe('the 3D assets', () => {
  it('are exactly what the pipeline makes from the recorded world and the URDF, within budget', () => {
    const web = join(REPO, 'lab_web');
    const out = execFileSync(process.execPath, [join(web, 'tools', 'assets', 'build_assets.mjs'), '--check'],
      { cwd: web, encoding: 'utf-8' });
    const r = JSON.parse(out.trim().split('\n').at(-1)!);
    expect(r.problems).toEqual([]);
    expect(r.first_scene.desktop_bytes).toBeLessThanOrEqual(5_000_000);
  }, 120_000);
});
