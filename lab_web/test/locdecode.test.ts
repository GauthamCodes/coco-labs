// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The localisation decoder against Python, bundle by bundle: every array's
// little-endian bytes must hash to what coco_lab wrote
// (golden/loc_expected.json, from tools/make_loc_expectations.py), and the
// content and map hashes are RECOMPUTED here and must equal the manifests'.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { columnBytes } from '../src/bundle/arrays';
import { BundleError } from '../src/bundle/errors';
import { sha256Hex } from '../src/bundle/sha256';
import { beamAngles, loadLocBytes, updateAt, type DecodedLocBundle } from '../src/loc/decode';
import { LAB_WEB, readBundleDir, REPO } from './helpers';

const expected = JSON.parse(readFileSync(join(LAB_WEB, 'test/golden/loc_expected.json'), 'utf-8'));

function f32Bytes(a: Float32Array): Uint8Array {
  return new Uint8Array(a.buffer, a.byteOffset, a.byteLength);
}

function columnOf(b: DecodedLocBundle, name: string): ArrayLike<number> & { length: number } {
  if (name === 'map.occupancy') return b.map.occupancy;
  const parts = name.split('.');
  if (parts[0] === 'world') {
    const key = ({
      t: 't', gt_x: 'gtX', gt_y: 'gtY', gt_yaw: 'gtYaw', odom_x: 'odomX', odom_y: 'odomY',
      odom_yaw: 'odomYaw', cmd_v: 'cmdV', cmd_w: 'cmdW', updates: 'updates', ranges: 'ranges',
    } as Record<string, keyof typeof b.world>)[parts[1]];
    return b.world[key] as Float64Array;
  }
  const run = b.runs.find((r) => r.id === parts[1])!;
  if (parts[2] === 'particles') return (run.particles as any)[parts[3]];
  return run.cols[parts[2]];
}

function bytesOf(col: ArrayLike<number>): Uint8Array {
  if (col instanceof Float32Array) return f32Bytes(col);
  return columnBytes(col as Float64Array);
}

const v = (x: unknown) => (x === 'inf' ? Infinity : x === '-inf' ? -Infinity : x);

async function load(dir: string) {
  const { manifest, arrays } = readBundleDir(join(REPO, dir));
  return loadLocBytes(manifest, arrays);
}

const cases: Array<[string, any]> = expected.bundles.map((e: any) => [e.id, e]);

describe.each(cases)('loc bundle %s', (_id, exp) => {
  it('decodes, every array byte-identical to coco_lab', async () => {
    const b = await load(exp.dir);
    expect(b.version).toBe(exp.version);
    expect(b.contentHash).toBe(exp.content_hash);
    expect(b.map.contentHash).toBe(exp.map_hash);
    expect(b.provenance.source_kind).toBe('sketch');
    expect(b.world.nRows).toBe(exp.n_rows);
    expect(b.world.updates.length).toBe(exp.n_updates);
    expect(b.world.kidnapRow).toBe(exp.kidnap_row);
    expect(b.world.status).toBe(exp.status);
    expect(b.world.nBeams).toBe(exp.n_beams);
    expect(b.runs.map((r) => [r.id, r.kind])).toEqual(exp.runs.map((r: any) => [r.id, r.kind]));
    for (const [i, r] of b.runs.entries()) {
      expect(r.summary).toEqual(exp.runs[i].summary);
      expect(r.params).toEqual(exp.runs[i].params);
    }
    for (const [name, e] of Object.entries<any>(exp.arrays)) {
      const col = columnOf(b, name);
      expect(col.length, name).toBe(e.count);
      expect(await sha256Hex(bytesOf(col)), name).toBe(e.sha256);
      if (e.count > 0) {
        expect(col[0], name).toBe(v(e.first));
        expect(col[col.length - 1], name).toBe(v(e.last));
      }
    }
  });

  it('refuses a flipped byte and an edited manifest', async () => {
    const { manifest, arrays } = readBundleDir(join(REPO, exp.dir));
    if (exp.compression === 'none') {
      const bad = arrays.slice();
      bad[bad.length >> 1] ^= 1;
      await expect(loadLocBytes(manifest, bad)).rejects.toBeInstanceOf(BundleError);
    }
    const text = new TextDecoder().decode(manifest).replace('"status":"', '"status":"x');
    await expect(loadLocBytes(new TextEncoder().encode(text), arrays)).rejects.toBeInstanceOf(BundleError);
  });
});

describe('loc decoder edges', () => {
  it('refuses a search bundle and an unknown major', async () => {
    const { manifest, arrays } = readBundleDir(join(REPO, 'coco_lab/test/fixtures/bundles/astar_open'));
    await expect(loadLocBytes(manifest, arrays)).rejects.toThrow(/schema/);
    const g = readBundleDir(join(REPO, expected.bundles[0].dir));
    const m = JSON.parse(new TextDecoder().decode(g.manifest));
    m.version = '2.0'; // checked before the content hash, so re-serialising is fine
    await expect(loadLocBytes(new TextEncoder().encode(JSON.stringify(m)), g.arrays))
      .rejects.toThrow(/major version 2/);
  });

  it('every run reads the world\'s update rows (identical inputs)', async () => {
    const b = await load(expected.bundles.find((e: any) => e.runs.length === 3).dir);
    for (const r of b.runs) expect(Array.from(r.cols.row)).toEqual(Array.from(b.world.updates));
  });

  it('particle weights sum to 1 per update (as decoded, f32)', async () => {
    const b = await load(expected.bundles[0].dir);
    for (const r of b.runs.filter((x) => x.particles)) {
      const p = r.particles!;
      for (let k = 0; k < r.n; k++) {
        let s = 0;
        for (let i = p.offset[k]; i < p.offset[k + 1]; i++) s += p.w[i];
        expect(Math.abs(s - 1)).toBeLessThan(1e-4);
      }
    }
  });

  it('beam angles and update lookup are the plain arithmetic they claim', async () => {
    const b = await load(expected.bundles[0].dir);
    const a = beamAngles(b.scenario.lidar);
    expect(a.length).toBe(b.world.nBeams);
    expect(a[0]).toBe(b.scenario.lidar.angle_min);
    expect(Math.abs(a[a.length - 1] - b.scenario.lidar.angle_max)).toBeLessThan(1e-12);
    const u = b.world.updates;
    expect(updateAt(b.world, 0)).toBe(0);
    expect(updateAt(b.world, u[3])).toBe(3);
    expect(updateAt(b.world, u[3] + 1)).toBe(u[4] === u[3] + 1 ? 4 : 3);
    expect(updateAt(b.world, b.world.nRows - 1)).toBe(u.length - 1);
  });
});
