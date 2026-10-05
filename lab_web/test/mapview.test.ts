// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// Lab 3's display arithmetic: it places what a map bundle holds, and reads
// scores coco_lab computed -- it never maps, localises or scores.

import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { loadSlamBytes } from '../src/map/decode';
import {
  aligned, challengeScore, diffRGBA, edgesUpTo, estimateAt, externalAt, finalAt, landmarksAt, observationsAt,
  occupancyRGBA, particlesAt, runStyle, scanEndpoints, truthAtUpdate,
} from '../src/map/view';
import { modeLabel, PYODIDE_TOOL } from '../src/model/mode';
import { readBundleDir, REPO } from './helpers';

const FIX = 'coco_lab/test/fixtures/slam_bundles';

async function load(name: string) {
  const { manifest, arrays } = readBundleDir(join(REPO, FIX, name));
  return loadSlamBytes(manifest, arrays);
}

describe('placing what a map bundle holds', () => {
  it('a scan from the truth lands on the truth map\'s walls (noise-free beams excepted)', async () => {
    const b = await load('loop_small');
    const geo = b.map.geo!;
    let onWall = 0;
    let total = 0;
    for (let k = 0; k < b.world.updates.length; k += 5) {
      for (const [x, y] of scanEndpoints(b, k, truthAtUpdate(b, k))) {
        const col = Math.floor((x - geo.origin[0]) / geo.resolution);
        const row = b.map.height - 1 - Math.floor((y - geo.origin[1]) / geo.resolution);
        let hit = false;
        for (let dr = -1; dr <= 1; dr++) {
          for (let dc = -1; dc <= 1; dc++) {
            const r = row + dr;
            const c = col + dc;
            if (r >= 0 && r < b.map.height && c >= 0 && c < b.map.width && b.map.occupancy[r * b.map.width + c] === 1) hit = true;
          }
        }
        onWall += hit ? 1 : 0;
        total++;
      }
    }
    expect(total).toBeGreaterThan(100);
    expect(onWall / total).toBeGreaterThan(0.97); // range noise sigma 0.02 m, one-cell neighbourhood
  });

  it('reads estimates, final trajectories and the truth from the arrays', async () => {
    const b = await load('loop_small');
    const pg = b.runs.find((r) => r.id === 'pose_graph')!;
    const k = pg.n - 1;
    expect(estimateAt(pg, k)).toEqual([pg.cols.est_x[k], pg.cols.est_y[k], pg.cols.est_yaw[k]]);
    expect(finalAt(pg, 0)).toEqual([pg.arrays['final.x'][0], pg.arrays['final.y'][0], pg.arrays['final.yaw'][0]]);
    const known = b.runs.find((r) => r.id === 'known')!;
    expect(finalAt(known, k)).toEqual(estimateAt(known, k)); // no final.* arrays: the online one
    expect(estimateAt(known, k)).toEqual(truthAtUpdate(b, k));
  });

  it('slices the per-update arrays by their offsets', async () => {
    const b = await load('loop_small');
    const fs = b.runs.find((r) => r.id === 'fastslam')!;
    const n = Number(fs.params.particles);
    for (let k = 0; k < fs.n; k++) expect(particlesAt(fs, k)).toHaveLength(n);
    const ekf = b.runs.find((r) => r.id === 'ekf_slam')!;
    const last = landmarksAt(ekf, ekf.n - 1);
    expect(last.length).toBe((ekf.cols.n_landmarks as Int32Array)[ekf.n - 1]);
    let obs = 0;
    for (let k = 0; k < b.world.updates.length; k++) obs += observationsAt(b, k).length;
    expect(obs).toBe(b.world.obsId.length);
    const pg = b.runs.find((r) => r.id === 'pose_graph')!;
    const all = edgesUpTo(pg, pg.n - 1);
    expect(all.length).toBe(pg.arrays['edges.i'].length);
    expect(edgesUpTo(pg, 0)).toHaveLength(0);
    for (const e of all) expect(['odom', 'icp', 'loop']).toContain(e.kind);
  });

  it('places an external run by the alignment coco_lab scored it with', async () => {
    const b = await load('recorded_small_gz');
    const e = b.external[0];
    const T = e.summary.ate_online.alignment;
    const p = externalAt(e, 0);
    const q = aligned(T, [e.estX[0], e.estY[0], e.estYaw[0]]);
    expect(p).toEqual(q);
    // the made-up run is the truth shifted by (0.02, -0.01): aligned, it is on the truth
    const tr = truthAtUpdate(b, 0);
    expect(Math.hypot(p[0] - tr[0], p[1] - tr[1])).toBeLessThan(1e-6);
  });
});

describe('colours, not thresholds', () => {
  it('an OccupancyGrid snapshot: unknown is transparent, occupied darker', () => {
    const rgba = occupancyRGBA(new Uint8Array([255, 0, 100]));
    expect(rgba[3]).toBe(0);
    expect(rgba[4]).toBeGreaterThan(rgba[8]);
    expect(rgba[7]).toBe(255);
  });

  it('the diff raster colours exactly the classes coco_lab wrote', () => {
    const rgba = diffRGBA(new Uint8Array([0, 1, 2, 3]));
    expect(rgba[3]).toBe(0);
    expect([rgba[7], rgba[11], rgba[15]]).toEqual([255, 255, 255]);
  });
});

describe('the challenge score is the documented computation', () => {
  it('is round(100 x F1) of the summary coco_lab wrote', async () => {
    const b = await load('loop_small');
    for (const r of b.runs) expect(challengeScore(r.summary.map.f1)).toBe(Math.round(100 * r.summary.map.f1));
    expect(challengeScore(0.875)).toBe(88);
    expect(challengeScore(0)).toBe(0);
  });
});

describe('labels (rule 4)', () => {
  it('a Sketch bundle says it is a model; a recording says it is a replay', async () => {
    const s = await load('loop_small');
    expect(modeLabel(s.provenance).text).toMatch(/model, not the robot/);
    expect(modeLabel({ ...s.provenance, tool: PYODIDE_TOOL }).text).toMatch(/computed in your browser/);
    const r = await load('recorded_small_gz');
    expect(modeLabel(r.provenance).mode).toBe('Replay');
  });

  it('names every run, and calls the landmark sensor idealised', () => {
    for (const id of ['known', 'odometry', 'ekf_slam', 'fastslam', 'pose_graph', 'pose_graph_noloop',
      'slam_toolbox_loop', 'slam_toolbox_noloop', 'cartographer_loop', 'cartographer_noloop']) {
      expect(runStyle(id).label).not.toBe(id);
    }
    expect(runStyle('ekf_slam').label).toMatch(/idealised/i);
    expect(runStyle('ekf_slam').what).toMatch(/IDEALISED/);
  });
});
