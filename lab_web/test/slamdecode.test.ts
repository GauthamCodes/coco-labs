// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The map-bundle decoder against Python, bundle by bundle: every array's
// little-endian bytes must hash to what coco_lab wrote
// (golden/slam_expected.json, from tools/make_slam_expectations.py), and the
// content and map hashes are RECOMPUTED here and must equal the manifests'.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { BundleError } from '../src/bundle/errors';
import { sha256Hex } from '../src/bundle/sha256';
import { loadSlamBytes, parseSlamManifest, snapshotAt, type Column, type DecodedSlamBundle } from '../src/map/decode';
import { LAB_WEB, readBundleDir, REPO } from './helpers';

const expected = JSON.parse(readFileSync(join(LAB_WEB, 'test/golden/slam_expected.json'), 'utf-8'));

function bytesOf(col: ArrayLike<number> & { buffer?: ArrayBufferLike }): Uint8Array {
  const c = col as unknown as Column;
  return new Uint8Array(c.buffer, c.byteOffset, c.byteLength);
}

const WORLD_KEY: Record<string, keyof DecodedSlamBundle['world']> = {
  t: 't', gt_x: 'gtX', gt_y: 'gtY', gt_yaw: 'gtYaw', odom_x: 'odomX', odom_y: 'odomY', odom_yaw: 'odomYaw',
  updates: 'updates', ranges: 'ranges',
};
const OBS_KEY: Record<string, keyof DecodedSlamBundle['world']> = {
  offset: 'obsOffset', id: 'obsId', r: 'obsR', b: 'obsB',
};

function columnOf(b: DecodedSlamBundle, name: string): Column {
  if (name === 'map.occupancy') return b.map.occupancy;
  const p = name.split('.');
  if (p[0] === 'world') {
    if (p[1] === 'obs') return b.world[OBS_KEY[p[2]]] as Column;
    return b.world[WORLD_KEY[p[1]]] as Column;
  }
  if (p[0] === 'ext') {
    const e = b.external.find((x) => x.id === p[1])!;
    const key = ({ est_x: 'estX', est_y: 'estY', est_yaw: 'estYaw', cells: 'cells', err_online: 'errOnline',
      diff: 'diff' } as Record<string, keyof typeof e>)[p[2]];
    return e[key] as Column;
  }
  const run = b.runs.find((r) => r.id === p[1])!;
  if (p[2] === 'col') return run.cols[p.slice(3).join('.')];
  if (p[2] === 'arr') return run.arrays[p.slice(3).join('.')];
  if (p[3] === 'k') return run.snapshots;
  // snap.cells: the snapshots back to back
  const all = new Uint8Array(run.maps.reduce((s, m) => s + m.length, 0));
  let o = 0;
  for (const m of run.maps) { all.set(m, o); o += m.length; }
  return all;
}

const v = (x: unknown) => (x === 'inf' ? Infinity : x === '-inf' ? -Infinity : x);

async function load(dir: string) {
  const { manifest, arrays } = readBundleDir(join(REPO, dir));
  return loadSlamBytes(manifest, arrays);
}

const cases: Array<[string, any]> = expected.bundles.map((e: any) => [e.id, e]);

describe.each(cases)('map bundle %s', (_id, exp) => {
  it('decodes, every array byte-identical to coco_lab', async () => {
    const b = await load(exp.dir);
    expect(b.version).toBe(exp.version);
    expect(b.contentHash).toBe(exp.content_hash);
    expect(b.map.contentHash).toBe(exp.map_hash);
    expect(b.world.source).toBe(exp.source);
    expect(b.world.nRows).toBe(exp.n_rows);
    expect(b.world.updates.length).toBe(exp.n_updates);
    expect(b.world.nBeams).toBe(exp.n_beams);
    expect(b.world.landmarks.length).toBe(exp.n_landmarks);
    for (const [name, a] of Object.entries(exp.arrays) as Array<[string, any]>) {
      const col = columnOf(b, name);
      expect(col.length, name).toBe(a.count);
      expect(await sha256Hex(bytesOf(col)), name).toBe(a.sha256);
      if (a.count) {
        expect(col[0], `${name}[0]`).toBe(v(a.first));
        expect(col[col.length - 1], `${name}[-1]`).toBe(v(a.last));
      }
    }
  });

  it('carries the runs and their scores as coco_lab wrote them', async () => {
    const b = await load(exp.dir);
    expect(b.runs.map((r) => r.id)).toEqual(exp.runs.map((r: any) => r.id));
    for (const [r, e] of b.runs.map((r, i) => [r, exp.runs[i]] as const)) {
      expect(r.algorithm).toBe(e.algorithm);
      expect(r.maps.length).toBe(e.n_snapshots);
      expect(r.summary).toEqual(e.summary);
      expect(r.maps[0].length).toBe(r.grid.width * r.grid.height);
    }
    expect(b.external.map((e) => e.id)).toEqual(exp.external.map((e: any) => e.id));
    for (const [e, x] of b.external.map((e, i) => [e, exp.external[i]] as const)) expect(e.summary).toEqual(x.summary);
  });
});

describe('map bundle refusals', () => {
  const dir = expected.bundles.find((e: any) => e.compression === 'none').dir;

  it('refuses a flipped byte (content hash)', async () => {
    const { manifest, arrays } = readBundleDir(join(REPO, dir));
    const bad = new Uint8Array(arrays);
    bad[2000] ^= 1;
    await expect(loadSlamBytes(manifest, bad)).rejects.toBeInstanceOf(BundleError);
  });

  it('refuses an unknown major version', () => {
    const { manifest } = readBundleDir(join(REPO, dir));
    const m = JSON.parse(new TextDecoder().decode(manifest));
    m.version = '2.0';
    expect(() => parseSlamManifest(new TextEncoder().encode(JSON.stringify(m)))).toThrow(/major version 2/);
  });

  it('refuses another schema', () => {
    const { manifest } = readBundleDir(join(REPO, dir));
    const m = JSON.parse(new TextDecoder().decode(manifest));
    m.schema = 'coco_lab.loc_bundle';
    expect(() => parseSlamManifest(new TextEncoder().encode(JSON.stringify(m)))).toThrow(/schema/);
  });

  it('finds the snapshot in force at an update', async () => {
    const b = await load(dir);
    const r = b.runs[0];
    expect(snapshotAt(r, 0)).toBe(0);
    expect(snapshotAt(r, r.n - 1)).toBe(r.snapshots.length - 1);
  });
});
