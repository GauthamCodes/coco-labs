// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// Lab 2's display arithmetic and reveal logic. None of it localises: the
// ellipse is the trace's covariance drawn, the scan is the trace's ranges
// placed, and the reveal reads coco_lab's own summary.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { loadLocBytes } from '../src/loc/decode';
import { ellipse, estimateAt, kidnapUpdate, outcome, outcomeText, questions, runStyle, scanEndpoints,
  truthAtUpdate } from '../src/loc/view';
import { modeLabel, PYODIDE_TOOL } from '../src/model/mode';
import { LAB_WEB, readBundleDir, REPO } from './helpers';

const expected = JSON.parse(readFileSync(join(LAB_WEB, 'test/golden/loc_expected.json'), 'utf-8'));
const load = async (id: string) => {
  const e = expected.bundles.find((b: any) => b.id === id);
  const { manifest, arrays } = readBundleDir(join(REPO, e.dir));
  return loadLocBytes(manifest, arrays);
};

describe('ellipse', () => {
  it('is a circle of 2 sigma for an isotropic covariance', () => {
    const e = ellipse(0.04, 0, 0.04);
    expect(e.rx).toBeCloseTo(0.4, 12);
    expect(e.ry).toBeCloseTo(0.4, 12);
  });
  it('puts the long axis along x or y for a diagonal covariance', () => {
    expect(ellipse(0.09, 0, 0.01).angle).toBe(0);
    expect(ellipse(0.01, 0, 0.09).angle).toBeCloseTo(Math.PI / 2, 12);
    const e = ellipse(0.09, 0, 0.01);
    expect([e.rx, e.ry]).toEqual([0.6, 0.2].map((v) => expect.closeTo(v, 12)));
  });
  it('recovers the axes of a rotated covariance', () => {
    // R(30 deg) diag(4, 1) R^T
    const th = Math.PI / 6;
    const c = Math.cos(th);
    const s = Math.sin(th);
    const a = 4 * c * c + 1 * s * s;
    const b = (4 - 1) * c * s;
    const d = 4 * s * s + 1 * c * c;
    const e = ellipse(a, b, d, 1);
    expect(e.rx).toBeCloseTo(2, 10);
    expect(e.ry).toBeCloseTo(1, 10);
    expect(e.angle).toBeCloseTo(th, 10);
  });
});

describe('placing what a trace holds', () => {
  it('a scan from the truth lands on the map\'s walls (twins room, beam ranges from the bundle)', async () => {
    const b = await load('twins_small');
    const pts = scanEndpoints(b, 0, truthAtUpdate(b, 0));
    expect(pts.length).toBeGreaterThan(0);
    const g = b.map.geo!;
    let onWall = 0;
    for (const [x, y] of pts) {
      // step 1 cm past the endpoint: inside the cell the ray stopped in
      const col = Math.floor((x - g.origin[0]) / g.resolution);
      const up = Math.floor((y - g.origin[1]) / g.resolution);
      for (const [dc, du] of [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const r = b.map.height - 1 - (up + du);
        const cc = col + dc;
        if (r >= 0 && r < b.map.height && cc >= 0 && cc < b.map.width && b.map.occupancy[r * b.map.width + cc] === 1) {
          onWall++;
          break;
        }
      }
    }
    // the world's range noise is 2 cm: every endpoint is within a cell of a wall
    expect(onWall / pts.length).toBeGreaterThan(0.95);
  });

  it('the kidnap update is the first update at or after the kidnap row', async () => {
    const b = await load('kidnap_small_gz');
    const k = kidnapUpdate(b)!;
    expect(b.world.updates[k]).toBeGreaterThanOrEqual(b.world.kidnapRow!);
    expect(b.world.updates[k - 1]).toBeLessThan(b.world.kidnapRow!);
    expect(kidnapUpdate(await load('twins_small'))).toBeNull();
  });

  it('estimates and truth are read from the columns', async () => {
    const b = await load('kidnap_small_gz');
    const r = b.runs[0];
    expect(estimateAt(r, 2)).toEqual([r.cols.est_x[2], r.cols.est_y[2], r.cols.est_yaw[2]]);
    const row = b.world.updates[2];
    expect(truthAtUpdate(b, 2)).toEqual([b.world.gtX[row], b.world.gtY[row], b.world.gtYaw[row]]);
  });
});

describe('predict, then reveal', () => {
  it('asks the kidnap question of every run, and answers from the summary', async () => {
    const b = await load('kidnap_small_gz');
    const qs = questions(b);
    expect(qs.map((q) => q.runId)).toEqual(['mcl_off', 'mcl_aug', 'ekf']);
    expect(qs.every((q) => /after the kidnap/.test(q.text))).toBe(true);
    for (const r of b.runs) {
      expect(outcome(b, r)).toBe(r.summary.recovered ? 'yes' : 'no');
      expect(outcomeText(b, r)).toMatch(r.summary.recovered ? /recovered/ : /did not recover/);
    }
  });
  it('asks the global question when the runs start from nowhere', async () => {
    const b = await load('twins_small');
    expect(questions(b).every((q) => /from nowhere/.test(q.text))).toBe(true);
    for (const r of b.runs) expect(outcome(b, r)).toBe(r.summary.converged_s !== null ? 'yes' : 'no');
  });
  it('names the runs as the page draws them', () => {
    expect(runStyle('mcl_coco').label).toMatch(/injection off/);
    expect(runStyle('ekf').label).toBe('EKF');
    expect(runStyle('other').label).toBe('other');
  });
});

describe('the Sketch label (rule 4)', () => {
  it('says it is a model, and where it was computed', () => {
    const fixture = modeLabel({ source_kind: 'sketch', tool: 'coco_lab/test/golden_loc_bundles.py' });
    expect(fixture.mode).toBe('Sketch');
    expect(fixture.text).toMatch(/not the robot/);
    const browser = modeLabel({ source_kind: 'sketch', tool: PYODIDE_TOOL });
    expect(browser.text).toMatch(/computed in your browser by coco_lab; a model, not the robot/);
  });
});
